# PRT661 – NEM Forecasting (3 pipelines + 2 dashboards)

## Pipelines

| # | Name | Script / DAG | Schedule | Behaviour |
|---|------|--------------|----------|-----------|
| 1 | **History load + train** | `scripts/run_history_pipeline.py` / `nem_history_load_train` | Manual | Full refresh staging→dwh→datamart, train models |
| 2 | **Daily load** | `scripts/run_daily_pipeline.py` / `nem_daily_load` | `@daily` | Extract **1 day**, **upsert** (keeps history), no train |
| 3 | **Weekly train** | `scripts/run_weekly_train.py` / `nem_weekly_train` | `@weekly` | Retrain on full `dwh.features`, append forecasts |

## Dashboards

| App | Port | Reads |
|-----|------|--------|
| Daily | http://localhost:8501 | `dm_daily_actuals`, latest `dm_forecasts` |
| Weekly/Monthly | http://localhost:8502 | `dm_monthly_actuals`, `dm_model_metrics`, forecast runs |

## Database layers (`nemdb`)

```
staging.stg_price_demand
dwh.panel / dwh.features
datamart.dm_daily_actuals
datamart.dm_monthly_actuals
datamart.dm_forecasts
datamart.dm_model_metrics
```

## Quick start

```bash
# Port 5433 if local Postgres already uses 5432
export POSTGRES_HOST_PORT=5433

docker compose down -v
docker compose up -d --build

# 1) History once (sample CSV or NEMOSIS)
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_history_pipeline.py --skip-extract

  # docker compose run --rm \                                       
  # -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  # dashboard-daily python /app/scripts/run_history_pipeline.py --start 2025/01/01 --end 2025/01/08

# 2) Daily incremental later
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_daily_pipeline.py --start 2025/01/01 --end 2025/01/08

# 3) Weekly retrain
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_weekly_train.py
```

Airflow UI: http://localhost:8080 (`admin`/`admin`)  
DBeaver: `localhost` / `5433` / db **`nemdb`** / `nemuser` / `nempassword`
