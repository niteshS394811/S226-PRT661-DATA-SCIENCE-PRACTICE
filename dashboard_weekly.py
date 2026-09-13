"""Weekly / monthly dashboard — model comparison, metrics, forecast runs."""
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


st.set_page_config(page_title="NEM Models | Danala Group 8", page_icon="📊", layout="wide")
st.title("NEM Model Comparison & Monthly View")
st.caption(
    f"PRT661 · Danala Group 8 · Seasonal Naive vs Ridge vs HistGB · {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
)

try:
    monthly = q(
        """
        SELECT month_start, regionid, avg_rrp, max_rrp, min_rrp,
               avg_demand, max_demand, min_demand,
               avg_netinterchange, avg_demandforecast, avg_aemo_demand_error, intervals
        FROM datamart.dm_monthly_actuals
        ORDER BY month_start, regionid
        """
    )
    metrics = q(
        """
        SELECT trained_at, regionid, target, model_name, mae, rmse,
               cv_mae, cv_rmse, n_train, n_test
        FROM datamart.dm_model_metrics
        ORDER BY trained_at DESC, regionid, target, model_name
        """
    )
    forecast_runs = q(
        """
        SELECT forecast_run_at, model_name,
               COUNT(*) AS n_rows,
               COUNT(DISTINCT regionid) AS n_regions,
               MIN(settlementdate) AS first_ts,
               MAX(settlementdate) AS last_ts
        FROM datamart.dm_forecasts
        GROUP BY forecast_run_at, model_name
        ORDER BY forecast_run_at DESC
        """
    )
except Exception as e:
    st.error(str(e))
    st.info("Run history + weekly train after HD schema migration.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["Model comparison", "Monthly actuals", "Forecast runs"])

with tab1:
    if metrics.empty:
        st.warning("No metrics — run history or weekly train.")
    else:
        metrics["trained_at"] = pd.to_datetime(metrics["trained_at"])
        for c in ("mae", "rmse", "cv_mae", "cv_rmse"):
            if c in metrics.columns:
                metrics[c] = pd.to_numeric(metrics[c], errors="coerce")
        latest_ts = metrics["trained_at"].max()
        latest = metrics[metrics["trained_at"] == latest_ts].copy()
        st.success(f"Latest training run: **{latest_ts}**")

        target = st.selectbox("Target", sorted(latest["target"].unique()))
        sub = latest[latest["target"] == target]
        st.subheader(f"Hold-out MAE by model — {target}")
        pivot = sub.pivot_table(index="regionid", columns="model_name", values="mae")
        st.bar_chart(pivot)
        st.subheader("Full metrics table (latest run)")
        st.dataframe(sub.sort_values(["regionid", "mae"]), use_container_width=True, hide_index=True)

        if sub["cv_mae"].notna().any():
            st.subheader(f"Walk-forward CV MAE — {target}")
            st.bar_chart(sub.pivot_table(index="regionid", columns="model_name", values="cv_mae"))

        # Best model count
        best = sub.sort_values("mae").groupby("regionid", as_index=False).first()
        st.markdown("**Best hold-out model by region**")
        st.dataframe(best[["regionid", "model_name", "mae", "rmse"]], use_container_width=True, hide_index=True)

with tab2:
    if monthly.empty:
        st.warning("Monthly mart empty.")
    else:
        monthly["month_start"] = pd.to_datetime(monthly["month_start"])
        for c in ("avg_rrp", "avg_demand", "avg_netinterchange"):
            if c in monthly.columns:
                monthly[c] = pd.to_numeric(monthly[c], errors="coerce")
        regions = st.multiselect(
            "Regions",
            sorted(monthly["regionid"].unique()),
            default=sorted(monthly["regionid"].unique()),
            key="mreg",
        )
        m = monthly[monthly["regionid"].isin(regions)]
        idx = m.set_index("month_start")
        c1, c2 = st.columns(2)
        with c1:
            st.line_chart(idx.pivot_table(index=idx.index, columns="regionid", values="avg_rrp"))
        with c2:
            st.line_chart(idx.pivot_table(index=idx.index, columns="regionid", values="avg_demand"))
        st.dataframe(m, use_container_width=True, hide_index=True)

with tab3:
    if forecast_runs.empty:
        st.warning("No forecast runs.")
    else:
        st.dataframe(forecast_runs, use_container_width=True, hide_index=True)
