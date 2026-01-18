-- Migrate geo_cache columns to bigint
ALTER TABLE geo_cache 
ALTER COLUMN master_geo_id TYPE bigint USING master_geo_id::bigint,
ALTER COLUMN populated_place_id TYPE bigint USING populated_place_id::bigint;

-- Migrate geo_candidates columns
-- Convert master_geo_id from text (csv) to bigint array
ALTER TABLE geo_candidates 
ALTER COLUMN pp_id TYPE bigint USING pp_id::bigint,
ALTER COLUMN master_geo_id TYPE bigint[] USING string_to_array(master_geo_id, ',')::bigint[];
