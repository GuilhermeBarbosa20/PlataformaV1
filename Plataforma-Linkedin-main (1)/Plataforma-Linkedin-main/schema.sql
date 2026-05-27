-- Supabase schema for LinkedIn Autonomous Agent Platform

-- Users are managed by Supabase Auth; we reference auth.users via uuid

-- Store LinkedIn session cookies and profile info for authenticated users
create table if not exists public.user_linkedin_auth (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references auth.users(id) on delete cascade,
  linkedin_li_at_cookie text not null, -- The li_at cookie for API calls (encrypted recommended)
  linkedin_profile_url text, -- User's LinkedIn profile URL
  linkedin_profile_name text, -- User's name from LinkedIn
  linkedin_profile_photo text, -- User's profile photo URL
  cookie_expires_at timestamptz, -- When the cookie expires
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_user_linkedin_auth_user_id
  on public.user_linkedin_auth (user_id);


create table if not exists public.user_style (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  persona_prompt text, -- consolidated "Persona System Prompt" the agent uses
  writing_style_embedding vector(1536), -- embedding of the user's writing style
  image_style_embedding vector(512), -- optional aggregate embedding for images
  cloudinary_folder text, -- base folder where this user's images are stored
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_user_style_user_id
  on public.user_style (user_id);


-- Raw assets & context uploaded during onboarding

create table if not exists public.user_assets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  asset_type text not null check (asset_type in ('post_text', 'post_pdf', 'image')),
  source_url text,          -- e.g. Cloudinary URL or storage reference
  original_filename text,
  text_content text,        -- extracted text for posts/PDFs
  embedding vector(1536),   -- semantic embedding for retrieval
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_user_assets_user_id
  on public.user_assets (user_id);

create index if not exists idx_user_assets_embedding
  on public.user_assets
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);


-- Planned & published posts

create type post_status as enum ('planned', 'scheduled', 'published', 'skipped', 'failed');
create type post_approval_status as enum ('aguardar', 'aprovado', 'revisar');

create table if not exists public.posts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  scheduled_for date not null,              -- the day this post belongs to in the 7-day window
  caption text not null default 'Conteúdo em preparação',
  image_cloudinary_id text,                 -- public_id or URL
  image_selection_metadata jsonb default '{}'::jsonb,
  status post_status not null default 'planned',
  linkedIn_post_id text,                    -- external LinkedIn post identifier
  expected_metrics jsonb default '{}'::jsonb, -- model's expectation (impressions, likes, comments, etc.)
  actual_metrics jsonb default '{}'::jsonb,   -- latest snapshot from analytics
  ai_context jsonb default '{}'::jsonb,      -- snapshot of themes/objectives/tone used for generation
  ai_content jsonb default '{}'::jsonb,      -- structured content generated pela AI
  ai_revision_history jsonb default '[]'::jsonb,
  last_generated_at timestamptz,
  approval_status post_approval_status not null default 'aguardar',
  approval_notes text,
  approved_at timestamptz,
  needs_regeneration boolean default false,
  image_generation_status text default 'idle' check (image_generation_status in ('idle', 'pending', 'ready', 'failed')),
  generated_image_url text,
  generated_image_prompt text,
  generated_image_metadata jsonb default '{}'::jsonb,
  image_provider text default 'vertex-gemini',
  image_generated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_posts_user_id_scheduled_for
  on public.posts (user_id, scheduled_for);


-- Analytics snapshots per post per day, sourced from Apify

create table if not exists public.analytics (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  post_id uuid not null references public.posts(id) on delete cascade,
  snapshot_date date not null,
  raw_payload jsonb not null,          -- raw Apify output (or subset)
  impressions integer,
  likes integer,
  comments integer,
  shares integer,
  engagement_rate numeric,             -- precomputed if desired
  created_at timestamptz not null default now()
);

create unique index if not exists idx_analytics_post_snapshot
  on public.analytics (post_id, snapshot_date);


-- Strategy evolution over time

create table if not exists public.strategy_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  strategy_version integer not null,
  applied_at timestamptz not null default now(),
  insights jsonb not null,           -- structured output of analyze_performance
  guidelines jsonb not null,         -- structured output of refine_strategy
  summary text,                      -- human readable explanation
  created_by text default 'agent',
  created_at timestamptz not null default now()
);

create index if not exists idx_strategy_logs_user_id_version
  on public.strategy_logs (user_id, strategy_version desc);


-- LinkedIn SSI (Sales Navigator Insights) metrics

create table if not exists public.linkedin_ssi_metrics (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  snapshot_date date not null,
  -- Profile metrics
  profile_views integer,
  search_appearances integer,
  profile_strength_score integer,         -- 0-100
  -- Post metrics
  total_post_impressions integer,
  total_engagement_rate numeric,
  recent_posts_count integer,
  -- Network metrics
  followers_count integer,
  connection_requests integer,
  -- Raw data
  raw_payload jsonb default '{}'::jsonb,  -- full Apify response
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_linkedin_ssi_user_id_date
  on public.linkedin_ssi_metrics (user_id, snapshot_date desc);

create unique index if not exists idx_linkedin_ssi_user_snapshot
  on public.linkedin_ssi_metrics (user_id, snapshot_date);


-- User themes with importance weights and communication tones
create type communication_tone as enum ('Leve', 'Simples', 'Técnico', 'Profissional', 'Criativo', 'Entusiasta');

create table if not exists public.user_themes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  theme_name text not null,                          -- e.g. "Tecnologia", "Inovação", "Transformação Digital"
  importance_weight integer default 50 check (importance_weight >= 0 and importance_weight <= 100), -- 0-100 scale
  communication_tone communication_tone default 'Simples',
  description text,                                  -- optional description
  is_suggested boolean default false,                -- true if auto-suggested from past posts
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_user_themes_user_id
  on public.user_themes (user_id);

create unique index if not exists idx_user_themes_user_name
  on public.user_themes (user_id, theme_name);


-- User objectives (predefined goals)
create type objective_type as enum ('Aumentar seguidores', 'Aumentar visualizações', 'Aumentar relevância', 'Gerar leads', 'Construir comunidade', 'Estabelecer autoridade', 'Networking');

create table if not exists public.user_objectives (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  objective objective_type not null,
  is_active boolean default true,
  priority integer default 0,                        -- 0 = lowest, higher = more important
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_user_objectives_user_id
  on public.user_objectives (user_id);

create unique index if not exists idx_user_objectives_user_objective
  on public.user_objectives (user_id, objective);


-- User agents table - stores profile analysis status and scraped posts
create table if not exists public.user_agents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references auth.users(id) on delete cascade,
  linkedin_profile_url text,                         -- Profile URL from LinkedIn API
  linkedin_vanity_name text,                         -- LinkedIn vanity name/username
  has_been_analyzed boolean default false,           -- True if posts were scraped and analyzed
  themes_suggested_at timestamptz,                   -- When themes were auto-suggested
  scraped_posts_count integer default 0,             -- Number of posts scraped
  last_scrape_at timestamptz,                        -- Last time posts were scraped
  scraped_posts_data jsonb default '[]'::jsonb,      -- Raw scraped posts from Apify
  analysis_summary text,                             -- AI-generated summary of content style
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_user_agents_user_id
  on public.user_agents (user_id);


-- Helper view for "Strategy Health" on dashboard:
-- You can later materialize or compute this server-side based on analytics & strategy_logs.


