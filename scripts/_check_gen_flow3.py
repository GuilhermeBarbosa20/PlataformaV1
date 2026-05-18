import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
idx = h.find("runLinkedinProfileAnalysis")
chunk = h[idx:idx+25000]
print("setLinkedin", "setLinkedinAnalysisSnapshot" in chunk)
print("reset", "resetLinkedinPostsAfterAnalysis" in chunk)
k = chunk.find("attachTabHandlers();")
print(chunk[k:k+200])
