import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
for needle in [".analysis-header", ".header-badges", ".badge.ok", ".badge {"]:
    i = h.find(needle)
    if i >= 0:
        print(f"\n--- {needle} ---")
        print(h[i : i + 500])

# company overview
import re
m = re.search(r"function renderLinkedinCompanyProfileOverview", h)
if m:
    i = m.start()
    print("\n--- company hero stats ---")
    chunk = h[i : i + 3500]
    j = chunk.find("li-profile-hero-stats")
    if j >= 0:
        print(chunk[j : j + 400])
