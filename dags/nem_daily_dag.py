"""DAG 2: Operational / Daily incremental load (max(date)+1)."""
from __future__ import annotations

import sys
from datetime import datetime

if "/opt/airflow" not in sys.path:
    sys.path.insert(0, "/opt/airflow")

from airflow.sdk import dag, task

RAW = "/opt/airflow/src/data/processed/nemweb_price_demand_raw.csv"
CLEAN = "/opt/airflow/src/data/processed/nemweb_price_demand_cleaned.csv"


def _ensure_src_path() -> None:
    if "/opt/airflow" not in sys.path:
        sys.path.insert(0, "/opt/airflow")


@dag(
    dag_id="nem_operational_daily",
    start_date=datetime(2026, 1, 1),
    schedule="0 6 * * *",
    catchup=False,
    tags=["NEM", "operational", "daily", "incremental"],
    doc_md="""
### Operational / Daily
Incremental upsert for the next calendar day after max(settlementdate).
CLI equivalent: `python /app/scripts/run_daily_pipeline.py`
""",
)
def nem_operational_daily():
    @task(task_id="extract_next_day")
    def extract_next_day() -> dict:
        _ensure_src_path()
        import pandas as pd
        from src.extraction import main as extract_main
        from src.loading import read_sql

        row = read_sql("SELECT MAX(settlementdate) AS mx FROM staging.stg_price_demand")
        if row.empty or pd.isna(row.iloc[0]["mx"]):
            raise RuntimeError("No staging data — run nem_strategic_history first.")
        mx = pd.to_datetime(row.iloc[0]["mx"])
        start = (mx.normalize() + pd.Timedelta(days=1)).strftime("%Y/%m/%d")
        end = (mx.normalize() + pd.Timedelta(days=2)).strftime("%Y/%m/%d")
        print(f"Daily window {start} → {end}")
        extract_main(start, end, mode="daily")
        return {"start": start, "end": end}

    @task(task_id="clean_upsert")
    def clean_upsert(window: dict):
        _ensure_src_path()
        import pandas as pd
        from src.cleaning import clean_data
        from src.loading import read_sql, upsert_window
        from src.transformation import build_panel, build_features
        from src.mart import load_daily_actuals, load_monthly_actuals

        cleaned = clean_data(pd.read_csv(RAW))
        cleaned.to_csv(CLEAN, index=False)
        cleaned["settlementdate"] = pd.to_datetime(cleaned["settlementdate"])
        win_start = pd.Timestamp(window["start"].replace("/", "-")).normalize()
        win_end = pd.Timestamp(window["end"].replace("/", "-")).normalize()
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
        print(f"Daily upsert complete for [{win_start}, {win_end})")

    w = extract_next_day()
    clean_upsert(w)


nem_operational_daily()
