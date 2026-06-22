-- Perfis LinkedIn que o utilizador segue (para comentários / engagement).
-- Executar no SQL Editor do projecto Supabase.

CREATE TABLE IF NOT EXISTS public.user_linkedin_followed_profiles (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  profiles jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_linkedin_followed_profiles_updated
  ON public.user_linkedin_followed_profiles (updated_at DESC);

ALTER TABLE public.user_linkedin_followed_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "user_linkedin_followed_profiles_select_own" ON public.user_linkedin_followed_profiles;
CREATE POLICY "user_linkedin_followed_profiles_select_own"
  ON public.user_linkedin_followed_profiles FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "user_linkedin_followed_profiles_insert_own" ON public.user_linkedin_followed_profiles;
CREATE POLICY "user_linkedin_followed_profiles_insert_own"
  ON public.user_linkedin_followed_profiles FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "user_linkedin_followed_profiles_update_own" ON public.user_linkedin_followed_profiles;
CREATE POLICY "user_linkedin_followed_profiles_update_own"
  ON public.user_linkedin_followed_profiles FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

GRANT SELECT, INSERT, UPDATE ON public.user_linkedin_followed_profiles TO authenticated;
GRANT ALL ON public.user_linkedin_followed_profiles TO service_role;
