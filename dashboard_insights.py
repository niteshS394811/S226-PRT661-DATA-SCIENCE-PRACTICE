"""Strategic Insights dashboard — modern fintech-style UI."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.express as px
except ImportError:
    px = None

st.set_page_config(page_title="NEM Strategic", page_icon="📊", layout="wide")

st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .stApp { background: #F4F7FB; }
  [data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E8EEF6; }
  .block-container { padding-top: 1.2rem; max-width: 1200px; }
  div[data-testid="stMetric"] {
    background: #FFFFFF; border: 1px solid #E8EEF6; border-radius: 16px;
    padding: 16px 18px; box-shadow: 0 4px 18px rgba(15,23,42,0.04);
  }
  div[data-testid="stMetric"] label { color: #64748B !important; }
  div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #0F172A !important; font-weight: 700;
  }
  .nem-card {
    background: #FFFFFF; border: 1px solid #E8EEF6; border-radius: 16px;
    padding: 18px 20px; box-shadow: 0 4px 18px rgba(15,23,42,0.04);
  }
  .nem-title { font-size: 1.45rem; font-weight: 700; color: #0F172A; }
  .nem-sub { color: #64748B; font-size: 0.9rem; }
  .insight {
    background: #EEF6FF; border-left: 4px solid #3B82F6; border-radius: 8px;
    padding: 10px 14px; margin-bottom: 8px; color: #0F172A; font-size: 0.92rem;
  }
</style>
""",
    unsafe_allow_html=True,
)

DATABASE_URL = os.environ.get(
    "NEM_DATABASE_URL",
    "postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb",
)
CANDIDATE_CSV = [
    Path("/app/src/data/processed/analysis_hourly.csv"),
    Path("src/data/processed/analysis_hourly.csv"),
    Path("/app/src/data/processed/analysis_raw_5min.csv"),
    Path("src/data/processed/analysis_raw_5min.csv"),
]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "settlementdate" in df.columns:
        df["settlementdate"] = pd.to_datetime(df["settlementdate"], errors="coerce")
    for col, src in [
        ("hour", "settlementdate"),
        ("dow", "settlementdate"),
        ("month", "settlementdate"),
        ("year", "settlementdate"),
    ]:
        if col not in df.columns and "settlementdate" in df.columns:
            if col == "hour":
                df["hour"] = df["settlementdate"].dt.hour
            elif col == "dow":
                df["dow"] = df["settlementdate"].dt.dayofweek
            elif col == "month":
                df["month"] = df["settlementdate"].dt.month
            elif col == "year":
                df["year"] = df["settlementdate"].dt.year
    return df


@st.cache_data(ttl=60)
def load_hourly() -> tuple[pd.DataFrame, str]:
    try:
        from sqlalchemy import create_engine

        eng = create_engine(DATABASE_URL)
        df = pd.read_sql("SELECT * FROM analytics.fact_hourly ORDER BY settlementdate", eng)
        if df is not None and len(df) > 0:
            return _normalize(df), "postgres:analytics.fact_hourly"
    except Exception as e:
        pg_err = str(e)
    else:
        pg_err = "empty"

    for path in CANDIDATE_CSV:
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
            df = _normalize(df)
            if "rrp" not in df.columns and "SETTLEMENTDATE" in [c.upper() for c in df.columns]:
                pass
            if len(df) > 0:
                return df, str(path)
        except Exception:
            continue
    return pd.DataFrame(), f"not found | pg: {pg_err}"


@st.cache_data(ttl=60)
def load_model_payloads() -> dict:
    try:
        from sqlalchemy import create_engine, text

        eng = create_engine(DATABASE_URL)
        with eng.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT kind, payload_json FROM analytics.model_results ORDER BY id DESC LIMIT 10"
                )
            ).fetchall()
        out = {}
        for kind, payload in rows:
            if kind not in out:
                out[kind] = json.loads(payload)
        return out
    except Exception:
        return {}


def insight_cards(df: pd.DataFrame) -> list[str]:
    if df.empty or "rrp" not in df.columns:
        return ["No data — run strategic history / analysis pipeline."]
    cards = []
    by_hour = df.groupby("hour")["rrp"].mean()
    h = int(by_hour.idxmax())
    cards.append(f"Peak price hour (avg): **{h:02d}:00** — ${by_hour.max():.1f}/MWh")
    by_reg = df.groupby("regionid")["rrp"].mean().sort_values(ascending=False)
    cards.append(
        f"Highest avg RRP: **{by_reg.index[0]}** (${by_reg.iloc[0]:.1f}) · "
        f"Lowest: **{by_reg.index[-1]}** (${by_reg.iloc[-1]:.1f})"
    )
    if "spare_capacity" in df.columns:
        corr = df[["rrp", "spare_capacity"]].dropna().corr().iloc[0, 1]
        cards.append(f"RRP vs spare capacity correlation: **{corr:.2f}**")
    if "semischedule_clearedmw" in df.columns and "totaldemand" in df.columns:
        share = df.groupby("regionid")[["semischedule_clearedmw", "totaldemand"]].mean()
        share["pct"] = 100 * share["semischedule_clearedmw"] / share["totaldemand"].replace(0, np.nan)
        top = share["pct"].idxmax()
        cards.append(f"Highest semi-scheduled share vs demand: **{top}** (~{share.loc[top, 'pct']:.1f}%)")
    return cards


