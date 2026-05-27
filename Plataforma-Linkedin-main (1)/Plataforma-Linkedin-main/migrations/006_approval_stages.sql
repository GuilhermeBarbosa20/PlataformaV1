-- Migration: Add approval stages for posts
-- This allows separate approval of text and image

-- Add new columns for staged approval
ALTER TABLE public.posts 
ADD COLUMN IF NOT EXISTS text_approved boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS text_approved_at timestamptz,
ADD COLUMN IF NOT EXISTS image_approved boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS image_approved_at timestamptz,
ADD COLUMN IF NOT EXISTS post_approved boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS post_approved_at timestamptz,
ADD COLUMN IF NOT EXISTS custom_image_url text; -- User uploaded custom image

-- Update existing approved posts to have text_approved = true
UPDATE public.posts 
SET text_approved = true, 
    text_approved_at = approved_at 
WHERE approval_status = 'aprovado';
