import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=", 1)[1].strip())
i = h.find('<motion class="form li-only-form"')
if i < 0:
    i = h.find('class="form li-only-form"')
print(h[i:i+2200])
print("---")
j = h.find('class="auth-row li-auth-row"')
print(h[j:j+1200])
