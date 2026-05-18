# -*- coding: utf-8 -*-
"""Reorganiza abas: Visão Geral limpa; Posts; Plano & Ações com ações/plano/ideias."""
import json
import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

# renderTabs(showPostsTab)
h = h.replace(
    """              function renderTabs() {
                return `
                  <div class="tabs">
                    <motion class="tab active" data-target="overview">Visão Geral</div>
                    <div class="tab" data-target="actions">Ações &amp; Ideias</div>
                    <div class="tab" data-target="content">Tipos de conteúdo</div>
                    <div class="tab" data-target="evolution">Plano &amp; Ações</motion>
                  </div>
                `.replace(/<motion class="tab"/g, '<div class="tab"').replace("</div>", "</div>");
              }""",
    """              function renderTabs(showPostsTab) {
                const postsTab = showPostsTab
                  ? '<div class="tab" data-target="posts">Posts</div>'
                  : "";
                return `
                  <div class="tabs">
                    <div class="tab active" data-target="overview">Visão Geral</motion>
                    ${postsTab}
                    <div class="tab" data-target="content">Tipos de conteúdo</div>
                    <div class="tab" data-target="evolution">Plano &amp; Ações</div>
                  </div>
                `.replace(/<\\/div>\\n                    <div class="tab active"/, '</div>\\n                    <div class="tab active"')
                  .replace('<motion class="tab active" data-target="overview">Visão Geral</motion>', '<div class="tab active" data-target="overview">Visão Geral</div>');
              }""",
)

if "function renderTabs(showPostsTab)" not in h:
    h = h.replace(
        """              function renderTabs() {
                return `
                  <div class="tabs">
                    <div class="tab active" data-target="overview">Visão Geral</div>
                    <motion class="tab" data-target="actions">Ações &amp; Ideias</div>
                    <div class="tab" data-target="content">Tipos de conteúdo</div>
                    <div class="tab" data-target="evolution">Plano &amp; Ações</div>
                  </div>
                `.replace(/<div class="tab"/g, '<div class="tab"').replace("</motion>", "</div>");""",
        """              function renderTabs(showPostsTab) {
                const postsTab = showPostsTab
                  ? '<div class="tab" data-target="posts">Posts</div>'
                  : "";
                return `
                  <div class="tabs">
                    <div class="tab active" data-target="overview">Visão Geral</div>
                    ${postsTab}
                    <div class="tab" data-target="content">Tipos de conteúdo</div>
                    <div class="tab" data-target="evolution">Plano &amp; Ações</div>
                  </div>
                `;
              }""",
    )

h = h.replace("${renderTabs()}", "${renderTabs(autoAuthenticated)}")

# Replace panels block in result.innerHTML - use regex for robustness
pattern = re.compile(
    r'<motion id="panel-overview"[^>]*>.*?</div>\s*\$\{autoAuthenticated.*?</motion>\s*</motion>\s*'
    r'<div id="panel-actions".*?</div>\s*'
    r'<div id="panel-content".*?</motion>\s*'
    r'<div id="panel-evolution".*?</div>\s*\$\{autoAuthenticated.*?</motion>\s*</motion>\s*',
    re.DOTALL,
)

NEW_PANELS = r"""<div id="panel-overview" class="panel active">
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
                    </div>

                    ${autoAuthenticated ? `
                    <motion id="panel-posts" class="panel">
                      <div class="section" data-section="posts-publicar">
                        <h3>Posts para publicar <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Gera rascunhos do teu perfil com IA. Aprova, edita ou refaz cada publicação.</p>
                        <div id="linkedinPostsContainer" class="li-posts-wrap"><div class="li-posts-loading">Clica em <strong>Gerar posts</strong> para criar publicações com IA.</div></div>
                        <button type="button" class="btn-analyze" style="margin-top:12px;max-width:260px" id="btnGenerateLinkedinPosts" data-action="generate-linkedin-posts" onclick="generateLinkedinPostsFromSnapshot()" disabled>Gerar posts</button>
                      </div>
                    </div>
                    ` : ""}

                    <div id="panel-content" class="panel">
                      <div class="section">
                        <h3>Tipos de conteúdo LinkedIn</h3>
                        ${renderFormatBars(enrichment.content_type_distribution || enrichment.format_distribution)}
                      </div>
                      <div class="section">
                        <h3>Top posts <span class="pill cool">reações</span></h3>
                        ${renderTopCards(enrichment.top_posts, "top posts")}
                      </div>
                      <div class="section">
                        <h3>Cadência de publicação</h3>
                        ${renderCadence(enrichment.posting_cadence || {})}
                      </div>
                    </div>

                    <div id="panel-evolution" class="panel">
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
                    </div>
                  """

NEW_PANELS = NEW_PANELS.replace("<motion ", "<div ").replace("</motion>", "</div>")

# Simpler string replace - find start and end markers
start = h.find('<div id="panel-overview"')
end = h.find("                  `;\n                  attachTabHandlers();")
if start < 0 or end < 0:
    raise SystemExit(f"markers not found start={start} end={end}")

h = h[:start] + NEW_PANELS + h[end:]

# Remove li-posts-cta-banner if still present
h = re.sub(
    r"\$\{autoAuthenticated \? `\s*<div class=\"section li-posts-cta-banner\">.*?</div>\s*` : \"\"\}",
    "",
    h,
    flags=re.DOTALL,
)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")

checks = {
    "no_banner": "li-posts-cta-banner" not in h,
    "panel_posts": 'data-target="posts">Posts' in h,
    "no_acoes_ideias": "Ações &amp; Ideias" not in h and "Ações & Ideias" not in h,
    "evolution_acoes": h.find("acoes_prioritarias") > h.find("panel-evolution"),
    "evolution_ideias": h.find("ideias_conteudo") > h.find("panel-evolution"),
    "posts_only": h.find("btnGenerateLinkedinPosts") > h.find("panel-posts") if "panel-posts" in h else "panel-posts" in h,
    "renderTabs_arg": "renderTabs(autoAuthenticated)" in h,
}
print("ok", checks)
