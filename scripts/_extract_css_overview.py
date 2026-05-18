# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
for pat in [".metric-pill", "panel-overview", "Performance (LinkedIn)", "Métricas específicas"]:
    i = h.find(pat)
    if i >= 0:
        print(f"\n=== {pat} @ {i} ===")
        print(h[max(0,i-80):i+400])
