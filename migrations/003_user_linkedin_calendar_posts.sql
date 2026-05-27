-- Posts do calendário semanal LinkedIn por utilizador (Supabase Auth).
-- Executar no SQL Editor do projecto Supabase.

CREATE TABLE IF NOT EXISTS public.user_linkedin_calendar_posts (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  week_start date NOT NULL DEFAULT CURRENT_DATE,
  posts jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_linkedin_calendar_posts_updated
  ON public.user_linkedin_calendar_posts (updated_at DESC);

ALTER TABLE public.user_linkedin_calendar_posts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "user_linkedin_calendar_posts_select_own" ON public.user_linkedin_calendar_posts;
CREATE POLICY "user_linkedin_calendar_posts_select_own"
  ON public.user_linkedin_calendar_posts FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "user_linkedin_calendar_posts_insert_own" ON public.user_linkedin_calendar_posts;
CREATE POLICY "user_linkedin_calendar_posts_insert_own"
  ON public.user_linkedin_calendar_posts FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "user_linkedin_calendar_posts_update_own" ON public.user_linkedin_calendar_posts;
CREATE POLICY "user_linkedin_calendar_posts_update_own"
  ON public.user_linkedin_calendar_posts FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

GRANT SELECT, INSERT, UPDATE ON public.user_linkedin_calendar_posts TO authenticated;
GRANT ALL ON public.user_linkedin_calendar_posts TO service_role;
