-- Apply if Postgres volume already exists
ALTER TABLE staging.stg_price_demand ADD COLUMN IF NOT EXISTS netinterchange DOUBLE PRECISION;
ALTER TABLE staging.stg_price_demand ADD COLUMN IF NOT EXISTS demandforecast DOUBLE PRECISION;

ALTER TABLE dwh.panel ADD COLUMN IF NOT EXISTS netinterchange DOUBLE PRECISION;
ALTER TABLE dwh.panel ADD COLUMN IF NOT EXISTS demandforecast DOUBLE PRECISION;
ALTER TABLE dwh.panel ADD COLUMN IF NOT EXISTS aemo_demand_error DOUBLE PRECISION;

ALTER TABLE dwh.features ADD COLUMN IF NOT EXISTS netinterchange DOUBLE PRECISION;
ALTER TABLE dwh.features ADD COLUMN IF NOT EXISTS demandforecast DOUBLE PRECISION;
ALTER TABLE dwh.features ADD COLUMN IF NOT EXISTS aemo_demand_error DOUBLE PRECISION;
ALTER TABLE dwh.features ADD COLUMN IF NOT EXISTS netinterchange_lag_1 DOUBLE PRECISION;

ALTER TABLE datamart.dm_daily_actuals ADD COLUMN IF NOT EXISTS avg_netinterchange DOUBLE PRECISION;
ALTER TABLE datamart.dm_daily_actuals ADD COLUMN IF NOT EXISTS avg_demandforecast DOUBLE PRECISION;
ALTER TABLE datamart.dm_daily_actuals ADD COLUMN IF NOT EXISTS avg_aemo_demand_error DOUBLE PRECISION;

ALTER TABLE datamart.dm_monthly_actuals ADD COLUMN IF NOT EXISTS avg_netinterchange DOUBLE PRECISION;
ALTER TABLE datamart.dm_monthly_actuals ADD COLUMN IF NOT EXISTS avg_demandforecast DOUBLE PRECISION;
ALTER TABLE datamart.dm_monthly_actuals ADD COLUMN IF NOT EXISTS avg_aemo_demand_error DOUBLE PRECISION;

ALTER TABLE datamart.dm_model_metrics ADD COLUMN IF NOT EXISTS cv_mae DOUBLE PRECISION;
ALTER TABLE datamart.dm_model_metrics ADD COLUMN IF NOT EXISTS cv_rmse DOUBLE PRECISION;
