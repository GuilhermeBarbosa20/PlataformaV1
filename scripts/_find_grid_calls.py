import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
needle = "renderLinkedinProfileGridCard("
idx = 0
while True:
    i = h.find(needle, idx)
    if i < 0:
        break
    print(h[i : i + 90])
    idx = i + 1
