import json
from pathlib import Path
PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())
old = "return noHash.replace(/\\/$/, \"\");\n                }\n                return \"\";"
new = "const u = noHash.replace(/\\/$/, \"\");\n                  return /^https?:\\/\\//i.test(u) ? u : \"https://\" + u.replace(/^\\/+/, \"\");\n                }\n                return \"\";"
if old in h:
    h = h.replace(old, new, 1)
    print("ok https fix")
else:
    print("pattern not found")
PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
