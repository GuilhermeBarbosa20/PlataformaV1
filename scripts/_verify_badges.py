import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
print("helper", "renderLinkedinAnalysisQualityBadges" in h)
print("hero badges in personal", "renderLinkedinAnalysisQualityBadges(ctx)" in h)
print("header call removed", "renderHeader(data)" not in h)
print("analysis-header in return", h.count('class="analysis-header"'))
i = h.find("renderLinkedinAnalysisQualityBadges(ctx)")
print(h[max(0, i - 200) : i + 120])
