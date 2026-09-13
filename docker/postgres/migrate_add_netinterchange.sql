-- Run against nemdb if volume already exists (init.sql will not re-run)
ALTER TABLE staging.stg_price_demand ADD COLUMN IF NOT EXISTS netinterchange DOUBLE PRECISION;
ALTER TABLE dwh.panel ADD COLUMN IF NOT EXISTS netinterchange DOUBLE PRECISION;
ALTER TABLE dwh.features ADD COLUMN IF NOT EXISTS netinterchange DOUBLE PRECISION;
ALTER TABLE dwh.features ADD COLUMN IF NOT EXISTS netinterchange_lag_1 DOUBLE PRECISION;
ALTER TABLE datamart.dm_daily_actuals ADD COLUMN IF NOT EXISTS avg_netinterchange DOUBLE PRECISION;
ALTER TABLE datamart.dm_monthly_actuals ADD COLUMN IF NOT EXISTS avg_netinterchange DOUBLE PRECISION;
