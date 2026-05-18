# -*- coding: utf-8 -*-
"""Auto-análise: localStorage URL + sessionStorage tokens OAuth LinkedIn."""

from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

STORAGE = r"""
              const LINKEDIN_PROFILE_URL_KEY = "plataforma_linkedin_profile_url";
              const LINKEDIN_PROVIDER_TOKEN_KEY = "plataforma_linkedin_provider_token";
              const LINKEDIN_ID_TOKEN_KEY = "plataforma_linkedin_id_token";

              function getStoredLinkedinProfileUrl() {
                try {
                  return (localStorage.getItem(LINKEDIN_PROFILE_URL_KEY) || "").trim();
                } catch (e) {
                  return "";
                }
              }

              function saveLinkedinProfileUrl(url) {
                const u = String(url || "").trim();
                if (!u || !/linkedin\.com\/(in|company)\//i.test(u)) return;
                try {
                  localStorage.setItem(LINKEDIN_PROFILE_URL_KEY, u);
                } catch (e) { /* privado */ }
              }

              function applyStoredLinkedinProfileUrl() {
                if (!profileInput) return;
                const stored = getStoredLinkedinProfileUrl();
                if (stored && !profileInput.value.trim()) {
                  profileInput.value = stored;
                  profileInput.placeholder = "URL guardado — podes editar ou usar Auto-análise";
                }
              }

              function captureLinkedinOAuthTokens(session) {
                if (!session) return;
                try {
                  if (session.provider_token) {
                    sessionStorage.setItem(LINKEDIN_PROVIDER_TOKEN_KEY, session.provider_token);
                  }
                  const idTok = session.provider_id_token || (session.user && session.user.id_token);
                  if (idTok) {
                    sessionStorage.setItem(LINKEDIN_ID_TOKEN_KEY, idTok);
                  }
                } catch (e) { /* storage */ }
              }

              function getPersistedLinkedinProviderToken(session) {
                if (session && session.provider_token) return session.provider_token;
                try {
                  return sessionStorage.getItem(LINKEDIN_PROVIDER_TOKEN_KEY) || null;
                } catch (e) {
                  return null;
                }
              }

              function getPersistedLinkedinIdToken(session) {
                try {
                  if (session && session.provider_id_token) return session.provider_id_token;
                  return sessionStorage.getItem(LINKEDIN_ID_TOKEN_KEY) || null;
                } catch (e) {
                  return null;
                }
              }

              function appendLinkedinSessionFields(payload, session) {
                if (!payload || !session || !session.access_token) return payload;
                payload.supabase_access_token = session.access_token;
                const pt = getPersistedLinkedinProviderToken(session);
                const idt = getPersistedLinkedinIdToken(session);
                if (pt) payload.linkedin_provider_token = pt;
                if (idt) payload.linkedin_id_token = idt;
                const stored = getStoredLinkedinProfileUrl();
                if (stored) payload.stored_linkedin_profile_url = stored;
                return payload;
              }

"""

if "LINKEDIN_PROFILE_URL_KEY" not in h:
    h = h.replace("              function escapeHtml(value) {", STORAGE + "              function escapeHtml(value) {")

# initSupabaseAuthFromUrl - capture tokens after exchange
if "captureLinkedinOAuthTokens" in h and "captureLinkedinOAuthTokens(data.session)" not in h:
    h = h.replace(
        "                return sb;\n              }\n\n              async function startLinkedInSupabaseLogin()",
        "                const { data: sessAfter } = await sb.auth.getSession();\n"
        "                if (sessAfter && sessAfter.session) {\n"
        "                  captureLinkedinOAuthTokens(sessAfter.session);\n"
        "                  await tryResolveLinkedinProfileUrl(sb);\n"
        "                }\n"
        "                return sb;\n              }\n\n              async function startLinkedInSupabaseLogin()",
    )

# tryResolveLinkedinProfileUrl body
OLD_RESOLVE_BODY = """                  const body = {
                    supabase_access_token: session.access_token,
                    linkedin_provider_token: session.provider_token || null,
                  };"""
NEW_RESOLVE_BODY = """                  captureLinkedinOAuthTokens(session);
                  const body = appendLinkedinSessionFields({
                    supabase_access_token: session.access_token,
                  }, session);"""

if OLD_RESOLVE_BODY in h:
    h = h.replace(OLD_RESOLVE_BODY, NEW_RESOLVE_BODY)

