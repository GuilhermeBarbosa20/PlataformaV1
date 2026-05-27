import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
print("resolve count", h.count("function resolveLinkedinMetricDetailValue"))
print("linkedinHarvestListItemLine count", h.count("function linkedinHarvestListItemLine"))
print("linkedinHarvestCoerceText count", h.count("function linkedinHarvestCoerceText"))
print("item modal", "linkedinMetricItemDetailModal" in h)
print("listFromObjects", "linkedinMetricDetailListHtmlFromObjects" in h)

# check for duplicate function syntax errors - two resolve in a row?
idx = h.find("function resolveLinkedinMetricDetailValue")
print(h[idx : idx + 500])
