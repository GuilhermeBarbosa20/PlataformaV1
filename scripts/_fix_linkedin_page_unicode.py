"""Corrige surrogates no HTML do agente LinkedIn e regrava o ficheiro .py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML  # noqa: E402


def _fix_surrogates(text: str) -> str:
    """Remove caracteres surrogate inválidos para UTF-8 HTTP."""

    return text.encode("utf-16", "surrogatepass").decode("utf-16")


def _ascii_safe_emojis(text: str) -> str:
    """Substitui emojis problemáticos por texto ASCII na UI."""

    return (
        text.replace("\ud83d\udcac", "com.")
        .replace("💬", "com.")
        .replace("♥", "likes")
        .replace("▶", "plays")
    )


h = _ascii_safe_emojis(_fix_surrogates(LINKEDIN_PERFIL_PAGE_HTML))

header = '''"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.

O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.
"""

from __future__ import annotations

LINKEDIN_PERFIL_PAGE_HTML: str = '''
footer = "\n"
out = ROOT / "agents" / "linkedin_perfil_page.py"
out.write_text(header + json.dumps(h, ensure_ascii=False) + footer, encoding="utf-8")

# verificar
fixed = out.read_text(encoding="utf-8")
assert "LINKEDIN_PERFIL_PAGE_HTML" in fixed
exec(compile(fixed, str(out), "exec"), {})
html = sys.modules.get("agents.linkedin_perfil_page")
import importlib
import agents.linkedin_perfil_page as mod

importlib.reload(mod)
mod.LINKEDIN_PERFIL_PAGE_HTML.encode("utf-8")
print("OK: linkedin_perfil_page.py UTF-8 válido")
