#!/usr/bin/env python3
"""Strategic load: 2024 + 2025 (default) — warehouse + insights from same extract."""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STRATEGIC_START = "2024/01/01"
STRATEGIC_END = "2026/01/01"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default=STRATEGIC_START)
    p.add_argument("--end", default=STRATEGIC_END)
    p.add_argument("--skip-extract", action="store_true")
    p.add_argument("--skip-analysis", action="store_true")
    args = p.parse_args()

    print("=" * 60)
    print(f"STRATEGIC HISTORY {args.start} → {args.end}")
    print("=" * 60)

    from src.cleaning import clean_data
    from src.extraction import main as extract_main
    from src.loading import replace_table, read_sql
    from src.mart import load_daily_actuals, load_monthly_actuals
    from src.modelling import train_and_forecast
    from src.transformation import build_panel, build_features
    import pandas as pd

    RAW = ROOT / "src" / "data" / "processed" / "nemweb_price_demand_raw.csv"
    CLEAN = ROOT / "src" / "data" / "processed" / "nemweb_price_demand_cleaned.csv"

    if not args.skip_extract:
        extract_main(args.start, args.end, mode="history")
    cleaned = clean_data(pd.read_csv(RAW))
    CLEAN.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(CLEAN, index=False)
    cleaned["settlementdate"] = pd.to_datetime(cleaned["settlementdate"])
    replace_table(cleaned, "staging", "stg_price_demand")

    stg = read_sql(
        "SELECT settlementdate, regionid, rrp, totaldemand, netinterchange, demandforecast "
        "FROM staging.stg_price_demand"
    )
    panel = build_panel(stg)
    features = build_features(panel)
    replace_table(panel, "dwh", "panel")
    replace_table(features, "dwh", "features")
    load_daily_actuals(panel, full_refresh=True)
    load_monthly_actuals(panel, full_refresh=True)
    train_and_forecast()
    print("Strategic warehouse load complete.")

    if not args.skip_analysis:
        print("Building strategic insights from same extract...")
        sys.argv = ["run_analysis_pipeline.py", "--from-operational"]
        runpy.run_path(str(ROOT / "scripts" / "run_analysis_pipeline.py"), run_name="__main__")


if __name__ == "__main__":
    main()
