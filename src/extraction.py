"""Extract NEM DISPATCHPRICE + DISPATCHREGIONSUM via NEMOSIS → CSV."""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from nemosis import dynamic_data_compiler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, "data", "raw_cache")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "data", "processed")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

########## Configurations ########
########### NEMWEB requires YYYY/MM/DD HH:MM:SS format ##############
START_DATE = "2025/01/06 00:00:00"
END_DATE = "2025/01/07 00:00:00"  # 1 week test range

############ Target regions defined in your proposal ###########3
REGIONS = ["NSW1", "QLD1", "VIC1", "SA1", "TAS1"]

# Used only when caller does not pass dates (history demo fallback)
HISTORY_START = "2025/01/01 00:00:00"
HISTORY_END = "2025/01/08 00:00:00"


def yesterday_window() -> tuple[str, str]:
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=1)
    return start.strftime("%Y/%m/%d %H:%M:%S"), end.strftime("%Y/%m/%d %H:%M:%S")


def normalize_date(s: str, is_end: bool = False) -> str:
    s = s.replace("-", "/")
    if " " not in s:
        s = s + (" 00:00:00")
    return s


def fetch_dispatch_prices(start: str, end: str) -> pd.DataFrame:
    print(f"Fetching DISPATCHPRICE ({start} → {end})...")
    df = dynamic_data_compiler(
        start_time=start,
        end_time=end,
        table_name="DISPATCHPRICE",
        raw_data_location=CACHE_DIR,
        select_columns=["SETTLEMENTDATE", "REGIONID", "RRP", "INTERVENTION"],
        filter_cols=["REGIONID"],
        filter_values=(REGIONS,),
    )
    if df is None or df.empty:
        return pd.DataFrame(columns=["SETTLEMENTDATE", "REGIONID", "RRP"])
    return df[df["INTERVENTION"] == 0].drop(columns=["INTERVENTION"])


def fetch_dispatch_demand(start: str, end: str) -> pd.DataFrame:
    print(f"Fetching DISPATCHREGIONSUM ({start} → {end})...")
    df = dynamic_data_compiler(
        start_time=start,
        end_time=end,
        table_name="DISPATCHREGIONSUM",
        raw_data_location=CACHE_DIR,
        select_columns=["SETTLEMENTDATE", "REGIONID", "TOTALDEMAND", "INTERVENTION"],
        filter_cols=["REGIONID"],
        filter_values=(REGIONS,),
    )
    if df is None or df.empty:
        return pd.DataFrame(columns=["SETTLEMENTDATE", "REGIONID", "TOTALDEMAND"])
    return df[df["INTERVENTION"] == 0].drop(columns=["INTERVENTION"])


def extract(start: str, end: str, output_name: str = "nemweb_price_demand_raw.csv") -> pd.DataFrame:
    price_df = fetch_dispatch_prices(start, end)
    demand_df = fetch_dispatch_demand(start, end)
    print("Merging price + demand...")
    merged = pd.merge(price_df, demand_df, on=["SETTLEMENTDATE", "REGIONID"], how="inner")
    merged["SETTLEMENTDATE"] = pd.to_datetime(merged["SETTLEMENTDATE"])
    merged = merged.sort_values(["SETTLEMENTDATE", "REGIONID"]).reset_index(drop=True)
    out = os.path.join(OUTPUT_DIR, output_name)
    merged.to_csv(out, index=False)
    print(f"Extraction OK: {len(merged):,} rows → {out}")
    return merged


def main(start: str | None = None, end: str | None = None, mode: str = "history"):
    """
    mode:
      history → use HISTORY_* defaults if dates missing
      daily   → yesterday window if dates missing
    """
    if start and end:
        start, end = normalize_date(start), normalize_date(end)
    elif mode == "daily":
        start, end = yesterday_window()
    else:
        start, end = HISTORY_START, HISTORY_END
    print(f"Working directory: {SCRIPT_DIR}")
    print(f"Mode={mode}  window={start} → {end}")
    return extract(start, end)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--mode", choices=["history", "daily"], default="history")
    p.add_argument("--days", type=int, default=None, help="Last N days ending yesterday")
    args = p.parse_args()
    start, end = args.start, args.end
    if args.days is not None and not (start or end):
        end_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=0)
        # end = yesterday midnight if we want last complete day only for days=1
        end_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        start_dt = end_dt - timedelta(days=args.days)
        start = start_dt.strftime("%Y/%m/%d %H:%M:%S")
        end = end_dt.strftime("%Y/%m/%d %H:%M:%S")
        args.mode = "history" if args.days > 1 else "daily"
    main(start, end, mode=args.mode)
