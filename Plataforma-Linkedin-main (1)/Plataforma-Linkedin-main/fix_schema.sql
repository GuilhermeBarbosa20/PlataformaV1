-- Adiciona a coluna person_urn na tabela linkedin_community_tokens se ela não existir
ALTER TABLE linkedin_community_tokens 
ADD COLUMN IF NOT EXISTS person_urn TEXT;

-- Atualiza o comentário da tabela para refletir a mudança (opcional)
COMMENT ON COLUMN linkedin_community_tokens.person_urn IS 'URN do usuário (ex: urn:li:person:...) obtido via OpenID';
