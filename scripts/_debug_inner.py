import json
import re
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)

pos = h.find("innerHTML = `", 174000)
print(h[pos - 800 : pos + 200])
print("\n--- after innerHTML start (2500) ---")
print(h[pos : pos + 2500])

# find closing of this template
start = pos + len("innerHTML = `")
depth = 0
i = start
while i < len(h):
    if h[i] == "`" and (i == 0 or h[i - 1] != "\\"):
        # check not ${}
        break
    i += 1
print("\n--- template ends around", i, "---")
print(h[i - 100 : i + 200])
