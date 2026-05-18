# -*- coding: utf-8 -*-
"""Botão Auto-análise (perfil LinkedIn autenticado via Supabase)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD_RUN = """async function runLinkedinProfileAnalysis() {
                const profileValue = profileInput.value.trim();
                const pl = "linkedin";
                let supabaseToken = null;
                let linkedinProviderToken = null;
                let useSessionProfile = false;

                if (SUPABASE_PUBLIC_URL && SUPABASE_ANON_KEY) {
                  try {
                    const sb = await getLinkedinSupabaseClient();
                    if (!sb) throw new Error("no client");
                    const { data } = await sb.auth.getSession();
                    if (data.session && data.session.access_token) {
                      supabaseToken = data.session.access_token;
                      linkedinProviderToken = data.session.provider_token || null;
                      if (!profileValue) useSessionProfile = true;
                    }
                  } catch (e) {
                    /* segue sem sessão */
                  }
                }

                if (!useSessionProfile && !profileValue) {
                  result.innerHTML = `<motion class="err"><strong>Erro:</strong> Inicia sessão com «Login LinkedIn (Supabase)» ou cola o URL público do perfil.</motion>`;
                  return;
                }"""

NEW_HELPERS_AND_RUN_START = """async function getLinkedinSupabaseSession() {
                if (!SUPABASE_PUBLIC_URL || !SUPABASE_ANON_KEY) return null;
                try {
                  const sb = await getLinkedinSupabaseClient();
                  if (!sb) return null;
                  const { data, error } = await sb.auth.getSession();
                  if (error || !data.session || !data.session.access_token) return null;
                  return { sb, session: data.session };
                } catch (e) {
                  return null;
                }
              }

              function updateAutoAnalyzeButton(hasSession) {
                const btn = document.getElementById("btnAutoAnalyze");
                if (!btn) return;
                const enabled = Boolean(hasSession);
                btn.disabled = !enabled;
                btn.style.opacity = enabled ? "1" : "0.45";
                btn.style.cursor = enabled ? "pointer" : "not-allowed";
                btn.title = enabled
                  ? "Analisa automaticamente o teu perfil LinkedIn autenticado (sessão Supabase + Apify + OpenAI)."
                  : "Inicia sessão com «Login LinkedIn (Supabase)» para analisar o teu perfil.";
              }

              async function runLinkedinAutoProfileAnalysis() {
                const ctx = await getLinkedinSupabaseSession();
                if (!ctx) {
                  result.innerHTML = `<div class="err"><strong>Erro:</strong> Inicia sessão com «Login LinkedIn (Supabase)» para usar a auto-análise do teu perfil.</motion>`;
                  updateAutoAnalyzeButton(false);
                  return;
                }
                await tryResolveLinkedinProfileUrl(ctx.sb);
                await runLinkedinProfileAnalysis({ autoAuthenticated: true });
              }

              async function runLinkedinProfileAnalysis(options) {
                options = options || {};
                const autoAuthenticated = options.autoAuthenticated === true;
                let profileValue = profileInput ? profileInput.value.trim() : "";
                const pl = "linkedin";
                let supabaseToken = null;
                let linkedinProviderToken = null;
                let useSessionProfile = false;

                const ctx = await getLinkedinSupabaseSession();
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
                    updateAutoAnalyzeButton(false);
                    return;
                  }
                  profileValue = "";
                  useSessionProfile = true;
                }

                if (!useSessionProfile && !profileValue) {
                  result.innerHTML = `<div class="err"><strong>Erro:</strong> Inicia sessão com «Login LinkedIn (Supabase)» ou cola o URL público do perfil.</motion>`;
                  return;
                }"""

# fix motion typos in NEW - use div
NEW_HELPERS_AND_RUN_START = NEW_HELPERS_AND_RUN_START.replace("</motion>", "</div>").replace('class="err">', 'class="err">')

OLD_RUN = OLD_RUN.replace("<motion", "<motion")  # keep div in original
OLD_RUN = """async function runLinkedinProfileAnalysis() {
                const profileValue = profileInput.value.trim();
                const pl = "linkedin";
                let supabaseToken = null;
                let linkedinProviderToken = null;
                let useSessionProfile = false;

                if (SUPABASE_PUBLIC_URL && SUPABASE_ANON_KEY) {
                  try {
                    const sb = await getLinkedinSupabaseClient();
                    if (!sb) throw new Error("no client");
                    const { data } = await sb.auth.getSession();
                    if (data.session && data.session.access_token) {
                      supabaseToken = data.session.access_token;
                      linkedinProviderToken = data.session.provider_token || null;
                      if (!profileValue) useSessionProfile = true;
                    }
                  } catch (e) {
                    /* segue sem sessão */
                  }
                }

                if (!useSessionProfile && !profileValue) {
                  result.innerHTML = `<motion class="err"><strong>Erro:</strong> Inicia sessão com «Login LinkedIn (Supabase)» ou cola o URL público do perfil.</motion>`;
                  return;
                }""".replace("<motion", "<div").replace("motion>", "div>")

NEW_HELPERS_AND_RUN_START = NEW_HELPERS_AND_RUN_START.replace("<motion", "<div").replace("motion>", "motion>")

if OLD_RUN not in h:
    raise SystemExit("OLD_RUN block not found")

h = h.replace(OLD_RUN, NEW_HELPERS_AND_RUN_START)

# loading hint for auto
h = h.replace(
    'const loadingHint = useSessionProfile\n'
    '                  ? "A recolher o teu perfil LinkedIn (sessão + Apify)…"\n'
    '                  : "LinkedIn (Apify + OpenAI) — pode demorar…";',
    'const loadingHint = autoAuthenticated\n'
    '                  ? "Auto-análise do teu perfil LinkedIn (sessão + Apify + OpenAI)…"\n'
    '                  : (useSessionProfile\n'
    '                    ? "A recolher o teu perfil LinkedIn (sessão + Apify)…"\n'
    '                    : "LinkedIn (Apify + OpenAI) — pode demorar…");',
)

# payload uses profileValue (empty on auto)
h = h.replace(
    "profile_input: profileValue,",
    "profile_input: autoAuthenticated ? \"\" : profileValue,",
)

# refreshLinkedinSupabaseSession - update button
h = h.replace(
    "el.className = \"badge ok\";\n"
    "                    el.innerHTML = \"<span class=\\\"dot\\\"></span> LinkedIn Supabase: \" + escapeHtml(String(label));\n"
    "                    if (profileInput) {",
    "el.className = \"badge ok\";\n"
    "                    el.innerHTML = \"<span class=\\\"dot\\\"></span> LinkedIn Supabase: \" + escapeHtml(String(label));\n"
    "                    updateAutoAnalyzeButton(true);\n"
    "                    if (profileInput) {",
)

h = h.replace(
    "el.className = \"badge\";\n"
    "                  el.innerHTML = \"<span class=\\\"dot\\\"></span> LinkedIn: sem sessão\";\n"
    "                    if (profileInput) {",
    "el.className = \"badge\";\n"
    "                  el.innerHTML = \"<span class=\\\"dot\\\"></span> LinkedIn: sem sessão\";\n"
    "                  updateAutoAnalyzeButton(false);\n"
    "                    if (profileInput) {",
)

h = h.replace(
    "el.className = \"badge bad\";\n"
    "                  el.innerHTML = \"<span class=\\\"dot\\\"></span> LinkedIn: indisponível\";",
    "el.className = \"badge bad\";\n"
    "                  el.innerHTML = \"<span class=\\\"dot\\\"></span> LinkedIn: indisponível\";\n"
    "                  updateAutoAnalyzeButton(false);",
)

h = h.replace(
    "el.className = \"badge\";\n"
    "                  el.innerHTML = \"<span class=\\\"dot\\\"></span> LinkedIn: não configurado\";\n"
    "                  return;",
    "el.className = \"badge\";\n"
    "                  el.innerHTML = \"<span class=\\\"dot\\\"></span> LinkedIn: não configurado\";\n"
    "                  updateAutoAnalyzeButton(false);\n"
    "                  return;",
)

# HTML button + CSS
if "btnAutoAnalyze" not in h:
    h = h.replace(
        ".btn-linkedin:disabled { opacity: 0.45; cursor: not-allowed; }",
        ".btn-linkedin:disabled { opacity: 0.45; cursor: not-allowed; }\n"
        "              .btn-auto-analyze {\n"
        "                background: linear-gradient(135deg, #0a66c2, #004182);\n"
        "                border: 1px solid rgba(255,255,255,0.2);\n"
        "                box-shadow: 0 6px 18px rgba(10,102,194,0.35);\n"
        "              }\n"
        "              .btn-auto-analyze:disabled { opacity: 0.45; cursor: not-allowed; filter: none; }",
    )
    h = h.replace(
        '<button type="button" class="btn-linkedin" onclick="startLinkedInSupabaseLogin()">Login LinkedIn (Supabase)</button>\n'
        '                  <span id="linkedinSupabaseStatus"',
        '<button type="button" class="btn-linkedin" onclick="startLinkedInSupabaseLogin()">Login LinkedIn (Supabase)</button>\n'
        '                  <button type="button" id="btnAutoAnalyze" class="btn-auto-analyze" onclick="runLinkedinAutoProfileAnalysis()" disabled>Auto-análise</button>\n'
        '                  <span id="linkedinSupabaseStatus"',
    )

# empty state hint
h = h.replace(
    "Clica <strong>Login LinkedIn (Supabase)</strong> e depois <strong>Analisar</strong>",
    "Clica <strong>Login LinkedIn (Supabase)</strong> e depois <strong>Auto-análise</strong> ou <strong>Analisar</strong>",
)

# bootstrap init button state
h = h.replace(
    "(async function bootstrapLinkedinPage() {\n"
    "                await initSupabaseAuthFromUrl();\n"
    "                await refreshLinkedinSupabaseSession();\n"
    "              })();",
    "(async function bootstrapLinkedinPage() {\n"
    "                await initSupabaseAuthFromUrl();\n"
    "                await refreshLinkedinSupabaseSession();\n"
    "                if (!document.getElementById(\"btnAutoAnalyze\")) updateAutoAnalyzeButton(false);\n"
    "              })();",
)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "btnAutoAnalyze" in h, "runLinkedinAutoProfileAnalysis" in h)
