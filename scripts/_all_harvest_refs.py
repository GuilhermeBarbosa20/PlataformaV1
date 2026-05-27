import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
needle = "renderLinkedinHarvestProfileOverview"
idx = 0
while True:
    i = h.find(needle, idx)
    if i < 0:
        break
    ctx = h[max(0, i - 30) : i + 80].replace("\n", " ")
    print(i, repr(ctx))
    idx = i + len(needle)
