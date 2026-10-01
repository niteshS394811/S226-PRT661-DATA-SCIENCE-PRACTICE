"""Operational / Daily dashboard — modern fintech-style UI."""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import psycopg
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
except ImportError:
    px = None
    go = None

DB_HOST = os.environ.get("NEM_DB_HOST", "postgres")
CONN = f"host={DB_HOST} port=5432 dbname=nemdb user=nemuser password=nempassword"

st.set_page_config(
    page_title="NEM Operational",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Modern light UI (inspired by fintech admin dashboards) ---
st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .stApp { background: #F4F7FB; }
  [data-testid="stSidebar"] {
    background: #FFFFFF;
    border-right: 1px solid #E8EEF6;
  }
  .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1200px; }
  div[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E8EEF6;
    border-radius: 16px;
    padding: 16px 18px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.04);
  }
  div[data-testid="stMetric"] label { color: #64748B !important; font-weight: 500; }
  div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #0F172A !important; font-weight: 700; font-size: 1.6rem;
  }
  .nem-card {
    background: #FFFFFF;
    border: 1px solid #E8EEF6;
    border-radius: 16px;
    padding: 18px 20px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.04);
    margin-bottom: 0.75rem;
  }
  .nem-title { font-size: 1.45rem; font-weight: 700; color: #0F172A; margin: 0; }
  .nem-sub { color: #64748B; font-size: 0.9rem; margin-top: 0.2rem; }
  .pill {
    display: inline-block; background: #ECFDF5; color: #059669;
    font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 999px;
  }
  header[data-testid="stHeader"] { background: rgba(244,247,251,0.85); }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=60)
def q(sql: str) -> pd.DataFrame:
    with psycopg.connect(CONN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            cols = [c.name for c in cur.description]
    return pd.DataFrame(rows, columns=cols)


st.markdown(
    f"""
<div class="nem-card">
  <div class="nem-title">⚡ NEM Operational / Daily</div>
  <div class="nem-sub">Short-term ops · actuals · ~12 hour forecasts · incremental load ·
  {datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC</div>
</div>
""",
    unsafe_allow_html=True,
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
    st.info("Run strategic history so the datamart exists.")
    st.stop()

try:
    forecasts = q(
        """
        SELECT forecast_run_at, settlementdate, regionid, target,
               prediction, model_name, horizon_steps
        FROM datamart.dm_forecasts
        WHERE forecast_run_at = (SELECT MAX(forecast_run_at) FROM datamart.dm_forecasts)
        """
    )
except Exception:
    forecasts = pd.DataFrame()

if daily.empty:
    st.warning("No daily actuals yet — run strategic history / daily pipeline.")
    st.stop()

daily["trade_date"] = pd.to_datetime(daily["trade_date"])
for c in [
    "avg_rrp", "max_rrp", "min_rrp", "avg_demand", "max_demand", "min_demand",
    "avg_netinterchange", "avg_demandforecast", "avg_aemo_demand_error",
]:
    if c in daily.columns:
        daily[c] = pd.to_numeric(daily[c], errors="coerce")

with st.sidebar:
    st.markdown("### Filters")
    regions = st.multiselect(
        "Regions",
        sorted(daily["regionid"].unique()),
        default=sorted(daily["regionid"].unique()),
    )
    dmin, dmax = daily["trade_date"].min().date(), daily["trade_date"].max().date()
    dr = st.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
    st.markdown("---")
    st.caption("Operational = Daily pipeline")
    st.caption("DAG: `nem_operational_daily`")

if not regions:
    st.warning("Select at least one region.")
    st.stop()

mask = daily["regionid"].isin(regions)
if isinstance(dr, (list, tuple)) and len(dr) == 2:
    mask &= (daily["trade_date"].dt.date >= dr[0]) & (daily["trade_date"].dt.date <= dr[1])
d = daily.loc[mask].copy()

# KPI row
latest = d.sort_values("trade_date").groupby("regionid").tail(1)
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("Avg RRP (latest days)", f"${latest['avg_rrp'].mean():.1f}", help="Mean of latest day per selected region")
with k2:
    st.metric("Avg demand (MW)", f"{latest['avg_demand'].mean():,.0f}")
with k3:
    st.metric("Max RRP in view", f"${d['max_rrp'].max():.1f}")
with k4:
    ni = latest["avg_netinterchange"].mean() if "avg_netinterchange" in latest else 0
    st.metric("Mean net interchange", f"{ni:,.0f} MW")

st.markdown("")

c1, c2 = st.columns((1.1, 1.2))
with c1:
    st.markdown('<div class="nem-card">', unsafe_allow_html=True)
    st.markdown("**Demand share by region** (selected range)")
    share = d.groupby("regionid", as_index=False)["avg_demand"].mean()
    if px and not share.empty:
        fig = px.pie(
            share, names="regionid", values="avg_demand", hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10), height=320,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="v", y=0.5),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.dataframe(share)
    st.markdown("</div>", unsafe_allow_html=True)

with c2:
    st.markdown('<div class="nem-card">', unsafe_allow_html=True)
    st.markdown("**Market overview — average daily RRP**")
    if px:
        fig = px.line(d, x="trade_date", y="avg_rrp", color="regionid")
        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10), height=320,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend_title_text="", xaxis_title="", yaxis_title="$/MWh",
        )
        fig.update_xaxes(showgrid=True, gridcolor="#EEF2F7")
        fig.update_yaxes(showgrid=True, gridcolor="#EEF2F7")
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

c3, c4 = st.columns(2)
with c3:
    st.markdown('<div class="nem-card">', unsafe_allow_html=True)
    st.markdown("**Average daily demand (MW)**")
    if px:
        fig = px.line(d, x="trade_date", y="avg_demand", color="regionid")
        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10), height=300,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend_title_text="", xaxis_title="", yaxis_title="MW",
        )
        fig.update_xaxes(gridcolor="#EEF2F7")
        fig.update_yaxes(gridcolor="#EEF2F7")
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with c4:
    st.markdown('<div class="nem-card">', unsafe_allow_html=True)
    st.markdown("**~12 hour forecasts (latest run)**")
    if forecasts is None or forecasts.empty:
        st.info("No forecasts in datamart.dm_forecasts yet — run train after strategic/daily load.")
    else:
        f = forecasts.copy()
        f["settlementdate"] = pd.to_datetime(f["settlementdate"])
        f = f[f["regionid"].isin(regions)]
        if px and not f.empty:
            fig = px.line(
                f, x="settlementdate", y="prediction", color="regionid",
                line_dash="target" if "target" in f.columns else None,
            )
            fig.update_layout(
                margin=dict(l=10, r=10, t=10, b=10), height=300,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                legend_title_text="", xaxis_title="", yaxis_title="Prediction",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.dataframe(f.head(50), use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="nem-card">', unsafe_allow_html=True)
st.markdown("**Recent activity (daily actuals table)**")
show = d.sort_values(["trade_date", "regionid"], ascending=[False, True]).head(30)
st.dataframe(show, use_container_width=True, hide_index=True)
st.markdown("</div>", unsafe_allow_html=True)
