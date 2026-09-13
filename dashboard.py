"""Legacy entry — prefer dashboard_daily.py / dashboard_weekly.py."""
import streamlit as st
st.set_page_config(page_title="NEM Dashboards")
st.title("NEM Dashboards")
st.markdown(
    """
Use the dedicated apps:

| App | Port | File |
|-----|------|------|
| Daily | http://localhost:8501 | `dashboard_daily.py` |
| Weekly / Monthly | http://localhost:8502 | `dashboard_weekly.py` |
"""
)
