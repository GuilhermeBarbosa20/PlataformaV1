-- Migration 002: User Photos, Vector Stores, and AI Agents
-- Run this in Supabase SQL Editor AFTER running 001_create_user_agents.sql

-- =====================================================
-- PART 1: User Photos table
-- Stores profile photos uploaded by users for AI image generation
-- =====================================================

CREATE TABLE IF NOT EXISTS public.user_photos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  storage_path text NOT NULL,                    -- Path in Supabase Storage
  public_url text,                               -- Public URL for the photo
  original_filename text,                        -- Original file name
  file_size integer,                             -- Size in bytes
  mime_type text,                                -- image/jpeg, image/png, etc.
  width integer,                                 -- Image width in pixels
  height integer,                                -- Image height in pixels
  is_primary boolean DEFAULT false,              -- Primary photo for image generation
  face_detected boolean DEFAULT true,            -- Whether a face was detected
  face_embedding jsonb DEFAULT '{}'::jsonb,      -- Optional face embedding data
  metadata jsonb DEFAULT '{}'::jsonb,            -- Additional metadata
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_user_photos_user_id ON public.user_photos (user_id);
CREATE INDEX IF NOT EXISTS idx_user_photos_primary ON public.user_photos (user_id, is_primary) WHERE is_primary = true;

-- RLS
ALTER TABLE public.user_photos ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own photos" ON public.user_photos;
DROP POLICY IF EXISTS "Users can insert own photos" ON public.user_photos;
DROP POLICY IF EXISTS "Users can update own photos" ON public.user_photos;
DROP POLICY IF EXISTS "Users can delete own photos" ON public.user_photos;
DROP POLICY IF EXISTS "Service role full access on user_photos" ON public.user_photos;

CREATE POLICY "Users can view own photos" ON public.user_photos
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own photos" ON public.user_photos
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own photos" ON public.user_photos
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own photos" ON public.user_photos
  FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Service role full access on user_photos" ON public.user_photos
  FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT ALL ON public.user_photos TO authenticated;
GRANT ALL ON public.user_photos TO service_role;


-- =====================================================
-- PART 2: Update user_agents table with AI agent fields
-- =====================================================

-- Add OpenAI Assistant fields
ALTER TABLE public.user_agents 
  ADD COLUMN IF NOT EXISTS openai_assistant_id text,
  ADD COLUMN IF NOT EXISTS openai_vector_store_id text,
  ADD COLUMN IF NOT EXISTS openai_thread_id text,
  ADD COLUMN IF NOT EXISTS agent_persona text,
  ADD COLUMN IF NOT EXISTS agent_instructions text,
  ADD COLUMN IF NOT EXISTS vector_store_file_ids jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS vector_store_created_at timestamptz,
  ADD COLUMN IF NOT EXISTS assistant_created_at timestamptz,
  ADD COLUMN IF NOT EXISTS last_agent_interaction timestamptz,
  ADD COLUMN IF NOT EXISTS onboarding_completed boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS onboarding_step text DEFAULT 'profile_url',
  ADD COLUMN IF NOT EXISTS photos_uploaded_count integer DEFAULT 0;

-- Update agent_config to be jsonb if it's text
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'user_agents' 
    AND column_name = 'agent_config' 
    AND data_type = 'text'
  ) THEN
    ALTER TABLE public.user_agents 
    ALTER COLUMN agent_config TYPE jsonb USING COALESCE(agent_config::jsonb, '{}'::jsonb);
  END IF;
END $$;


-- =====================================================
-- PART 3: User AI Conversations table
-- Stores conversation history with user's AI agent
-- =====================================================

CREATE TABLE IF NOT EXISTS public.user_ai_conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  openai_thread_id text,                         -- OpenAI Thread ID
  role text NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content text NOT NULL,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_ai_conversations_user_id ON public.user_ai_conversations (user_id);
CREATE INDEX IF NOT EXISTS idx_user_ai_conversations_thread ON public.user_ai_conversations (openai_thread_id);

ALTER TABLE public.user_ai_conversations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own conversations" ON public.user_ai_conversations;
DROP POLICY IF EXISTS "Users can insert own conversations" ON public.user_ai_conversations;
DROP POLICY IF EXISTS "Service role full access on conversations" ON public.user_ai_conversations;

CREATE POLICY "Users can view own conversations" ON public.user_ai_conversations
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own conversations" ON public.user_ai_conversations
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role full access on conversations" ON public.user_ai_conversations
  FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT ALL ON public.user_ai_conversations TO authenticated;
GRANT ALL ON public.user_ai_conversations TO service_role;


-- =====================================================
-- PART 4: Create Supabase Storage bucket for user photos
-- Note: This needs to be run separately or via Supabase Dashboard
-- =====================================================

-- Create storage bucket (run in SQL Editor)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'user-photos',
  'user-photos',
  true,
  5242880, -- 5MB limit
  ARRAY['image/jpeg', 'image/png', 'image/webp']
)
ON CONFLICT (id) DO UPDATE SET
  public = true,
  file_size_limit = 5242880,
  allowed_mime_types = ARRAY['image/jpeg', 'image/png', 'image/webp'];

-- Storage RLS policies
DROP POLICY IF EXISTS "Users can upload own photos" ON storage.objects;
DROP POLICY IF EXISTS "Users can view own photos" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete own photos" ON storage.objects;
DROP POLICY IF EXISTS "Public can view user photos" ON storage.objects;

CREATE POLICY "Users can upload own photos" ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'user-photos' 
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

CREATE POLICY "Users can view own photos" ON storage.objects
  FOR SELECT TO authenticated
  USING (
    bucket_id = 'user-photos' 
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

CREATE POLICY "Users can delete own photos" ON storage.objects
  FOR DELETE TO authenticated
  USING (
    bucket_id = 'user-photos' 
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

CREATE POLICY "Public can view user photos" ON storage.objects
  FOR SELECT TO public
  USING (bucket_id = 'user-photos');


-- =====================================================
-- VERIFICATION
-- =====================================================

SELECT 'user_photos' as table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'user_photos'
UNION ALL
SELECT 'user_agents' as table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'user_agents'
UNION ALL
SELECT 'user_ai_conversations' as table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'user_ai_conversations'
ORDER BY table_name, column_name;
