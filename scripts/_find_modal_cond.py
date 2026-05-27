import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)

idx = h.find('id="linkedinMetricDetailModal"')
# walk back for ${ autoAuthenticated or similar
back = h[max(0, idx - 3000) : idx]
for needle in ["${autoAuthenticated", "${ autoAuthenticated", "` : \"\"", "panel-calendar"]:
    print(needle, back.rfind(needle))

print("\n--- 2500 before modal ---")
print(back[-2500:])

# after modal
print("\n--- 400 after modal ---")
print(h[idx : idx + 400])
