import json
import re
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)

for needle in ["Confian", "Qualidade", "renderHeader", "li-profile-hero-stats", "badge info", "data_quality", "confidence"]:
    idx = 0
    count = 0
    while True:
        i = h.find(needle, idx)
        if i < 0:
            break
        count += 1
        if count <= 2:
            print(f"\n--- {needle} #{count} at {i} ---")
            print(h[max(0, i - 120) : i + 280])
        idx = i + 1
    print(f"{needle}: {count} matches")
