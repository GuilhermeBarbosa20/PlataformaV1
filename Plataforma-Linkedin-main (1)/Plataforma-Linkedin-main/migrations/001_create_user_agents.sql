-- Migration: Create or update tables for first-login analysis
-- Run this in Supabase SQL Editor

-- =====================================================
-- PART 1: user_agents table (for storing analysis data)
-- =====================================================

-- Create the table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.user_agents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  linkedin_profile_url text,
  linkedin_vanity_name text,
  has_been_analyzed boolean DEFAULT false,
  themes_suggested_at timestamptz,
  scraped_posts_count integer DEFAULT 0,
  last_scraped_at timestamptz,
  scraped_posts_data jsonb DEFAULT '[]'::jsonb,
  analysis_summary jsonb DEFAULT '{}'::jsonb,
  agent_config jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_user_agents_user_id ON public.user_agents (user_id);

-- If table exists but analysis_summary is text, alter it to jsonb
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 
    FROM information_schema.columns 
    WHERE table_name = 'user_agents' 
    AND column_name = 'analysis_summary' 
    AND data_type = 'text'
  ) THEN
    ALTER TABLE public.user_agents ALTER COLUMN analysis_summary TYPE jsonb USING analysis_summary::jsonb;
  END IF;
END $$;

-- Add agent_config column if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 
    FROM information_schema.columns 
    WHERE table_name = 'user_agents' 
    AND column_name = 'agent_config'
  ) THEN
    ALTER TABLE public.user_agents ADD COLUMN agent_config jsonb DEFAULT '{}'::jsonb;
  END IF;
END $$;

-- Enable RLS
ALTER TABLE public.user_agents ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if any
DROP POLICY IF EXISTS "Users can view own agents" ON public.user_agents;
DROP POLICY IF EXISTS "Users can insert own agents" ON public.user_agents;
DROP POLICY IF EXISTS "Users can update own agents" ON public.user_agents;
DROP POLICY IF EXISTS "Service role can do all on user_agents" ON public.user_agents;

-- Create RLS policies
CREATE POLICY "Users can view own agents" ON public.user_agents
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own agents" ON public.user_agents
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own agents" ON public.user_agents
  FOR UPDATE USING (auth.uid() = user_id);

-- Allow service_role to bypass RLS (important for server-side operations)
CREATE POLICY "Service role can do all on user_agents" ON public.user_agents
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Grant permissions
GRANT ALL ON public.user_agents TO authenticated;
GRANT ALL ON public.user_agents TO service_role;


-- =====================================================
-- PART 2: user_themes table (for storing content themes)
-- =====================================================

-- Create communication_tone type if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'communication_tone') THEN
    CREATE TYPE communication_tone AS ENUM ('Leve', 'Simples', 'Técnico', 'Profissional', 'Criativo', 'Entusiasta');
  END IF;
END $$;

-- Create the table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.user_themes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  theme_name text NOT NULL,
  importance_weight integer DEFAULT 50 CHECK (importance_weight >= 0 AND importance_weight <= 100),
  communication_tone communication_tone DEFAULT 'Simples',
  description text,
  is_suggested boolean DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_user_themes_user_id ON public.user_themes (user_id);

-- Create unique index for user_id + theme_name (prevent duplicates)
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_themes_user_name 
  ON public.user_themes (user_id, theme_name);

-- Enable RLS
ALTER TABLE public.user_themes ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if any
DROP POLICY IF EXISTS "Users can view own themes" ON public.user_themes;
DROP POLICY IF EXISTS "Users can insert own themes" ON public.user_themes;
DROP POLICY IF EXISTS "Users can update own themes" ON public.user_themes;
DROP POLICY IF EXISTS "Users can delete own themes" ON public.user_themes;
DROP POLICY IF EXISTS "Service role can do all on user_themes" ON public.user_themes;

-- Create RLS policies
CREATE POLICY "Users can view own themes" ON public.user_themes
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own themes" ON public.user_themes
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own themes" ON public.user_themes
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own themes" ON public.user_themes
  FOR DELETE USING (auth.uid() = user_id);

-- Allow service_role to bypass RLS (important for server-side operations)
CREATE POLICY "Service role can do all on user_themes" ON public.user_themes
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Grant permissions
GRANT ALL ON public.user_themes TO authenticated;
GRANT ALL ON public.user_themes TO service_role;


-- =====================================================
-- VERIFICATION: Show created tables
-- =====================================================

SELECT 'user_agents' as table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'user_agents'
UNION ALL
SELECT 'user_themes' as table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'user_themes'
ORDER BY table_name, column_name;
