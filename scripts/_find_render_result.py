import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML as h

for term in ["renderKpis(data)", "renderHeader(data)", "renderTabs(", "result.innerHTML"]:
    idx = 0
    while True:
        i = h.find(term, idx)
        if i < 0:
            break
        print(f"\n--- {term} @ {i} ---")
        print(h[i : i + 600])
        idx = i + 1
        if idx > i + 3:
            break
