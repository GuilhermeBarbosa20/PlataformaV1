-- Permite ao utilizador apagar a própria autorização de publicação (ex.: token revogado).
-- Executar no SQL Editor do Supabase se já correste 004_user_linkedin_publish_oauth.sql.

DROP POLICY IF EXISTS "user_linkedin_publish_oauth_delete_own" ON public.user_linkedin_publish_oauth;
CREATE POLICY "user_linkedin_publish_oauth_delete_own"
  ON public.user_linkedin_publish_oauth FOR DELETE
  TO authenticated
  USING (auth.uid() = user_id);

GRANT DELETE ON public.user_linkedin_publish_oauth TO authenticated;
