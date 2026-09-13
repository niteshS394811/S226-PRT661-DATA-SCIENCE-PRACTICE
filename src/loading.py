"""PostgreSQL load helpers for staging / dwh / datamart schemas."""
from __future__ import annotations

import os
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


def upsert_window(
    df: pd.DataFrame,
    schema: str,
    table_name: str,
    start,
    end,
    date_col: str = "settlementdate",
):
    """Incremental: delete only [start, end), then append."""
    if df is None or df.empty:
        print(f"  skip upsert: {schema}.{table_name} (empty)")
        return
    delete_date_window(schema, table_name, start, end, date_col=date_col)
    load_data(df, table_name, schema=schema, if_exists="append")


def read_sql(sql: str, params: Optional[dict] = None) -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql(text(sql), engine, params=params or {})
    engine.dispose()
    return df


def window_bounds(df: pd.DataFrame, date_col: str = "settlementdate"):
    """Return (start, end) exclusive end = day after max date."""
    s = pd.to_datetime(df[date_col])
    start = s.min().to_pydatetime()
    end = (s.max().normalize() + pd.Timedelta(days=1)).to_pydatetime()
    return start, end
