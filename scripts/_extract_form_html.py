# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
for needle in ["profileInput", "myProfileInput", "Analisar", "Auto-análise", "outro perfil", "meu perfil"]:
    i = h.find(needle)
    while i >= 0:
        print(f"\n--- {needle} @ {i} ---")
        print(h[max(0,i-150):i+250])
        i = h.find(needle, i+1)
        if needle in ("profileInput", "myProfileInput") and i > 0 and h.find(needle, i) - i > 5000:
            break
