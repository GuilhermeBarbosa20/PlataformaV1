import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML as h

ov = h.split('id="panel-overview"', 1)[1].split('id="panel-posts"', 1)[0]
ev = h.split('id="panel-evolution"', 1)[1].split('id="panel-content"', 1)[0]
print("Principais Insights in overview:", "Principais Insights" in ov)
print("Indicadores in overview:", "Indicadores de desempenho" in ov)
print("li-profile-overview anywhere:", "li-profile-overview" in h)
print("renderLinkedinHarvestProfileOverview:", "renderLinkedinHarvestProfileOverview" in h)
idx = h.find("function renderAnalysis")
if idx > 0:
    chunk = h[idx : idx + 6000]
    print("harvest call in renderAnalysis:", "Harvest" in chunk or "harvest" in chunk.lower())
    print("profile-overview in renderAnalysis:", "profile-overview" in chunk)
