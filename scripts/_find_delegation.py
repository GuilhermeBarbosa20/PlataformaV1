import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
i = h.find("function ensureLinkedinMetricDetailModal")
print("idx", i)
if i >= 0:
    Path("scripts/_delegation2.txt").write_text(h[i : i + 2000], encoding="utf-8")
