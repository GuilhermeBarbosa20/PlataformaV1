-- Permite guardar páginas /school/ na tabela user_linkedin_profiles.
-- Executar no SQL Editor do Supabase se já aplicaste 001_user_linkedin_profiles.sql.

ALTER TABLE public.user_linkedin_profiles
  DROP CONSTRAINT IF EXISTS user_linkedin_profiles_url_check;

ALTER TABLE public.user_linkedin_profiles
  ADD CONSTRAINT user_linkedin_profiles_url_check
  CHECK (profile_url ~* '^https?://([a-z0-9-]+\.)?linkedin\.com/(in|company|school)/');
