import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
funcs = [
    "linkedinHarvestCoerceText",
    "linkedinHarvestItemHasDetail",
    "openLinkedinMetricItemDetailModal",
    "linkedinMetricItemRegisterDetail",
    "linkedinMetricDetailListHtmlFromObjects",
]
for f in funcs:
    print(f, h.count(f"function {f}"))

i = h.find("function resolveLinkedinMetricDetailValue")
j = h.find("function linkedinMetricRegisterDetail")
print("bytes between resolve and register", j - i)
Path("scripts/_between.txt").write_text(h[i:j][:4000], encoding="utf-8")
