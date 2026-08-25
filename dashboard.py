from pathlib import Path

import pandas as pd
import psycopg
import streamlit as st


DATABASE_URL = "postgresql://nemuser:nempassword@postgres:5432/nemdb"


@st.cache_data(ttl=30)
def load_data() -> pd.DataFrame:
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM nem_market_data")
            rows = cursor.fetchall()
            columns = [column.name for column in cursor.description]
    data = pd.DataFrame(rows, columns=columns)
    data["SETTLEMENTDATE"] = pd.to_datetime(
        data["SETTLEMENTDATE"], errors="coerce"
    )

    data["RRP"] = pd.to_numeric(data["RRP"], errors="coerce")
    data["TOTALDEMAND"] = pd.to_numeric(
        data["TOTALDEMAND"], errors="coerce"
    )
    return data.dropna(subset=["SETTLEMENTDATE", "REGIONID"])


st.set_page_config(
    page_title="NEM Market Dashboard",
    page_icon="⚡",
    layout="wide",
)

st.title("NEM Market Dashboard")
st.caption("Historical AEMO dispatch prices and regional demand")

try:
    data = load_data()
except Exception as error:
    st.error(str(error))
    st.stop()

with st.sidebar:
    st.header("Filters")
    regions = st.multiselect(
        "Regions",
        options=sorted(data["REGIONID"].unique()),
        default=sorted(data["REGIONID"].unique()),
    )
    date_range = st.date_input(
        "Date range",
        value=(data["SETTLEMENTDATE"].min().date(), data["SETTLEMENTDATE"].max().date()),
        min_value=data["SETTLEMENTDATE"].min().date(),
        max_value=data["SETTLEMENTDATE"].max().date(),
    )

filtered = data[data["REGIONID"].isin(regions)].copy()
if len(date_range) == 2:
    start_date, end_date = date_range
    filtered = filtered[
        filtered["SETTLEMENTDATE"].dt.date.between(start_date, end_date)
    ]

if filtered.empty:
    st.warning("No data matches the selected filters.")
    st.stop()

metric_columns = st.columns(4)
metric_columns[0].metric("Records", f"{len(filtered):,}")
metric_columns[1].metric("Average price", f"${filtered['RRP'].mean():,.2f}")
metric_columns[2].metric("Peak price", f"${filtered['RRP'].max():,.2f}")
metric_columns[3].metric("Average demand", f"{filtered['TOTALDEMAND'].mean():,.0f} MW")

chart_data = filtered.set_index("SETTLEMENTDATE")
left, right = st.columns(2)
with left:
    st.subheader("Regional reference price")
    st.line_chart(chart_data.pivot_table(index=chart_data.index, columns="REGIONID", values="RRP"))
with right:
    st.subheader("Regional demand")
    st.line_chart(chart_data.pivot_table(index=chart_data.index, columns="REGIONID", values="TOTALDEMAND"))

st.subheader("Data")
st.dataframe(
    filtered.sort_values("SETTLEMENTDATE", ascending=False),
    use_container_width=True,
    hide_index=True,
)
st.caption("Source: PostgreSQL table nem_market_data")