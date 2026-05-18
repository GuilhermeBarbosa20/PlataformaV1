from pathlib import Path
import codecs

raw = (Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8")
html = raw.split('LINKEDIN_PERFIL_PAGE_HTML: str = ', 1)[1]
decoded = codecs.decode(html, "unicode_escape")
for name in ["renderHeader", "renderEnrichmentPills", "renderMetricsTable", "metricas_universais", "panel-content", "ideias_conteudo"]:
    start = decoded.find(name)
    if start < 0:
        print(name, "NOT FOUND")
        continue
    print("\n===", name, "===\n")
    print(decoded[start : start + 2500])
