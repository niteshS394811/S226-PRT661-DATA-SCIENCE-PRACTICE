from datetime import datetime

from airflow.sdk import dag, task


@dag(
    dag_id="nem_data_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["NEM", "ETL", "PRT661"],
)
def nem_data_pipeline():

    @task
    def extract():
        from src.extraction import main

        main()

    @task
    def clean():
        import pandas as pd
        from src.cleaning import clean_data

        input_file = (
            "/opt/airflow/src/data/processed/"
            "nemweb_price_demand_raw.csv"
        )

        df = pd.read_csv(input_file)

        cleaned = clean_data(df)

        cleaned.to_csv(
            "/opt/airflow/src/data/processed/"
            "nemweb_price_demand_cleaned.csv",
            index=False,
        )

    @task
    def transform():
        import pandas as pd
        from src.transformation import transform_data

        input_file = (
            "/opt/airflow/src/data/processed/"
            "nemweb_price_demand_cleaned.csv"
        )

        df = pd.read_csv(input_file)

        transformed = transform_data(df)

        transformed.to_csv(
            "/opt/airflow/src/data/processed/"
            "nemweb_price_demand_transformed.csv",
            index=False,
        )

    extract() >> clean() >> transform()


nem_data_pipeline()