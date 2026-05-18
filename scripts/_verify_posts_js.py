import json,re
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
i = h.find("function renderLinkedinPostsContainer")
print(h[i:i+3500])
print("--- motion count", h.count("<motion"))
