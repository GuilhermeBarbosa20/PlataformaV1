# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
for fn in ["function appendLinkedinSessionFields", "function applyStoredLinkedinProfileUrl", "function loadLinkedinProfileForSession", "function getStoredLinkedinProfileUrl", "function saveLinkedinProfileUrl"]:
    i = h.find(fn)
    if i >= 0:
        print(f"\n=== {fn} ===\n")
        print(h[i:i+1200])
