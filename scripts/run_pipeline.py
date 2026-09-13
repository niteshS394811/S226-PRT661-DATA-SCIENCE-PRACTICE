#!/usr/bin/env python3
"""Run the full layered pipeline without Airflow (local / docker app)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.cleaning import clean_data
from src.extraction import main as extract_main
from src.loading import replace_table, read_sql
from src.mart import load_daily_actuals
from src.modelling import train_and_forecast
from src.transformation import build_panel, build_features

RAW = ROOT / "src" / "data" / "processed" / "nemweb_price_demand_raw.csv"
CLEAN = ROOT / "src" / "data" / "processed" / "nemweb_price_demand_cleaned.csv"


def run(skip_extract: bool = False, start: str | None = None, end: str | None = None):
    print("=" * 60)
    print("NEM layered pipeline: staging → dwh → datamart")
    print("=" * 60)

    if not skip_extract:
        print("\n[1/6] Extract (NEMOSIS)")
        extract_main(start, end)
    else:
        print("\n[1/6] Extract skipped – using existing CSV")

    print("\n[2/6] Clean")
    raw = pd.read_csv(RAW)
    cleaned = clean_data(raw)
    CLEAN.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(CLEAN, index=False)
    print(f"  {len(cleaned):,} cleaned rows")

    print("\n[3/6] Load staging.stg_price_demand")
    cleaned["settlementdate"] = pd.to_datetime(cleaned["settlementdate"])
    replace_table(cleaned, schema="staging", table_name="stg_price_demand")

    print("\n[4/6] Transform → dwh.panel + dwh.features")
    stg = read_sql(
        "SELECT settlementdate, regionid, rrp, totaldemand FROM staging.stg_price_demand"
    )
    panel = build_panel(stg)
    features = build_features(panel)
    replace_table(panel, schema="dwh", table_name="panel")
    replace_table(features, schema="dwh", table_name="features")
    print(f"  panel={len(panel):,}  features={len(features):,}")

    print("\n[5/6] Datamart daily actuals")
    daily = load_daily_actuals(panel)
    print(f"  dm_daily_actuals={len(daily):,}")

    print("\n[6/6] Train models + write forecasts")
    _, forecasts = train_and_forecast()
    print(f"  dm_forecasts rows this run={0 if forecasts is None else len(forecasts)}")

    print("\nDone. Inspect in DBeaver:")
    print("  staging.stg_price_demand")
    print("  dwh.panel / dwh.features")
    print("  datamart.dm_daily_actuals / datamart.dm_forecasts")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--skip-extract", action="store_true")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    args = p.parse_args()
    # Allow host override when running on host machine
    if "NEM_DATABASE_URL" not in os.environ:
        # Prefer docker network host; user can override
        pass
    run(skip_extract=args.skip_extract, start=args.start, end=args.end)
