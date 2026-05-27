import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
idx = 0
while True:
    i = h.find("renderHeader", idx)
    if i < 0:
        break
    print(repr(h[i : i + 60]))
    idx = i + 1
