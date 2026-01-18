-- Fix existing incorrect cache entries
-- Regional locations (like Ontario) should NOT have a populated_place_id
UPDATE geo_cache 
SET populated_place_id = NULL 
WHERE populated_place_id = master_geo_id;
