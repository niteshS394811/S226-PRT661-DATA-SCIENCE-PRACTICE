#!/usr/bin/env python3
"""Pipeline 3: WEEKLY model retrain + forecasts (uses existing DWH features)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.modelling import train_and_forecast


def run():
    print("=" * 60)
    print("PIPELINE 3: WEEKLY model train + forecasts")
    print("=" * 60)
    result, forecasts = train_and_forecast()
    metrics = result.get("metrics")
    n_m = 0 if metrics is None else len(metrics)
    n_f = 0 if forecasts is None else len(forecasts)
    print(f"  metrics rows={n_m}  forecast rows={n_f}")
    print("\nWeekly train complete.")


if __name__ == "__main__":
    run()
