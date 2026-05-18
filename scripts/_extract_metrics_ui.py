# -*- coding: utf-8 -*-
import json,re
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())

for pat in ["Evolução", "data-target=\"evolution\"", "renderMetricPills", "function renderMetricPills", "metricas_universais", "metricas_linkedin"]:
    i = h.find(pat)
    print(pat, i)
    if i >= 0 and "function" in pat:
        print(h[i:i+1500])
        print("---")

# tabs
i = h.find('class="tabs"')
print("\ntabs:", h[i:i+600])
