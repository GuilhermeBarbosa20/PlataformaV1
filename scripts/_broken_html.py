import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)

idx = h.find('id="linkedinMetricDetailModal"')
print(h[idx - 200 : idx + 900])

# find autoAuthenticated ternary boundaries near modal
start = h.rfind("${autoAuthenticated", 0, idx)
end = h.find("` : \"\"", idx)
print("\nautoAuth block starts", start)
print("ternary end after modal", end)
print(h[end : end + 80] if end >= 0 else "no end")
