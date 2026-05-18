"""Regenera agents/linkedin_perfil_page.py com patches na UI LinkedIn."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML  # noqa: E402

h = LINKEDIN_PERFIL_PAGE_HTML

NEW_TRY_RESOLVE = """
              async function tryResolveLinkedinProfileUrl(sb) {
                if (!profileInput || !sb) return;
                try {
                  const { data } = await sb.auth.getSession();
                  const session = data && data.session;
                  if (!session || !session.access_token) return;
                  const body = {
                    supabase_access_token: session.access_token,
                    linkedin_provider_token: session.provider_token || null,
                  };
                  const res = await fetch("/agents/linkedin/resolve-profile-url", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body),
                  });
                  const json = await res.json();
                  if (res.ok && json.profile_url) {
                    profileInput.value = json.profile_url;
                    profileInput.placeholder = "URL do perfil detectado — podes editar ou clicar Analisar";
                  }
                } catch (e) {
                  /* URL manual continua disponível */
                }
              }

"""

if "async function tryResolveLinkedinProfileUrl" not in h:
    h = h.replace(
        "              async function refreshLinkedinSupabaseSession() {",
        NEW_TRY_RESOLVE + "              async function refreshLinkedinSupabaseSession() {",
    )

h = h.replace(
    '                      profileInput.placeholder = "Com sessão activa: clica Analisar para o teu perfil (ou cola outro URL)";\n                      profileInput.value = "";',
    '                      profileInput.placeholder = "A obter URL do perfil… ou cola manualmente";\n                      await tryResolveLinkedinProfileUrl(sb);',
)

h = h.replace(
    "                      linkedinProviderToken = data.session.provider_token || null;\n                      useSessionProfile = true;",
    "                      linkedinProviderToken = data.session.provider_token || null;\n                      if (!profileValue) useSessionProfile = true;",
)

h = h.replace(
    "                  profile_input: useSessionProfile ? \"\" : profileValue,",
    "                  profile_input: profileValue,",
)

out = ROOT / "agents" / "linkedin_perfil_page.py"
header = '''"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.

O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.
"""

from __future__ import annotations

LINKEDIN_PERFIL_PAGE_HTML: str = '''
footer = "\n"
out.write_text(header + json.dumps(h, ensure_ascii=False) + footer, encoding="utf-8")
print("Patched", out)
