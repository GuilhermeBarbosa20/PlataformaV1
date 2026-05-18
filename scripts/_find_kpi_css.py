import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
i = h.find(".kpi-grid")
print(h[i:i+600])
i2 = h.find("function renderKpis")
print("\nrenderKpis at", i2)
