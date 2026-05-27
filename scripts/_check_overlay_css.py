import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
for sel in [
    ".li-profile-overview",
    ".li-metrics-grid",
    ".li-metrics-section",
    "#result",
    ".results",
    ".panel.active",
]:
    idx = h.find(sel)
    while idx >= 0:
        chunk = h[idx : idx + 400]
        if "pointer-events" in chunk[:300]:
            print("---", sel, "---")
            print(chunk[:350])
        idx = h.find(sel, idx + 1)
