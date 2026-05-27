-- ============================================
-- Migration 012: LinkedIn Community App Tokens
-- Store tokens for the second LinkedIn app (Community Management)
-- Used for analytics, comments, SSI, etc.
-- ============================================

-- Create linkedin_community_tokens table
CREATE TABLE IF NOT EXISTS linkedin_community_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- OAuth tokens for Community Management app
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    scopes TEXT[] DEFAULT '{}',
    
    -- LinkedIn user info (should match the login user)
    linkedin_user_id TEXT NOT NULL,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Ensure one token per user
    CONSTRAINT unique_user_community UNIQUE (user_id)
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_linkedin_community_user_id ON linkedin_community_tokens(user_id);

-- Enable Row Level Security
ALTER TABLE linkedin_community_tokens ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view own community tokens"
    ON linkedin_community_tokens FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own community tokens"
    ON linkedin_community_tokens FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own community tokens"
    ON linkedin_community_tokens FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own community tokens"
    ON linkedin_community_tokens FOR DELETE
    USING (auth.uid() = user_id);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_linkedin_community_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_linkedin_community_updated_at
    BEFORE UPDATE ON linkedin_community_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_linkedin_community_updated_at();
