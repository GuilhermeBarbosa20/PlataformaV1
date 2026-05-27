-- =====================================================
-- Migration para adicionar comentários sugeridos
-- Execute este SQL no Supabase SQL Editor
-- =====================================================

-- 1. Adicionar coluna suggested_comment na tabela monitored_posts
ALTER TABLE monitored_posts ADD COLUMN IF NOT EXISTS suggested_comment TEXT;

-- 2. Resetar posts para reanálise (para que gerem os comentários)
-- NOTA: Isso vai reanalisar TODOS os posts - serão geradas novas chamadas de IA
UPDATE monitored_posts 
SET is_analyzed = false, 
    suggested_comment = NULL,
    ai_relevance_score = NULL,
    ai_reason = NULL,
    is_relevant = false
WHERE is_analyzed = true;

-- 3. Verificar se a coluna foi criada
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'monitored_posts' 
AND column_name = 'suggested_comment';
