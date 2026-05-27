-- Migration: 013_trend_monitoring.sql
-- Created: 2025-12-23
-- Description: Add trend monitoring feature for tracking LinkedIn profiles

-- Add trends_monitoring_enabled to user_settings
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS trends_monitoring_enabled BOOLEAN DEFAULT false;

-- Monitored profiles table (max 10 per user enforced at app level)
CREATE TABLE IF NOT EXISTS monitored_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    profile_url TEXT NOT NULL,
    profile_name TEXT,
    profile_vanity_name TEXT,
    profile_avatar_url TEXT,
    last_fetched_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, profile_url)
);

-- Fetched posts from monitored profiles
CREATE TABLE IF NOT EXISTS monitored_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES monitored_profiles(id) ON DELETE CASCADE,
    linkedin_post_urn TEXT,
    post_url TEXT,
    post_content TEXT,
    author_name TEXT,
    author_avatar_url TEXT,
    posted_at TIMESTAMPTZ,
    likes_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    ai_relevance_score FLOAT,
    ai_reason TEXT,
    suggested_comment TEXT,                         -- AI-generated comment suggestion
    is_relevant BOOLEAN DEFAULT false,
    is_analyzed BOOLEAN DEFAULT false,
    user_action TEXT, -- 'liked', 'commented', 'reposted', 'dismissed', NULL
    user_action_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, linkedin_post_urn)
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_monitored_profiles_user_id ON monitored_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_monitored_posts_user_id ON monitored_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_monitored_posts_profile_id ON monitored_posts(profile_id);
CREATE INDEX IF NOT EXISTS idx_monitored_posts_relevant ON monitored_posts(user_id, is_relevant) WHERE is_relevant = true;
CREATE INDEX IF NOT EXISTS idx_monitored_posts_posted_at ON monitored_posts(posted_at DESC);

-- Enable RLS
ALTER TABLE monitored_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitored_posts ENABLE ROW LEVEL SECURITY;

-- RLS Policies for monitored_profiles
CREATE POLICY "Users can view own monitored profiles" ON monitored_profiles
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own monitored profiles" ON monitored_profiles
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own monitored profiles" ON monitored_profiles
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own monitored profiles" ON monitored_profiles
    FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for monitored_posts
CREATE POLICY "Users can view own monitored posts" ON monitored_posts
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own monitored posts" ON monitored_posts
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own monitored posts" ON monitored_posts
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own monitored posts" ON monitored_posts
    FOR DELETE USING (auth.uid() = user_id);
