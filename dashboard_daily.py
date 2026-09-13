"""Daily dashboard — actuals + forecasts at 1 hour (5-min) or 1 day hourly."""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import psycopg
import streamlit as st

DB_HOST = os.environ.get("NEM_DB_HOST", "postgres")
CONN = f"host={DB_HOST} port=5432 dbname=nemdb user=nemuser password=nempassword"


@st.cache_data(ttl=60)
def q(sql: str) -> pd.DataFrame:
    with psycopg.connect(CONN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            cols = [c.name for c in cur.description]
    return pd.DataFrame(rows, columns=cols)


st.set_page_config(page_title="NEM Daily | Danala Group 8", page_icon="📅", layout="wide")
st.title("NEM Daily Operations Dashboard")
st.caption(
    f"PRT661 · Danala Group 8 · Actuals, interchange, AEMO error · "
    f"Forecasts: **1 hour (5-min)** or **1 day (hourly)** · "
    f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
)

try:
    daily = q(
        """
        SELECT trade_date, regionid, avg_rrp, max_rrp, min_rrp,
               avg_demand, max_demand, min_demand,
               avg_netinterchange, avg_demandforecast, avg_aemo_demand_error, intervals
        FROM datamart.dm_daily_actuals
        ORDER BY trade_date, regionid
        """
    )
except Exception as e:
    st.error(str(e))
    st.info("Run history pipeline so daily mart exists.")
    st.stop()

# Optional tables — empty if not migrated / not trained yet
try:
    forecasts_5min = q(
        """
        SELECT forecast_run_at, settlementdate, regionid, target,
               prediction, model_name, horizon_steps
        FROM datamart.dm_forecasts
        WHERE forecast_run_at = (SELECT MAX(forecast_run_at) FROM datamart.dm_forecasts)
        """
    )
except Exception:
    forecasts_5min = pd.DataFrame()

try:
    forecasts_hourly = q(
        """
        SELECT forecast_run_at, forecast_hour, regionid, target,
               prediction, model_name, horizon_hours, horizon_label
        FROM datamart.dm_hourly_forecasts
        WHERE forecast_run_at = (
            SELECT MAX(forecast_run_at) FROM datamart.dm_hourly_forecasts
        )
        """
    )
except Exception:
    forecasts_hourly = pd.DataFrame()

if daily.empty:
    st.warning("No daily actuals yet — run the history pipeline.")
    st.stop()

daily["trade_date"] = pd.to_datetime(daily["trade_date"])
num_cols = [
    "avg_rrp", "max_rrp", "min_rrp", "avg_demand", "max_demand", "min_demand",
    "avg_netinterchange", "avg_demandforecast", "avg_aemo_demand_error",
]
for c in num_cols:
    if c in daily.columns:
        daily[c] = pd.to_numeric(daily[c], errors="coerce")

with st.sidebar:
    st.header("Filters")
    regions = st.multiselect(
        "Regions",
        sorted(daily["regionid"].unique()),
        default=sorted(daily["regionid"].unique()),
    )
    dmin, dmax = daily["trade_date"].min().date(), daily["trade_date"].max().date()
    dr = st.date_input("Date range (actuals)", (dmin, dmax), min_value=dmin, max_value=dmax)
    st.markdown("---")
    st.subheader("Forecast view")
    horizon_choice = st.radio(
        "Horizon",
        [
            "1 hour (5-min steps)",
            "1 day (hourly)",
            "1 week (hourly)",
        ],
        index=0,
    )
    st.markdown("---")
    st.markdown("**Units:** RRP $/MWh · Demand / interchange MW")
    st.markdown("**Interchange:** + import · − export")

f = daily[daily["regionid"].isin(regions)].copy()
if len(dr) == 2:
    f = f[f["trade_date"].dt.date.between(dr[0], dr[1])]

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Days", f"{f['trade_date'].nunique()}")
k2.metric("Avg RRP", f"${f['avg_rrp'].mean():,.1f}")
k3.metric("Avg demand", f"{f['avg_demand'].mean():,.0f} MW")
k4.metric(
    "Avg interchange",
    f"{f['avg_netinterchange'].mean():,.0f} MW" if "avg_netinterchange" in f else "—",
)
if "avg_aemo_demand_error" in f.columns and f["avg_aemo_demand_error"].notna().any():
    k5.metric("Avg AEMO demand error", f"{f['avg_aemo_demand_error'].mean():,.0f} MW")
else:
    k5.metric("Peak RRP", f"${f['max_rrp'].max():,.0f}")

t1, t2, t3 = st.tabs(["Market actuals", "Interchange & AEMO", "Forecasts"])

with t1:
    c1, c2 = st.columns(2)
    idx = f.set_index("trade_date")
    with c1:
        st.subheader("Daily average RRP")
        st.line_chart(idx.pivot_table(index=idx.index, columns="regionid", values="avg_rrp"))
    with c2:
        st.subheader("Daily average demand")
        st.line_chart(idx.pivot_table(index=idx.index, columns="regionid", values="avg_demand"))
    st.dataframe(f.sort_values("trade_date", ascending=False), use_container_width=True, hide_index=True)

with t2:
    c1, c2 = st.columns(2)
    idx = f.set_index("trade_date")
    with c1:
        st.subheader("Net interchange (daily avg)")
        if "avg_netinterchange" in f.columns:
            st.line_chart(
                idx.pivot_table(index=idx.index, columns="regionid", values="avg_netinterchange")
            )
            st.caption("Positive ≈ net import; negative ≈ net export.")
        else:
            st.info("Interchange not loaded.")
    with c2:
        st.subheader("AEMO demand forecast error")
        if "avg_aemo_demand_error" in f.columns and f["avg_aemo_demand_error"].notna().any():
            st.line_chart(
                idx.pivot_table(index=idx.index, columns="regionid", values="avg_aemo_demand_error")
            )
            st.caption("Actual demand − AEMO DEMANDFORECAST (MW).")
        else:
            st.info("DEMANDFORECAST not available for this window.")

with t3:
    st.subheader(f"Forecast — {horizon_choice}")
    target = st.radio("Target", ["demand", "price"], horizontal=True, key="fc_target")

    if horizon_choice.startswith("1 hour"):
        # 5-min / ~1 hour from dm_forecasts
        if forecasts_5min.empty:
            st.info("No 5-min forecasts yet — run weekly train / history train.")
        else:
            fc = forecasts_5min.copy()
            fc["settlementdate"] = pd.to_datetime(fc["settlementdate"])
            fc["prediction"] = pd.to_numeric(fc["prediction"], errors="coerce")
            fc = fc[fc["regionid"].isin(regions) & (fc["target"] == target)]
            if fc.empty:
                st.warning("No rows for this target/region.")
            else:
                st.caption(
                    f"Model: **{fc['model_name'].iloc[0]}** · "
                    f"Run: {fc['forecast_run_at'].iloc[0]} · "
                    f"Grain: 5-minute · Horizon: up to 1 hour"
                )
                st.line_chart(
                    fc.set_index("settlementdate").pivot_table(
                        index="settlementdate", columns="regionid", values="prediction"
                    )
                )
                st.dataframe(
                    fc.sort_values(["regionid", "settlementdate"]),
                    use_container_width=True,
                    hide_index=True,
                )

    else:
        # Hourly 1d or 1w from dm_hourly_forecasts
        label = "1d" if horizon_choice.startswith("1 day") else "1w"
        if forecasts_hourly.empty:
            st.info(
                "No hourly forecasts yet. Create tables (migrate_hourly_forecast.sql) "
                "and run: python /app/scripts/run_hourly_forecast.py"
            )
        else:
            fc = forecasts_hourly.copy()
            fc["forecast_hour"] = pd.to_datetime(fc["forecast_hour"])
            fc["prediction"] = pd.to_numeric(fc["prediction"], errors="coerce")
            fc = fc[
                fc["regionid"].isin(regions)
                & (fc["target"] == target)
                & (fc["horizon_label"] == label)
            ]
            if fc.empty:
                st.warning(
                    f"No hourly rows for label **{label}**. "
                    "Re-run hourly forecast with day and/or week enabled."
                )
            else:
                st.caption(
                    f"Model: **{fc['model_name'].iloc[0]}** · "
                    f"Run: {fc['forecast_run_at'].iloc[0]} · "
                    f"Grain: hourly · Label: **{label}** "
                    f"({'24 hours' if label == '1d' else '168 hours'})"
                )
                st.line_chart(
                    fc.set_index("forecast_hour").pivot_table(
                        index="forecast_hour", columns="regionid", values="prediction"
                    )
                )
                st.dataframe(
                    fc.sort_values(["regionid", "forecast_hour"]),
                    use_container_width=True,
                    hide_index=True,
                )
