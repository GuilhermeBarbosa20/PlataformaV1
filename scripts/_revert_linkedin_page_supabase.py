"""Reverte a página LinkedIn para login Supabase apenas."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML  # noqa: E402

h = LINKEDIN_PERFIL_PAGE_HTML

# UI textos e botão
h = h.replace('onclick="startLinkedInLogin()"', 'onclick="startLinkedInSupabaseLogin()"')
h = h.replace("Entrar com LinkedIn", "Login LinkedIn (Supabase)")
h = h.replace('id="linkedinAuthStatus"', 'id="linkedinSupabaseStatus"')
h = h.replace("LinkedIn: cola o URL", "LinkedIn Supabase")
h = h.replace(">LinkedIn<", ">LinkedIn Supabase<", 1)

# Remover blocos JS do OAuth directo / localStorage
for fn in (
    "function startLinkedInLogin()",
    "function refreshLinkedinAuthStatus()",
    "function handleLinkedinAuthQuery()",
    "const LINKEDIN_PROFILE_URL_KEY",
    "function getStoredLinkedinProfileUrl()",
    "function saveLinkedinProfileUrl(",
    "function applyStoredLinkedinProfileUrl()",
):
    while fn in h:
        start = h.index(fn)
        # encontrar fim da função (próxima function async ou function ao mesmo nível)
        rest = h[start + len(fn) :]
        m = re.search(r"\n              (async )?function ", rest)
        end = start + len(fn) + (m.start() if m else len(rest))
        h = h[:start] + h[end:]

h = h.replace("handleLinkedinAuthQuery();\n              ", "")
h = h.replace("applyStoredLinkedinProfileUrl();\n              ", "")
h = h.replace("refreshLinkedinAuthStatus();", "refreshLinkedinSupabaseSession();")

# Remover referências localStorage / status OAuth no analyze
h = re.sub(
    r"\n                let linkedinConnected = false;.*?if \(!useSessionProfile && !profileValue && !supabaseToken && !linkedinConnected\)",
    "\n                if (!useSessionProfile && !profileValue && !supabaseToken)",
    h,
    flags=re.DOTALL,
    count=1,
)

h = h.replace("stored_linkedin_profile_url", "removed_stored")
h = re.sub(r",\s*removed_stored: getStoredLinkedinProfileUrl\(\) \|\| null", "", h)
h = re.sub(r"const storedLi = getStoredLinkedinProfileUrl\(\);.*?payload\.removed_stored = storedLi;\n", "", h, flags=re.DOTALL)
h = h.replace("saveLinkedinProfileUrl(json.profile_url);\n                    ", "")
h = re.sub(r"const resolvedUrl = .*?saveLinkedinProfileUrl\(resolvedUrl\);\n", "", h, flags=re.DOTALL)

h = h.replace(', credentials: "same-origin"', "", 2)

# Callback Supabase (?code=) após OAuth
if "exchangeCodeForSession" not in h:
    init = """
              async function initSupabaseAuthFromUrl() {
                if (!SUPABASE_PUBLIC_URL || !SUPABASE_ANON_KEY) return;
                const params = new URLSearchParams(window.location.search);
                const code = params.get("code");
                if (!code) return;
                try {
                  const { createClient } = await import("https://esm.sh/@supabase/supabase-js@2");
                  const sb = createClient(SUPABASE_PUBLIC_URL, SUPABASE_ANON_KEY);
                  await sb.auth.exchangeCodeForSession(code);
                  window.history.replaceState({}, "", window.location.pathname);
                } catch (e) { /* */ }
              }

"""
    h = h.replace(
        "              refreshLinkedinSupabaseSession();",
        "              initSupabaseAuthFromUrl();\n              refreshLinkedinSupabaseSession();",
    )

# tryResolve simplificado (sem stored)
h = re.sub(
    r"stored_linkedin_profile_url: getStoredLinkedinProfileUrl\(\) \|\| null,\n",
    "",
    h,
)

h = h.replace(
    "Entra com LinkedIn e analisa o teu perfil com um clique — sem colar URL.",
    "Login com <strong>LinkedIn (OIDC)</strong> via Supabase e análise de perfil por URL pública.",
)

h = h.replace(
    "Clica <strong>Entrar com LinkedIn</strong> e depois <strong>Analisar</strong>",
    "Coloca o <strong>URL do perfil</strong> e clica <strong>Analisar</strong>, ou usa <strong>sessão Supabase</strong>",
)

out = ROOT / "agents" / "linkedin_perfil_page.py"
header = '''"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.

O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.
"""

from __future__ import annotations

LINKEDIN_PERFIL_PAGE_HTML: str = '''
footer = "\n"
out.write_text(header + json.dumps(h, ensure_ascii=False) + footer, encoding="utf-8")
print("Reverted page ->", out)
