import json
from pathlib import Path
_, rest = (Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())
for n in ["btnAutoAnalyze", "btn-auto-analyze", "Auto-análise", "runLinkedinAutoProfileAnalysis", "li-auth-row", "startLinkedInSupabaseLogin"]:
    print(n, "->", n in h)
i = h.find("li-auth-row")
print("\n--- auth row HTML ---\n")
# find the div with auth buttons
j = h.find('class="auth-row li-auth-row"')
print(h[j:j+900])
