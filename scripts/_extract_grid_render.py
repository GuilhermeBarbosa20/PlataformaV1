import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
for term in [
    "function renderLinkedinPersonalProfileOverview",
    "function renderLinkedinCompanyProfileOverview",
    "function renderLinkedinMetricValueHtml",
    "li-cal-modal",
    "gridEntries.map",
]:
    i = h.find(term)
    if i >= 0:
        Path("scripts/_ext.txt").open("a", encoding="utf-8").write(f"\n\n=== {term} @ {i} ===\n")
        Path("scripts/_ext.txt").open("a", encoding="utf-8").write(h[i : i + 3500])
