# -*- coding: utf-8 -*-
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD = """                    <div id="panel-evolution" class="panel">
                      <div class="section">
                        <h3>Comparação Temporal</h3>
                        ${renderComparisons(data.comparisons)}
                      </div>
                      <div class="section">
                        <h3>Lacunas de Dados</h3>
                        <ul class="gap-list">${listSection(data.lacunas_de_dados)}</ul>
                      </div>
                    </div>"""

NEW = """                    <motion id="panel-evolution" class="panel">
                      <div class="section" data-section="acoes-prioritarias">
                        <h3>Ações Prioritárias <span class="pill">agora</span></h3>
                        <ul class="insight-list actions">${listSection(data.acoes_prioritarias)}</ul>
                      </div>
                      <div class="section" data-section="plano-crescimento">
                        <h3>Plano de Crescimento (curto prazo)</h3>
                        <ul class="insight-list">${listSection(data.plano_crescimento_curto_prazo)}</ul>
                      </div>
                    </div>""".replace("<motion id=", "<div id=")

if OLD in h:
    h = h.replace(OLD, NEW, 1)
    print("replaced evolution panel")
else:
    print("OLD not found, trying locate...")
    i = h.find("Comparação Temporal")
    print("idx", i, h[i-120:i+400] if i>=0 else "missing")

# Remove duplicate reset function if any
marker = "function resetLinkedinPostsAfterAnalysis"
first = h.find(marker)
second = h.find(marker, first + 10)
if second > first:
    end = h.find("function linkedinPostTypeLabel", second)
    h = h[:second] + h[end:]
    print("removed duplicate reset")

# Fix broken panel-content if missing
if 'id="panel-content"' not in h:
    print("WARNING panel-content missing")
    i = h.find("panel-overview")
    print("overview at", i)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("evolution has acoes:", "acoes_prioritarias" in h.split('panel-evolution')[1][:600] if "panel-evolution" in h else False)
print("panel-content:", 'id="panel-content"' in h)
