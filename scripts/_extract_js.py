import json
import re
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)

funcs = [
    "linkedinMetricNeedsDetailModal",
    "linkedinMetricCardPreview",
    "linkedinMetricDetailBodyHtml",
    "linkedinMetricRegisterDetail",
    "openLinkedinMetricDetailModal",
    "closeLinkedinMetricDetailModal",
    "renderLinkedinProfileGridCard",
    "renderLinkedinPersonalProfileOverview",
    "renderLinkedinHarvestProfileOverview",
]

Path("scripts/_extract_out.txt").write_text("", encoding="utf-8")
for name in funcs:
    m = re.search(rf"function {name}\([^)]*\)\s*\{{", h)
    if not m:
        print(f"\n=== {name}: NOT FOUND ===")
        continue
    start = m.start()
    depth = 0
    i = h.find("{", m.start())
    for j in range(i, len(h)):
        if h[j] == "{":
            depth += 1
        elif h[j] == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    else:
        end = start + 2000
    snippet = h[start:end]
    out = Path("scripts/_extract_out.txt")
    with out.open("a", encoding="utf-8") as f:
        f.write(f"\n=== {name} ({len(snippet)} chars) ===\n")
        f.write(snippet[:5000])
        if len(snippet) > 5000:
            f.write("\n... [truncated]\n")

# CSS for expandable
for pat in [".li-metric-card.is-expandable", "linkedinMetricDetailModal", "pointer-events"]:
    idx = h.find(pat)
    if idx >= 0:
        with Path("scripts/_extract_out.txt").open("a", encoding="utf-8") as f:
            f.write(f"\n--- CSS/fragment {pat} ---\n")
            f.write(h[max(0, idx - 80) : idx + 400])
