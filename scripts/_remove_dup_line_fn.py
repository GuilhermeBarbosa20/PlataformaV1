import json
import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"

raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

matches = list(re.finditer(r"function linkedinHarvestListItemLine\(item, pageKind\) \{", h))
print("matches", len(matches))
if len(matches) < 2:
    print("no duplicate to remove")
    exit(0)

# Remove first (old) occurrence - find which is old (uses String(item.company) without CoerceText)
for i, m in enumerate(matches):
    end = m.end()
    snippet = h[m.start() : m.start() + 800]
    has_coerce = "linkedinHarvestCoerceText" in snippet
    print(i, "coerce", has_coerce, "at", m.start())

# Remove the one WITHOUT linkedinHarvestCoerceText in first 400 chars
to_remove = None
for m in matches:
    snippet = h[m.start() : m.start() + 600]
    if "linkedinHarvestCoerceText" not in snippet:
        to_remove = m
        break

if not to_remove:
    # remove second duplicate (keep first new block)
    to_remove = matches[1]

start = to_remove.start()
depth = 0
i = h.find("{", to_remove.start())
for j in range(i, len(h)):
    if h[j] == "{":
        depth += 1
    elif h[j] == "}":
        depth -= 1
        if depth == 0:
            end = j + 1
            break
else:
    raise SystemExit("could not find end")

h = h[:start] + h[end:]
PAGE.write_text(
    prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print("removed old linkedinHarvestListItemLine at", start)
print("remaining count", h.count("function linkedinHarvestListItemLine"))
