import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=", 1)[1].strip())
i = h.find('id="panel-actions"')
print(h[i:i+1200])
