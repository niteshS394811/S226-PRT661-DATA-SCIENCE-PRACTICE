#!/usr/bin/env python3
"""OPERATIONAL / DAILY pipeline (same thing).

- Default: next calendar day after max(settlementdate) in staging (incremental).
- Optional --start/--end: load a specific window with upsert (e.g. first ops week
  after strategic history: 2026/01/01 → 2026/01/08).

Strategic 2024–2025 is separate (run_strategic_history.py).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cleaning import clean_data
from src.extraction import main as extract_main
from src.loading import read_sql, upsert_window
from src.mart import load_daily_actuals, load_monthly_actuals
from src.modelling import train_and_forecast
from src.transformation import build_panel, build_features

RAW = ROOT / "src" / "data" / "processed" / "nemweb_price_demand_raw.csv"
CLEAN = ROOT / "src" / "data" / "processed" / "nemweb_price_demand_cleaned.csv"

# First operational week after strategic end (2025) — use when seeding ops
DEFAULT_OPS_START = "2026/01/01"
DEFAULT_OPS_END = "2026/01/08"


def next_day_window_from_db() -> tuple[str, str]:
    row = read_sql("SELECT MAX(settlementdate) AS mx FROM staging.stg_price_demand")
    if row.empty or pd.isna(row.iloc[0]["mx"]):
        raise SystemExit(
            "No data in staging. Run strategic history first, or:\n"
            "  run_daily_pipeline.py --start 2026/01/01 --end 2026/01/08"
        )
    mx = pd.to_datetime(row.iloc[0]["mx"])
    start = (mx.normalize() + pd.Timedelta(days=1)).strftime("%Y/%m/%d")
    end = (mx.normalize() + pd.Timedelta(days=2)).strftime("%Y/%m/%d")
    return start, end


def window_bounds(cleaned: pd.DataFrame, start: str | None, end: str | None):
    cleaned = cleaned.copy()
    cleaned["settlementdate"] = pd.to_datetime(cleaned["settlementdate"])
    if start and end:
        win_start = pd.Timestamp(start.replace("/", "-")).normalize()
        win_end = pd.Timestamp(end.replace("/", "-")).normalize()
    else:
        win_start = cleaned["settlementdate"].min().normalize()
        win_end = win_start + pd.Timedelta(days=1)
    return win_start, win_end


def run(
    skip_extract: bool = False,
    start: str | None = None,
    end: str | None = None,
    retrain: bool = False,
):
    print("=" * 60)
    print("OPERATIONAL / DAILY load (same pipeline)")
    print("=" * 60)

    if not skip_extract:
        if not start or not end:
            start, end = next_day_window_from_db()
        print(f"\n[1] Extract: {start} → {end}")
        extract_main(start, end, mode="daily")
    else:
        print("\n[1] Extract skipped")

    print("\n[2] Clean")
    cleaned = clean_data(pd.read_csv(RAW))
    CLEAN.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(CLEAN, index=False)
    cleaned["settlementdate"] = pd.to_datetime(cleaned["settlementdate"])
    win_start, win_end = window_bounds(cleaned, start, end)
    print(f"  window [{win_start}, {win_end})  rows={len(cleaned):,}")

    print("\n[3] UPSERT staging (incremental — keeps prior history)")
    upsert_window(cleaned, "staging", "stg_price_demand", win_start, win_end)

    print("\n[4] Rebuild features; upsert window")
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

    print("\n[5] UPSERT datamart daily (+ monthly refresh)")
    daily = load_daily_actuals(panel_new, full_refresh=False)
    monthly = load_monthly_actuals(None, full_refresh=True)
    print(f"  daily upserted={len(daily):,} monthly={len(monthly):,}")

    if retrain:
        print("\n[6] Retrain short-term (~1h) models")
        _, forecasts = train_and_forecast()
        print(f"  forecasts={0 if forecasts is None else len(forecasts)}")

    print("\nOperational/daily pipeline complete.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Operational = Daily (incremental). Optional --start/--end to seed a week."
    )
    p.add_argument("--skip-extract", action="store_true")
    p.add_argument("--start", default=None, help="e.g. 2026/01/01 (else max+1 day)")
    p.add_argument("--end", default=None, help="e.g. 2026/01/08")
    p.add_argument(
        "--seed-ops-week",
        action="store_true",
        help=f"Shorthand for --start {DEFAULT_OPS_START} --end {DEFAULT_OPS_END} --retrain",
    )
    p.add_argument("--retrain", action="store_true", help="Refresh ~1h forecasts after load")
    args = p.parse_args()
    start, end, retrain = args.start, args.end, args.retrain
    if args.seed_ops_week:
        start = start or DEFAULT_OPS_START
        end = end or DEFAULT_OPS_END
        retrain = True
    run(args.skip_extract, start, end, retrain)
