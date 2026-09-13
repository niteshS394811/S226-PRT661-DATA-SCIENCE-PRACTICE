"""DAG 1: History load (full refresh) + train."""
from datetime import datetime
from airflow.sdk import dag, task

RAW = "/opt/airflow/src/data/processed/nemweb_price_demand_raw.csv"
CLEAN = "/opt/airflow/src/data/processed/nemweb_price_demand_cleaned.csv"


@dag(
    dag_id="nem_history_load_train",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["NEM", "history", "train"],
)
def nem_history_load_train():
    @task
    def extract():
        from src.extraction import main
        main(mode="history")

    @task
    def clean_and_load():
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
            SELECT settlementdate, regionid, rrp, totaldemand, netinterchange
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

    extract() >> clean_and_load()


nem_history_load_train()
