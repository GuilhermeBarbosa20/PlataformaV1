"""Inspeciona funções JS na página LinkedIn perfil."""
from pathlib import Path

text = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = text.read_text(encoding="utf-8")
html = raw.split('LINKEDIN_PERFIL_PAGE_HTML: str = ', 1)[1]
for fn in [
    "renderKpis",
    "renderHeader",
    "renderMetrics",
    "renderActions",
    "renderContent",
    "metricas_instagram",
    "seguidores",
    "Reels",
    "crescimento_seguidores",
]:
    i = html.find(fn)
    print(fn, i)
    if i >= 0:
        snippet = html[i : i + 400].replace("\\n", "\n")
        print(snippet[:350])
        print("---")