if "saveLinkedinProfileUrl(json.profile_url)" not in h:
    h = h.replace(
        'profileInput.placeholder = "URL do perfil detectado — podes editar ou clicar Analisar";',
        'saveLinkedinProfileUrl(json.profile_url);\n'
        '                    profileInput.placeholder = "URL do perfil detectado — podes editar ou clicar Analisar";',
    )

# runLinkedinProfileAnalysis - replace token/session block
OLD_SESSION_BLOCK = """                const ctx = await getLinkedinSupabaseSession();
                if (ctx) {
                  supabaseToken = ctx.session.access_token;
                  linkedinProviderToken = ctx.session.provider_token || null;
                  if (autoAuthenticated || !profileValue) {
                    useSessionProfile = true;
                  }
                }

                if (autoAuthenticated) {
                  if (!ctx) {
                    result.innerHTML = `<motion class="err"><strong>Erro:</strong> Sessão LinkedIn expirada ou inválida. Volta a iniciar sessão.</motion>`;
                    updateLinkedinAuthButtons(false);
                    return;
                  }
                  profileValue = "";
                  useSessionProfile = true;
                }""".replace("<motion", "<motion")

OLD_SESSION_BLOCK = """                const ctx = await getLinkedinSupabaseSession();
                if (ctx) {
                  supabaseToken = ctx.session.access_token;
                  linkedinProviderToken = ctx.session.provider_token || null;
                  if (autoAuthenticated || !profileValue) {
                    useSessionProfile = true;
                  }
                }

                if (autoAuthenticated) {
                  if (!ctx) {
                    result.innerHTML = `<div class="err"><strong>Erro:</strong> Sessão LinkedIn expirada ou inválida. Volta a iniciar sessão.</motion>`;
                    updateLinkedinAuthButtons(false);
                    return;
                  }
                  profileValue = "";
                  useSessionProfile = true;
                }""".replace("</motion>", "</div>")

NEW_SESSION_BLOCK = """                const ctx = await getLinkedinSupabaseSession();
                if (ctx) {
                  captureLinkedinOAuthTokens(ctx.session);
                  supabaseToken = ctx.session.access_token;
                  linkedinProviderToken = getPersistedLinkedinProviderToken(ctx.session);
                  const storedUrl = getStoredLinkedinProfileUrl();
                  if (storedUrl && !profileValue) profileValue = storedUrl;
                  if (autoAuthenticated || !profileValue) {
                    useSessionProfile = true;
                  }
                }

                if (autoAuthenticated) {
                  if (!ctx) {
                    result.innerHTML = `<div class="err"><strong>Erro:</strong> Sessão LinkedIn expirada ou inválida. Volta a iniciar sessão.</motion>`;
                    updateLinkedinAuthButtons(false);
                    return;
                  }
                  const storedUrl = getStoredLinkedinProfileUrl();
                  if (storedUrl && !profileValue) profileValue = storedUrl;
                  if (!profileValue) {
                    await tryResolveLinkedinProfileUrl(ctx.sb);
                    profileValue = profileInput ? profileInput.value.trim() : "";
                  }
                  if (!profileValue) {
                    useSessionProfile = true;
                  }
                }""".replace("</motion>", "</motion>").replace("<motion", "<motion")
NEW_SESSION_BLOCK = NEW_SESSION_BLOCK.replace("</motion>", "</motion>").replace(
    'expirada ou inválida. Volta a iniciar sessão.</motion>',
    "expirada ou inválida. Volta a iniciar sessão.</div>",
)

if OLD_SESSION_BLOCK in h:
    h = h.replace(OLD_SESSION_BLOCK, NEW_SESSION_BLOCK)
else:
    print("WARN: session block not found, partial patch")

# payload building
OLD_PAYLOAD = """                const payload = {
                  profile_input: autoAuthenticated ? "" : profileValue,
                  messages: [],
                  language: "pt-PT",
                  platform: pl,
                };
                if (supabaseToken) {
                  payload.supabase_access_token = supabaseToken;
                }
                if (linkedinProviderToken) {
                  payload.linkedin_provider_token = linkedinProviderToken;
                }"""

NEW_PAYLOAD = """                const payload = {
                  profile_input: profileValue,
                  messages: [],
                  language: "pt-PT",
                  platform: pl,
                };
                if (ctx && ctx.session) {
                  appendLinkedinSessionFields(payload, ctx.session);
                } else if (supabaseToken) {
                  payload.supabase_access_token = supabaseToken;
                  if (linkedinProviderToken) payload.linkedin_provider_token = linkedinProviderToken;
                  const storedLi = getStoredLinkedinProfileUrl();
                  if (storedLi) payload.stored_linkedin_profile_url = storedLi;
                }"""

