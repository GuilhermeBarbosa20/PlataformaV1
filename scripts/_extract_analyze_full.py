# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
i = h.find("async function runLinkedinProfileAnalysis")
j = h.find("profileInput.addEventListener", i)
print(h[i:j])
