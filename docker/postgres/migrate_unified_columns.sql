-- Run once on existing databases (fresh init.sql already has these columns)
ALTER TABLE staging.stg_price_demand ADD COLUMN IF NOT EXISTS availablegeneration DOUBLE PRECISION;
ALTER TABLE staging.stg_price_demand ADD COLUMN IF NOT EXISTS dispatchablegeneration DOUBLE PRECISION;
ALTER TABLE staging.stg_price_demand ADD COLUMN IF NOT EXISTS initialsupply DOUBLE PRECISION;
ALTER TABLE staging.stg_price_demand ADD COLUMN IF NOT EXISTS clearedsupply DOUBLE PRECISION;
ALTER TABLE staging.stg_price_demand ADD COLUMN IF NOT EXISTS totalintermittentgeneration DOUBLE PRECISION;
ALTER TABLE staging.stg_price_demand ADD COLUMN IF NOT EXISTS uigf DOUBLE PRECISION;
ALTER TABLE staging.stg_price_demand ADD COLUMN IF NOT EXISTS semischedule_clearedmw DOUBLE PRECISION;
ALTER TABLE staging.stg_price_demand ADD COLUMN IF NOT EXISTS spare_capacity DOUBLE PRECISION;