if OLD_PAYLOAD in h:
    h = h.replace(OLD_PAYLOAD, NEW_PAYLOAD)

# save URL after analysis
if "saveLinkedinProfileUrl(data.profile_url)" not in h:
    h = h.replace(
        "                  attachTabHandlers();\n                                  } catch (err) {",
        "                  attachTabHandlers();\n"
        "                  const resolvedUrl = data.profile_url\n"
        "                    || (data.public_profile_data && data.public_profile_data.profile_url)\n"
        "                    || (profileInput && profileInput.value.trim());\n"
        "                  if (resolvedUrl) saveLinkedinProfileUrl(resolvedUrl);\n"
        "                                  } catch (err) {",
    )

# runLinkedinAutoProfileAnalysis - simplify (resolve inside main)
OLD_AUTO = """              async function runLinkedinAutoProfileAnalysis() {
                const ctx = await getLinkedinSupabaseSession();
                if (!ctx) {
                  result.innerHTML = `<div class="err"><strong>Erro:</strong> Inicia sessão com «Login LinkedIn (Supabase)» para usar a auto-análise do teu perfil.</div>`;
                  updateLinkedinAuthButtons(false);
                  return;
                }
                await tryResolveLinkedinProfileUrl(ctx.sb);
                await runLinkedinProfileAnalysis({ autoAuthenticated: true });
              }"""

NEW_AUTO = """              async function runLinkedinAutoProfileAnalysis() {
                const ctx = await getLinkedinSupabaseSession();
                if (!ctx) {
                  result.innerHTML = `<div class="err"><strong>Erro:</strong> Inicia sessão com «Login LinkedIn (Supabase)» para usar a auto-análise do teu perfil.</div>`;
                  updateLinkedinAuthButtons(false);
                  return;
                }
                captureLinkedinOAuthTokens(ctx.session);
                await runLinkedinProfileAnalysis({ autoAuthenticated: true });
              }"""

if OLD_AUTO in h:
    h = h.replace(OLD_AUTO, NEW_AUTO)

# logout clears storage
if "LINKEDIN_PROFILE_URL_KEY" in h and "removeItem(LINKEDIN_PROFILE_URL_KEY)" not in h:
    h = h.replace(
        "if (profileInput) {\n                  profileInput.value = \"\";",
        "try {\n"
        "                  sessionStorage.removeItem(LINKEDIN_PROVIDER_TOKEN_KEY);\n"
        "                  sessionStorage.removeItem(LINKEDIN_ID_TOKEN_KEY);\n"
        "                } catch (e) { /* */ }\n"
        "                if (profileInput) {\n                  profileInput.value = \"\";",
    )

# bootstrap
if "applyStoredLinkedinProfileUrl();" not in h:
    h = h.replace(
        "await initSupabaseAuthFromUrl();\n                await refreshLinkedinSupabaseSession();",
        "await initSupabaseAuthFromUrl();\n"
        "                applyStoredLinkedinProfileUrl();\n"
        "                await refreshLinkedinSupabaseSession();",
    )

# auth state listener
if "onAuthStateChange" not in h:
    h = h.replace(
        "(async function bootstrapLinkedinPage() {",
        "(async function setupLinkedinAuthListener() {\n"
        "                const sb = await getLinkedinSupabaseClient();\n"
        "                if (!sb) return;\n"
        "                sb.auth.onAuthStateChange((event, session) => {\n"
        "                  if (session) captureLinkedinOAuthTokens(session);\n"
        "                  if (event === \"SIGNED_IN\" && session) {\n"
        "                    tryResolveLinkedinProfileUrl(sb);\n"
        "                  }\n"
        "                  refreshLinkedinSupabaseSession();\n"
        "                });\n"
        "              })();\n\n"
        "              (async function bootstrapLinkedinPage() {",
    )

# subtitle hint
h = h.replace(
    "Login com <strong>LinkedIn (OIDC)</strong> via Supabase e análise de perfil por URL pública.",
    "Login com <strong>LinkedIn (OIDC)</strong> via Supabase. Na 1.ª vez cola o URL público do perfil; depois a <strong>Auto-análise</strong> usa o URL guardado.",
)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "LINKEDIN_PROFILE_URL_KEY" in h, "appendLinkedinSessionFields" in h)
