"""DAG 2: Daily incremental load + hourly 1d/1w forecast refresh."""
from __future__ import annotations

import sys
from datetime import datetime

if "/opt/airflow" not in sys.path:
    sys.path.insert(0, "/opt/airflow")

from airflow.sdk import dag, task

RAW = "/opt/airflow/src/data/processed/nemweb_price_demand_raw.csv"
CLEAN = "/opt/airflow/src/data/processed/nemweb_price_demand_cleaned.csv"


def _ensure_src_path() -> None:
    root = "/opt/airflow"
    if root not in sys.path:
        sys.path.insert(0, root)


@dag(
    dag_id="nem_daily_load",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["NEM", "daily", "incremental"],
)
def nem_daily_load():
    @task
    def extract_daily():
        _ensure_src_path()
        from src.extraction import main
        from src.loading import next_day_window_from_db

        start, end = next_day_window_from_db()
        print(f"Daily auto window: {start} → {end}")
        main(start, end, mode="daily")

    @task
    def incremental_load():
        _ensure_src_path()
        import pandas as pd
        from src.cleaning import clean_data
        from src.loading import read_sql, upsert_window, window_bounds
        from src.transformation import build_panel, build_features
        from src.mart import load_daily_actuals, load_monthly_actuals
        from src.modelling import train_and_forecast_hourly

        cleaned = clean_data(pd.read_csv(RAW))
        cleaned.to_csv(CLEAN, index=False)
        cleaned["settlementdate"] = pd.to_datetime(cleaned["settlementdate"])
        win_start, win_end = window_bounds(cleaned)
        upsert_window(cleaned, "staging", "stg_price_demand", win_start, win_end)

        stg = read_sql(
            """
            SELECT settlementdate, regionid, rrp, totaldemand, netinterchange, demandforecast
            FROM staging.stg_price_demand
            """
        )
        panel_all = build_panel(stg)
        features_all = build_features(panel_all)
        panel_new = panel_all[
            (panel_all["settlementdate"] >= win_start)
            & (panel_all["settlementdate"] < win_end)
        ]
        features_new = features_all[
            (features_all["settlementdate"] >= win_start)
            & (features_all["settlementdate"] < win_end)
        ]
        upsert_window(panel_new, "dwh", "panel", win_start, win_end)
        upsert_window(features_new, "dwh", "features", win_start, win_end)
        load_daily_actuals(panel_new, full_refresh=False)
        load_monthly_actuals(None, full_refresh=True)

        try:
            train_and_forecast_hourly(do_1d=True, do_1w=True)
        except Exception as e:
            print(f"hourly step failed (daily load still OK): {e}")

    extract_daily() >> incremental_load()


nem_daily_load()
