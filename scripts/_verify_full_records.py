import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
checks = [
    "resolveLinkedinMetricDetailValue",
    "linkedinHarvestListItemLine",
    "renderLinkedinProfileGridCard(k, v, pageKind, rawProfile)",
    "detailValue = resolveLinkedinMetricDetailValue",
    "linkedinHarvestListItemLine(item, pageKind)",
]
for c in checks:
    print(c, c in h)
# any old 3-arg calls left?
import re
old = len(re.findall(r"renderLinkedinProfileGridCard\(k, v, pageKind\)\)", h))
new = len(re.findall(r"renderLinkedinProfileGridCard\(k, v, pageKind, rawProfile\)", h))
null = len(re.findall(r"renderLinkedinProfileGridCard\(k, v, pageKind, null\)", h))
print("old 3-arg calls", old, "rawProfile", new, "null", null)
