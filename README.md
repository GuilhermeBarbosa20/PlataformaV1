# Plataforma de Agentes de Marketing AI

Colaborador virtual com interface web: o **Diretor de Marketing** recebe instruções em linguagem natural e encaminha para o agente especializado mais adequado. Inclui agentes de copy, design, redes sociais (Instagram/Meta) e **LinkedIn (perfil)** com análise Apify, geração de posts com IA, calendário semanal e publicação OAuth.

## Funcionalidades principais

| Área | Descrição |
|------|-----------|
| **Diretor** | Classificação da intenção (OpenAI ou fallback por palavras-chave) e encaminhamento para o agente certo |
| **Copywriter / Designer** | Geração de copy e imagens via chat |
| **Redes sociais** | Análise Instagram (Apify + Meta OAuth), histórico temporal |
| **LinkedIn (perfil)** | Login OIDC (Supabase), análise de perfil (harvestapi + OpenAI), abas Visão Geral / Posts / Calendário, OAuth de publicação (`w_member_social`) |

### Agente LinkedIn (`/agentes/linkedin-perfil`)

- **Auto-análise** do perfil guardado (login + URL na base de dados)
- **Analisar** outro perfil público por URL
- **Posts** — gerar rascunhos com IA, aprovar, editar, imagem, publicar
- **Calendário** — planear semana, modal por dia, mesmo fluxo de publicação
- **OAuth publicação** — fluxo separado do login Supabase; token persistido em Supabase (`user_linkedin_publish_oauth`)
- Após autorizar publicação, regressa à aba **Posts** ou **Calendário** (não à página inicial)

## Requisitos

