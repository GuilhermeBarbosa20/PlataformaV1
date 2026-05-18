"""UI quando OAuth LinkedIn não obtém URL automático (?auth=need_url)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML  # noqa: E402

h = LINKEDIN_PERFIL_PAGE_HTML
d = "motion"  # placeholder
d = "div"

HANDLER = f"""
              function handleLinkedinAuthQuery() {{
                const params = new URLSearchParams(window.location.search);
                const auth = params.get("auth");
                if (auth === "need_url") {{
                  if (profileInput) {{
                    profileInput.focus();
                    profileInput.placeholder = "Cola o URL do teu perfil (barra do LinkedIn) — só desta vez";
                  }}
                  if (result) {{
                    result.innerHTML = "<{d} class=\\"err\\"><strong>Quase lá:</strong> o LinkedIn entrou. Cola o URL do perfil (barra do LinkedIn) e clica <strong>Analisar</strong>.</{d}>";
                  }}
                  const el = document.getElementById("linkedinAuthStatus");
                  if (el) {{ el.className = "badge warn"; el.innerHTML = "<span class=\\"dot\\"></span> LinkedIn: cola o URL"; }}
                }} else if (auth === "ok") {{
                  const el = document.getElementById("linkedinAuthStatus");
                  if (el) {{ el.className = "badge ok"; el.innerHTML = "<span class=\\"dot\\"></span> LinkedIn: ligado"; }}
                }} else if (auth === "error") {{
                  const reason = (params.get("reason") || "erro").replace(/_/g, " ");
                  if (result) {{
                    result.innerHTML = "<{d} class=\\"err\\"><strong>Erro:</strong> " + escapeHtml(decodeURIComponent(reason)) + "</{d}>";
                  }}
                }}
                if (auth) {{ window.history.replaceState({{}}, "", window.location.pathname); }}
              }}

"""

if "function handleLinkedinAuthQuery()" not in h:
    h = h.replace(
        "              applyStoredLinkedinProfileUrl();\n              refreshLinkedinAuthStatus();",
        "              applyStoredLinkedinProfileUrl();\n              handleLinkedinAuthQuery();\n              refreshLinkedinAuthStatus();",
    )
    h = h.replace("              function applyStoredLinkedinProfileUrl() {", HANDLER + "              function applyStoredLinkedinProfileUrl() {")

if "data.needs_profile_url" not in h:
    h = h.replace(
        "                  if (data.connected) {",
        "                  if (data.needs_profile_url) {\n"
        "                    el.className = \"badge warn\";\n"
        "                    el.innerHTML = \"<span class=\\\"dot\\\"></span> LinkedIn: cola o URL do perfil\";\n"
        "                    return;\n"
        "                  }\n"
        "                  if (data.connected) {",
        1,
    )
    h = h.replace(
        "linkedinConnected = Boolean(stData.connected);",
        "linkedinConnected = Boolean(stData.connected || stData.authenticated || stData.needs_profile_url);",
    )

out = ROOT / "agents" / "linkedin_perfil_page.py"
header = '''"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.

O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.
"""

from __future__ import annotations

LINKEDIN_PERFIL_PAGE_HTML: str = '''
footer = "\n"
out.write_text(header + json.dumps(h, ensure_ascii=False) + footer, encoding="utf-8")
print("Patched need_url ->", out)
