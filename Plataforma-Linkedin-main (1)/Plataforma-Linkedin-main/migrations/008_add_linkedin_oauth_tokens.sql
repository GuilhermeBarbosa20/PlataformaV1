-- Migration: Add OAuth 2.0 columns to user_linkedin_auth table
-- These columns are needed for the official LinkedIn API integration

-- Add access token column (the OAuth 2.0 token from LinkedIn API)
ALTER TABLE public.user_linkedin_auth 
ADD COLUMN IF NOT EXISTS linkedin_access_token text;

-- Add refresh token column (optional, for token refresh)
ALTER TABLE public.user_linkedin_auth 
ADD COLUMN IF NOT EXISTS linkedin_refresh_token text;

-- Add person URN column (LinkedIn's unique identifier for the user)
ALTER TABLE public.user_linkedin_auth 
ADD COLUMN IF NOT EXISTS linkedin_person_urn text;

-- Add token expiration timestamp
ALTER TABLE public.user_linkedin_auth 
ADD COLUMN IF NOT EXISTS token_expires_at timestamptz;

-- Remove NOT NULL constraint from linkedin_li_at_cookie since we now use OAuth tokens
-- First, check if it has the constraint and alter if needed
ALTER TABLE public.user_linkedin_auth 
ALTER COLUMN linkedin_li_at_cookie DROP NOT NULL;

-- Create index on token_expires_at for efficient expiration checks
CREATE INDEX IF NOT EXISTS idx_user_linkedin_auth_token_expires 
ON public.user_linkedin_auth (token_expires_at) 
WHERE token_expires_at IS NOT NULL;