- Python 3.11+ (recomendado)
- Conta [OpenAI](https://platform.openai.com/) (análises e geração de texto)
- Conta [Apify](https://apify.com/) (scraping LinkedIn/Instagram)
- Projeto [Supabase](https://supabase.com/) (auth LinkedIn OIDC + perfil/calendário/publicação)
- App [LinkedIn Developer](https://www.linkedin.com/developers/) (login + publicação)
- (Opcional) App Meta para Instagram

## Instalação local

```bash
python -m venv .venv
```

**PowerShell (Windows):**

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edita .env com as tuas chaves
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Abre [http://127.0.0.1:8000](http://127.0.0.1:8000).

> Em produção (Render) usa `python -m uvicorn app:app --host 0.0.0.0 --port $PORT` **sem** `--reload`.

## Variáveis de ambiente

Copia `.env.example` para `.env`. Resumo das mais importantes:

| Variável | Uso |
|----------|-----|
| `OPENAI_API_KEY` | Análises, posts LinkedIn, Diretor |
| `OPENAI_MODEL` | Modelo OpenAI (ex.: `gpt-4o-mini`) |
| `APIFY_API_TOKEN` | Scraping LinkedIn/Instagram |
| `APIFY_LINKEDIN_PROFILE_SCRAPER_ACTOR` | Perfil detalhado (ex.: `harvestapi/linkedin-profile-scraper`) |
| `NEXT_PUBLIC_SUPABASE_URL` / `SUPABASE_URL` | Projeto Supabase |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` / `SUPABASE_ANON_KEY` | Chave anon Supabase |
| `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | App LinkedIn Developer |
| `LINKEDIN_REDIRECT_URI` | Callback login OIDC (Supabase) |
| `LINKEDIN_PUBLISH_REDIRECT_URI` | Callback publicação (`/agents/linkedin/connect-publish/callback`) |
| `LINKEDIN_SCOPES` | Ex.: `openid profile email w_member_social` |
| `LINKEDIN_COOKIE_SECURE` | `1` em HTTPS (Render); `0` em localhost |
| `META_*` | OAuth Instagram (agente Redes sociais) |

No **LinkedIn Developer** → Auth → **Authorized redirect URLs**, inclui:

- `http://127.0.0.1:8000/agents/linkedin/connect-publish/callback` (local)
- `https://<teu-dominio>/agents/linkedin/connect-publish/callback` (produção)

E os redirects configurados no Supabase para o login OIDC.

## Migrations Supabase

Executa no **SQL Editor** do projeto (por ordem):

1. `migrations/001_user_linkedin_profiles.sql` — URL do perfil LinkedIn por utilizador  
2. `migrations/002_linkedin_school_urls.sql` — URLs de escolas (se aplicável)  
3. `migrations/003_user_linkedin_calendar_posts.sql` — posts do calendário  
4. `migrations/004_user_linkedin_publish_oauth.sql` — token OAuth de publicação LinkedIn  

## Deploy (Render)

1. Liga o repositório GitHub ao Render como **Web Service** (não Static Site).  
2. **Build:** `pip install -r requirements.txt`  
3. **Start:** `python -m uvicorn app:app --host 0.0.0.0 --port $PORT`  
4. **Publish Directory:** vazio  
5. Copia todas as variáveis do `.env` para o painel Render; substitui URLs `localhost` pelo domínio `*.onrender.com`.  
6. `git push` → redeploy automático.

## Testar OAuth de publicação outra vez

A autorização de **publicação** é independente do login «Autenticado» (Supabase).

**1. Browser** (consola F12 na página do agente):

```javascript
sessionStorage.removeItem("plataforma_linkedin_publish_token");
sessionStorage.removeItem("plataforma_linkedin_publish_person_urn");
sessionStorage.removeItem("plataforma_linkedin_publish_expires_at");
location.reload();
```

**2. Supabase** (obrigatório se já gravaste na BD):

```sql
DELETE FROM public.user_linkedin_publish_oauth;
-- ou só o teu user_id
```

**3. LinkedIn** (opcional): Definições → Privacidade → remover a app da plataforma.

Depois: aba Posts ou Calendário → **Autorizar publicação no LinkedIn**.

## Rotas úteis

| Rota | Descrição |
|------|-----------|
| `GET /` | Diretor de Marketing |
| `POST /chat` | Encaminhar pedido do utilizador |
| `GET /agentes/linkedin-perfil` | UI agente LinkedIn |
| `GET /agentes/redes-sociais` | UI Instagram / redes |
| `GET /agentes/copywriter` | UI Copywriter |
| `GET /agentes/designer` | UI Designer |
| `POST /agents/social-media/profile-analyze` | Análise de perfil (LinkedIn, etc.) |
| `POST /agents/linkedin/generate-posts` | Gerar posts com IA |
| `GET /agents/linkedin/connect-publish` | Iniciar OAuth publicação |
| `POST /agents/linkedin/publish-auth/store` | Persistir token na Supabase |
| `POST /agents/linkedin/publish-post` | Publicar post aprovado |

Lista completa de agentes (slugs): `copywriter`, `designer`, `redes-sociais`, `linkedin-perfil`, `meta-ads`, `linkedin-ads`, `google-ads`, `web-developer`, `seo`, `geo`, `analista-score`.

## Diretor — modo IA

Por defeito usa OpenAI:

```powershell
$env:OPENAI_API_KEY="sk-..."
$env:DIRECTOR_AI_MODEL="gpt-4o-mini"
python -m uvicorn app:app --reload
```

Endpoint:

```http
POST /chat
Content-Type: application/json

{"user_input": "Quero melhorar a taxa de conversão dos meus anúncios"}
```

Se a IA falhar, o sistema usa classificação por palavras-chave.

API compatível (ex. Ollama): define `DIRECTOR_ALLOW_COMPATIBLE_API=true` e `DIRECTOR_AI_API_URL`.

## Estrutura do projeto

```
app.py                          # FastAPI — rotas e orquestração
agents/
  linkedin_perfil_page.py       # HTML/JS do agente LinkedIn (embutido)
  linkedin_harvest_profile.py   # Métricas harvestapi
  linkedin_oauth.py             # OAuth publicação
  linkedin_publish.py           # API UGC LinkedIn
  linkedin_publish_auth_db.py   # Persistência Supabase
  social_media.py               # Análises e geração de posts
migrations/                     # SQL Supabase
.env.example                    # Modelo de configuração
requirements.txt
```

## Notas de segurança

- Não commits `.env` nem tokens Apify/OpenAI.  
- Em produção usa `LINKEDIN_COOKIE_SECURE=1` e `META_COOKIE_SECURE=1`.  
- Roda as migrations antes de testar calendário ou publicação OAuth.
