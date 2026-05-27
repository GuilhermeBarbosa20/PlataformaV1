# 🚀 Guia de Deploy em VM - LinkedIn Content Platform

Este guia cobre o deploy completo da plataforma em uma VM "pelada" (Ubuntu/Debian).

---

## 📋 Pré-requisitos da VM

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| RAM | 2GB | 4GB |
| CPU | 2 vCPU | 4 vCPU |
| Disco | 20GB | 40GB |
| SO | Ubuntu 22.04+ / Debian 12+ | Ubuntu 24.04 LTS |

---

## 🔧 1. Preparar a VM

```bash
# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo apt install docker-compose-plugin -y

# Relogar para aplicar grupo docker
exit
# Conecte novamente na VM
```

---

## 🔑 2. Credenciais Necessárias

### Obrigatórias

| Variável | Onde obter |
|----------|------------|
| `NEXT_PUBLIC_SUPABASE_URL` | [Supabase Dashboard](https://supabase.com/dashboard) → Project Settings → API |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Project Settings → API → anon public |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API → service_role |
| `OPENAI_API_KEY` | [OpenAI Platform](https://platform.openai.com/api-keys) |
| `GOOGLE_CREDENTIALS_BASE64` | GCP Console → Service Account JSON → Base64 encode |
| `VERTEX_PROJECT_ID` | GCP Console → Project ID |
| `APIFY_TOKEN` | [Apify Console](https://console.apify.com/account/integrations) |
| `LINKEDIN_CLIENT_ID` | [LinkedIn Developers](https://www.linkedin.com/developers/apps) |
| `LINKEDIN_CLIENT_SECRET` | LinkedIn Developers → Your App → Auth |
| `NEXT_PUBLIC_BASE_URL` | URL do seu domínio (ex: `https://linkedin.seudominio.com`) |

### Converter Google Credentials para Base64

```bash
# Linux/Mac:
base64 -w 0 seu-arquivo-service-account.json

# Windows PowerShell:
[Convert]::ToBase64String([IO.File]::ReadAllBytes("seu-arquivo-service-account.json"))

# Copie a saída inteira (sem quebras de linha)
```

---

## 📁 3. Subir o Código para a VM

```bash
# Na sua máquina local, na pasta do projeto

# Opção 1: Git (recomendado)
git remote add vm ssh://user@sua-vm-ip:/home/user/linkedin-platform
git push vm main

# Opção 2: SCP
scp -r . user@sua-vm-ip:/home/user/linkedin-platform

# Opção 3: rsync (melhor para atualizações)
rsync -avz --exclude 'node_modules' --exclude '.next' . user@sua-vm-ip:/home/user/linkedin-platform
```

---

## ⚙️ 4. Configurar Variáveis de Ambiente

```bash
cd /home/user/linkedin-platform

# Criar arquivo .env
cp .env.example .env
nano .env

# Preencha TODAS as variáveis listadas na seção 2
```

**Exemplo de `.env` preenchido:**
```env
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://abc123.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# OpenAI
OPENAI_API_KEY=sk-proj-xxxxx

# Google Cloud / Vertex AI
GOOGLE_CREDENTIALS_BASE64=ewogICJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIs...
VERTEX_PROJECT_ID=seu-projeto-gcp
VERTEX_LOCATION=us-central1

# Apify
APIFY_TOKEN=apify_api_xxxxx

# LinkedIn OAuth
LINKEDIN_CLIENT_ID=77xxxxx
LINKEDIN_CLIENT_SECRET=AbCdEfGh...

# Base URL (seu domínio)
NEXT_PUBLIC_BASE_URL=https://linkedin.seudominio.com
```

---

## 🐳 5. Deploy com Docker

### Opção A: Apenas a Aplicação (porta 3000)
```bash
# Build e start
docker compose up -d app

# Ver logs
docker compose logs -f app

# Verificar saúde
curl http://localhost:3000/api/health
```

### Opção B: Com Nginx (portas 80/443)
```bash
# Criar pasta para certificados SSL (se usar HTTPS)
mkdir -p nginx/ssl

# Iniciar com Nginx
docker compose --profile with-nginx up -d

# Ver logs
docker compose logs -f
```

---

## 🔐 6. Configurar SSL (HTTPS)

### Opção 1: Let's Encrypt com Certbot
```bash
# Instalar Certbot na VM (fora do Docker)
sudo apt install certbot -y

# Parar o Nginx temporariamente
docker compose stop nginx

# Gerar certificado
sudo certbot certonly --standalone -d linkedin.seudominio.com

# Copiar certificados para pasta do projeto
sudo cp /etc/letsencrypt/live/linkedin.seudominio.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/linkedin.seudominio.com/privkey.pem nginx/ssl/
sudo chmod 644 nginx/ssl/*.pem

# Editar nginx.conf - descomentar seção HTTPS (linhas 74-129)
nano nginx/nginx.conf

# Reiniciar
docker compose --profile with-nginx up -d
```

### Opção 2: Cloudflare (mais fácil)
1. Aponte DNS do domínio para IP da VM via Cloudflare
2. Ative "Proxied" no DNS
3. SSL → Full (strict)
4. Use apenas HTTP no servidor (Cloudflare faz SSL termination)

---

## 🔄 7. LinkedIn OAuth - Configurar Redirect URI

No [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps):
1. Selecione sua app
2. Vá em **Auth** → **OAuth 2.0 settings**
3. Adicione em **Authorized redirect URLs**:
   ```
   https://linkedin.seudominio.com/api/linkedin/callback
   ```

> **Importante:** A URL deve corresponder exatamente ao `NEXT_PUBLIC_BASE_URL` + `/api/linkedin/callback`

---

## 🗄️ 8. Banco de Dados (Supabase)

Execute as migrations no Supabase SQL Editor **em ordem**:

```sql
-- Execute cada arquivo separadamente, na ordem:
-- 1. schema.sql
-- 2. migrations/001_create_user_agents.sql
-- 3. migrations/002_user_photos_and_agents.sql
-- 4. migrations/003_add_post_refinements.sql
-- 5. migrations/004_add_subscriptions.sql
-- 6. migrations/005_add_generated_images.sql
-- 7. migrations/006_approval_stages.sql
-- 8. migrations/007_linkedin_publishing.sql
-- 9. migrations/008_add_linkedin_oauth_tokens.sql
```

> **Nota:** Abra cada arquivo no editor de texto, copie o conteúdo e cole no SQL Editor do Supabase.

---

## 📊 9. Comandos Úteis

```bash
# Status dos containers
docker compose ps

# Logs em tempo real
docker compose logs -f app

# Reiniciar aplicação
docker compose restart app

# Rebuild após mudanças no código
docker compose build --no-cache app && docker compose up -d app

# Parar tudo
docker compose down

# Limpar tudo (containers, imagens, volumes)
docker compose down --rmi all --volumes
```

---

## 🔍 10. Verificar Deploy

```bash
# Health check completo
curl https://linkedin.seudominio.com/api/health | jq

# Resposta esperada:
# {
#   "status": "healthy",
#   "checks": {
#     "environment": {"status": "ok"},
#     "googleCloud": {"status": "ok"},
#     "openai": {"status": "ok"},
#     "apify": {"status": "ok"}
#   }
# }
```

---

## ⚠️ Troubleshooting

| Problema | Solução |
|----------|---------|
| `ECONNREFUSED` Supabase | Verifique `NEXT_PUBLIC_SUPABASE_URL` |
| LinkedIn OAuth falha | Verifique redirect URI no Developer Portal |
| Google Cloud error | Verifique `GOOGLE_CREDENTIALS_BASE64` (base64 sem quebras de linha) |
| Build falha | Execute `docker compose build --no-cache app` |
| 502 Bad Gateway | App ainda iniciando, aguarde 30s ou veja logs |
| Imagem não gera | Verifique `GOOGLE_CREDENTIALS_BASE64` e `VERTEX_PROJECT_ID` |
| Onboarding não aparece | Execute a migration `002_user_photos_and_agents.sql` |

---

## 📝 Checklist Final

- [ ] VM com Docker instalado
- [ ] Código copiado para VM
- [ ] `.env` preenchido com TODAS as credenciais
- [ ] Migrations executadas no Supabase (em ordem)
- [ ] LinkedIn OAuth redirect configurado
- [ ] DNS apontando para IP da VM
- [ ] SSL configurado (Let's Encrypt ou Cloudflare)
- [ ] `/api/health` retorna `"status": "healthy"`
- [ ] Login com LinkedIn funcionando
- [ ] Onboarding aparece para novos usuários
