-- Optional: run once if DB already exists (fresh init can also create via Python ensure_analytics_schema)
CREATE SCHEMA IF NOT EXISTS analytics;

GRANT USAGE, CREATE ON SCHEMA analytics TO nemuser;
GRANT ALL ON ALL TABLES IN SCHEMA analytics TO nemuser;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT ALL ON TABLES TO nemuser;

CREATE TABLE IF NOT EXISTS analytics.fact_hourly (
    settlementdate TIMESTAMP NOT NULL,
    regionid TEXT NOT NULL,
    rrp DOUBLE PRECISION,
    totaldemand DOUBLE PRECISION,
    netinterchange DOUBLE PRECISION,
    availablegeneration DOUBLE PRECISION,
    dispatchablegeneration DOUBLE PRECISION,
    semischedule_clearedmw DOUBLE PRECISION,
    uigf DOUBLE PRECISION,
    spare_capacity DOUBLE PRECISION,
    hour INTEGER,
    dow INTEGER,
    month INTEGER,
    year INTEGER,
    is_weekend INTEGER,
    price_regime TEXT,
    tight_system INTEGER,
    net_importer INTEGER,
    PRIMARY KEY (settlementdate, regionid)
);

CREATE TABLE IF NOT EXISTS analytics.model_results (
    id SERIAL PRIMARY KEY,
    kind TEXT,
    payload_json TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
