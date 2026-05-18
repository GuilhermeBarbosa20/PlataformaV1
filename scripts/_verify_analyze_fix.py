import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
print("profileInput.value = stored", "profileInput.value = stored" in h)
print("useSessionProfile true assign", h.count("useSessionProfile = true"))
i = h.find("async function runLinkedinProfileAnalysis")
print(h[i:i+2200])
