import json
from pathlib import Path
PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())
bad = (
    'if (hintEl) hintEl.textContent = "Inicia sessão para associar o teu perfil à conta.";\n\n                }\n                updateLinkedinAuthButtons(false);'
)
good = (
    'if (hintEl) hintEl.textContent = "Inicia sessão para associar o teu perfil à conta.";\n                updateLinkedinAuthButtons(false);'
)
if bad in h:
    h = h.replace(bad, good)
    PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
    print("fixed brace")
else:
    # try without newline variants
    h2 = h.replace("\n\n                }\n                updateLinkedinAuthButtons(false);", "\n                updateLinkedinAuthButtons(false);", 1)
    if h2 != h:
        PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("fixed brace alt")
    else:
        print("not found")
