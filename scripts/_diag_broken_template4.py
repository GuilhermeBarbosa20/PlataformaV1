# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
print("Total len", len(h))
# first </html>
i = h.find("</html>")
print("first </html> at", i)
print("last 500 chars:", repr(h[-500:]))
# everything after first </html>
garbage = h[i+7:]
print("garbage len", len(garbage))
print("garbage start:", repr(garbage[:400]))
print("garbage end:", repr(garbage[-400:]))
