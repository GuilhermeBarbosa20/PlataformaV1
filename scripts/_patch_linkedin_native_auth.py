"""Login LinkedIn directo (OAuth app) + status por cookies — Analisar sem colar URL."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML  # noqa: E402

h = LINKEDIN_PERFIL_PAGE_HTML

# Botão: OAuth directo em vez de Supabase
h = h.replace(
    'onclick="startLinkedInSupabaseLogin()"',
    'onclick="startLinkedInLogin()"',
)
h = h.replace(
    "Login LinkedIn (Supabase)",
    "Entrar com LinkedIn",
)
h = h.replace(
    'id="linkedinSupabaseStatus"',
    'id="linkedinAuthStatus"',
)
h = h.replace(
    "LinkedIn Supabase",
    "LinkedIn",
)

NEW_LOGIN = """
              function startLinkedInLogin() {
                const returnTo = window.location.pathname + window.location.search;
                window.location.href = "/agents/linkedin/auth/login?return_to=" + encodeURIComponent(returnTo);
              }

"""

if "function startLinkedInLogin()" not in h:
    h = h.replace(
        "              async function startLinkedInSupabaseLogin() {",
        NEW_LOGIN + "              async function startLinkedInSupabaseLogin() {",
    )

# Status via cookies OAuth
NEW_REFRESH = """
              async function refreshLinkedinAuthStatus() {
                const el = document.getElementById("linkedinAuthStatus") || document.getElementById("linkedinSupabaseStatus");
                if (!el) return;
                try {
                  const res = await fetch("/agents/linkedin/auth/status", { credentials: "same-origin" });
                  const data = await res.json();
                  if (data.connected) {
                    const label = data.display_name || data.profile_url || "sessão activa";
                    el.className = "badge ok";
                    el.innerHTML = "<span class=\\"dot\\"></span> LinkedIn: " + escapeHtml(String(label));
                    if (profileInput && data.profile_url && !profileInput.value.trim()) {
                      profileInput.value = data.profile_url;
                      saveLinkedinProfileUrl(data.profile_url);
                      profileInput.placeholder = "Perfil ligado — clica Analisar";
                    }
                    return;
                  }
                } catch (e) { /* fallback supabase */ }
                await refreshLinkedinSupabaseSession();
              }

"""

if "async function refreshLinkedinAuthStatus()" not in h:
    h = h.replace(
        "              async function refreshLinkedinSupabaseSession() {",
        NEW_REFRESH + "              async function refreshLinkedinSupabaseSession() {",
    )

h = h.replace("refreshLinkedinSupabaseSession();", "refreshLinkedinAuthStatus();")

# Analisar: sessão = cookies OU supabase; não exigir URL manual
h = h.replace(
    """                if (!useSessionProfile && !profileValue) {
                  result.innerHTML = `<motion class="err"><strong>Erro:</strong> Inicia sessão com «Login LinkedIn (Supabase)» ou cola o URL público do perfil.</div>`;
                  return;
                }""",
    """                let linkedinConnected = false;
                try {
                  const st = await fetch("/agents/linkedin/auth/status", { credentials: "same-origin" });
                  const stData = await st.json();
                  linkedinConnected = Boolean(stData.connected);
                  if (stData.profile_url && !profileValue) {
                    profileInput.value = stData.profile_url;
                    saveLinkedinProfileUrl(stData.profile_url);
                  }
                } catch (e) { /* */ }
                if (!useSessionProfile && !profileValue && !supabaseToken && !linkedinConnected) {
                  result.innerHTML = `<div class="err"><strong>Erro:</strong> Clica «Entrar com LinkedIn» e depois «Analisar».</motion>`;
                  return;
                }""",
)

# fix typo if present
h = h.replace("<motion class=", "<div class=")
h = h.replace("</motion>", "</motion>")
h = h.replace("</motion>", "</motion>")

h = h.replace(
    'result.innerHTML = `<div class="err"><strong>Erro:</strong> Clica «Entrar com LinkedIn» e depois «Analisar».</motion>`;',
    'result.innerHTML = `<motion class="err"><strong>Erro:</strong> Clica «Entrar com LinkedIn» e depois «Analisar».</div>`;',
)

# Actually fix properly
h = h.replace(
    'result.innerHTML = `<motion class="err"><strong>Erro:</strong> Clica «Entrar com LinkedIn» e depois «Analisar».</motion>`;',
    'result.innerHTML = `<div class="err"><strong>Erro:</strong> Clica «Entrar com LinkedIn» e depois «Analisar».</motion>`;',
)
h = h.replace("</motion>`;", "</div>`;")

h = h.replace(
    "const useSessionProfile = true",
    "const useSessionProfile = !profileInput.value.trim()",
)

# fetch analyze with cookies
h = h.replace(
    'const response = await fetch(endpoint, {\n                    method: "POST",\n                    headers: { "Content-Type": "application/json" },\n                    body: JSON.stringify(payload)\n                  });',
    'const response = await fetch(endpoint, {\n                    method: "POST",\n                    headers: { "Content-Type": "application/json" },\n                    credentials: "same-origin",\n                    body: JSON.stringify(payload)\n                  });',
)

h = h.replace(
    "Coloca o <strong>URL do perfil ou empresa</strong> e clica <strong>Analisar</strong>, ou deixa o campo vazio com <strong>sessão Supabase activa</strong> para analisar o teu perfil (Apify + OpenAI no servidor).",
    "Clica <strong>Entrar com LinkedIn</strong> e depois <strong>Analisar</strong> — o teu perfil é detectado automaticamente (Apify + OpenAI).",
)

h = h.replace(
    "Login com <strong>LinkedIn (OIDC)</strong> confirma a tua identidade; na 1.ª vez cola o URL público do perfil (barra do LinkedIn) — depois fica guardado.",
    "Entra com LinkedIn e analisa o teu perfil com um clique — sem colar URL.",
)

out = ROOT / "agents" / "linkedin_perfil_page.py"
header = '''"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.

O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.
"""

from __future__ import annotations

LINKEDIN_PERFIL_PAGE_HTML: str = '''
footer = "\n"
out.write_text(header + json.dumps(h, ensure_ascii=False) + footer, encoding="utf-8")
print("Patched native auth ->", out)
