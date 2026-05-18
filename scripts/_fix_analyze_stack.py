import json
from pathlib import Path
PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())
h = h.replace(
    ".analyze-actions {\n                display: grid;\n                grid-template-columns: 1fr 1fr;\n                gap: 10px;\n              }",
    ".analyze-actions {\n                display: flex;\n                flex-direction: column;\n                gap: 10px;\n              }",
)
h = h.replace(
    "@media (max-width: 780px) {\n                .hero-layout { grid-template-columns: 1fr; }\n                .li-my-profile-form { grid-template-columns: 1fr; }\n                .analyze-actions { grid-template-columns: 1fr; }\n              }",
    "@media (max-width: 780px) {\n                .hero-layout { grid-template-columns: 1fr; }\n                .li-my-profile-form { grid-template-columns: 1fr; }\n              }",
)
# logout status text
h = h.replace(
    'el.innerHTML = \'<span class="dot"></span> LinkedIn: sem sessão\';',
    'el.innerHTML = \'<span class="dot"></span> Não autenticado\';',
)
PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
