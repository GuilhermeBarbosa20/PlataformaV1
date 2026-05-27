-- Migration: Add LinkedIn OAuth tokens and publishing support
-- This allows storing LinkedIn access tokens for API publishing

-- Add new columns for LinkedIn OAuth
ALTER TABLE public.user_linkedin_auth 
ADD COLUMN IF NOT EXISTS linkedin_access_token text,
ADD COLUMN IF NOT EXISTS linkedin_person_urn text,
ADD COLUMN IF NOT EXISTS token_expires_at timestamptz;

-- Add publishing columns to posts
ALTER TABLE public.posts
ADD COLUMN IF NOT EXISTS linkedin_post_urn text,
ADD COLUMN IF NOT EXISTS published_at timestamptz,
ADD COLUMN IF NOT EXISTS publish_error text;

-- Index for finding published posts
CREATE INDEX IF NOT EXISTS idx_posts_linkedin_post_urn 
ON public.posts (linkedin_post_urn) 
WHERE linkedin_post_urn IS NOT NULL;

-- Index for finding posts by status
CREATE INDEX IF NOT EXISTS idx_posts_status 
ON public.posts (status);

-- Update status enum if needed (if column doesn't exist, skip)
-- ALTER TYPE post_status ADD VALUE IF NOT EXISTS 'published';
