import json
import re
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
m = re.search(r"function renderLinkedinCompanyProfileOverview\([^)]*\)\s*\{", h)
start = m.start()
depth = 0
i = h.find("{", m.start())
for j in range(i, len(h)):
    if h[j] == "{":
        depth += 1
    elif h[j] == "}":
        depth -= 1
        if depth == 0:
            Path("scripts/_company.txt").write_text(h[start : j + 1], encoding="utf-8")
            break
