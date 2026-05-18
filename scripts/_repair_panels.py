# -*- coding: utf-8 -*-
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

# Find broken segment: after overview ends, before `;
start_marker = "${renderMetricPills(data.metricas_linkedin || data.metricas_instagram)}"
start = h.find(start_marker)
if start < 0:
    raise SystemExit("start marker not found")
start = h.find("</div>", start)  # end of overview inner section - need outer panel close
# find overview panel closing: last </motion> before panel-actions
actions_idx = h.find('id="panel-actions"', start)
overview_end = h.rfind("</motion>", start, actions_idx)
if overview_end < 0:
    overview_end = h.rfind("</motion>", start, actions_idx)

backtick = h.find("                  `;", actions_idx)
if backtick < 0:
    raise SystemExit("backtick not found")

PANELS = """
                    <div id="panel-actions" class="panel">
                      <div class="section" data-section="posts-publicar">
                        <h3>Posts para publicar <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Gerados com IA a partir do teu perfil. Aprova, edita ou refaz cada post.</p>
                        <div id="linkedinPostsContainer" class="li-posts-wrap"><div class="li-posts-loading">Clica em <strong>Gerar posts</strong> para criar publicações com IA.</div></div>
                        <button type="button" class="btn-save-profile" style="margin-top:10px" id="btnGenerateLinkedinPosts" onclick="generateLinkedinPostsFromSnapshot()" disabled>Gerar posts</button>
                      </div>
                    </div>

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
                        <h3>Destaques <span class="pill violet">posts</span></h3>
                        ${renderTopCards(enrichment.top_posts, "publicações")}
                      </div>
                      <div class="section">
                        <h3>Cadência de publicação</h3>
                        ${renderCadence(enrichment.posting_cadence || {}, {})}
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
                    </div>
"""

# overview ends with </div> for panel-overview
oe = h.find('id="panel-overview"', start)
oe_close = h.find("</motion>", h.find("metricas_linkedin", oe))
# use first </div> after metricas_instagram line that's panel close
line_end = h.find("metricas_instagram)}", oe)
panel_close = h.find("</motion>", line_end)
if h[panel_close:panel_close+6] != "</div>":
    panel_close = h.find("</motion>", line_end)
# simpler: replace from first panel-actions to backtick
pa = h.find('id="panel-actions"', start)
h_new = h[:pa] + PANELS.strip() + "\n                  " + h[backtick:]

# fix if we duplicated - ensure single panel-actions
if h_new.count('id="panel-actions"') > 1:
    # keep repair only
    pass

h = h_new

# Remove duplicate reset function
marker = "function resetLinkedinPostsAfterAnalysis"
first = h.find(marker)
second = h.find(marker, first + 20)
if second > first:
    end = h.find("function linkedinPostTypeLabel", second)
    h = h[:second] + h[end:]

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")

checks = {
    "panel-content": 'id="panel-content"' in h,
    "panel-evolution div": '<div id="panel-evolution"' in h,
    "acoes in evolution": h.find("acoes_prioritarias") > h.find("panel-evolution"),
    "posts in actions": "Posts para publicar" in h[h.find("panel-actions"):h.find("panel-content")],
    "reset hook": "resetLinkedinPostsAfterAnalysis();" in h,
}
print("ok", checks)
