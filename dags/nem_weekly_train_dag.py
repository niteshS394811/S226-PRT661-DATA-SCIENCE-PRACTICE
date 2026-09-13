"""DAG 3: Weekly model retrain + forecasts."""
from datetime import datetime
from airflow.sdk import dag, task


@dag(
    dag_id="nem_weekly_train",
    start_date=datetime(2026, 1, 1),
    schedule="@weekly",
    catchup=False,
    tags=["NEM", "weekly", "train"],
)
def nem_weekly_train():
    @task
    def train():
        from src.modelling import train_and_forecast
        train_and_forecast()

    train()


nem_weekly_train()
