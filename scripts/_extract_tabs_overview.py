# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())

# tabs
i = h.find('class="tabs"')
print("TABS:\n", h[i:i+400])

# panel-actions
pa = h.find('id="panel-actions"')
pc = h.find('id="panel-content"')
pe = h.find('id="panel-evolution"')
po = h.find('id="panel-overview"')
print("\n=== ACTIONS ===\n", h[pa:pc][:1500])
print("\n=== OVERVIEW (metrics part) ===\n")
om = h.find("Indicadores de desempenho")
print(h[om-200:om+1200])
print("\n=== EVOLUTION ===\n", h[pe:pe+800])
