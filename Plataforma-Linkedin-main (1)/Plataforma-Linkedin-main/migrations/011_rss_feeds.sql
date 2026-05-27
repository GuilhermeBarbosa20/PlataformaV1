-- Migration: 011_rss_feeds.sql
-- Created: 2025-12-18
-- Description: Add user settings table and RSS feeds table for news-based post generation

-- User settings table (stores persistent user preferences)
CREATE TABLE IF NOT EXISTS user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    news_posts_enabled BOOLEAN DEFAULT false,
    auto_like_on_reply BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

-- RSS feeds table (stores user's RSS feed subscriptions)
CREATE TABLE IF NOT EXISTS rss_feeds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_fetched_at TIMESTAMPTZ DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, url)
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_user_id ON rss_feeds(user_id);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_active ON rss_feeds(user_id, is_active) WHERE is_active = true;

-- Enable RLS
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE rss_feeds ENABLE ROW LEVEL SECURITY;

-- RLS Policies for user_settings
CREATE POLICY "Users can view own settings" ON user_settings
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own settings" ON user_settings
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own settings" ON user_settings
    FOR UPDATE USING (auth.uid() = user_id);

-- RLS Policies for rss_feeds
CREATE POLICY "Users can view own feeds" ON rss_feeds
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own feeds" ON rss_feeds
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own feeds" ON rss_feeds
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own feeds" ON rss_feeds
    FOR DELETE USING (auth.uid() = user_id);
