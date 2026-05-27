import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)

idx = h.find('id="linkedinMetricDetailModal"')
# find enclosing script tag
script_start = h.rfind("<script", 0, idx)
script_end = h.find("</script>", idx)
print("modal at", idx)
print("script_start before modal", script_start)
print("script_end after modal", script_end)
print("inside script?", script_start >= 0 and (script_end < 0 or script_end > idx))

# static HTML: find </body>
body_end = h.find("</body>")
print("body_end", body_end, "modal before body_end?", idx < body_end)

# snippet around script_start
if script_start >= 0:
    print("\nscript context:", repr(h[script_start : script_start + 80]))
