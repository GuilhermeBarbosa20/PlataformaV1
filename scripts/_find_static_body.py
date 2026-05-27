import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)

for needle in ["</body>", 'id="result"', "linkedinCalendarModal", "</html>"]:
    print(needle, h.find(needle))

# static calendar modal?
idx = h.find('id="linkedinCalendarModal"')
print("\nfirst calendar modal at", idx, "script at", h.find("<script"))
print("calendar in static?", idx < h.find("<script"))

# find good insertion point - before first script
script = h.find("<script")
print("\n--- 500 chars before first script ---")
print(h[script - 500 : script])
