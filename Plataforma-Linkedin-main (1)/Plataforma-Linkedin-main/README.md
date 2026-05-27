# 🚀 LinkedIn Content Platform

Plataforma completa para criação automática de conteúdo para LinkedIn com IA.

## ✨ Funcionalidades

- 📝 **Geração de Posts com IA** - Criação automática de conteúdo personalizado baseado em temas e objetivos
- 🖼️ **Imagens com IA** - Geração de imagens contextuais para posts (personalizadas quando há fotos do usuário)
- 🎯 **Análise de Perfil** - Scraping automático do LinkedIn para identificar temas e estilo de escrita
- 💬 **Refinamento via Chat** - Ajuste fino de texto e imagens com IA
- 📊 **Planejamento Semanal** - Organize 7 dias de conteúdo com aprovação individual
- 👤 **Agente IA Pessoal** - Cada usuário tem seu próprio assistente OpenAI com vector store
- 🔗 **Publicação Direta** - Publique posts diretamente no LinkedIn via OAuth

## 🛠️ Stack Tecnológico

| Camada | Tecnologia |
|--------|------------|
| Frontend | Next.js 14, React 18, Tailwind CSS |
| Backend | Next.js API Routes, TypeScript |
| Database | Supabase (PostgreSQL + Storage) |
| Auth | Supabase Auth + LinkedIn OAuth 2.0 manual |
| IA Texto | OpenAI GPT-4o |
| IA Imagem | Google Vertex AI (Gemini 2.5 Flash) |
| Scraping | Apify |
| Deploy | Docker, Nginx |

## 📁 Estrutura do Projeto

```
src/
├── app/
│   ├── api/                  # API Routes
│   │   ├── health/           # Health check
│   │   ├── linkedin/         # OAuth (auth/callback)
│   │   ├── posts/            # Gerenciamento de posts
│   │   ├── user/             # Fotos, uso, etc
│   │   ├── onboarding/       # Análise inicial
│   │   └── apify/            # Scraping de posts
│   ├── posts/                # Página de planejamento
│   ├── onboarding/           # Configuração inicial
│   ├── themes/               # Gerenciar temas
│   └── auth/                 # Callbacks de auth
├── components/               # Componentes React
├── lib/
│   ├── ai/                   # OpenAI Agent Service
│   ├── posts/                # Geração de conteúdo e imagens
│   ├── storage/              # Upload de imagens
│   ├── google-auth.ts        # Auth Google Cloud
│   ├── linkedin-api.ts       # API do LinkedIn
│   └── rateLimit.ts          # Sistema de limites
└── utils/
    └── supabase/             # Clientes Supabase (client/server)
```

## 📊 Rate Limits (Plano Teste)

Limites atuais para usuários de teste:

| Recurso | Limite |
|---------|--------|
| **Posts** | 30/mês |
| **Imagens** | 10/mês |
| **Refinamentos** | 5/dia |
| **Fotos de perfil** | 3 |
| **Agente IA** | ✅ Habilitado |
| **API requests** | 60/minuto |

> Os limites são verificados automaticamente. Posts resetam no início do mês, refinamentos resetam à meia-noite.

## 🚀 Instalação

### Desenvolvimento Local

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/linkedin-platform.git
cd linkedin-platform

# Instale dependências
npm install

# Configure variáveis
cp .env.example .env.local
# Edite .env.local com suas credenciais

# Execute
npm run dev
```

### Produção (Docker)

```bash
# Configure .env
cp .env.example .env

# Build e execute
docker compose up -d app

# Verifique logs
docker compose logs -f app

# Verifique saúde
curl http://localhost:3000/api/health
```

📖 **Guia completo de instalação**: [INSTALL.md](./INSTALL.md)

## 🔧 Configuração

### Variáveis de Ambiente Necessárias

```env
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# OpenAI
OPENAI_API_KEY=sk-proj-...

