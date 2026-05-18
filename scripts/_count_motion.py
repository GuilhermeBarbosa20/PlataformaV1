import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
print("motion open", h.count("<motion"))
print("motion close", h.count("</motion>"))
for i, line in enumerate(h.split("motion")):
    if "panel" in line[:30] or "</" in line[:5]:
        pass
idx = 0
while True:
    i = h.find("</motion>", idx)
    if i < 0: break
    print(repr(h[max(0,i-60):i+9]))
    idx = i + 1
