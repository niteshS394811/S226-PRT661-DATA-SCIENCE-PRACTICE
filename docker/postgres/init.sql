CREATE DATABASE nemdb;
CREATE USER nemuser WITH PASSWORD 'nempassword';
GRANT ALL PRIVILEGES ON DATABASE nemdb TO nemuser;

\connect nemdb

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS dwh;
CREATE SCHEMA IF NOT EXISTS datamart;

CREATE TABLE IF NOT EXISTS staging.stg_price_demand (
    settlementdate  TIMESTAMP NOT NULL,
    regionid        TEXT      NOT NULL,
    rrp             DOUBLE PRECISION,
    totaldemand     DOUBLE PRECISION,
    loaded_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (settlementdate, regionid)
);

CREATE TABLE IF NOT EXISTS dwh.panel (
    settlementdate  TIMESTAMP NOT NULL,
    regionid        TEXT      NOT NULL,
    rrp             DOUBLE PRECISION,
    totaldemand     DOUBLE PRECISION,
    hour            INTEGER,
    day             INTEGER,
    month           INTEGER,
    day_of_week     INTEGER,
    is_weekend      INTEGER,
    loaded_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (settlementdate, regionid)
);

CREATE TABLE IF NOT EXISTS dwh.features (
    settlementdate       TIMESTAMP NOT NULL,
    regionid             TEXT      NOT NULL,
    rrp                  DOUBLE PRECISION,
    totaldemand          DOUBLE PRECISION,
    hour                 INTEGER,
    day_of_week          INTEGER,
    is_weekend           INTEGER,
    demand_lag_1         DOUBLE PRECISION,
    demand_lag_12        DOUBLE PRECISION,
    demand_lag_288       DOUBLE PRECISION,
    demand_roll_mean_12  DOUBLE PRECISION,
    demand_roll_std_12   DOUBLE PRECISION,
    price_lag_1          DOUBLE PRECISION,
    price_lag_12         DOUBLE PRECISION,
    loaded_at            TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (settlementdate, regionid)
);

CREATE TABLE IF NOT EXISTS datamart.dm_daily_actuals (
    trade_date   TIMESTAMP NOT NULL,
    regionid     TEXT NOT NULL,
    avg_rrp      DOUBLE PRECISION,
    max_rrp      DOUBLE PRECISION,
    min_rrp      DOUBLE PRECISION,
    avg_demand   DOUBLE PRECISION,
    max_demand   DOUBLE PRECISION,
    min_demand   DOUBLE PRECISION,
    intervals    INTEGER,
    loaded_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, regionid)
);

CREATE TABLE IF NOT EXISTS datamart.dm_monthly_actuals (
    month_start  TIMESTAMP NOT NULL,
    regionid     TEXT NOT NULL,
    avg_rrp      DOUBLE PRECISION,
    max_rrp      DOUBLE PRECISION,
    min_rrp      DOUBLE PRECISION,
    avg_demand   DOUBLE PRECISION,
    max_demand   DOUBLE PRECISION,
    min_demand   DOUBLE PRECISION,
    intervals    INTEGER,
    loaded_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (month_start, regionid)
);

CREATE TABLE IF NOT EXISTS datamart.dm_forecasts (
    forecast_run_at  TIMESTAMP NOT NULL,
    settlementdate   TIMESTAMP NOT NULL,
    regionid         TEXT      NOT NULL,
    target           TEXT      NOT NULL,
    prediction       DOUBLE PRECISION,
    model_name       TEXT,
    horizon_steps    INTEGER,
    PRIMARY KEY (forecast_run_at, settlementdate, regionid, target)
);

CREATE TABLE IF NOT EXISTS datamart.dm_model_metrics (
    trained_at   TIMESTAMP NOT NULL,
    regionid     TEXT NOT NULL,
    target       TEXT NOT NULL,
    mae          DOUBLE PRECISION,
    rmse         DOUBLE PRECISION,
    n_train      INTEGER,
    n_test       INTEGER,
    model_name   TEXT,
    PRIMARY KEY (trained_at, regionid, target)
);

GRANT USAGE ON SCHEMA staging  TO nemuser;
GRANT USAGE ON SCHEMA dwh      TO nemuser;
GRANT USAGE ON SCHEMA datamart TO nemuser;
GRANT ALL ON SCHEMA public TO nemuser;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA staging  TO nemuser;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA dwh      TO nemuser;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA datamart TO nemuser;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public   TO nemuser;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging  GRANT ALL ON TABLES TO nemuser;
ALTER DEFAULT PRIVILEGES IN SCHEMA dwh      GRANT ALL ON TABLES TO nemuser;
ALTER DEFAULT PRIVILEGES IN SCHEMA datamart GRANT ALL ON TABLES TO nemuser;
