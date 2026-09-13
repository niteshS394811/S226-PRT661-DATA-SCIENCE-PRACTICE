# Setup Guide — NEM Price & Demand Forecasting

**Repository:** https://github.com/niteshS394811/S226-PRT661-DATA-SCIENCE-PRACTICE  
**Unit:** S226 PRT661 Data Science Practice · Danala Group 8 · Theme 2  

This guide is to **clone the repo and run the project on a local machine**.

---

## 1. What you need (prerequisites)

### Required

| Software | Why | Download |
|----------|-----|----------|
| **Git** | Clone the repository | https://git-scm.com/downloads |
| **Docker Desktop** | Runs Postgres, pipelines, dashboards, and Airflow in containers | https://www.docker.com/products/docker-desktop/ |

**Docker Desktop must be running** before any `docker compose` command.

| Platform | Notes |
|----------|--------|
| **Windows** | Install Docker Desktop; enable WSL 2 if prompted. Use PowerShell or Git Bash. |
| **macOS** | Install Docker Desktop; grant it enough RAM (recommended **6–8 GB**). |
| **Linux** | Docker Engine + Docker Compose plugin is enough. |

### Optional (only if you want them)

| Software | Purpose |
|----------|---------|
| **DBeaver** or pgAdmin | Browse the database tables | https://dbeaver.io/ |
| **Local Python 3.11+** | Not required for the main path (everything runs inside Docker) |
| **Local PostgreSQL** | Not required — Postgres runs in Docker |

> **Important:** Do **not** put the project folder in a path that contains a colon `:` (e.g. avoid folders named like `2:09`). Docker volume mounts can fail on those paths (especially on Mac).

---

## 2. Clone the repository

```bash
git clone https://github.com/niteshS394811/S226-PRT661-DATA-SCIENCE-PRACTICE.git
cd S226-PRT661-DATA-SCIENCE-PRACTICE
```

---
open docker dektop 

## 3. Start all services (Docker)

If port **5432** is already used on your machine (local Postgres), use host port **5433**:

```bash
# macOS / Linux
export POSTGRES_HOST_PORT=5433

# Windows PowerShell
# $env:POSTGRES_HOST_PORT=5433
```

Build and start:

```bash

# delete existing volumne if already exist

docker compose down -v
docker compose up -d --build
```

First build can take **5–15 minutes** (images + dependencies).

Check containers:

```bash
docker compose ps
```

You should see Postgres healthy, dashboards, and Airflow services. Wait until Postgres shows **healthy** before running pipelines.

---


## 4. Load data and train models (history pipeline)

This downloads real AEMO data via **NEMOSIS** (needs internet), loads the warehouse, trains models, and writes forecasts.

after build complete. either run by airflow UI or by CLI.
##  Optional: Airflow DAGs

1. Open http://localhost:8080 (`admin` / `admin`).
2. Enable DAGs: `nem_history_load_train`, `nem_daily_load`, `nem_weekly_train`.
3. Trigger a run manually if needed. also run sequentially. of encounter error first time rerun(error may occur when docker still loading.)

```bash

docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_history_pipeline.py \
  --start 2025/01/01 --end 2025/02/12
```

| Flag | Meaning |
|------|---------|
| `--start` | Inclusive start date |
| `--end` | **Exclusive** end date (use the next calendar day) |

**Notes:**

- Internet is required (AEMO / NEMWEB).
- First run downloads and caches files under `src/data/raw_cache` (can take several minutes).
- A shorter window is fine for a quick demo, e.g. `--start 2025/01/01 --end 2025/01/08`.

To re-run training without re-downloading:

```bash
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_history_pipeline.py --skip-extract
```

---

## 5. Open the applications

| Service | URL | Login (if any) |
|---------|-----|----------------|
| **Daily dashboard** | http://localhost:8501 | — |
| **Weekly / model dashboard** | http://localhost:8502 | — |
| **Airflow** | http://localhost:8080 | `admin` / `admin` |

### Database (optional — DBeaver)

| Setting | Value |
|---------|--------|
| Host | `localhost` |
| Port | `5433` (or `5432` if you did not set `POSTGRES_HOST_PORT`) |
| Database | `nemdb` |
| User | `nemuser` |
| Password | `nempassword` |

Schemas: **staging**, **dwh**, **datamart**.

---

## 6. Optional: daily incremental load

After history has run at least once:

```bash
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_daily_pipeline.py
```

This loads **the next calendar day** after `MAX(settlementdate)` in the database (or use `--start` / `--end` for a fixed window).

Weekly retrain only:

```bash
docker compose run --rm \
  -e NEM_DATABASE_URL=postgresql+psycopg://nemuser:nempassword@postgres:5432/nemdb \
  dashboard-daily python /app/scripts/run_weekly_train.py
```

---

## 7. Optional: Airflow DAGs

1. Open http://localhost:8080 (`admin` / `admin`).
2. Enable DAGs: `nem_history_load_train`, `nem_daily_load`, `nem_weekly_train`.
3. Trigger a run manually if needed.

**Note:** Scheduled DAGs only run while your computer and Docker are on. For marking demos, the **CLI commands in sections 4–6** are more reliable.

---

## 8. Stop and clean up

Stop containers (keep data):

```bash
docker compose down
```

Stop and **delete all database data** (full reset):

```bash
docker compose down -v
```

Then start again with section 3 and re-run the history pipeline.

---

## 9. Common problems

| Problem | Fix |
|---------|-----|
| `port 5432 already in use` | `export POSTGRES_HOST_PORT=5433` then `docker compose up -d` |
| `invalid volume specification` (colon in path) | Move/clone the repo to a folder **without** `:` in the path |
| `NoDataToReturn` from NEMOSIS | Check internet; ensure `--end` is **after** `--start`; try a recent public date range |
| Dashboards empty | History pipeline has not finished or failed — re-run section 4 |
| Docker build fails | Update Docker Desktop; free disk space; retry `docker compose up -d --build` |
| Airflow DAG import errors | Prefer CLI pipelines; ensure `src/` is present in the repo |

---

## 10. Project structure (short)

```text
S226-PRT661-DATA-SCIENCE-PRACTICE/
├── docker-compose.yml      # All services
├── docker/postgres/init.sql
├── src/                    # extraction, cleaning, loading, transform, modelling
├── scripts/                # run_history_pipeline, run_daily_pipeline, run_weekly_train
├── dags/                   # Airflow DAGs
├── dashboard_daily.py
├── dashboard_weekly.py
└── requirements.txt
```

**Data flow:** NEMWEB → NEMOSIS → staging → dwh → datamart → Streamlit / metrics.

---

*Danala Group 8 · PRT661 · September 2026*
