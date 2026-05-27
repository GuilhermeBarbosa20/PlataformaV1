-- =====================================================
-- Migration 014: Custom Prompts
-- Allows users to customize AI generation prompts
-- =====================================================

-- Create user_custom_prompts table
CREATE TABLE IF NOT EXISTS user_custom_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    prompt_type TEXT NOT NULL,
    prompt_content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, prompt_type)
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_custom_prompts_user_type 
    ON user_custom_prompts(user_id, prompt_type);

-- Enable RLS
ALTER TABLE user_custom_prompts ENABLE ROW LEVEL SECURITY;

-- RLS Policies
DROP POLICY IF EXISTS "Users can view own prompts" ON user_custom_prompts;
CREATE POLICY "Users can view own prompts" ON user_custom_prompts
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own prompts" ON user_custom_prompts;
CREATE POLICY "Users can insert own prompts" ON user_custom_prompts
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own prompts" ON user_custom_prompts;
CREATE POLICY "Users can update own prompts" ON user_custom_prompts
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own prompts" ON user_custom_prompts;
CREATE POLICY "Users can delete own prompts" ON user_custom_prompts
    FOR DELETE USING (auth.uid() = user_id);

-- Add prompts_customization_enabled to user_settings
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS prompts_customization_enabled BOOLEAN DEFAULT false;

-- Grant permissions
GRANT ALL ON user_custom_prompts TO authenticated;
GRANT ALL ON user_custom_prompts TO service_role;
