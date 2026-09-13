"""PostgreSQL load helpers for staging / dwh / datamart schemas."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get(
    "NEM_DATABASE_URL",
    "postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb",
)


def get_engine():
    return create_engine(DATABASE_URL)


def load_data(
    df: pd.DataFrame,
    table_name: str,
    schema: str = "public",
    if_exists: str = "append",
    chunksize: int = 5000,
):
    if df is None or df.empty:
        print(f"  skip load: {schema}.{table_name} (empty dataframe)")
        return
    max_rows_per_batch = max(1, 65535 // max(len(df.columns), 1))
    chunksize = min(chunksize, max_rows_per_batch)
    engine = get_engine()
    df.to_sql(
        table_name,
        engine,
        schema=schema,
        if_exists=if_exists,
        index=False,
        chunksize=chunksize,
        method="multi",
    )
    engine.dispose()
    print(f"  loaded {len(df):,} rows → {schema}.{table_name} ({if_exists})")


def truncate_table(schema: str, table_name: str):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f'TRUNCATE TABLE "{schema}"."{table_name}"'))
    engine.dispose()
    print(f"  truncated {schema}.{table_name}")


def replace_table(df: pd.DataFrame, schema: str, table_name: str):
    """Full refresh: TRUNCATE then append."""
    if df is None or df.empty:
        print(f"  skip replace: {schema}.{table_name} (empty)")
        return
    truncate_table(schema, table_name)
    load_data(df, table_name, schema=schema, if_exists="append")


def delete_date_window(
    schema: str,
    table_name: str,
    start,
    end,
    date_col: str = "settlementdate",
):
    """
    Delete rows in [start, end).
    Start/end are normalized to calendar-day midnights so we never miss
    rows when the CSV first interval is 00:05 instead of 00:00.
    """
    start = pd.Timestamp(start).normalize().to_pydatetime()
    end = pd.Timestamp(end).normalize().to_pydatetime()
    if end <= start:
        end = (pd.Timestamp(start) + pd.Timedelta(days=1)).to_pydatetime()

    engine = get_engine()
    sql = text(
        f'DELETE FROM "{schema}"."{table_name}" '
        f'WHERE "{date_col}" >= :start AND "{date_col}" < :end'
    )
    with engine.begin() as conn:
        result = conn.execute(sql, {"start": start, "end": end})
        n = result.rowcount
    engine.dispose()
    print(f"  deleted {n} rows from {schema}.{table_name} [{start}, {end})")
    return n


def window_bounds(df: pd.DataFrame, date_col: str = "settlementdate"):
    """
    Full calendar days covering the data.
    start = midnight of min date (inclusive)
    end   = midnight after max date (exclusive)
    """
    s = pd.to_datetime(df[date_col])
    start = s.min().normalize().to_pydatetime()
    end = (s.max().normalize() + pd.Timedelta(days=1)).to_pydatetime()
    return start, end


def upsert_window(
    df: pd.DataFrame,
    schema: str,
    table_name: str,
    start=None,
    end=None,
    date_col: str = "settlementdate",
):
    """
    Incremental load: delete full calendar day(s) covered by df, then append.
    start/end arguments are ignored if df is non-empty — bounds always come
    from the dataframe so DELETE and INSERT cover the same keys.
    """
    if df is None or df.empty:
        print(f"  skip upsert: {schema}.{table_name} (empty)")
        return

    # Always derive window from the data being loaded (avoids 00:05 PK clashes)
    start, end = window_bounds(df, date_col=date_col)
    delete_date_window(schema, table_name, start, end, date_col=date_col)
    load_data(df, table_name, schema=schema, if_exists="append")


def read_sql(sql: str, params: Optional[dict] = None) -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql(text(sql), engine, params=params or {})
    engine.dispose()
    return df


def next_day_window_from_db(
    schema: str = "staging",
    table: str = "stg_price_demand",
    date_col: str = "settlementdate",
) -> tuple[str, str]:
    """
    Return NEMOSIS-style (start, end) for the calendar day AFTER the latest
    settlement date already in the table.

    Uses MAX(date)::date so a lone midnight row does not skip a full day of data.
    If the table is empty, fall back to yesterday 00:00 → today 00:00 UTC.
    """
    df = read_sql(
        f'SELECT MAX("{date_col}")::date AS max_d FROM "{schema}"."{table}"'
    )
    if df.empty or df.iloc[0]["max_d"] is None or pd.isna(df.iloc[0]["max_d"]):
        end = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start = end - timedelta(days=1)
        print(f"  DB empty — fallback window {start} → {end}")
        return (
            start.strftime("%Y/%m/%d %H:%M:%S"),
            end.strftime("%Y/%m/%d %H:%M:%S"),
        )

    max_d = pd.Timestamp(df.iloc[0]["max_d"]).normalize()
    start = (max_d + pd.Timedelta(days=1)).to_pydatetime()
    end = (max_d + pd.Timedelta(days=2)).to_pydatetime()
    print(f"  max loaded date={max_d.date()} → next day {start} → {end}")
    return (
        start.strftime("%Y/%m/%d %H:%M:%S"),
        end.strftime("%Y/%m/%d %H:%M:%S"),
    )
