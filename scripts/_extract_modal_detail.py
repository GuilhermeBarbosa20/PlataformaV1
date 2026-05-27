import json
import re
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)

for name in [
    "linkedinMetricRegisterDetail",
    "linkedinMetricDetailBodyHtml",
    "renderLinkedinProfileGridCard",
    "harvestRawProfile",
    "linkedinProfileMetricRaw",
]:
    m = re.search(rf"function {name}\([^)]*\)\s*\{{", h)
    if not m:
        print(name, "NOT FOUND")
        continue
    start = m.start()
    depth = 0
    i = h.find("{", m.start())
    for j in range(i, len(h)):
        if h[j] == "{":
            depth += 1
        elif h[j] == "}":
            depth -= 1
            if depth == 0:
                Path(f"scripts/_{name}.txt").write_text(h[start : j + 1], encoding="utf-8")
                print(name, "ok", j - start)
                break
