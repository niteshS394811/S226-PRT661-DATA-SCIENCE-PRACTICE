# S226 PRT661 — NEM (2 dashboards only)

## Dashboards

| Port | App | File |
|------|-----|------|
| **8501** | Operational / Daily | `dashboard_daily.py` |
| **8502** | Strategic Insights | `dashboard_insights.py` |

## Pipelines kept

| Script | Role |
|--------|------|
| `scripts/run_strategic_history.py` | **2024–2025** full load + insights |
| `scripts/run_daily_pipeline.py` | **Operational = Daily** incremental (`max+1` or `--seed-ops-week`) |
| `scripts/run_analysis_pipeline.py` | Rebuild insights from same extract if needed |

## Quick start

```bash
export POSTGRES_HOST_PORT=5433
docker compose up -d --build

docker compose exec -T postgres psql -U postgres -d nemdb \
  < docker/postgres/migrate_unified_columns.sql

# Strategic 2024–2025
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_strategic_history.py

# full extract may take time. for short extract 
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_strategic_history.py \
  --start 2025/01/01 --end 2025/01/08
  
#skip extract
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  -v "$(pwd)/src:/app/src" \
  -v "$(pwd)/scripts:/app/scripts" \
  dashboard-daily python -c "
from src.extraction import extract
df = extract('2024/01/01 00:00:00', '2026/01/01 00:00:00')
print('ROWS', len(df))
"

docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_strategic_history.py --skip-extract


# Next days
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_daily_pipeline.py
```

- http://localhost:8501 — Operational / Daily  
- http://localhost:8502 — Strategic  

See `docs/REMOVED.md` for files deleted under this plan.
