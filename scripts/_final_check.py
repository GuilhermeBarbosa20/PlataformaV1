import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
checks = {
    "no A gerar in static template": 'A gerar posts' not in h.split("panel-actions")[1].split("btnGenerate")[0],
    "reset once": h.count("function resetLinkedinPostsAfterAnalysis") == 1,
    "hook": "setLinkedinAnalysisSnapshot(data);\n                  resetLinkedinPostsAfterAnalysis();" in h,
    "btnDone": "btnDone.textContent" in h,
    "btnErr": "btnErr.textContent" in h,
    "evolution acoes": 'data-section="acoes-prioritarias"' in h,
    "evolution plano": 'data-section="plano-crescimento"' in h,
    "actions only posts": "Posts para publicar" in h and "acoes_prioritarias" not in h[h.find("panel-actions"):h.find("panel-content")],
    "panel-content": 'id="panel-content"' in h,
    "no motion tags": "<motion" not in h and "</motion>" not in h,
    "no broken div": "<motion <" not in h and "<div <div" not in h,
}
print(checks)
print("all ok:", all(checks.values()))
