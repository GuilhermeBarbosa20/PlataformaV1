# -*- coding: utf-8 -*-
"""Garante Visão Geral com harvest + métricas (sem insights); não altera publicação/calendário."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "agents" / "linkedin_perfil_page.py"

PANEL_OVERVIEW_GOOD = '''<div id="panel-overview" class="panel active">
                      <div class="section li-metrics-section">
                        <h3>Indicadores de desempenho <span class="pill cool">LinkedIn</span></h3>
                        <p class="section-desc">Perfil via <strong>harvestapi/linkedin-profile-scraper</strong> (ligações, experiência, formação) e publicações via Apify. Campos sem dado público aparecem assinalados.</p>
                        ${(data.overview_data_source || (profile && profile.overview_source)) ? `<p class="section-desc" style="margin-top:6px"><span class="badge info"><span class="dot"></span> Visão geral: ${escapeHtml(String(data.overview_data_source || profile.overview_source || "harvestapi/linkedin-profile-scraper"))}</span></p>` : ""}
                        <div class="li-metrics-group">
                          ${renderLinkedinHarvestProfileOverview(data.metricas_linkedin || data.metricas_instagram, data, profile)}
                        </div>
                        <div class="li-metrics-group li-metrics-group--posts">
                          <h4 class="li-metrics-group-title">Desempenho das publicações</h4>
                          ${renderLinkedinPostMetrics(data.metricas_universais, data)}
                        </div>
                      </div>
                    </div>'''

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

PANEL_EVOLUTION_ACTIONS = """                      <div class="section" data-section="acoes-prioritarias">
                        <h3>Ações Prioritárias <span class="pill">agora</span></h3>
                        <ul class="insight-list actions">${listSection(data.acoes_prioritarias)}</ul>
                      </div>"""


def load_html() -> str:
    raw = PAGE.read_text(encoding="utf-8")
    prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
    return json.loads(rest.strip())


def save_html(h: str) -> None:
    raw = PAGE.read_text(encoding="utf-8")
    prefix = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[0]
    PAGE.write_text(
        prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def replace_panel_overview(h: str) -> tuple[str, bool]:
    pattern = re.compile(
        r'<div id="panel-overview" class="panel active">.*?</div>\s*\n\s*\n\s*\$\{autoAuthenticated',
        re.DOTALL,
    )
    repl = PANEL_OVERVIEW_GOOD + "\n\n                    ${autoAuthenticated"
    new_h, n = pattern.subn(repl, h, count=1)
    return new_h, n == 1


def ensure_evolution_has_insights(h: str) -> tuple[str, bool]:
    if 'id="panel-evolution"' not in h:
        return h, False
    ev_start = h.find('id="panel-evolution"')
    ev_end = h.find('id="panel-content"', ev_start)
    if ev_end < 0:
        return h, False
    ev = h[ev_start:ev_end]
    if "Principais Insights" in ev:
        return h, False
    if PANEL_EVOLUTION_ACTIONS not in ev:
        return h, False
    new_ev = ev.replace(PANEL_EVOLUTION_ACTIONS, INSIGHTS_BLOCK + PANEL_EVOLUTION_ACTIONS, 1)
    return h[:ev_start] + new_ev + h[ev_end:], True


def main() -> None:
    h = load_html()
    changed = False

    ov = h.split('id="panel-overview"', 1)[1].split('id="panel-posts"', 1)[0]
    needs_ov = (
        "Principais Insights" in ov
        or "renderLinkedinMetricCards(data.metricas_linkedin" in ov
        or "renderLinkedinHarvestProfileOverview" not in ov
    )
    if needs_ov:
        h, ok = replace_panel_overview(h)
        if not ok:
            raise SystemExit("Não foi possível substituir panel-overview")
        changed = True
        print("panel-overview restaurado")

    h2, ev_ok = ensure_evolution_has_insights(h)
    if ev_ok:
        h = h2
        changed = True
        print("insights movidos para Plano & Ações")

    if not changed:
        print("Visão Geral já estava correcta; nada a alterar")
    else:
        save_html(h)
        print("gravado", PAGE)

    ov2 = h.split('id="panel-overview"', 1)[1].split('id="panel-posts"', 1)[0]
    assert "Principais Insights" not in ov2
    assert "renderLinkedinHarvestProfileOverview" in ov2
    assert "renderLinkedinHarvestProfileOverview" in h
    assert "renderLinkedinCompanyProfileOverview" in h
    assert "findLinkedinPostEntry(id, preferredScope)" in h or "findLinkedinPostEntry(id, scope)" in h


if __name__ == "__main__":
    main()
