"""Load analysis frames into Postgres analytics schema."""
from __future__ import annotations

import os

import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get(
    "NEM_DATABASE_URL",
    "postgresql+psycopg://nemuser:nempassword@localhost:5433/nemdb",
)


def get_engine():
    return create_engine(DATABASE_URL)


def ensure_analytics_schema():
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS analytics"))
        # grants if possible
        try:
            conn.execute(text("GRANT USAGE, CREATE ON SCHEMA analytics TO nemuser"))
            conn.execute(text("GRANT ALL ON ALL TABLES IN SCHEMA analytics TO nemuser"))
        except Exception:
            pass
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS analytics.fact_hourly (
                    settlementdate TIMESTAMP NOT NULL,
                    regionid TEXT NOT NULL,
                    rrp DOUBLE PRECISION,
                    totaldemand DOUBLE PRECISION,
                    netinterchange DOUBLE PRECISION,
                    availablegeneration DOUBLE PRECISION,
                    dispatchablegeneration DOUBLE PRECISION,
                    semischedule_clearedmw DOUBLE PRECISION,
                    uigf DOUBLE PRECISION,
                    spare_capacity DOUBLE PRECISION,
                    hour INTEGER,
                    dow INTEGER,
                    month INTEGER,
                    year INTEGER,
                    is_weekend INTEGER,
                    price_regime TEXT,
                    tight_system INTEGER,
                    net_importer INTEGER,
                    PRIMARY KEY (settlementdate, regionid)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS analytics.region_summary (
                    regionid TEXT PRIMARY KEY,
                    metrics_json TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS analytics.model_results (
                    id SERIAL PRIMARY KEY,
                    kind TEXT,
                    payload_json TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
        )


def load_hourly(df: pd.DataFrame, replace: bool = True):
    ensure_analytics_schema()
    eng = get_engine()
    cols = {
        "SETTLEMENTDATE": "settlementdate",
        "REGIONID": "regionid",
        "RRP": "rrp",
        "TOTALDEMAND": "totaldemand",
        "NETINTERCHANGE": "netinterchange",
        "AVAILABLEGENERATION": "availablegeneration",
        "DISPATCHABLEGENERATION": "dispatchablegeneration",
        "SEMISCHEDULE_CLEAREDMW": "semischedule_clearedmw",
        "UIGF": "uigf",
        "SPARE_CAPACITY": "spare_capacity",
        "hour": "hour",
        "dow": "dow",
        "month": "month",
        "year": "year",
        "is_weekend": "is_weekend",
        "price_regime": "price_regime",
        "tight_system": "tight_system",
        "net_importer": "net_importer",
    }
    out = df.rename(columns={k: v for k, v in cols.items() if k in df.columns})
    keep = [c for c in cols.values() if c in out.columns]
    out = out[keep]
    if replace:
        with eng.begin() as conn:
            conn.execute(text("TRUNCATE analytics.fact_hourly"))
    out.to_sql(
        "fact_hourly",
        eng,
        schema="analytics",
        if_exists="append",
        index=False,
        method="multi",
        chunksize=5000,
    )
    print(f"[analysis] loaded {len(out):,} rows → analytics.fact_hourly")


def load_json_result(kind: str, payload: dict):
    import json

    ensure_analytics_schema()
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO analytics.model_results (kind, payload_json) VALUES (:k, :p)"
            ),
            {"k": kind, "p": json.dumps(payload)},
        )
