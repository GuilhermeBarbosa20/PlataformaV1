-- Perfil LinkedIn público associado ao utilizador Supabase Auth.
-- Executar no SQL Editor do projecto Supabase (PlataformaV1).

CREATE TABLE IF NOT EXISTS public.user_linkedin_profiles (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  profile_url text NOT NULL,
  profile_slug text,
  display_name text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT user_linkedin_profiles_url_check
    CHECK (profile_url ~* '^https?://([a-z0-9-]+\.)?linkedin\.com/(in|company)/')
);

CREATE INDEX IF NOT EXISTS idx_user_linkedin_profiles_slug
  ON public.user_linkedin_profiles (profile_slug);

ALTER TABLE public.user_linkedin_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "user_linkedin_profiles_select_own" ON public.user_linkedin_profiles;
CREATE POLICY "user_linkedin_profiles_select_own"
  ON public.user_linkedin_profiles FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "user_linkedin_profiles_insert_own" ON public.user_linkedin_profiles;
CREATE POLICY "user_linkedin_profiles_insert_own"
  ON public.user_linkedin_profiles FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "user_linkedin_profiles_update_own" ON public.user_linkedin_profiles;
CREATE POLICY "user_linkedin_profiles_update_own"
  ON public.user_linkedin_profiles FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

GRANT SELECT, INSERT, UPDATE ON public.user_linkedin_profiles TO authenticated;
GRANT ALL ON public.user_linkedin_profiles TO service_role;
