import json
from pathlib import Path
raw = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
_, rest = raw.read_text(encoding="utf-8").split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())
for needle in ["li-only-form", "runLinkedinProfileAnalysis", "refreshLinkedinSupabaseSession", "useSessionProfile"]:
    i = h.find(needle)
    print("===", needle, i)
    print(h[max(0,i-200):i+1200])
    print()
