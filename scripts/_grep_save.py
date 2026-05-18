import json,re
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=", 1)[1].strip())
m = re.search(r"saveLinkedinProfileUrl\([^)]+\)", h)
print(m.group(0) if m else "none")
i = h.find("saveLinkedinProfileUrl")
print(h[i-80:i+200])
