# -*- coding: utf-8 -*-
"""Ações & Ideias = acções + ideias; Plano & Ações = plano + posts; métricas rede primeiro."""

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

NEW_ACTIONS_PANEL = """                    <div id="panel-actions" class="panel">
                      <div class="section" data-section="acoes-prioritarias">
                        <h3>Ações Prioritárias <span class="pill">agora</span></h3>
                        <ul class="insight-list actions">${listSection(data.acoes_prioritarias)}</ul>
                      </div>
                      <motion class="section" data-section="ideias-conteudo">
                        <h3>Ideias por tipo de conteúdo <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Formatos: post texto, artigo, documento/PDF, sondagem, vídeo nativo.</p>
                        <ul class="insight-list violet">${listSection(data.ideias_conteudo)}</ul>
                      </div>
                    </div>""".replace('<motion class="section"', '<div class="section"', 1)

NEW_EVOLUTION_PANEL = """                    <div id="panel-evolution" class="panel">
                      <div class="section" data-section="plano-crescimento">
                        <h3>Plano de Crescimento (curto prazo)</h3>
                        <ul class="insight-list">${listSection(data.plano_crescimento_curto_prazo)}</ul>
                      </div>
                      <div class="section" data-section="posts-publicar">
                        <h3>Posts para publicar <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Gerados com IA a partir do teu perfil. Aprova, edita ou refaz cada post.</p>
                        <div id="linkedinPostsContainer" class="li-posts-wrap"><div class="li-posts-loading">Clica em <strong>Gerar posts</strong> para criar publicações com IA.</div></div>
                        <button type="button" class="btn-save-profile" style="margin-top:10px" id="btnGenerateLinkedinPosts" onclick="generateLinkedinPostsFromSnapshot()" disabled>Gerar posts</button>
                      </div>
                    </div>"""


def replace_panel(html, panel_id, new_html):
    pid = f'id="{panel_id}"'
    start = html.find(pid)
    if start < 0:
        return html, False
    div_start = html.rfind("<div", start - 60, start + 5)
    next_panel = html.find('<div id="panel-', start + 15)
    if next_panel < 0:
        next_panel = html.find("                  `;", start)
    if div_start < 0 or next_panel <= start:
        return html, False
    return html[:div_start] + new_html + "\n\n                    " + html[next_panel:], True


h, ok1 = replace_panel(h, "panel-actions", NEW_ACTIONS_PANEL)
h, ok2 = replace_panel(h, "panel-evolution", NEW_EVOLUTION_PANEL)

OLD_METRICS = """                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Desempenho geral</h4>
                          ${renderLinkedinMetricCards(data.metricas_universais)}
                        </div>
                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Atividade no perfil</h4>
                          ${renderLinkedinMetricCards(data.metricas_linkedin || data.metricas_instagram)}
                        </div>"""

NEW_METRICS = """                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Métricas específicas (LinkedIn)</h4>
                          ${renderLinkedinMetricCards(data.metricas_linkedin || data.metricas_instagram)}
                        </div>
                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Desempenho geral</h4>
                          ${renderLinkedinMetricCards(data.metricas_universais)}
                        </div>"""

if OLD_METRICS in h:
    h = h.replace(OLD_METRICS, NEW_METRICS, 1)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")


def slice_panel(html, name):
    a = html.find(f'id="{name}"')
    b = html.find('<div id="panel-', a + 15)
    if b < 0:
        b = html.find("                  `;", a)
    return html[a:b] if a >= 0 else ""

mi = h.find("li-metrics-section")
checks = {
    "panels_ok": ok1 and ok2,
    "actions_acoes": "acoes_prioritarias" in slice_panel(h, "panel-actions"),
    "actions_ideias": "ideias_conteudo" in slice_panel(h, "panel-actions"),
    "actions_no_posts": "linkedinPostsContainer" not in slice_panel(h, "panel-actions"),
    "evo_plano": "plano_crescimento" in slice_panel(h, "panel-evolution"),
    "evo_posts": "linkedinPostsContainer" in slice_panel(h, "panel-evolution"),
    "evo_no_acoes": "acoes_prioritarias" not in slice_panel(h, "panel-evolution"),
    "metrics_first": h.find("metricas_linkedin", mi) < h.find("metricas_universais", mi) if mi >= 0 else False,
    "no_motion": "<motion" not in h,
}
print("ok", checks)
