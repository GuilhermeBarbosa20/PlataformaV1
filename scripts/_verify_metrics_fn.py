import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
i = h.find("function renderLinkedinMetricCards")
print(h[i:i+2200])
print("\nmotion tags:", h.count("<motion"), h.count("</motion>"))
print("tab:", "Plano" in h[h.find("data-target=\"evolution\""):h.find("data-target=\"evolution\"")+80])
