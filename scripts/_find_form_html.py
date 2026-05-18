import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
idx = h.find("li-analyze-form")
# find in HTML not CSS - search for class="form li-analyze
idx = h.find('class="form li-analyze-form"')
print("idx", idx)
if idx >= 0:
    Path(r"C:\Users\Gui\Desktop\Cursor Teste\PlataformaV1\scripts\_form_html.txt").write_text(h[idx-500:idx+2000], encoding="utf-8")
