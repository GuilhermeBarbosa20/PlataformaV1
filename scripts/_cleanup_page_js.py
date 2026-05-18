# -*- coding: utf-8 -*-
import json
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = p.read_text(encoding="utf-8")
pre, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

h = h.replace(
    "`.replace(/</motion>/g, \"</motion>\").replace(/<motion/g, \"<motion\").replace(/<div class=\"li-metric-value\">/g, '<motion class=\"li-metric-value\">');",
    "`;",
)
h = h.replace(
    "`.replace(/</motion>/g, \"</div>\").replace(/<motion/g, \"<motion\").replace(/<motion class=\"li-metric-value\">/g, '<motion class=\"li-metric-value\">');",
    "`;",
)
h = h.replace(
    "`.replace(/</motion>/g, \"</div>\").replace(/<motion/g, \"<motion\").replace(/<div class=\"li-metric-value\">/g, '<motion class=\"li-metric-value\">');",
    "`;",
)
h = h.replace(
    "`.replace(\"<div class=\\\"metric-pills\\\">\", '<div class=\"metric-pills\">'.replace(\"motion\", \"motion\")).replace('</div>`', '</div>`');",
    "`;",
)
h = h.replace(
    "`.replace(/<div class=\"tab\"/g, '<div class=\"tab\"').replace(\"</div>\", \"</motion>\");",
    "`;",
)
h = h.replace(
    "`.replace(/<div class=\"tab\"/g, '<div class=\"tab\"').replace(\"</div>\", \"</motion>\");",
    "`;",
)
h = h.replace(
    "`.replace(\"<div class=\\\"spinner\\\"></div>\", '<div class=\"spinner\"></div>').replace('</div>', '</div>');",
    "`;",
)
h = h.replace(
    "return `<motion class=\"metric-pills\"><span class=\"metric-pill\">Sem datas nas publicações recolhidas.</span></motion>`;",
    'return `<div class="metric-pills"><span class="metric-pill">Sem datas nas publicações recolhidas.</span></div>`;',
)

p.write_text(pre + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", h.count("`.replace("))
