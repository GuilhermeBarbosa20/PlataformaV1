import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
for needle in ["closeLinkedinMetricDetailModal", "keydown", "linkedinMetricDetailModal"]:
    idx = h.find(needle)
    while idx >= 0 and idx < 200000:
        if needle == "keydown" and "Escape" not in h[idx:idx+200]:
            idx = h.find(needle, idx + 1)
            continue
        print("---", needle, idx, "---")
        print(h[idx : idx + 450])
        break
    else:
        idx = h.find(needle)
        if idx >= 0:
            print("---", needle, idx, "---")
            print(h[idx : idx + 450])

# static modals
static = h.split("<script")[0]
print("item modal in static", "linkedinMetricItemDetailModal" in static)
print("metric modal in static", "linkedinMetricDetailModal" in static)
