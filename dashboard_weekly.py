"""Weekly / monthly dashboard — monthly actuals, model metrics, forecast runs."""
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


st.set_page_config(page_title="NEM Weekly / Monthly Dashboard", page_icon="📊", layout="wide")
st.title("NEM Weekly / Monthly Dashboard")
st.caption("Sources: **dm_monthly_actuals**, **dm_model_metrics**, **dm_forecasts**")

try:
    monthly = q(
        """
        SELECT month_start, regionid, avg_rrp, max_rrp, min_rrp,
               avg_demand, max_demand, min_demand, avg_netinterchange, intervals
        FROM datamart.dm_monthly_actuals
        ORDER BY month_start, regionid
        """
    )
    metrics = q(
        """
        SELECT trained_at, regionid, target, mae, rmse, n_train, n_test, model_name
        FROM datamart.dm_model_metrics
        ORDER BY trained_at DESC, regionid, target
        """
    )
    forecast_runs = q(
        """
        SELECT forecast_run_at,
               COUNT(*) AS n_rows,
               COUNT(DISTINCT regionid) AS n_regions,
               MIN(settlementdate) AS first_ts,
               MAX(settlementdate) AS last_ts
        FROM datamart.dm_forecasts
        GROUP BY forecast_run_at
        ORDER BY forecast_run_at DESC
        """
    )
except Exception as e:
    st.error(str(e))
    st.info("Run history pipeline first so monthly / metrics tables exist.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["Monthly actuals", "Model metrics", "Forecast runs"])

with tab1:
    if monthly.empty:
        st.warning("dm_monthly_actuals is empty.")
    else:
        monthly["month_start"] = pd.to_datetime(monthly["month_start"])
        for c in ["avg_rrp", "avg_demand", "max_rrp", "max_demand"]:
            monthly[c] = pd.to_numeric(monthly[c], errors="coerce")
        regions = st.multiselect(
            "Regions",
            sorted(monthly["regionid"].unique()),
            default=sorted(monthly["regionid"].unique()),
            key="mreg",
        )
        m = monthly[monthly["regionid"].isin(regions)]
        c1, c2 = st.columns(2)
        idx = m.set_index("month_start")
        with c1:
            st.subheader("Monthly average RRP")
            st.line_chart(idx.pivot_table(index=idx.index, columns="regionid", values="avg_rrp"))
        with c2:
            st.subheader("Monthly average demand")
            st.line_chart(idx.pivot_table(index=idx.index, columns="regionid", values="avg_demand"))
        st.dataframe(m, use_container_width=True, hide_index=True)

with tab2:
    if metrics.empty:
        st.warning("No model metrics — run history or weekly train.")
    else:
        metrics["trained_at"] = pd.to_datetime(metrics["trained_at"])
        st.subheader("Latest training metrics")
        st.dataframe(metrics, use_container_width=True, hide_index=True)
        latest = metrics.sort_values("trained_at").groupby(["regionid", "target"], as_index=False).tail(1)
        st.subheader("MAE by region (latest train)")
        st.bar_chart(latest.pivot_table(index="regionid", columns="target", values="mae"))

with tab3:
    if forecast_runs.empty:
        st.warning("No forecast runs yet.")
    else:
        st.subheader("Forecast run history (weekly train appends a new run)")
        st.dataframe(forecast_runs, use_container_width=True, hide_index=True)
