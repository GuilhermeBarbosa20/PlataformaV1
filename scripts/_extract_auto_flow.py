import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=", 1)[1].strip())
for n in ["autoAuthenticated", "profileValue = \"\"", "tryResolveLinkedinProfileUrl", "stored_linkedin"]:
    i = h.find(n)
    print("===", n)
    if i >= 0:
        print(h[i:i+800])
    print()
