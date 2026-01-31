-- Enable UUID extension if not already enabled
create extension if not exists "uuid-ossp";

-- Saved search configurations
CREATE TABLE IF NOT EXISTS saved_searches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    name TEXT NOT NULL,
    keywords TEXT,
    location TEXT,
    time_range TEXT DEFAULT 'all',
    job_limit INTEGER DEFAULT 25,
    easy_apply BOOLEAN DEFAULT false,
    relevant BOOLEAN DEFAULT false,
    workplace_type INTEGER[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Search execution history
CREATE TABLE IF NOT EXISTS search_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    keywords TEXT,
    location TEXT,
    time_range TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    total_found INTEGER DEFAULT 0,
    total_dismissed INTEGER DEFAULT 0,
    total_skipped INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running'
);

-- Enable RLS
ALTER TABLE saved_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_history ENABLE ROW LEVEL SECURITY;

-- Create policies (drop if exists first to avoid errors on re-run)
DROP POLICY IF EXISTS "Users can manage own searches" ON saved_searches;
CREATE POLICY "Users can manage own searches" ON saved_searches
    FOR ALL USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own history" ON search_history;
CREATE POLICY "Users can view own history" ON search_history
    FOR ALL USING (auth.uid() = user_id);
