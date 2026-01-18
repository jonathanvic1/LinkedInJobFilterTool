-- Remove the redundant place_name column
ALTER TABLE geo_cache DROP COLUMN IF EXISTS place_name;

-- Standardize existing queries to Title Case
UPDATE geo_cache SET location_query = initcap(location_query);
