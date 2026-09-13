"""Daily dashboard — datamart.dm_daily_actuals + latest forecasts."""
from __future__ import annotations

import os
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


st.set_page_config(page_title="NEM Daily Dashboard", page_icon="📅", layout="wide")
st.title("NEM Daily Dashboard")
st.caption(
    "Source: **datamart.dm_daily_actuals** (price, demand, **net interchange**) + latest forecasts"
)

try:
    daily = q(
        """
        SELECT trade_date, regionid, avg_rrp, max_rrp, min_rrp,
               avg_demand, max_demand, min_demand, avg_netinterchange, intervals
        FROM datamart.dm_daily_actuals
        ORDER BY trade_date, regionid
        """
    )
    forecasts = q(
        """
        SELECT forecast_run_at, settlementdate, regionid, target,
               prediction, model_name, horizon_steps
        FROM datamart.dm_forecasts
        WHERE forecast_run_at = (SELECT MAX(forecast_run_at) FROM datamart.dm_forecasts)
        """
    )
except Exception as e:
    st.error(str(e))
    st.stop()

if daily.empty:
    st.warning("dm_daily_actuals is empty — run history or daily pipeline first.")
    st.stop()

daily["trade_date"] = pd.to_datetime(daily["trade_date"])
for c in [
    "avg_rrp", "max_rrp", "min_rrp", "avg_demand", "max_demand", "min_demand",
    "avg_netinterchange",
]:
    if c in daily.columns:
        daily[c] = pd.to_numeric(daily[c], errors="coerce")

with st.sidebar:
    regions = st.multiselect(
        "Regions",
        sorted(daily["regionid"].unique()),
        default=sorted(daily["regionid"].unique()),
    )
    dmin, dmax = daily["trade_date"].min().date(), daily["trade_date"].max().date()
    dr = st.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)

f = daily[daily["regionid"].isin(regions)].copy()
if len(dr) == 2:
    f = f[f["trade_date"].dt.date.between(dr[0], dr[1])]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Days", f"{f['trade_date'].nunique()}")
m2.metric("Avg price", f"${f['avg_rrp'].mean():,.2f}")
m3.metric("Avg demand", f"{f['avg_demand'].mean():,.0f} MW")
if "avg_netinterchange" in f.columns:
    m4.metric("Avg net interchange", f"{f['avg_netinterchange'].mean():,.0f} MW")
else:
    m4.metric("Peak price", f"${f['max_rrp'].max():,.2f}")

c1, c2, c3 = st.columns(3)
idx = f.set_index("trade_date")
with c1:
    st.subheader("Daily average RRP")
    st.line_chart(idx.pivot_table(index=idx.index, columns="regionid", values="avg_rrp"))
with c2:
    st.subheader("Daily average demand")
    st.line_chart(idx.pivot_table(index=idx.index, columns="regionid", values="avg_demand"))
with c3:
    st.subheader("Daily avg net interchange")
    if "avg_netinterchange" in f.columns:
        st.line_chart(
            idx.pivot_table(index=idx.index, columns="regionid", values="avg_netinterchange")
        )
        st.caption("Positive ≈ net import into region; negative ≈ net export")
    else:
        st.info("avg_netinterchange not in table — re-run history pipeline after schema update.")

st.subheader("Daily actuals table")
st.dataframe(f.sort_values("trade_date", ascending=False), use_container_width=True, hide_index=True)

st.subheader("Latest model forecasts (1h horizon)")
if forecasts.empty:
    st.info("No forecasts yet — run history or weekly train pipeline.")
else:
    forecasts["settlementdate"] = pd.to_datetime(forecasts["settlementdate"])
    forecasts["prediction"] = pd.to_numeric(forecasts["prediction"], errors="coerce")
    fc = forecasts[forecasts["regionid"].isin(regions)]
    target = st.radio("Target", ["demand", "price"], horizontal=True)
    fc = fc[fc["target"] == target]
    if not fc.empty:
        st.line_chart(
            fc.set_index("settlementdate").pivot_table(
                index="settlementdate", columns="regionid", values="prediction"
            )
        )
        st.dataframe(fc, use_container_width=True, hide_index=True)
