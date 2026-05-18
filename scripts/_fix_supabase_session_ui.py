"""Corrige deteção de sessão Supabase após OAuth (#access_token ou ?code=)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8")
h = json.loads(raw.split("=", 1)[1].strip())

# Remover initSupabaseAuthFromUrl partido / incompleto se existir
h = re.sub(
    r"\n              async function initSupabaseAuthFromUrl\(\) \{.*?\n              \}\n\n",
    "\n",
    h,
    count=1,
    flags=re.DOTALL,
)

# Remover await solto no refresh
h = re.sub(
    r"profileInput\.placeholder = \"A obter URL do perfil.*?\";\n                      await\n",
    'profileInput.placeholder = "A obter URL do perfil… ou cola manualmente";\n                      await tryResolveLinkedinProfileUrl(sb);\n',
    h,
)

h = h.replace(
    'el.innerHTML = "<span class=\\"dot\\"></span> LinkedIn: " + escapeHtml(String(label));',
    'el.innerHTML = "<span class=\\"dot\\"></span> LinkedIn Supabase: " + escapeHtml(String(label));',
)

AUTH_BLOCK = r"""
              let linkedinSupabaseClient = null;

              async function getLinkedinSupabaseClient() {
                if (!SUPABASE_PUBLIC_URL || !SUPABASE_ANON_KEY) return null;
                if (linkedinSupabaseClient) return linkedinSupabaseClient;
                const { createClient } = await import("https://esm.sh/@supabase/supabase-js@2");
                linkedinSupabaseClient = createClient(SUPABASE_PUBLIC_URL, SUPABASE_ANON_KEY, {
                  auth: {
                    detectSessionInUrl: true,
                    persistSession: true,
                    autoRefreshToken: true,
                  },
                });
                return linkedinSupabaseClient;
              }

              async function initSupabaseAuthFromUrl() {
                const sb = await getLinkedinSupabaseClient();
                if (!sb) return null;
                const search = window.location.search || "";
                const hash = window.location.hash || "";
                const params = new URLSearchParams(search);
                const code = params.get("code");
                try {
                  if (code) {
                    await sb.auth.exchangeCodeForSession(code);
                  } else if (hash && (hash.includes("access_token") || hash.includes("refresh_token"))) {
                    const { data, error } = await sb.auth.getSession();
                    if (error) console.warn("Supabase hash session:", error.message);
                    if (!data.session) {
                      await new Promise((r) => setTimeout(r, 150));
                      await sb.auth.getSession();
                    }
                  }
                } catch (e) {
                  console.warn("initSupabaseAuthFromUrl:", e);
                }
                if (code || (hash && hash.includes("access_token"))) {
                  const clean = window.location.pathname + (window.location.search.split("?")[0] || "").replace(/\?code=[^&]+&?/, "?").replace(/\?$/, "");
                  window.history.replaceState({}, "", window.location.pathname);
                }
                return sb;
              }

"""

if "async function getLinkedinSupabaseClient" not in h:
    h = h.replace(
        "              async function startLinkedInSupabaseLogin() {",
        AUTH_BLOCK + "              async function startLinkedInSupabaseLogin() {",
    )

# startLinkedInSupabaseLogin usa cliente partilhado
h = h.replace(
    "                try {\n"
    "                  const { createClient } = await import(\"https://esm.sh/@supabase/supabase-js@2\");\n"
    "                  const sb = createClient(SUPABASE_PUBLIC_URL, SUPABASE_ANON_KEY);\n"
    "                  const redirectTo = window.location.href.split(\"#\")[0].split(\"?\")[0];\n"
    "                  const { data, error } = await sb.auth.signInWithOAuth({\n"
    "                    provider: \"linkedin_oidc\",\n"
    "                    options: { redirectTo },\n"
    "                  });",
    "                try {\n"
    "                  const sb = await getLinkedinSupabaseClient();\n"
    "                  if (!sb) return;\n"
    "                  const redirectTo = window.location.origin + window.location.pathname;\n"
    "                  const { data, error } = await sb.auth.signInWithOAuth({\n"
    "                    provider: \"linkedin_oidc\",\n"
    "                    options: { redirectTo },\n"
    "                  });",
)

# refresh usa cliente partilhado
h = h.replace(
    "                try {\n"
    "                  const { createClient } = await import(\"https://esm.sh/@supabase/supabase-js@2\");\n"
    "                  const sb = createClient(SUPABASE_PUBLIC_URL, SUPABASE_ANON_KEY);\n"
    "                  const { data, error } = await sb.auth.getSession();",
    "                try {\n"
    "                  const sb = await getLinkedinSupabaseClient();\n"
    "                  if (!sb) return;\n"
    "                  const { data, error } = await sb.auth.getSession();",
)

# runLinkedinProfileAnalysis usa cliente partilhado
h = h.replace(
    "                if (SUPABASE_PUBLIC_URL && SUPABASE_ANON_KEY) {\n"
    "                  try {\n"
    "                    const { createClient } = await import(\"https://esm.sh/@supabase/supabase-js@2\");\n"
    "                    const sb = createClient(SUPABASE_PUBLIC_URL, SUPABASE_ANON_KEY);\n"
    "                    const { data } = await sb.auth.getSession();",
    "                if (SUPABASE_PUBLIC_URL && SUPABASE_ANON_KEY) {\n"
    "                  try {\n"
    "                    const sb = await getLinkedinSupabaseClient();\n"
    "                    if (!sb) throw new Error(\"no client\");\n"
    "                    const { data } = await sb.auth.getSession();",
)

# arranque: await init antes de refresh
h = h.replace(
    "              initSupabaseAuthFromUrl();\n              refreshLinkedinSupabaseSession();",
    "              (async function bootstrapLinkedinPage() {\n"
    "                await initSupabaseAuthFromUrl();\n"
    "                await refreshLinkedinSupabaseSession();\n"
    "              })();",
)

header = '''"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.

O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.
"""

from __future__ import annotations

LINKEDIN_PERFIL_PAGE_HTML: str = '''
footer = "\n"
(ROOT / "agents" / "linkedin_perfil_page.py").write_text(
    header + json.dumps(h, ensure_ascii=False) + footer,
    encoding="utf-8",
)
print("ok")
