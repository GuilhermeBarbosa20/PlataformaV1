import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
for needle in [
    "close-metric-detail",
    "data-detail-id",
    "ensureLinkedin",
    'document.addEventListener("click"',
]:
    print(needle, h.count(needle))

i = h.find("close-metric-detail")
if i >= 0:
    # find click listener near it
    j = h.rfind('document.addEventListener("click"', 0, i + 5000)
    k = h.find('document.addEventListener("click"', i)
    print("click before", j, "click after", k)
    if k >= 0:
        Path("scripts/_click_handler.txt").write_text(h[k : k + 1200], encoding="utf-8")
