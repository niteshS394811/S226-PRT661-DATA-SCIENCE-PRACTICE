#!/usr/bin/env python3
"""Build insights from the SAME operational extract (no second history download).

Default: use nemweb_price_demand_raw.csv / analysis_raw_5min.csv written by history.
Optional: --extract to pull a custom window only when you need more years.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from src.analysis_transform import build_hourly_panel, summary_by_region
from src.analysis_models import run_classification, run_regression
from src.analysis_loading import load_hourly, load_json_result, ensure_analytics_schema

PROCESSED = ROOT / "src" / "data" / "processed"
CANDIDATES = [
    PROCESSED / "nemweb_price_demand_raw.csv",
    PROCESSED / "analysis_raw_5min.csv",
    Path("/app/src/data/processed/nemweb_price_demand_raw.csv"),
    Path("/app/src/data/processed/analysis_raw_5min.csv"),
]


def load_operational_raw() -> pd.DataFrame:
    for path in CANDIDATES:
        if path.exists():
            print(f"[1] Using operational extract: {path}")
            return pd.read_csv(path, parse_dates=["SETTLEMENTDATE"] if True else None)
    raise SystemExit(
        "No operational CSV found. Run history pipeline first:\n"
        "  python /app/scripts/run_history_pipeline.py --start ... --end ..."
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--from-operational", action="store_true", default=True)
    p.add_argument("--extract", action="store_true", help="Optional second NEMOSIS pull")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--csv", default=None)
    args = p.parse_args()

    print("=" * 60)
    print("ANALYSIS from unified history (no duplicate history load)")
    print("=" * 60)

    ensure_analytics_schema()

    if args.csv:
        raw = pd.read_csv(args.csv)
    elif args.extract:
        raise SystemExit(
            "--extract removed. Use run_strategic_history.py for long history, "
            "then run_analysis_pipeline.py --from-operational"
        )
    else:
        raw = load_operational_raw()
        # normalize column case
        if "SETTLEMENTDATE" not in raw.columns and "settlementdate" in raw.columns:
            raw = raw.rename(columns={c: c.upper() if c != "settlementdate" else "SETTLEMENTDATE" for c in raw.columns})
            # better mapping
        cols = {c: c.upper() for c in raw.columns}
        # only upper known
        upper_map = {}
        for c in raw.columns:
            if c.lower() in (
                "settlementdate", "regionid", "rrp", "totaldemand", "netinterchange",
                "demandforecast", "availablegeneration", "dispatchablegeneration",
                "semischedule_clearedmw", "uigf", "spare_capacity", "initialsupply",
                "clearedsupply", "totalintermittentgeneration",
            ):
                upper_map[c] = c.upper() if c.lower() != "spare_capacity" else "SPARE_CAPACITY"
            else:
                upper_map[c] = c
        raw = raw.rename(columns=upper_map)
        if "SETTLEMENTDATE" in raw.columns:
            raw["SETTLEMENTDATE"] = pd.to_datetime(raw["SETTLEMENTDATE"])

    print("[2] Hourly panel + regimes")
    hourly = build_hourly_panel(raw)
    print(f"    hourly rows={len(hourly):,}")
    out_csv = PROCESSED / "analysis_hourly.csv"
    try:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        hourly.to_csv(out_csv, index=False)
        print(f"    saved {out_csv}")
    except Exception:
        hourly.to_csv("/tmp/analysis_hourly.csv", index=False)

    print("[3] Load analytics.fact_hourly (optional)")
    try:
        load_hourly(hourly, replace=True)
    except Exception as e:
        print(f"    WARN DB: {e} (CSV still available for dashboard)")

    print("[4] Models")
    summary = summary_by_region(hourly)
    print(summary.to_string(index=False))
    reg_all = run_regression(hourly, target="RRP")
    clf_all = run_classification(hourly)
    try:
        load_json_result("regression_rrp", reg_all)
        load_json_result("classification_regime", clf_all)
    except Exception as e:
        print(f"    WARN model store: {e}")

    if reg_all.get("results"):
        print("\nRegression (RRP):")
        for r in reg_all["results"]:
            print(f"  {r['model']}: MAE={r['mae']:.2f} RMSE={r['rmse']:.2f} R2={r['r2']:.3f}")
    if clf_all.get("results"):
        print("\nClassification:")
        for r in clf_all["results"]:
            if "accuracy" in r:
                print(f"  {r['model']}: accuracy={r['accuracy']:.3f}")

    print("\nDone. streamlit run dashboard_insights.py --server.port 8503")


if __name__ == "__main__":
    main()
