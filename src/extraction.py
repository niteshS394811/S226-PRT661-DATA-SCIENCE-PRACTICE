import csv
import glob
import os

import pandas as pd
from nemosis import dynamic_data_compiler
from nemosis.custom_errors import NoDataToReturn


########### Gets the exact folder path where this script (ass.py) is located #######33
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

###### Point directly to root 'data/raw_cache' and 'data/processed' #######3
CACHE_DIR = os.path.join(SCRIPT_DIR, "data", "raw_cache")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "data", "processed")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

########## Configurations ########
########### NEMWEB requires YYYY/MM/DD HH:MM:SS format ##############
START_DATE = "2025/01/01 00:00:00"
END_DATE = "2025/01/07 00:00:00"  # 1 week test range

############ Target regions defined in your proposal ###########3
REGIONS = ["NSW1", "QLD1", "VIC1", "SA1", "TAS1"]


def read_archive_cache(
    table_name: str,
    start: str,
    end: str,
    columns: list[str],
) -> pd.DataFrame:
    rows = []
    header = None

    pattern = os.path.join(
        CACHE_DIR,
        f"PUBLIC_ARCHIVE#{table_name}#FILE01#*.CSV",
    )
    for filepath in glob.glob(pattern):
        with open(filepath, newline="", encoding="utf-8-sig") as file:
            for row in csv.reader(file):
                if row and row[0] == "I" and header is None:
                    header = row[4:]
                elif row and row[0] == "D":
                    rows.append(row[4:])

    if header is None or not rows:
        raise NoDataToReturn(
            f"No cached {table_name} archive files found in {CACHE_DIR}"
        )

    cached = pd.DataFrame(rows, columns=header)
    cached["SETTLEMENTDATE"] = pd.to_datetime(
        cached["SETTLEMENTDATE"], errors="coerce"
    )
    start_date = pd.Timestamp(start)
    end_date = pd.Timestamp(end)
    cached = cached[
        cached["SETTLEMENTDATE"].between(start_date, end_date)
        & cached["REGIONID"].isin(REGIONS)
    ]
    cached["INTERVENTION"] = pd.to_numeric(
        cached["INTERVENTION"], errors="coerce"
    )
    return cached[columns].copy()


def fetch_table(
    table_name: str,
    start: str,
    end: str,
    columns: list[str],
) -> pd.DataFrame:
    try:
        return dynamic_data_compiler(
            start_time=start,
            end_time=end,
            table_name=table_name,
            raw_data_location=CACHE_DIR,
            select_columns=columns,
            filter_cols=["REGIONID"],
            filter_values=(REGIONS,),
        )
    except NoDataToReturn:
        print(f"Using local archive cache for {table_name}.")
        return read_archive_cache(table_name, start, end, columns)


def fetch_dispatch_prices(start: str, end: str) -> pd.DataFrame:
    """Fetch 5-minute Regional Reference Price (RRP) data."""
    print("Fetching DISPATCHPRICE table from NEMWEB...")
    df_price = fetch_table(
        "DISPATCHPRICE",
        start,
        end,
        ["SETTLEMENTDATE", "REGIONID", "RRP", "INTERVENTION"],
    )
    ########## Filter out physical interventions ############
    df_price = df_price[df_price["INTERVENTION"] == 0].drop(
        columns=["INTERVENTION"]
    )
    return df_price


def fetch_dispatch_demand(start: str, end: str) -> pd.DataFrame:
    """Fetch 5-minute Total Operational Demand data."""
    print("Fetching DISPATCHREGIONSUM table from NEMWEB...")
    df_demand = fetch_table(
        "DISPATCHREGIONSUM",
        start,
        end,
        [
            "SETTLEMENTDATE",
            "REGIONID",
            "TOTALDEMAND",
            "INTERVENTION",
        ],
    )
    df_demand = df_demand[df_demand["INTERVENTION"] == 0].drop(
        columns=["INTERVENTION"]
    )
    return df_demand


def main():
    print(f"Working Directory: {SCRIPT_DIR}")

    ######## 1. Download price and demand data #########
    price_df = fetch_dispatch_prices(START_DATE, END_DATE)
    demand_df = fetch_dispatch_demand(START_DATE, END_DATE)

    ######## 2. Merge into a single dataset #########   
    print("Merging Price and Demand datasets...")
    merged_df = pd.merge(
        price_df, demand_df, on=["SETTLEMENTDATE", "REGIONID"], how="inner"
    )

    ######## 3. Format datetime and sort #########
    merged_df["SETTLEMENTDATE"] = pd.to_datetime(merged_df["SETTLEMENTDATE"])
    merged_df.sort_values(by=["SETTLEMENTDATE", "REGIONID"], inplace=True)

    ######## 4. Save processed output in same folder's subfolder #########
    output_filepath = os.path.join(OUTPUT_DIR, "nemweb_price_demand_raw.csv")
    merged_df.to_csv(output_filepath, index=False)

    print(f"\nExtraction successful! Extracted {len(merged_df)} records.")
    print(f"File saved to: {output_filepath}")


if __name__ == "__main__":
    main()