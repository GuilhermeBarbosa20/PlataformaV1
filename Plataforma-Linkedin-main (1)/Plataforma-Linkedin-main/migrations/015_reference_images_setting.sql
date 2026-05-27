-- Migration 015: Add reference_images_enabled to user_settings
-- This column controls whether AI image generation uses the user's reference photos for identity preservation

-- Add reference_images_enabled column (defaults to true for identity preservation)
ALTER TABLE public.user_settings
ADD COLUMN IF NOT EXISTS reference_images_enabled boolean DEFAULT true;

-- Add comment for documentation
COMMENT ON COLUMN public.user_settings.reference_images_enabled IS 'When true, AI image generation will use user reference photos for identity preservation';
