import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
print(h[h.find("async function tryResolveLinkedinProfileUrl"):h.find("async function tryResolveLinkedinProfileUrl")+1200])
