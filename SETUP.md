# Setup – 3 pipelines, 2 dashboards

## Commands

```bash
export POSTGRES_HOST_PORT=5433   # if 5432 busy
docker compose down -v
docker compose up -d --build
```

### Pipeline 1 – history (once)

```bash
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_history_pipeline.py --skip-extract
# or with dates:
# ... run_history_pipeline.py --start 2025/01/01 --end 2025/01/08
```

docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_history_pipeline.py --start 2025/01/01 --end 2025/01/08


### Pipeline 2 – daily (adds rows)

```bash
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_daily_pipeline.py
# or fixed day:
# ... --start 2025/01/06 --end 2025/01/07
```

docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_daily_pipeline.py --start 2025/01/06 --end 2025/01/07
```

### Pipeline 3 – weekly train

```bash
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_weekly_train.py
```

## Airflow DAGs

| DAG id | Schedule |
|--------|----------|
| `nem_history_load_train` | manual |
| `nem_daily_load` | `@daily` |
| `nem_weekly_train` | `@weekly` |

## Verify incremental daily

```sql
SELECT settlementdate::date, COUNT(*)
FROM staging.stg_price_demand
GROUP BY 1 ORDER BY 1;
```

Multiple dates = history kept.

## NETINTERCHANGE feature

Pipelines now load `NETINTERCHANGE` from DISPATCHREGIONSUM into staging → dwh → features → models.

**Existing Docker volume?** Either:

```bash
docker compose down -v   # full reset, then history pipeline
```

or apply:

```bash
docker compose exec -T postgres psql -U postgres -d nemdb < docker/postgres/migrate_add_netinterchange.sql
```

Then re-run **history** extract (not `--skip-extract`) and **weekly train**.

