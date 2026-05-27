-- Migration 003: Add refinement support to posts
-- Run this in Supabase SQL Editor

-- =====================================================
-- PART 1: Add refinement columns to posts table
-- =====================================================

ALTER TABLE public.posts
  ADD COLUMN IF NOT EXISTS refinement_history jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS last_refined_at timestamptz;

-- Add comment for documentation
COMMENT ON COLUMN public.posts.refinement_history IS 'Array of refinement operations with type, instruction, previous/new content, and timestamp';
COMMENT ON COLUMN public.posts.last_refined_at IS 'Timestamp of the last refinement operation';

-- =====================================================
-- PART 2: Create index for refinement queries
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_posts_last_refined ON public.posts(last_refined_at) 
WHERE last_refined_at IS NOT NULL;

-- =====================================================
-- PART 3: Function to get refinement stats
-- =====================================================

CREATE OR REPLACE FUNCTION get_user_refinement_stats(p_user_id uuid)
RETURNS jsonb AS $$
DECLARE
  v_stats jsonb;
BEGIN
  SELECT jsonb_build_object(
    'total_refinements', COALESCE(SUM(jsonb_array_length(refinement_history)), 0),
    'text_refinements', (
      SELECT COUNT(*) FROM posts, jsonb_array_elements(refinement_history) AS r
      WHERE user_id = p_user_id AND r->>'type' = 'text'
    ),
    'image_refinements', (
      SELECT COUNT(*) FROM posts, jsonb_array_elements(refinement_history) AS r
      WHERE user_id = p_user_id AND r->>'type' = 'image'
    ),
    'posts_refined', COUNT(*) FILTER (WHERE jsonb_array_length(refinement_history) > 0),
    'last_refinement_at', MAX(last_refined_at)
  ) INTO v_stats
  FROM posts
  WHERE user_id = p_user_id;
  
  RETURN v_stats;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- VERIFICATION
-- =====================================================

SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'posts' 
  AND column_name IN ('refinement_history', 'last_refined_at');