# Google Cloud / Vertex AI
GOOGLE_CREDENTIALS_BASE64=ewog...  # Base64 do JSON
VERTEX_PROJECT_ID=seu-projeto
VERTEX_LOCATION=us-central1

# Apify
APIFY_TOKEN=apify_api_...

# LinkedIn OAuth
LINKEDIN_CLIENT_ID=77...
LINKEDIN_CLIENT_SECRET=...

# URL Base
NEXT_PUBLIC_BASE_URL=https://seudominio.com
```

### Migrations do Banco

Execute no SQL Editor do Supabase, **em ordem**:

1. `schema.sql`
2. `migrations/001_create_user_agents.sql`
3. `migrations/002_user_photos_and_agents.sql`
4. `migrations/003_add_post_refinements.sql`
5. `migrations/004_add_subscriptions.sql`
6. `migrations/005_add_generated_images.sql`
7. `migrations/006_approval_stages.sql`
8. `migrations/007_linkedin_publishing.sql`
9. `migrations/008_add_linkedin_oauth_tokens.sql`

## 📡 APIs Principais

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/health` | GET | Health check com status dos serviços |
| `/api/user/usage` | GET | Uso atual e limites do usuário |
| `/api/linkedin/auth` | GET | Inicia OAuth do LinkedIn |
| `/api/linkedin/callback` | GET | Callback do OAuth |
| `/api/posts/week` | GET/POST | Listar/gerar posts da semana |
| `/api/posts/[id]/approve` | PUT | Aprovar texto do post |
| `/api/posts/[id]/approve-post` | POST | Publicar no LinkedIn |
| `/api/posts/[id]/generate-image` | POST | Gerar imagem para post |
| `/api/posts/[id]/refine-text` | POST | Refinar texto via chat |
| `/api/posts/[id]/refine-image` | POST | Refinar imagem via chat |
| `/api/user/photos` | GET/POST | Gerenciar fotos do usuário |
| `/api/onboarding/analyze` | POST | Análise inicial de perfil |

## 🔄 Fluxo do Usuário

```
1. Login via LinkedIn OAuth
      ↓
2. Onboarding (primeira vez)
   - Inserir URL do perfil
   - Upload de fotos (opcional)
   - Scraping automático de posts
   - Criação do Agente IA
   - Sugestão de temas
      ↓
3. Configurar Temas e Objetivos
      ↓
4. Gerar Posts da Semana
      ↓
5. Aprovar/Refinar cada post
      ↓
6. Gerar imagem para posts aprovados
      ↓
7. Publicar no LinkedIn
```

## 🔐 Segurança

- ✅ Rate limiting por usuário (plano)
- ✅ Rate limiting anti-abuso (60 req/min)
- ✅ Middleware de segurança (CORS, headers)
- ✅ LinkedIn OAuth 2.0 com CSRF protection
- ✅ Supabase Auth + RLS
- ✅ Credenciais Google via Base64 (sem arquivos)
- ✅ Tokens armazenados com expiração

## 📊 Monitoramento

```bash
# Health check (retorna status de todos os serviços)
curl http://localhost:3000/api/health

# Uso do usuário (requer autenticação)
# Retorna: postsThisMonth, imagesThisMonth, refinementsToday
curl http://localhost:3000/api/user/usage

# Logs Docker
docker compose logs -f app
```

## 🗄️ Banco de Dados

### Tabelas Principais

| Tabela | Descrição |
|--------|-----------|
| `user_agents` | Agente IA, onboarding, posts scraped |
| `user_linkedin_auth` | Tokens OAuth do LinkedIn |
| `user_photos` | Fotos do usuário para imagens |
| `user_themes` | Temas configurados |
| `user_objectives` | Objetivos de conteúdo |
| `posts` | Posts gerados/agendados |
| `generated_images` | Imagens geradas |

## 📄 Licença

Este projeto é proprietário. Todos os direitos reservados.

---

Desenvolvido com ❤️ para criadores de conteúdo LinkedIn.
