# -*- coding: utf-8 -*-
"""Escreve linkedin_perfil_page.py sem duplicar a declaração da variável."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
if "LINKEDIN_PERFIL_PAGE_HTML: str = " not in raw:
    raise SystemExit("formato inesperado")
head, _, rest = raw.partition("LINKEDIN_PERFIL_PAGE_HTML: str = ")
# head ends with docstring + from __future__ ... \n\n
# rest is JSON string + optional newline
html = json.loads(rest.strip())
out = (
    '"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.\n\n'
    "O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.\n"
    '"""\n\n'
    "from __future__ import annotations\n\n"
    "LINKEDIN_PERFIL_PAGE_HTML: str = "
    + json.dumps(html, ensure_ascii=False)
    + "\n"
)
PAGE.write_text(out, encoding="utf-8")
print("written", len(html))
