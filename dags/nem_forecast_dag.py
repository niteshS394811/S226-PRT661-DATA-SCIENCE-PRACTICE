from datetime import datetime

from airflow.sdk import Asset, dag, task


nem_market_data = Asset(
    "postgres://postgres:5432/nemdb/public/nem_market_data"
)


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

    @task(outlets=[nem_market_data])
    def load_database():
        import pandas as pd
        from src.loading import load_data

        input_file = (
            "/opt/airflow/src/data/processed/"
            "nemweb_price_demand_cleaned.csv"
        )
        cleaned = pd.read_csv(input_file)
        load_data(cleaned, "nem_market_data", if_exists="replace")

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

    extract() >> clean() >> load_database() >> transform()


nem_data_pipeline()