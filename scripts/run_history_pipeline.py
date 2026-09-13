#!/usr/bin/env python3
"""Pipeline 1: HISTORY load (full refresh) + 5-min train + hourly 1d/1w forecasts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cleaning import clean_data
from src.extraction import main as extract_main
from src.loading import replace_table, read_sql
from src.mart import load_daily_actuals, load_monthly_actuals
from src.modelling import train_and_forecast, train_and_forecast_hourly
from src.transformation import build_panel, build_features

RAW = ROOT / "src" / "data" / "processed" / "nemweb_price_demand_raw.csv"
CLEAN = ROOT / "src" / "data" / "processed" / "nemweb_price_demand_cleaned.csv"


def run(skip_extract: bool = False, start: str | None = None, end: str | None = None):
    print("=" * 60)
    print("PIPELINE 1: HISTORY load + 5-min train + hourly forecasts")
    print("=" * 60)

    if not skip_extract:
        print("\n[1] Extract history window")
        extract_main(start, end, mode="history")
    else:
        print("\n[1] Extract skipped")

    print("\n[2] Clean")
    cleaned = clean_data(pd.read_csv(RAW))
    CLEAN.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(CLEAN, index=False)
    print(f"  {len(cleaned):,} rows  cols={list(cleaned.columns)}")

    print("\n[3] FULL REFRESH staging")
    cleaned["settlementdate"] = pd.to_datetime(cleaned["settlementdate"])
    replace_table(cleaned, "staging", "stg_price_demand")

    print("\n[4] FULL REFRESH dwh.panel + dwh.features")
    stg = read_sql(
        """
        SELECT settlementdate, regionid, rrp, totaldemand, netinterchange, demandforecast
        FROM staging.stg_price_demand
        """
    )
    panel = build_panel(stg)
    features = build_features(panel)
    replace_table(panel, "dwh", "panel")
    replace_table(features, "dwh", "features")
    print(f"  panel={len(panel):,} features={len(features):,}")

    print("\n[5] FULL REFRESH datamart daily + monthly")
    daily = load_daily_actuals(panel, full_refresh=True)
    monthly = load_monthly_actuals(panel, full_refresh=True)
    print(f"  daily={len(daily):,} monthly={len(monthly):,}")

    print("\n[6] Train 5-min models + ~1h forecasts")
    _, forecasts = train_and_forecast()
    print(f"  5-min forecasts={0 if forecasts is None else len(forecasts)}")

    print("\n[7] Hourly aggregate models + 1d/1w forecasts")
    try:
        hourly = train_and_forecast_hourly(do_1d=True, do_1w=True)
        n = 0 if hourly["forecasts"] is None else len(hourly["forecasts"])
        print(f"  hourly forecasts={n}")
    except Exception as e:
        print(f"  hourly forecast step failed (5-min pipeline still OK): {e}")

    print("\nHistory pipeline complete.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--skip-extract", action="store_true")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    args = p.parse_args()
    run(args.skip_extract, args.start, args.end)
