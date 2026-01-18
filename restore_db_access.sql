-- EMERGENCY RECOVERY: Restore Database Access & Cleanup
-- Run this in the Supabase SQL Editor

-- 1. CLEANUP LEGACY POLICIES (Fixes "column name does not exist")
-- We drop EVERY policy that might be using the old schema.
DROP POLICY IF EXISTS "Allow authenticated selects on blocklists" ON blocklists;
DROP POLICY IF EXISTS "Allow authenticated all on blocklists" ON blocklists;
DROP POLICY IF EXISTS "Allow only Jonathan access" ON blocklists;
DROP POLICY IF EXISTS "blocklists_policy" ON blocklists;
DROP POLICY IF EXISTS "Allow authenticated selects on dismissed_jobs" ON dismissed_jobs;
DROP POLICY IF EXISTS "Allow authenticated all on dismissed_jobs" ON dismissed_jobs;
DROP POLICY IF EXISTS "Allow authenticated selects on geo_cache" ON geo_cache;
DROP POLICY IF EXISTS "Allow authenticated all on geo_cache" ON geo_cache;

-- 2. SETUP CLEAN POLICIES
-- These allow Authenticated Users (you) full access. 
-- Note: Your server-side Python code should use the SERVICE_ROLE key to bypass these and work 100% of the time.

-- Blocklists
CREATE POLICY "Allow authenticated selects on blocklists" ON blocklists FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow authenticated all on blocklists" ON blocklists FOR ALL TO authenticated USING (auth.jwt() ->> 'email' = 'jonathanvictormascarenhas@gmail.com') WITH CHECK (auth.jwt() ->> 'email' = 'jonathanvictormascarenhas@gmail.com');

-- Dismissed Jobs (History)
CREATE POLICY "Allow authenticated selects on dismissed_jobs" ON dismissed_jobs FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow authenticated all on dismissed_jobs" ON dismissed_jobs FOR ALL TO authenticated USING (auth.jwt() ->> 'email' = 'jonathanvictormascarenhas@gmail.com') WITH CHECK (auth.jwt() ->> 'email' = 'jonathanvictormascarenhas@gmail.com');

-- Geo Cache
CREATE POLICY "Allow authenticated selects on geo_cache" ON geo_cache FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow authenticated all on geo_cache" ON geo_cache FOR ALL TO authenticated USING (auth.jwt() ->> 'email' = 'jonathanvictormascarenhas@gmail.com') WITH CHECK (auth.jwt() ->> 'email' = 'jonathanvictormascarenhas@gmail.com');

-- Geo Candidates
ALTER TABLE geo_candidates ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow authenticated selects on geo_candidates" ON geo_candidates;
CREATE POLICY "Allow authenticated selects on geo_candidates" ON geo_candidates FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "Allow authenticated all on geo_candidates" ON geo_candidates;
CREATE POLICY "Allow authenticated all on geo_candidates" ON geo_candidates FOR ALL TO authenticated USING (true) WITH CHECK (true);
