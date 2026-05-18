# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())

garbage_start = h.find("            </script>\n          </body>\n        </html")
print("garbage_start", garbage_start)
print("snippet:", repr(h[garbage_start:garbage_start+100]))

# Find second </script>
s2 = h.find("</script>", garbage_start + 10)
print("second script at", s2)
print("between:", repr(h[garbage_start:s2+20]))

# The fix: keep everything up to and including bootstrap end BEFORE first </script>
# Actually first </script> should be removed along with </body></html and duplicate until second </script> is removed too - we only want ONE closing

# Correct end should be: bootstrap ends, then </script></body></html>
# So delete from first </script> to second </script> exclusive, but the duplicate content between includes a DUPLICATE tail of functions

# Simpler fix: 
# h_fixed = h[:garbage_start] + h[s2:]  # removes first </script> through start of second </script>
# But then we'd have two </script> - we need h[:garbage_start] + "\n            </script>\n          </body>\n        </html>"

# What's BEFORE garbage_start - should end with })();
before = h[garbage_start-80:garbage_start]
print("\nbefore garbage:", repr(before))
