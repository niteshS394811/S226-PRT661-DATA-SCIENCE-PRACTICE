"""Populate datamart tables from DWH."""
from __future__ import annotations

import pandas as pd

from src.loading import read_sql, replace_table, upsert_window


def build_daily_actuals(panel: pd.DataFrame | None = None) -> pd.DataFrame:
    if panel is None:
        panel = read_sql(
            """
            SELECT settlementdate, regionid, rrp, totaldemand, netinterchange
            FROM dwh.panel
            """
        )
    if panel is None or panel.empty:
        return pd.DataFrame()
    df = panel.copy()
    df["settlementdate"] = pd.to_datetime(df["settlementdate"], errors="coerce")
    df["trade_date"] = df["settlementdate"].dt.normalize()
    if "netinterchange" not in df.columns:
        df["netinterchange"] = 0.0
    daily = (
        df.groupby(["trade_date", "regionid"], as_index=False)
        .agg(
            avg_rrp=("rrp", "mean"),
            max_rrp=("rrp", "max"),
            min_rrp=("rrp", "min"),
            avg_demand=("totaldemand", "mean"),
            max_demand=("totaldemand", "max"),
            min_demand=("totaldemand", "min"),
            avg_netinterchange=("netinterchange", "mean"),
            intervals=("rrp", "count"),
        )
    )
    return daily


def build_monthly_actuals(panel: pd.DataFrame | None = None) -> pd.DataFrame:
    if panel is None:
        panel = read_sql(
            """
            SELECT settlementdate, regionid, rrp, totaldemand, netinterchange
            FROM dwh.panel
            """
        )
    if panel is None or panel.empty:
        return pd.DataFrame()
    df = panel.copy()
    df["settlementdate"] = pd.to_datetime(df["settlementdate"], errors="coerce")
    df["month_start"] = df["settlementdate"].dt.to_period("M").dt.to_timestamp()
    if "netinterchange" not in df.columns:
        df["netinterchange"] = 0.0
    monthly = (
        df.groupby(["month_start", "regionid"], as_index=False)
        .agg(
            avg_rrp=("rrp", "mean"),
            max_rrp=("rrp", "max"),
            min_rrp=("rrp", "min"),
            avg_demand=("totaldemand", "mean"),
            max_demand=("totaldemand", "max"),
            min_demand=("totaldemand", "min"),
            avg_netinterchange=("netinterchange", "mean"),
            intervals=("rrp", "count"),
        )
    )
    return monthly


def load_daily_actuals(panel: pd.DataFrame | None = None, full_refresh: bool = False):
    daily = build_daily_actuals(panel)
    if daily.empty:
        return daily
    if full_refresh:
        replace_table(daily, schema="datamart", table_name="dm_daily_actuals")
        return daily
    for trade_date, chunk in daily.groupby("trade_date"):
        start = pd.Timestamp(trade_date).to_pydatetime()
        end = (pd.Timestamp(trade_date) + pd.Timedelta(days=1)).to_pydatetime()
        upsert_window(
            chunk,
            schema="datamart",
            table_name="dm_daily_actuals",
            start=start,
            end=end,
            date_col="trade_date",
        )
    return daily


def load_monthly_actuals(panel: pd.DataFrame | None = None, full_refresh: bool = True):
    monthly = build_monthly_actuals(panel)
    if monthly.empty:
        return monthly
    if full_refresh:
        replace_table(monthly, schema="datamart", table_name="dm_monthly_actuals")
    else:
        for month_start, chunk in monthly.groupby("month_start"):
            start = pd.Timestamp(month_start).to_pydatetime()
            end = (pd.Timestamp(month_start) + pd.offsets.MonthBegin(1)).to_pydatetime()
            upsert_window(
                chunk,
                schema="datamart",
                table_name="dm_monthly_actuals",
                start=start,
                end=end,
                date_col="month_start",
            )
    return monthly
