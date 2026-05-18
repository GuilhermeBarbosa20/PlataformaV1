import json
from pathlib import Path
_, rest = (Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())
for needle in ["runLinkedinAutoProfileAnalysis", "getLinkedinSupabaseSession", "updateAutoAnalyzeButton", "autoAuthenticated", "btnAutoAnalyze", "<motion"]:
    print(needle, needle in h)
start = h.find("async function getLinkedinSupabaseSession")
print(h[start:start+2200])
