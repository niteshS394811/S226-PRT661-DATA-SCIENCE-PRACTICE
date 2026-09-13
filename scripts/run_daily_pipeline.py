#!/usr/bin/env python3
"""Pipeline 2: DAILY incremental load + refresh hourly 1d/1w forecasts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cleaning import clean_data
from src.extraction import main as extract_main
from src.loading import (
    next_day_window_from_db,
    read_sql,
    upsert_window,
    window_bounds,
)
from src.mart import load_daily_actuals, load_monthly_actuals
from src.modelling import train_and_forecast_hourly
from src.transformation import build_panel, build_features

RAW = ROOT / "src" / "data" / "processed" / "nemweb_price_demand_raw.csv"
CLEAN = ROOT / "src" / "data" / "processed" / "nemweb_price_demand_cleaned.csv"


def run(skip_extract: bool = False, start: str | None = None, end: str | None = None):
    print("=" * 60)
    print("PIPELINE 2: DAILY incremental load + hourly forecasts")
    print("=" * 60)

    if not skip_extract:
        if not start or not end:
            start, end = next_day_window_from_db()
        print(f"\n[1] Extract one day: {start} → {end}")
        extract_main(start, end, mode="daily")
    else:
        print("\n[1] Extract skipped")

    print("\n[2] Clean")
    cleaned = clean_data(pd.read_csv(RAW))
    cleaned.to_csv(CLEAN, index=False)
    cleaned["settlementdate"] = pd.to_datetime(cleaned["settlementdate"])
    win_start, win_end = window_bounds(cleaned)
    print(f"  window [{win_start}, {win_end})  rows={len(cleaned):,}")

    print("\n[3] UPSERT staging (keep history)")
    upsert_window(cleaned, "staging", "stg_price_demand", win_start, win_end)

    print("\n[4] Rebuild features from full staging; upsert new window only")
    stg = read_sql(
        """
        SELECT settlementdate, regionid, rrp, totaldemand, netinterchange, demandforecast
        FROM staging.stg_price_demand
        """
    )
    panel_all = build_panel(stg)
    features_all = build_features(panel_all)
    panel_new = panel_all[
        (panel_all["settlementdate"] >= win_start) & (panel_all["settlementdate"] < win_end)
    ]
    features_new = features_all[
        (features_all["settlementdate"] >= win_start)
        & (features_all["settlementdate"] < win_end)
    ]
    upsert_window(panel_new, "dwh", "panel", win_start, win_end)
    upsert_window(features_new, "dwh", "features", win_start, win_end)
    print(f"  panel+={len(panel_new):,} features+={len(features_new):,}")

    print("\n[5] UPSERT datamart daily (+ refresh monthly)")
    daily = load_daily_actuals(panel_new, full_refresh=False)
    monthly = load_monthly_actuals(None, full_refresh=True)
    print(f"  daily upserted={len(daily):,} monthly={len(monthly):,}")

    print("\n[6] Refresh hourly 1d/1w forecasts (tables auto-created if needed)")
    try:
        hourly = train_and_forecast_hourly(do_1d=True, do_1w=True)
        n = 0 if hourly["forecasts"] is None else len(hourly["forecasts"])
        print(f"  hourly forecasts={n}")
    except Exception as e:
        print(f"  hourly forecast step failed (daily load still OK): {e}")

    print("\nDaily pipeline complete.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--skip-extract", action="store_true")
    p.add_argument("--start", default=None, help="Override start (else max(date)+1 from DB)")
    p.add_argument("--end", default=None, help="Override end")
    args = p.parse_args()
    run(args.skip_extract, args.start, args.end)
