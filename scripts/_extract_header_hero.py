import json
import re
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)

def extract_fn(name):
    m = re.search(rf"function {name}\([^)]*\)\s*\{{", h)
    if not m:
        return f"NOT FOUND: {name}"
    start = m.start()
    depth = 0
    i = h.find("{", m.start())
    for j in range(i, len(h)):
        if h[j] == "{":
            depth += 1
        elif h[j] == "}":
            depth -= 1
            if depth == 0:
                return h[start : j + 1]
    return "truncated"

Path("scripts/_renderHeader.txt").write_text(extract_fn("renderHeader"), encoding="utf-8")
Path("scripts/_renderPersonal.txt").write_text(
    extract_fn("renderLinkedinPersonalProfileOverview")[:8000], encoding="utf-8"
)
