-- 1. geo_candidates constraints
-- Ensure pp_id is unique and can be used for upsert (ON CONFLICT)
ALTER TABLE geo_candidates DROP CONSTRAINT IF EXISTS geo_candidates_pkey;
ALTER TABLE geo_candidates ADD PRIMARY KEY (pp_id);

-- 2. geo_cache constraints
-- Ensure location_query is unique and can be used for upsert
ALTER TABLE geo_cache DROP CONSTRAINT IF EXISTS geo_cache_pkey;
ALTER TABLE geo_cache ADD PRIMARY KEY (location_query);

-- 3. Optimization indexes
CREATE INDEX IF NOT EXISTS idx_geo_candidates_master_geo_id ON geo_candidates USING gin (master_geo_id);
