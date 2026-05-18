import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
for needle in ["profileInput", "myProfileInput", "Analisar", "Auto-an", "outro", "meu perfil", "li-field-label"]:
    i = h.find(needle)
    if i >= 0:
        Path("scripts/_snippet.txt").write_text(h[max(0,i-300):i+400], encoding="utf-8")
        break
# write form section
i = h.find("li-analyze-form")
Path("scripts/_form_snippet.txt").write_text(h[i-800:i+900], encoding="utf-8")
print("written")
