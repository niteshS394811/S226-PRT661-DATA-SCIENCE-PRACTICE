"""DAG 1: Strategic history load (full refresh) + short-term train + insights.

Trigger manually. Default window is set in extraction / run_strategic_history
(2024-01-01 → 2026-01-01) unless you change extract main() args.
"""
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
    dag_id="nem_strategic_history",
    start_date=datetime(2026, 1, 1),
    schedule=None,  # manual only
    catchup=False,
    tags=["NEM", "strategic", "history"],
    doc_md="""
### Strategic history
Full refresh of staging → dwh → datamart for the strategic window, trains ~1h models,
then builds analytics insights from the same extract.

Equivalent CLI: `python /app/scripts/run_strategic_history.py`
""",
)
def nem_strategic_history():
    @task(task_id="extract_strategic")
    def extract_strategic():
        _ensure_src_path()
        from src.extraction import main

        # Default strategic window (override by editing these two lines if needed)
        main(start="2024/01/01", end="2026/01/01", mode="history")

    @task(task_id="clean_load_train")
    def clean_load_train():
        _ensure_src_path()
        import pandas as pd
        from src.cleaning import clean_data
        from src.loading import replace_table, read_sql
        from src.transformation import build_panel, build_features
        from src.mart import load_daily_actuals, load_monthly_actuals
        from src.modelling import train_and_forecast

        cleaned = clean_data(pd.read_csv(RAW))
        cleaned.to_csv(CLEAN, index=False)
        cleaned["settlementdate"] = pd.to_datetime(cleaned["settlementdate"])
        replace_table(cleaned, "staging", "stg_price_demand")

        stg = read_sql(
            """
            SELECT settlementdate, regionid, rrp, totaldemand, netinterchange, demandforecast
            FROM staging.stg_price_demand
            """
        )
        panel = build_panel(stg)
        features = build_features(panel)
        replace_table(panel, "dwh", "panel")
        replace_table(features, "dwh", "features")
        load_daily_actuals(panel, full_refresh=True)
        load_monthly_actuals(panel, full_refresh=True)
        train_and_forecast()
        print("Strategic warehouse + ~1h train complete.")

    @task(task_id="build_strategic_insights")
    def build_strategic_insights():
        _ensure_src_path()
        import runpy
        from pathlib import Path

        # Rebuild insights from operational extract (no second NEMOSIS pull)
        sys.argv = ["run_analysis_pipeline.py", "--from-operational"]
        runpy.run_path(
            "/opt/airflow/scripts/run_analysis_pipeline.py"
            if Path("/opt/airflow/scripts/run_analysis_pipeline.py").exists()
            else str(Path("/opt/airflow") / "scripts" / "run_analysis_pipeline.py"),
            run_name="__main__",
        )

    extract_strategic() >> clean_load_train() >> build_strategic_insights()


nem_strategic_history()
