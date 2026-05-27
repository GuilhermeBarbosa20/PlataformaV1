# LinkedIn Autonomous Agent Platform - Setup Guide

## 🚀 Quick Start

### 1. **Rodar o Schema no Supabase**

```sql
-- Execute isso no SQL Editor do Supabase
-- (incluindo a tabela user_linkedin_auth para guardar os cookies)
```

**Status:** ✅ Já executado

### 2. **Configurar Variáveis de Ambiente**

Atualize seu `.env.local`:

```env
# Supabase (já deve estar configurado)
NEXT_PUBLIC_SUPABASE_URL=seu_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=seu_anon_key

# LinkedIn OAuth (já deve estar configurado)
NEXT_PUBLIC_LINKEDIN_CLIENT_ID=seu_linkedin_client_id

# Apify Token (OBRIGATÓRIO para SSI Scraping)
APIFY_TOKEN=apify_api_your_token_here

# Base URL
NEXT_PUBLIC_BASE_URL=http://localhost:3000

# Vertex AI (Geração de imagem)
VERTEX_PROJECT_ID=o_seu_projecto
VERTEX_LOCATION=us-central1
VERTEX_IMAGE_MODEL=gemini-1.5-flash-002
# Caminho absoluto para o JSON da service account (ficheiro fora do repo)
GOOGLE_APPLICATION_CREDENTIALS=C:/chaves/vertex-service-account.json
```

**Status:** ✅ Configura o token Apify no `.env.local` (nunca commits o valor real)

> 💡 Dê à service account as permissões `Vertex AI User` e `Storage Object Viewer`. Guarde o ficheiro JSON fora do repositório e aponte `GOOGLE_APPLICATION_CREDENTIALS` para esse caminho absoluto. O backend usa essas credenciais para gerar o token OAuth automaticamente (via `google-auth-library`).

### 3. **Instalar Dependências**

```bash
npm install recharts
```

### 4. **Rodar o Aplicativo**

```bash
npm run dev
```

---

## 📊 Fluxo de Funcionamento

### **1. User faz login com LinkedIn**
- Redirecionado para `/auth/callback`
- Supabase Auth configura a sessão

### **2. Component `LinkedInCookieCapture` é ativado**
- Extrai o cookie `li_at` do browser
- Envia para `/api/auth/store-linkedin-cookie`
- Cookie é armazenado na tabela `user_linkedin_auth`

### **3. User acessa `/ssi` Dashboard**
- Clica em "📊 SSI Dashboard" na navbar
- Page tenta carregar métricas do banco

### **4. User clica "Refresh Now"**
- Chama `/api/apify/scrape-ssi`
- API busca o `li_at` cookie do banco de dados
- Passa para o Apify Puppeteer Scraper
- Apify executa o scraping da página LinkedIn SSI
- Dados são parseados e salvos em `linkedin_ssi_metrics`
- Gráficos são atualizados

---

## 🔑 Tabelas do Banco

### **user_linkedin_auth**
Armazena as credenciais do LinkedIn para cada user:

```sql
- id (uuid)
- user_id (uuid) - referencia auth.users
- linkedin_li_at_cookie (text) - o cookie de sessão
- linkedin_profile_url (text)
- linkedin_profile_name (text)
- linkedin_profile_photo (text)
- cookie_expires_at (timestamptz) - 30 dias
- created_at, updated_at
```

### **linkedin_ssi_metrics**
Armazena os snapshots do SSI:

```sql
- id (uuid)
- user_id (uuid)
- snapshot_date (date) - data do snapshot
- profile_strength_score (integer) - 0-100
- [outros campos do SSI]
- raw_payload (jsonb) - resposta completa do Apify
```

---

## 🐛 Troubleshooting

### **"LinkedIn cookie not found"**
- User não fez login com LinkedIn, ou
- O componente `LinkedInCookieCapture` não foi ativado
- **Solução:** Fazer login novamente

### **"Apify token not configured"**
- Variável `APIFY_TOKEN` não está no `.env.local`
- **Solução:** Adicionar o token

### **"Apify actor run failed"**
- Cookie `li_at` expirou ou é inválido
- Estrutura HTML do LinkedIn mudou
- **Solução:** Fazer login novamente para renovar o cookie

### **Gráficos não aparecem**
- Recharts não foi instalado
- **Solução:** `npm install recharts`

---

## 📝 Próximas Melhorias

- [ ] Refresh automático dos dados a cada 24h
- [ ] Exportar dados como CSV/PDF
- [ ] Comparar tendências ao longo do tempo
- [ ] Alertas quando SSI score cai
- [ ] Integração com o Agent Loop para IA analisar SSI

---

## 🔗 Arquivos Principais

```
src/
├── app/
│   ├── page.tsx                          # Home page com navbar
│   ├── ssi/page.tsx                      # Dashboard SSI
│   ├── api/
│   │   ├── apify/scrape-ssi/route.ts     # API para scraping
│   │   └── auth/store-linkedin-cookie/   # API para guardar cookie
│   └── auth/callback/route.ts            # Callback do OAuth
├── components/
│   └── LinkedInCookieCapture.tsx         # Component que captura cookie
├── lib/
│   └── linkedin-auth.ts                  # Funções de auth
└── utils/supabase/
    ├── client.ts                         # Supabase client (browser)
    └── server.ts                         # Supabase server
```

---

**Status:** ✅ Tudo configurado e pronto para usar!
