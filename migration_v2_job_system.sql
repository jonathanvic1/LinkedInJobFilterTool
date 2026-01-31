-- 1. Create search_logs table
CREATE TABLE IF NOT EXISTS search_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    history_id UUID NOT NULL REFERENCES search_history(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    level TEXT DEFAULT 'info',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Add history_id to dismissed_jobs if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='dismissed_jobs' AND column_name='history_id') THEN
        ALTER TABLE dismissed_jobs ADD COLUMN history_id UUID REFERENCES search_history(id) ON DELETE SET NULL;
    END IF;
END $$;

-- 3. Enable RLS for search_logs
ALTER TABLE search_logs ENABLE ROW LEVEL SECURITY;

-- 4. Create RLS Policy for search_logs
DROP POLICY IF EXISTS "Users can view own search logs" ON search_logs;
CREATE POLICY "Users can view own search logs" ON search_logs
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM search_history 
            WHERE search_history.id = search_logs.history_id 
            AND search_history.user_id = auth.uid()
        )
    );

-- 5. Add indices for better query performance
CREATE INDEX IF NOT EXISTS idx_search_logs_history_id ON search_logs(history_id);
CREATE INDEX IF NOT EXISTS idx_dismissed_jobs_history_id ON dismissed_jobs(history_id);
