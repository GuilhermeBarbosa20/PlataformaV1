import json
import re
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
m = re.search(r"function renderLinkedinMetricCards\([^)]*\)\s*\{", h)
if m:
    start = m.start()
    depth = 0
    i = h.find("{", m.start())
    for j in range(i, len(h)):
        if h[j] == "{":
            depth += 1
        elif h[j] == "}":
            depth -= 1
            if depth == 0:
                Path("scripts/_metric_cards_fn.txt").write_text(h[start : j + 1], encoding="utf-8")
                break
print("onclick expandable", h.count('is-expandable" role="button"'))
print("data-detail-id", h.count("data-detail-id"))
