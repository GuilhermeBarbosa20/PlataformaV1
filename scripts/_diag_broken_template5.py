# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
pos = 0
while True:
    i = h.find("</html>", pos)
    if i < 0: break
    print(f"</html> at {i} context: {repr(h[max(0,i-40):i+20])}")
    pos = i + 1

pos = 0
while True:
    i = h.find("</script>", pos)
    if i < 0: break
    print(f"</script> at {i}")
    pos = i + 1

# content at 83260
print("\n83200-83400:", repr(h[83200:83400]))
