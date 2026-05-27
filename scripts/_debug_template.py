import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)

idx = h.find('id="linkedinMetricDetailModal"')
# walk back to find template start `${ or ` 
chunk = h[max(0, idx - 5000) : idx + 500]
# find last occurrence of ` : ""} before modal
for marker in ["` : \"\"", "` : ''", "innerHTML = `", "return `"]:
    pos = chunk.rfind(marker)
    if pos >= 0:
        print(marker, "at offset", pos, "abs", max(0, idx - 5000) + pos)

# show 300 chars before modal including backticks
print("\n--- 600 chars before modal ---")
print(h[idx - 600 : idx])
