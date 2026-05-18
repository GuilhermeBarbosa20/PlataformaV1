# -*- coding: utf-8 -*-
"""Remove duplicate HTML/JS leaked after premature </html>."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

# Markers
premature = h.find("            </script>\n          </body>\n        </html")
if premature < 0:
    premature = h.find("</script>\n          </body>\n        </html")

if premature < 0:
    raise SystemExit("premature close not found")

# Real document end
real_end = h.rfind("</html>")
if real_end <= premature:
    # only one </html> but with garbage after it without proper close
    # garbage is: </html> + duplicate panels + duplicate JS tail
    pass

# Find where duplicate tail ends - should be second bootstrap block + </script></body></html>
marker2 = "              (async function bootstrapLinkedinPage() {"
first_boot = h.find(marker2)
second_boot = h.find(marker2, first_boot + 10)
print("first_boot", first_boot, "second_boot", second_boot)

if second_boot > first_boot:
    # Remove from premature to second_boot (exclusive) - keep one bootstrap at end
    # Actually premature is AFTER first bootstrap - so structure is:
    # ... first bootstrap ... </script></body></html GARBAGE ... second bootstrap ... </script></body></html>
    real_close = h.rfind("            </script>\n          </body>\n        </html>")
    h_fixed = h[:premature] + "\n            </script>\n          </body>\n        </html>"
    print("removed bytes", len(h) - len(h_fixed))
    h = h_fixed
else:
    # garbage after </html without second bootstrap
    # truncate at premature + proper ending
    h_fixed = h[:premature] + "\n            </script>\n          </body>\n        </html>"
    # if there's more after malformed html, drop it
    after = h[premature:]
    if len(after) > 50:
        h = h_fixed
        print("truncated", len(after), "chars of garbage")

# Verify
assert h.count("</html>") == 1 or h.endswith("</html>"), h.count("</html>")
assert "${listSection(data.acoes_prioritarias)}" in h
# must be only in script
i = h.find("${listSection(data.acoes_prioritarias)}")
in_script = h.rfind("<script", 0, i) > h.rfind("</script>", 0, i)
assert in_script, "still outside script"
assert h.count("<script") == 1
assert h.count("</script>") == 1

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok len", len(h), "scripts", h.count("</script>"))
