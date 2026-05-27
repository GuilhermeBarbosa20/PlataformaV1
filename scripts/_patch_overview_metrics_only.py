# -*- coding: utf-8 -*-
"""Visão Geral: só indicadores; Insights/Problemas/Oportunidades → Plano & Ações."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD_OVERVIEW = """<div id="panel-overview" class="panel active">
                      <div class="section">
                        <h3>Principais Insights <span class="pill cool">IA</span></h3>
                        <ul class="insight-list">${listSection(data.principais_insights)}</ul>
                      </div>
                      <div class="section">
                        <h3>Problemas Identificados <span class="pill">atenção</span></h3>
                        <ul class="insight-list problems">${listSection(data.problemas_identificados)}</ul>
                      </div>
                      <div class="section">
                        <h3>Oportunidades <span class="pill cool">crescimento</span></h3>
                        <ul class="insight-list opps">${listSection(data.oportunidades)}</ul>
                      </div>
                      <div class="section li-metrics-section">
                        <h3>Indicadores de desempenho <span class="pill cool">LinkedIn</span></h3>
                        <p class="section-desc">Resumo quantitativo da página e das publicações analisadas. Campos sem dado público aparecem assinalados.</p>
                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Métricas específicas (LinkedIn)</h4>
                          ${renderLinkedinMetricCards(data.metricas_linkedin || data.metricas_instagram, data)}
                        </div>
                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Desempenho geral</h4>
                          ${renderLinkedinMetricCards(data.metricas_universais, data)}
                        </div>
                      </div>
                    </div>"""

NEW_OVERVIEW = """<div id="panel-overview" class="panel active">
                      <div class="section li-metrics-section">
                        <h3>Indicadores de desempenho <span class="pill cool">LinkedIn</span></h3>
                        <p class="section-desc">Resumo quantitativo da página e das publicações analisadas. Campos sem dado público aparecem assinalados.</p>
                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Métricas específicas (LinkedIn)</h4>
                          ${renderLinkedinMetricCards(data.metricas_linkedin || data.metricas_instagram, data)}
                        </div>
                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Desempenho geral</h4>
                          ${renderLinkedinMetricCards(data.metricas_universais, data)}
                        </div>
                      </div>
                    </div>"""

INSIGHTS_BLOCK = """                      <div class="section">
                        <h3>Principais Insights <span class="pill cool">IA</span></h3>
                        <ul class="insight-list">${listSection(data.principais_insights)}</ul>
                      </div>
                      <div class="section">
                        <h3>Problemas Identificados <span class="pill">atenção</span></h3>
                        <ul class="insight-list problems">${listSection(data.problemas_identificados)}</ul>
                      </div>
                      <div class="section">
                        <h3>Oportunidades <span class="pill cool">crescimento</span></h3>
                        <ul class="insight-list opps">${listSection(data.oportunidades)}</ul>
                      </div>
"""

OLD_EVOLUTION = """<div id="panel-evolution" class="panel">
                      <div class="section" data-section="acoes-prioritarias">
                        <h3>Ações Prioritárias <span class="pill">agora</span></h3>
                        <ul class="insight-list actions">${listSection(data.acoes_prioritarias)}</ul>
                      </div>
                      <div class="section" data-section="plano-crescimento">
                        <h3>Plano de Crescimento (curto prazo)</h3>
                        <ul class="insight-list">${listSection(data.plano_crescimento_curto_prazo)}</ul>
                      </div>
                      <div class="section" data-section="ideias-conteudo">
                        <h3>Ideias por tipo de conteúdo <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Formatos: post texto, artigo, documento/PDF, sondagem, vídeo nativo.</p>
                        <ul class="insight-list violet">${listSection(data.ideias_conteudo)}</ul>
                      </div>
                    </div>"""

NEW_EVOLUTION = """<div id="panel-evolution" class="panel">
""" + INSIGHTS_BLOCK + """                      <div class="section" data-section="acoes-prioritarias">
                        <h3>Ações Prioritárias <span class="pill">agora</span></h3>
                        <ul class="insight-list actions">${listSection(data.acoes_prioritarias)}</ul>
                      </div>
                      <div class="section" data-section="plano-crescimento">
                        <h3>Plano de Crescimento (curto prazo)</h3>
                        <ul class="insight-list">${listSection(data.plano_crescimento_curto_prazo)}</ul>
                      </div>
                      <div class="section" data-section="ideias-conteudo">
                        <h3>Ideias por tipo de conteúdo <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Formatos: post texto, artigo, documento/PDF, sondagem, vídeo nativo.</p>
                        <ul class="insight-list violet">${listSection(data.ideias_conteudo)}</ul>
                      </div>
                    </div>"""

if OLD_OVERVIEW not in h:
    raise SystemExit("panel-overview block not found")
h = h.replace(OLD_OVERVIEW, NEW_OVERVIEW, 1)

if OLD_EVOLUTION not in h:
    raise SystemExit("panel-evolution block not found")
h = h.replace(OLD_EVOLUTION, NEW_EVOLUTION, 1)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
checks = {
    "overview_metrics_only": h.count("panel-overview") == 1 and "principais_insights" in h.split("panel-evolution")[1].split("panel-content")[0],
    "overview_no_insights": "principais_insights" not in h.split("panel-posts")[0].split("panel-overview")[1] if "panel-posts" in h else True,
}
# simpler checks
ov = h.split('id="panel-overview"')[1].split('id="panel-posts"')[0]
ev = h.split('id="panel-evolution"')[1].split('id="panel-content"')[0]
print("ok", {
    "overview_has_metrics": "Indicadores de desempenho" in ov,
    "overview_no_insights": "Principais Insights" not in ov,
    "evolution_has_insights": "Principais Insights" in ev and "Problemas Identificados" in ev and "Oportunidades" in ev,
    "evolution_has_acoes": "Ações Prioritárias" in ev,
})
