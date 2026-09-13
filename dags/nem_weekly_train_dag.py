"""DAG 3: Weekly model retrain + forecasts."""
from __future__ import annotations

import sys
from datetime import datetime

if "/opt/airflow" not in sys.path:
    sys.path.insert(0, "/opt/airflow")

from airflow.sdk import dag, task


def _ensure_src_path() -> None:
    root = "/opt/airflow"
    if root not in sys.path:
        sys.path.insert(0, root)


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
        _ensure_src_path()
        from src.modelling import train_and_forecast

        train_and_forecast()

    train()


nem_weekly_train()
