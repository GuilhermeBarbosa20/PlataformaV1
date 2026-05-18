# -*- coding: utf-8 -*-
import json,re
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())

i = h.find("async function runLinkedinProfileAnalysis")
print(h[i:i+4500])
print("\n--- btnAnalyze ---")
for pat in ["btnAnalyze", "btnAutoAnalyze", "profileInput", "myProfileInput", "stored_linkedin", "link_as_own"]:
    print(pat, h.count(pat))
