-- Autorização OAuth LinkedIn para publicar posts (w_member_social), uma vez por utilizador.
-- Executar no SQL Editor do projecto Supabase.

CREATE TABLE IF NOT EXISTS public.user_linkedin_publish_oauth (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  linkedin_access_token text NOT NULL,
  linkedin_refresh_token text,
  linkedin_person_urn text,
  token_expires_at timestamptz,
  authorized_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_linkedin_publish_oauth_expires
  ON public.user_linkedin_publish_oauth (token_expires_at)
  WHERE token_expires_at IS NOT NULL;

ALTER TABLE public.user_linkedin_publish_oauth ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "user_linkedin_publish_oauth_select_own" ON public.user_linkedin_publish_oauth;
CREATE POLICY "user_linkedin_publish_oauth_select_own"
  ON public.user_linkedin_publish_oauth FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "user_linkedin_publish_oauth_insert_own" ON public.user_linkedin_publish_oauth;
CREATE POLICY "user_linkedin_publish_oauth_insert_own"
  ON public.user_linkedin_publish_oauth FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "user_linkedin_publish_oauth_update_own" ON public.user_linkedin_publish_oauth;
CREATE POLICY "user_linkedin_publish_oauth_update_own"
  ON public.user_linkedin_publish_oauth FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

GRANT SELECT, INSERT, UPDATE ON public.user_linkedin_publish_oauth TO authenticated;
GRANT ALL ON public.user_linkedin_publish_oauth TO service_role;