st.markdown(
    """
<div class="nem-card">
  <div class="nem-title">📊 NEM Strategic Insights</div>
  <div class="nem-sub">Multi-year patterns · generation context · regimes · models · DAG: nem_strategic_history</div>
</div>
""",
    unsafe_allow_html=True,
)

df, source = load_hourly()
if df.empty:
    st.error("No strategic analytics data found.")
    st.code(source)
    st.info("Trigger Airflow DAG `nem_strategic_history` or run `run_strategic_history.py`.")
    st.stop()

st.success(f"Loaded **{len(df):,}** rows from `{source}`")

regions = sorted(df["regionid"].dropna().unique().tolist()) if "regionid" in df.columns else []
with st.sidebar:
    st.markdown("### Filters")
    region = st.multiselect("Regions", regions, default=regions)
    years = sorted(df["year"].dropna().unique().tolist()) if "year" in df.columns else []
    year_sel = st.multiselect("Years", years, default=years) if years else []

d = df[df["regionid"].isin(region)] if region else df
if year_sel and "year" in d.columns:
    d = d[d["year"].isin(year_sel)]

# KPIs
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("Mean RRP", f"${d['rrp'].mean():.1f}")
with k2:
    st.metric("Mean demand", f"{d['totaldemand'].mean():,.0f} MW" if "totaldemand" in d else "—")
with k3:
    st.metric("Rows in view", f"{len(d):,}")
with k4:
    st.metric("Regions", f"{d['regionid'].nunique()}" if "regionid" in d else "—")

st.markdown("#### Key insights")
for card in insight_cards(d):
    st.markdown(f'<div class="insight">{card}</div>', unsafe_allow_html=True)

if px is None:
    st.warning("Install plotly for charts.")
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Heatmaps", "Generation", "Models"])

with tab1:
    a, b = st.columns(2)
    with a:
        st.markdown('<div class="nem-card">', unsafe_allow_html=True)
        daily = (
            d.groupby([d["settlementdate"].dt.date, "regionid"])[["rrp", "totaldemand"]]
            .mean()
            .reset_index()
        )
        daily.columns = ["date", "regionid", "rrp", "totaldemand"]
        fig = px.line(daily, x="date", y="rrp", color="regionid", title="Average daily RRP")
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with b:
        st.markdown('<div class="nem-card">', unsafe_allow_html=True)
        bar = d.groupby("regionid")["rrp"].mean().reset_index()
        fig = px.bar(bar, x="regionid", y="rrp", title="Mean RRP by region",
                     color="regionid", color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(height=340, showlegend=False, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    if "price_regime" in d.columns:
        pie = d["price_regime"].value_counts().reset_index()
        pie.columns = ["regime", "count"]
        fig = px.pie(pie, names="regime", values="count", hole=0.45, title="Hours by price regime")
        fig.update_layout(height=320, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    reg_one = st.selectbox("Region", regions)
    sub = d[d["regionid"] == reg_one]
    piv = sub.pivot_table(index="hour", columns="dow", values="rrp", aggfunc="mean")
    piv.columns = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][: len(piv.columns)]
    fig = px.imshow(piv, aspect="auto", color_continuous_scale="YlOrRd",
                    title=f"Mean RRP heatmap — {reg_one}", labels=dict(color="RRP"))
    fig.update_layout(height=400, paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    cols = [c for c in ["semischedule_clearedmw", "dispatchablegeneration", "spare_capacity", "netinterchange"] if c in d.columns]
    if cols:
        g = d.groupby("regionid")[cols].mean().reset_index()
        fig = px.bar(g, x="regionid", y=cols, barmode="group", title="Generation / capacity / interchange (mean)")
        fig.update_layout(height=380, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    if "spare_capacity" in d.columns:
        sample = d.sample(min(4000, len(d)), random_state=42)
        fig = px.scatter(sample, x="spare_capacity", y="rrp", color="regionid", opacity=0.35, title="RRP vs spare capacity")
        fig.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    payloads = load_model_payloads()
    reg = payloads.get("regression_rrp", {})
    if reg.get("results"):
        st.dataframe(pd.DataFrame(reg["results"])[["model", "region", "mae", "rmse", "r2", "n_train", "n_test"]], hide_index=True)
    else:
        st.caption("Model metrics appear after analysis step stores results in analytics.model_results.")
    clf = payloads.get("classification_regime", {})
    if clf.get("results"):
        for r in clf["results"]:
            if "accuracy" in r:
                st.write(f"**{r['model']}** accuracy: {r['accuracy']:.3f}")
