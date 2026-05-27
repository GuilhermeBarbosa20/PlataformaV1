-- Migration: Create unipile_accounts table for storing Unipile-connected LinkedIn accounts
-- This table tracks the connection between users and their Unipile account IDs

CREATE TABLE IF NOT EXISTS public.unipile_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  unipile_account_id text NOT NULL UNIQUE,
  provider text NOT NULL DEFAULT 'LINKEDIN',
  status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'OK', 'CREDENTIALS', 'ERROR', 'STOPPED')),
  account_info jsonb DEFAULT '{}'::jsonb,
  connected_at timestamptz,
  disconnected_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_unipile_accounts_user_id ON public.unipile_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_unipile_accounts_status ON public.unipile_accounts(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unipile_accounts_user_provider ON public.unipile_accounts(user_id, provider);

-- Enable Row Level Security
ALTER TABLE public.unipile_accounts ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Users can read their own accounts
CREATE POLICY "Users can view own unipile accounts"
  ON public.unipile_accounts
  FOR SELECT
  USING (auth.uid() = user_id);

-- Users can insert their own accounts (through the callback)
CREATE POLICY "Users can insert own unipile accounts"
  ON public.unipile_accounts
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Users can update their own accounts
CREATE POLICY "Users can update own unipile accounts"
  ON public.unipile_accounts
  FOR UPDATE
  USING (auth.uid() = user_id);

-- Users can delete their own accounts
CREATE POLICY "Users can delete own unipile accounts"
  ON public.unipile_accounts
  FOR DELETE
  USING (auth.uid() = user_id);

-- Service role can do everything (for webhooks and server-side operations)
CREATE POLICY "Service role has full access to unipile accounts"
  ON public.unipile_accounts
  FOR ALL
  USING (auth.role() = 'service_role');

-- Comment on table
COMMENT ON TABLE public.unipile_accounts IS 'Stores Unipile-connected accounts for LinkedIn integration';
COMMENT ON COLUMN public.unipile_accounts.unipile_account_id IS 'The unique account ID from Unipile';
COMMENT ON COLUMN public.unipile_accounts.provider IS 'The provider type (e.g., LINKEDIN, WHATSAPP)';
COMMENT ON COLUMN public.unipile_accounts.status IS 'Connection status: PENDING, OK, CREDENTIALS (needs re-auth), ERROR, STOPPED';
COMMENT ON COLUMN public.unipile_accounts.account_info IS 'JSON blob with full account details from Unipile';
