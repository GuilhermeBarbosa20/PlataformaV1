# -*- coding: utf-8 -*-
"""Corrige _patch_linkedin_publish_fixes para ler/gravar via ficheiro (sem import)."""

from pathlib import Path

PATCH = Path(__file__).resolve().parent / "_patch_linkedin_publish_fixes.py"
text = PATCH.read_text(encoding="utf-8")

old_main = '''def main() -> None:
    """Aplica patches ao HTML embutido do agente LinkedIn (perfil)."""

    sys.path.insert(0, str(ROOT))
    import agents.linkedin_perfil_page as mod

    h = mod.LINKEDIN_PERFIL_PAGE_HTML'''

new_main = '''def load_html() -> str:
    """Carrega o HTML embutido a partir do ficheiro (json.dumps)."""
    raw = PAGE_PATH.read_text(encoding="utf-8")
    _prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
    rest = rest.strip()
    if rest.startswith('"'):
        import json
        return json.loads(rest)
    import ast
    return ast.literal_eval(rest)


def save_html(h: str) -> None:
    """Grava o HTML em json.dumps para compatibilidade com outros patches."""
    import json
    header = PAGE_PATH.read_text(encoding="utf-8").split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[0]
    PAGE_PATH.write_text(
        header + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\\n",
        encoding="utf-8",
    )


def main() -> None:
    """Aplica patches ao HTML embutido do agente LinkedIn (perfil)."""

    h = load_html()'''

if old_main not in text:
    raise SystemExit("main() block not found in patch file")

text = text.replace(old_main, new_main, 1)

old_footer = '''    header = \'\'\'"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.

O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.
"""

from __future__ import annotations

LINKEDIN_PERFIL_PAGE_HTML: str = \'\'\'
    footer = "\\n"
    PAGE_PATH.write_text(header + repr(h) + footer, encoding="utf-8")
    print("ok", PAGE_PATH)'''

new_footer = '''    save_html(h)
    print("ok", PAGE_PATH)'''

if old_footer not in text:
    raise SystemExit("footer block not found")

text = text.replace(old_footer, new_footer, 1)
PATCH.write_text(text, encoding="utf-8")
print("patched loader in", PATCH)
