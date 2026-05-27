-- Migration: Add generated_images table for image storage tracking
-- Run this in Supabase SQL Editor

-- Generated images table to track all images created by users
CREATE TABLE IF NOT EXISTS generated_images (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  post_id UUID REFERENCES posts(id) ON DELETE SET NULL,
  storage_path TEXT NOT NULL,
  public_url TEXT NOT NULL,
  prompt TEXT,
  theme TEXT,
  style TEXT,
  aspect_ratio TEXT DEFAULT '1:1',
  model_used TEXT,
  is_personalized BOOLEAN DEFAULT FALSE,
  generation_params JSONB DEFAULT '{}',
  performance_metrics JSONB DEFAULT '{}',
  status TEXT DEFAULT 'generated' CHECK (status IN ('generating', 'generated', 'failed', 'deleted')),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add generated_image_id column to posts table if it doesn't exist
DO $$ 
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'posts' AND column_name = 'generated_image_id'
  ) THEN
    ALTER TABLE posts ADD COLUMN generated_image_id UUID REFERENCES generated_images(id) ON DELETE SET NULL;
  END IF;
END $$;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_generated_images_user ON generated_images(user_id);
CREATE INDEX IF NOT EXISTS idx_generated_images_post ON generated_images(post_id);
CREATE INDEX IF NOT EXISTS idx_generated_images_created ON generated_images(created_at);
CREATE INDEX IF NOT EXISTS idx_generated_images_status ON generated_images(status);
CREATE INDEX IF NOT EXISTS idx_posts_generated_image ON posts(generated_image_id);

-- RLS Policies
ALTER TABLE generated_images ENABLE ROW LEVEL SECURITY;

-- Users can view their own images
CREATE POLICY "Users can view own images" ON generated_images
  FOR SELECT USING (auth.uid() = user_id);

-- Users can insert their own images
CREATE POLICY "Users can insert own images" ON generated_images
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Users can update their own images
CREATE POLICY "Users can update own images" ON generated_images
  FOR UPDATE USING (auth.uid() = user_id);

-- Users can delete their own images
CREATE POLICY "Users can delete own images" ON generated_images
  FOR DELETE USING (auth.uid() = user_id);

-- ================================================
-- STORAGE BUCKET SETUP
-- ================================================
-- Run these commands SEPARATELY in Supabase Dashboard:
-- 
-- 1. Go to Storage section in Supabase Dashboard
-- 2. Click "New bucket"
-- 3. Name: generated-images
-- 4. Check "Public bucket" option
-- 5. Click "Create bucket"
--
-- OR use SQL (requires storage schema permissions):
-- 
-- INSERT INTO storage.buckets (id, name, public)
-- VALUES ('generated-images', 'generated-images', true)
-- ON CONFLICT (id) DO NOTHING;
--
-- Storage Policies (run in SQL editor):

-- Allow authenticated users to upload to their own folder
CREATE POLICY "Users can upload own images" ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'generated-images' AND 
    (storage.foldername(name))[1] = auth.uid()::text
  );

-- Allow authenticated users to update their own images
CREATE POLICY "Users can update own images" ON storage.objects
  FOR UPDATE TO authenticated
  USING (
    bucket_id = 'generated-images' AND 
    (storage.foldername(name))[1] = auth.uid()::text
  );

-- Allow authenticated users to delete their own images
CREATE POLICY "Users can delete own images" ON storage.objects
  FOR DELETE TO authenticated
  USING (
    bucket_id = 'generated-images' AND 
    (storage.foldername(name))[1] = auth.uid()::text
  );

-- Allow public read access (since bucket is public)
CREATE POLICY "Public read access" ON storage.objects
  FOR SELECT TO public
  USING (bucket_id = 'generated-images');
