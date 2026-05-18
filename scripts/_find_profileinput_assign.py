# -*- coding: utf-8 -*-
import json,re
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
for m in re.finditer(r"profileInput\.value\s*=", h):
    print(h[max(0,m.start()-100):m.start()+120])
