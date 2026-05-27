import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
print("modal in html", "linkedinMetricDetailModal" in h)
print("expandable onclick count", h.count("openLinkedinMetricDetailModal"))
print("data-detail-id count", h.count("data-detail-id"))
print("personal fn count", h.count("function renderLinkedinPersonalProfileOverview"))
print("grid card fn count", h.count("function renderLinkedinProfileGridCard"))

# tab switching
idx = h.find("querySelectorAll(\".tab\")")
if idx < 0:
    idx = h.find("querySelectorAll('.tab')")
print("tab qs", idx)
if idx >= 0:
    print(h[idx : idx + 500])

# is-long-text overflow blocking?
idx = h.find(".li-metric-card.is-long-text")
if idx >= 0:
    print(h[idx : idx + 200])
