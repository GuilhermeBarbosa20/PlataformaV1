# -*- coding: utf-8 -*-
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

i = h.find("function renderTabs()")
j = h.find("function attachTabHandlers()", i)
if i < 0:
    raise SystemExit("renderTabs not found")

new_block = (
    "              function renderTabs(showPostsTab) {\n"
    "                const postsTab = showPostsTab\n"
    '                  ? \'<div class="tab" data-target="posts">Posts</div>\'\n'
    '                  : "";\n'
    "                return `\n"
    '                  <div class="tabs">\n'
    '                    <div class="tab active" data-target="overview">Visão Geral</div>\n'
    "                    ${postsTab}\n"
    '                    <div class="tab" data-target="content">Tipos de conteúdo</div>\n'
    '                    <div class="tab" data-target="evolution">Plano &amp; Ações</motion>\n'
    "                  </div>\n"
    "                `;\n"
    "              }\n\n"
)
new_block = new_block.replace("</motion>\n", "</div>\n")

h = h[:i] + new_block + h[j:]
h = h.replace("${renderTabs()}", "${renderTabs(autoAuthenticated)}")

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "showPostsTab" in h, "panel-posts" in h, "Ações &amp; Ideias" not in h)
