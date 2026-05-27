import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML as h

ev = h.split('id="panel-evolution"', 1)[1].split('id="panel-content"', 1)[0]
print(ev[:1200])
print("---")
print("Principais Insights in evolution:", "Principais Insights" in ev)
