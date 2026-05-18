import json
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = p.read_text(encoding="utf-8")
h = json.loads(raw.split("=", 1)[1].strip())
h = h.replace(
    "\n              async \n              async function refreshLinkedinSupabaseSession",
    "\n              async function refreshLinkedinSupabaseSession",
)
if "initSupabaseAuthFromUrl" not in h:
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
        init + "              initSupabaseAuthFromUrl();\n              refreshLinkedinSupabaseSession();",
    )
header = '''"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.

O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.
"""

from __future__ import annotations

LINKEDIN_PERFIL_PAGE_HTML: str = '''
footer = "\n"
p.write_text(header + json.dumps(h, ensure_ascii=False) + footer, encoding="utf-8")
print("fixed js")
