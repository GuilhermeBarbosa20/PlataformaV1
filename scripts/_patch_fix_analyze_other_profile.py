# -*- coding: utf-8 -*-
"""Analisar: só URL do profileInput; perfil guardado só em myProfileInput / Auto-análise."""

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

# 1) applyStoredLinkedinProfileUrl — não preencher profileInput (só myProfileInput)
OLD_APPLY = """              function applyStoredLinkedinProfileUrl() {
                if (!profileInput) return;
                const stored = getStoredLinkedinProfileUrl();
                if (stored && !profileInput.value.trim()) {
                  profileInput.value = stored;
                  profileInput.placeholder = "URL guardado — podes editar ou usar Auto-análise";
                }
              }"""

NEW_APPLY = """              function applyStoredLinkedinProfileUrl() {
                const stored = getStoredLinkedinProfileUrl();
                if (!stored) return;
                if (myProfileInput && !myProfileInput.value.trim()) {
                  myProfileInput.value = stored;
                }
                if (profileInput) {
                  profileInput.placeholder = "https://www.linkedin.com/in/nome ou /company/empresa";
                }
              }"""

if OLD_APPLY in h:
    h = h.replace(OLD_APPLY, NEW_APPLY, 1)
else:
    h = h.replace(
        "profileInput.value = stored;\n                  profileInput.placeholder = \"URL guardado",
        "/* não preencher campo «outro perfil» com URL guardado */\n                  if (myProfileInput && !myProfileInput.value.trim()) myProfileInput.value = stored;\n                  if (profileInput) profileInput.placeholder = \"https://www.linkedin.com/in/nome ou /company/empresa\";\n                  void(\"URL guardado",
        1,
    )

# 2) appendLinkedinSessionFields — stored URL opcional
OLD_APPEND = """              function appendLinkedinSessionFields(payload, session) {
                if (!payload || !session || !session.access_token) return payload;
                payload.supabase_access_token = session.access_token;
                const pt = getPersistedLinkedinProviderToken(session);
                const idt = getPersistedLinkedinIdToken(session);
                if (pt) payload.linkedin_provider_token = pt;
                if (idt) payload.linkedin_id_token = idt;
                const stored = getStoredLinkedinProfileUrl();
                if (stored) payload.stored_linkedin_profile_url = stored;
                return payload;
              }"""

NEW_APPEND = """              function appendLinkedinSessionFields(payload, session, options) {
                options = options || {};
                if (!payload || !session || !session.access_token) return payload;
                payload.supabase_access_token = session.access_token;
                const pt = getPersistedLinkedinProviderToken(session);
                const idt = getPersistedLinkedinIdToken(session);
                if (pt) payload.linkedin_provider_token = pt;
                if (idt) payload.linkedin_id_token = idt;
                if (options.includeStoredUrl !== false) {
                  const stored = getStoredLinkedinProfileUrl();
                  if (stored) payload.stored_linkedin_profile_url = stored;
                }
                return payload;
              }"""

if OLD_APPEND in h:
    h = h.replace(OLD_APPEND, NEW_APPEND, 1)

# 3) runLinkedinProfileAnalysis — useSessionProfile só na auto-análise
OLD_SESSION_FLAG = """                const ctx = await getLinkedinSupabaseSession();
                if (ctx) {
                  captureLinkedinOAuthTokens(ctx.session);
                  supabaseToken = ctx.session.access_token;
                  linkedinProviderToken = getPersistedLinkedinProviderToken(ctx.session);
                  if (autoAuthenticated || !profileValue) {
                    useSessionProfile = true;
                  }
                }"""

NEW_SESSION_FLAG = """                const ctx = await getLinkedinSupabaseSession();
                if (ctx) {
                  captureLinkedinOAuthTokens(ctx.session);
                  supabaseToken = ctx.session.access_token;
                  linkedinProviderToken = getPersistedLinkedinProviderToken(ctx.session);
                }"""

if OLD_SESSION_FLAG in h:
    h = h.replace(OLD_SESSION_FLAG, NEW_SESSION_FLAG, 1)

# 4) appendLinkedinSessionFields no analyze — sem stored quando há URL explícito
h = h.replace(
    "                if (ctx && ctx.session) {\n                  appendLinkedinSessionFields(payload, ctx.session);\n                } else if (supabaseToken) {",
    "                if (ctx && ctx.session) {\n"
    "                  appendLinkedinSessionFields(payload, ctx.session, {\n"
    "                    includeStoredUrl: autoAuthenticated || !profileValue,\n"
    "                  });\n"
    "                } else if (supabaseToken) {",
    1,
)

# 5) Mensagem de erro mais clara quando Analisar sem URL
h = h.replace(
    "if (!useSessionProfile && !profileValue) {\n"
    "                  result.innerHTML = `<motion class=\"err\"><strong>Erro:</strong> Inicia sessão com «Login LinkedIn (Supabase)» ou cola o URL público do perfil.</div>`;\n"
    "                  return;\n"
    "                }",
    "if (!profileValue && !autoAuthenticated) {\n"
    "                  result.innerHTML = `<div class=\"err\"><strong>Erro:</strong> Cola o URL público do perfil que queres analisar (campo «Analisar outro perfil»).</div>`;\n"
    "                  return;\n"
    "                }",
)
h = h.replace(
    "if (!useSessionProfile && !profileValue) {\n"
    "                  result.innerHTML = `<div class=\"err\"><strong>Erro:</strong> Inicia sessão com «Login LinkedIn (Supabase)» ou cola o URL público do perfil.</div>`;\n"
    "                  return;\n"
    "                }",
    "if (!profileValue && !autoAuthenticated) {\n"
    "                  result.innerHTML = `<motion class=\"err\"><strong>Erro:</strong> Cola o URL público do perfil que queres analisar (campo «Analisar outro perfil»).</div>`;\n"
    "                  return;\n"
    "                }",
)
# fix motion typo if introduced
h = h.replace('<motion class="err">', '<div class="err">').replace('</motion>`;', '</motion>`;')
h = h.replace('analisar (campo «Analisar outro perfil»).</motion>`;', 'analisar (campo «Analisar outro perfil»).</div>`;')

# 6) loading hint — remove useSessionProfile branch confusion for manual
OLD_HINT = """                const loadingHint = autoAuthenticated
                  ? "Auto-análise do teu perfil LinkedIn (sessão + Apify + OpenAI)…"
                  : (useSessionProfile
                    ? "A recolher o teu perfil LinkedIn (sessão + Apify)…"
                    : "LinkedIn (Apify + OpenAI) — pode demorar…");"""

NEW_HINT = """                const loadingHint = autoAuthenticated
                  ? "Auto-análise do teu perfil LinkedIn (sessão + Apify + OpenAI)…"
                  : "A analisar o perfil indicado (Apify + OpenAI) — pode demorar…";"""

if OLD_HINT in h:
    h = h.replace(OLD_HINT, NEW_HINT, 1)

# 7) resolve-profile-url body — keep stored for resolve endpoint only
# tryResolve uses appendLinkedinSessionFields without options — OK (default include stored)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")

checks = {
    "no profileInput fill": "profileInput.value = stored" not in h,
    "myProfile fill": "myProfileInput.value = stored" in h,
    "includeStoredUrl": "includeStoredUrl" in h,
    "no auto session on empty": "autoAuthenticated || !profileValue" not in h,
    "explicit url error": "Analisar outro perfil" in h,
}
print("ok", checks)
