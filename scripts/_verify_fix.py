import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
static = h.split("<script")[0]
print("modal in static", "linkedinMetricDetailModal" in static)
print("modal count", h.count("linkedinMetricDetailModal"))
print("data-detail-id", h.count("data-detail-id"))
print("onclick openLinkedin", h.count("openLinkedinMetricDetailModal("))
print("EXPANDABLE_KEYS", "LINKEDIN_EXPANDABLE_METRIC_KEYS" in h)
i = static.find("linkedinMetricDetailModal")
if i >= 0:
    print(static[max(0, i - 80) : i + 250])
