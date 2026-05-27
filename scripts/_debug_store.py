import json
import re
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)

for pat in [
    "linkedinMetricDetailStore",
    "const linkedinMetricDetailStore",
    "let linkedinMetricDetailStore",
    "var linkedinMetricDetailStore",
]:
    print(pat, h.count(pat))

# modal HTML structure
idx = h.find('id="linkedinMetricDetailModal"')
print("modal idx", idx)
if idx >= 0:
    print(h[idx : idx + 1200])

# check for overlay on profile
for sel in [".li-profile-overview", ".li-profile-section", ".li-metrics-grid"]:
    i = h.find(sel + " {")
    if i < 0:
        i = h.find(sel)
    print(sel, "found", i >= 0)

# errors: unclosed template in script?
# Check if openLinkedinMetricDetailModal is exposed on window
print("window.openLinkedin", "window.openLinkedinMetricDetailModal" in h)

# duplicate const linkedinMetricDetailStore causing error?
matches = [m.start() for m in re.finditer(r"linkedinMetricDetailStore\s*=", h)]
print("assignments", len(matches))
