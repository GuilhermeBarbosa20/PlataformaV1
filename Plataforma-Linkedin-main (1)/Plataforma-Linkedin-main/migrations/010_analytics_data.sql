-- Add analytics_data column to posts table to store LinkedIn metrics
-- This data is fetched from Unipile and stored locally to avoid frequent API calls

-- Add analytics_data JSONB column
ALTER TABLE posts 
ADD COLUMN IF NOT EXISTS analytics_data JSONB DEFAULT NULL;

-- Add analytics_updated_at timestamp to track when data was last refreshed
ALTER TABLE posts 
ADD COLUMN IF NOT EXISTS analytics_updated_at TIMESTAMPTZ DEFAULT NULL;

-- Create index on analytics_updated_at for efficient queries
CREATE INDEX IF NOT EXISTS idx_posts_analytics_updated_at 
ON posts (analytics_updated_at);

-- Comment on columns for documentation
COMMENT ON COLUMN posts.analytics_data IS 'LinkedIn post analytics data from Unipile API: reaction_counter, comment_counter, repost_counter, impressions_counter, analytics object';
COMMENT ON COLUMN posts.analytics_updated_at IS 'Timestamp of when analytics data was last refreshed from LinkedIn';
