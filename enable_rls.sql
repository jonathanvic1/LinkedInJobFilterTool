-- Security Script for LinkedIn Job Filter Tool
-- Copy and Paste this into your Supabase SQL Editor and click 'Run'.

-- 1. Enable RLS on all tables
ALTER TABLE blocklists ENABLE ROW LEVEL SECURITY;
ALTER TABLE dismissed_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE geo_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE geo_candidates ENABLE ROW LEVEL SECURITY;

-- 2. Create policies for Authenticated Users (Logged-in users)
-- This ensures that only you can access your data once logged in.

-- BLOCKLISTS
DROP POLICY IF EXISTS "Allow authenticated selects on blocklists" ON blocklists;
CREATE POLICY "Allow authenticated selects on blocklists" ON blocklists FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "Allow authenticated all on blocklists" ON blocklists;
CREATE POLICY "Allow authenticated all on blocklists" ON blocklists FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- DISMISSED JOBS
DROP POLICY IF EXISTS "Allow authenticated selects on dismissed_jobs" ON dismissed_jobs;
CREATE POLICY "Allow authenticated selects on dismissed_jobs" ON dismissed_jobs FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "Allow authenticated all on dismissed_jobs" ON dismissed_jobs;
CREATE POLICY "Allow authenticated all on dismissed_jobs" ON dismissed_jobs FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- GEO CACHE
DROP POLICY IF EXISTS "Allow authenticated selects on geo_cache" ON geo_cache;
CREATE POLICY "Allow authenticated selects on geo_cache" ON geo_cache FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "Allow authenticated all on geo_cache" ON geo_cache;
CREATE POLICY "Allow authenticated all on geo_cache" ON geo_cache FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- GEO CANDIDATES
DROP POLICY IF EXISTS "Allow authenticated selects on geo_candidates" ON geo_candidates;
CREATE POLICY "Allow authenticated selects on geo_candidates" ON geo_candidates FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "Allow authenticated all on geo_candidates" ON geo_candidates;
CREATE POLICY "Allow authenticated all on geo_candidates" ON geo_candidates FOR ALL TO authenticated USING (true) WITH CHECK (true);
