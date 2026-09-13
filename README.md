# PRT661 – NEM Forecasting (complete package)

Danala Group 8 · Theme 2 · Australian NEM price & demand

## Features

- Layered Postgres: staging → dwh → datamart
- 5-min models + **hourly 1d/1w** (tables created in `init.sql` on first volume)
- History and daily pipelines refresh hourly forecasts automatically
- Daily dashboard: 1 hour / 1 day / 1 week forecast views

## Clean start (no manual SQL)

```bash
export POSTGRES_HOST_PORT=5433
docker compose down -v
docker compose up -d --build

docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_history_pipeline.py \
  --start 2025/01/01 --end 2025/02/12
```

Hourly tables exist from init; history fills 5-min + hourly forecasts.

Daily:

```bash
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_daily_pipeline.py
```

- http://localhost:8501 · http://localhost:8502 · Airflow :8080
- DBeaver: localhost:5433 · nemdb · nemuser / nempassword


Detail guide in SETUP.md