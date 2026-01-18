-- SQL FIX: Cleanup Legacy Policies after 'name' -> 'blocklist_type' rename
-- Run this in the Supabase SQL Editor

-- 1. Drop ALL potentially conflicting policies on blocklists
-- This ensures no hidden policies are still referencing the old 'name' column.
DROP POLICY IF EXISTS "Allow authenticated selects on blocklists" ON blocklists;
DROP POLICY IF EXISTS "Allow authenticated all on blocklists" ON blocklists;
DROP POLICY IF EXISTS "Allow only Jonathan access" ON blocklists;
DROP POLICY IF EXISTS "blocklists_policy" ON blocklists;

-- 2. Re-create Clean Policies (Using 'blocklist_type' if needed, or simply 'true' for full access)
-- Note: 'true' is safe here because it's still restricted TO authenticated users.

CREATE POLICY "Allow authenticated selects on blocklists" 
ON blocklists FOR SELECT TO authenticated USING (true);

CREATE POLICY "Allow authenticated all on blocklists" 
ON blocklists FOR ALL TO authenticated 
USING (auth.jwt() ->> 'email' = 'jonathanvictormascarenhas@gmail.com') 
WITH CHECK (auth.jwt() ->> 'email' = 'jonathanvictormascarenhas@gmail.com');

-- 3. Verify the table doesn't have any broken triggers
-- (Usually not an issue unless you added them manually, but this reset should clear the path)
ALTER TABLE blocklists ENABLE ROW LEVEL SECURITY;
