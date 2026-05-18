import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
lines = h.split("\n")
# approximate - html is one line in json. search for onclick around runLinkedin
idx = h.find("onclick=\"runLinkedinProfileAnalysis()\"")
print("Analisar onclick at char", idx)
print(h[idx-200:idx+100])
idx2 = h.find("runLinkedinAutoProfileAnalysis")
print("Auto at", idx2, h[idx2:idx2+120])
