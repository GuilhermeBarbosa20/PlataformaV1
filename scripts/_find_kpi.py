import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
for s in ["renderHeaderKpis", "LIGAÇÕES", "metric-grid", "enrich-pill"]:
    print(s, h.find(s))
