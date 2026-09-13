#!/usr/bin/env python3
"""Run hourly aggregated 1-day and/or 1-week forecasts (logic lives in src.modelling)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.modelling import train_and_forecast_hourly


def main():
    p = argparse.ArgumentParser(description="Hourly 1d/1w forecast layer")
    p.add_argument("--day-only", action="store_true", help="Only 24-hour ahead")
    p.add_argument("--week-only", action="store_true", help="Only 168-hour ahead")
    args = p.parse_args()
    do_1d, do_1w = True, True
    if args.day_only:
        do_1d, do_1w = True, False
    if args.week_only:
        do_1d, do_1w = False, True
    train_and_forecast_hourly(do_1d=do_1d, do_1w=do_1w)


if __name__ == "__main__":
    main()
