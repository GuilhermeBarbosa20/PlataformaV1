import json
from pathlib import Path
_, rest = (Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())
start = h.find("async function runLinkedinProfileAnalysis")
end = h.find("profileInput.addEventListener", start)
Path(__file__).parent.joinpath("_run_analysis.js").write_text(h[start:end], encoding="utf-8")
print("len", end - start)
