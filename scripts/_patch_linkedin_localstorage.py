"""Adiciona localStorage e stored_linkedin_profile_url à página LinkedIn perfil."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML  # noqa: E402

h = LINKEDIN_PERFIL_PAGE_HTML

STORAGE_HELPERS = """
              const LINKEDIN_PROFILE_URL_KEY = "plataforma_linkedin_profile_url";

              function getStoredLinkedinProfileUrl() {
                try {
                  return (localStorage.getItem(LINKEDIN_PROFILE_URL_KEY) || "").trim();
                } catch (e) {
                  return "";
                }
              }

              function saveLinkedinProfileUrl(url) {
                const u = String(url || "").trim();
                if (!u || !/linkedin\\.com\\/in\\//i.test(u)) return;
                try {
                  localStorage.setItem(LINKEDIN_PROFILE_URL_KEY, u);
                } catch (e) { /* privado */ }
              }

              function applyStoredLinkedinProfileUrl() {
                if (!profileInput) return;
                const stored = getStoredLinkedinProfileUrl();
                if (stored && !profileInput.value.trim()) {
                  profileInput.value = stored;
                  profileInput.placeholder = "URL guardado — podes editar ou clicar Analisar";
                }
              }

"""

if "LINKEDIN_PROFILE_URL_KEY" not in h:
    h = h.replace(
        "              function escapeHtml(value) {",
        STORAGE_HELPERS + "              function escapeHtml(value) {",
    )

if "stored_linkedin_profile_url" not in h:
    h = h.replace(
        "                  const body = {\n                    supabase_access_token: session.access_token,\n                    linkedin_provider_token: session.provider_token || null,\n                  };",
        "                  const body = {\n                    supabase_access_token: session.access_token,\n                    linkedin_provider_token: session.provider_token || null,\n                    stored_linkedin_profile_url: getStoredLinkedinProfileUrl() || null,\n                  };",
    )
    h = h.replace(
        "                  if (res.ok && json.profile_url) {\n                    profileInput.value = json.profile_url;\n                    profileInput.placeholder = \"URL do perfil detectado — podes editar ou clicar Analisar\";\n                  }",
        "                  if (res.ok && json.profile_url) {\n                    profileInput.value = json.profile_url;\n                    saveLinkedinProfileUrl(json.profile_url);\n                    profileInput.placeholder = \"URL do perfil detectado — podes editar ou clicar Analisar\";\n                  }",
    )
    h = h.replace(
        "                if (linkedinProviderToken) {\n                  payload.linkedin_provider_token = linkedinProviderToken;\n                }",
        "                if (linkedinProviderToken) {\n                  payload.linkedin_provider_token = linkedinProviderToken;\n                }\n                const storedLi = getStoredLinkedinProfileUrl();\n                if (storedLi) {\n                  payload.stored_linkedin_profile_url = storedLi;\n                }",
    )

if "saveLinkedinProfileUrl(resolvedUrl)" not in h:
    h = h.replace(
        "                  attachTabHandlers();\n                } catch (err) {",
        "                  attachTabHandlers();\n                  const resolvedUrl = (data.public_profile_data || {}).perfil_input\n                    || (data.public_profile_data || {}).profile_url\n                    || profileInput.value.trim();\n                  if (resolvedUrl) saveLinkedinProfileUrl(resolvedUrl);\n                } catch (err) {",
    )

if "applyStoredLinkedinProfileUrl();" not in h:
    h = h.replace(
        "              refreshLinkedinSupabaseSession();",
        "              applyStoredLinkedinProfileUrl();\n              refreshLinkedinSupabaseSession();",
    )

h = h.replace(
    "Login com <strong>LinkedIn (OIDC)</strong> via Supabase e análise de perfil por URL pública.",
    "Login com <strong>LinkedIn (OIDC)</strong> confirma a tua identidade; na 1.ª vez cola o URL público do perfil (barra do LinkedIn) — depois fica guardado.",
)

out = ROOT / "agents" / "linkedin_perfil_page.py"
header = '''"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.

O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.
"""

from __future__ import annotations

LINKEDIN_PERFIL_PAGE_HTML: str = '''
footer = "\n"
out.write_text(header + json.dumps(h, ensure_ascii=False) + footer, encoding="utf-8")
print("Patched localStorage ->", out)
