Your new README is much closer to the **actual system** (2 dashboards + dual pipelines). Below is a tightened version you can paste as `README.md` — clearer for markers and aligned with the strict mark feedback.

---

```markdown
# S226 PRT661 — NEM Forecasting (2 dashboards)

**Danala Group 8 · Theme 2**  
Australian NEM price & demand — extract → warehouse → models → dashboards

## Dashboards

| Port | App | File |
|------|-----|------|
| **8501** | Operational / Daily | `dashboard_daily.py` |
| **8502** | Strategic Insights | `dashboard_insights.py` |

## Pipelines

| Script | Role |
|--------|------|
| `scripts/run_strategic_history.py` | Strategic full load (e.g. 2024–2025) + insights |
| `scripts/run_daily_pipeline.py` | Operational daily incremental (`max(date)+1`, or `--seed-ops-week`) |
| `scripts/run_analysis_pipeline.py` | Rebuild insights from existing extract if needed |

Airflow DAGs (optional): `nem_strategic_history` · `nem_operational_daily`

## Architecture (short)

AEMO → NEMOSIS extract → clean → `staging` → `dwh` (panel/features) → `datamart` / analytics → Streamlit UIs

## Prerequisites

- Docker Desktop
- Ports free: **5433** (Postgres host), **8501**, **8502** (and **8080** if using Airflow)

## Quick start

```bash
docker compose down -v #if want to delete previous volume

export POSTGRES_HOST_PORT=5433
docker compose up -d --build

# One-time column migration (if needed on existing volume)
docker compose exec -T postgres psql -U postgres -d nemdb \
  < docker/postgres/migrate_unified_columns.sql
```
run from apache airflow pipeline
http://localhost:8080

 or
CLI
### 1) Strategic history (full window — first run)

```bash
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_strategic_history.py
```

Long extract? Use NEMOSIS cache, then:

```bash
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  -v "$(pwd)/src:/app/src" \
  dashboard-daily python /app/scripts/run_strategic_history.py --skip-extract
```

### 2) Operational / daily (next calendar day only)

```bash
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_daily_pipeline.py
```

### 3) Open dashboards

- Operational / Daily: http://localhost:8501  
- Strategic Insights: http://localhost:8502  

DBeaver (optional): `localhost:5433` · database `nemdb` · user `nemuser` / `nempassword`

## Notes 

- **Strategic** = multi-year full refresh + analytics/insights  
- **Operational = Daily** = incremental upsert only (`max(settlementdate)+1`)  
- Forecast horizon is **short-term** (ops-focused), not multi-day 1d/1w hourly products  
- Stack runs on **local Docker**; Airflow schedules only while the host is on  


## Repo

https://github.com/niteshS394811/S226-PRT661-DATA-SCIENCE-PRACTICE
```
