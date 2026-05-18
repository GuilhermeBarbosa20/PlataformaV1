import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=", 1)[1].strip())
for n in ["id=\"btnAutoAnalyze\"", "btn-auto-analyze", "Auto-análise", "updateAutoAnalyzeButton"]:
    idx = h.find(n) if n != "Auto-análise" else h.find("Auto-an")
    print(n, idx)
    if idx >= 0:
        print(repr(h[idx:idx+120]))
        print()
