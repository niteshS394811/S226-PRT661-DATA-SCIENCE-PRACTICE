-- Hourly aggregated forecasts (additive — does not change 5-min tables)

CREATE TABLE IF NOT EXISTS datamart.dm_hourly_model_metrics (
    trained_at   TIMESTAMP NOT NULL,
    regionid     TEXT NOT NULL,
    target       TEXT NOT NULL,
    model_name   TEXT NOT NULL,
    grain        TEXT NOT NULL DEFAULT 'hourly',
    mae          DOUBLE PRECISION,
    rmse         DOUBLE PRECISION,
    n_train      INTEGER,
    n_test       INTEGER,
    PRIMARY KEY (trained_at, regionid, target, model_name)
);

CREATE TABLE IF NOT EXISTS datamart.dm_hourly_forecasts (
    forecast_run_at  TIMESTAMP NOT NULL,
    forecast_hour    TIMESTAMP NOT NULL,
    regionid         TEXT      NOT NULL,
    target           TEXT      NOT NULL,
    prediction       DOUBLE PRECISION,
    model_name       TEXT,
    horizon_hours    INTEGER,
    horizon_label    TEXT,   -- '1d' or '1w'
    grain            TEXT DEFAULT 'hourly',
    PRIMARY KEY (forecast_run_at, forecast_hour, regionid, target, horizon_label)
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA datamart TO nemuser;
