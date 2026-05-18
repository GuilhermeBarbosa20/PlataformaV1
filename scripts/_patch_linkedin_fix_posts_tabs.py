# -*- coding: utf-8 -*-
"""Corrige: posts só ao clicar; move acções/plano para Evolução; HTML válido."""

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

NEW_ACTIONS_PANEL = """                    <div id="panel-actions" class="panel">
                      <div class="section" data-section="posts-publicar">
                        <h3>Posts para publicar <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Gerados com IA a partir do teu perfil. Aprova, edita ou refaz cada post.</p>
                        <motion id="linkedinPostsContainer" class="li-posts-wrap"><div class="li-posts-loading">Clica em <strong>Gerar posts</strong> para criar publicações com IA.</div></div>
                        <button type="button" class="btn-save-profile" style="margin-top:10px" id="btnGenerateLinkedinPosts" onclick="generateLinkedinPostsFromSnapshot()" disabled>Gerar posts</button>
                      </div>
                    </div>""".replace("<motion id=", "<motion id=").replace("</div></div>", "</div></div>")

NEW_ACTIONS_PANEL = NEW_ACTIONS_PANEL.replace(
    '<motion id="linkedinPostsContainer"',
    '<div id="linkedinPostsContainer"',
)

NEW_EVOLUTION_PANEL = """                    <div id="panel-evolution" class="panel">
                      <div class="section" data-section="acoes-prioritarias">
                        <h3>Ações Prioritárias <span class="pill">agora</span></h3>
                        <ul class="insight-list actions">${listSection(data.acoes_prioritarias)}</ul>
                      </div>
                      <div class="section" data-section="plano-crescimento">
                        <h3>Plano de Crescimento (curto prazo)</h3>
                        <ul class="insight-list">${listSection(data.plano_crescimento_curto_prazo)}</ul>
                      </div>
                    </div>"""

# Replace panel-actions block
pa = h.find('id="panel-actions"')
pe = h.find('id="panel-evolution"', pa)
if pa >= 0 and pe > pa:
    # rewind to opening <div
    start = h.rfind("<div", pa - 80, pa + 5)
    if start < 0:
        start = h.rfind("<motion", pa - 80, pa + 5)
    h = h[:start] + NEW_ACTIONS_PANEL + "\n\n                    " + h[pe:]

# Replace panel-evolution block
pe = h.find('id="panel-evolution"')
if pe >= 0:
    start = h.rfind("<div", pe - 80, pe + 5)
    end = h.find("</motion>", pe)
    if end < 0:
        end = h.find("</div>", pe)
    # find closing of panel (next ` after panel closes)
    close = h.find("                  `;", pe)
    if close > pe:
        # backtrack to last </div> before `;
        panel_end = h.rfind("</div>", pe, close)
        # need the panel's outer closing div - count sections
        chunk = h[pe:close]
        if "panel-evolution" in chunk:
            h = h[:start] + NEW_EVOLUTION_PANEL + h[close:]

NEW_RESET = """              function resetLinkedinPostsAfterAnalysis() {
                linkedinGeneratedPosts = [];
                const el = document.getElementById("linkedinPostsContainer");
                const btn = document.getElementById("btnGenerateLinkedinPosts");
                if (btn) {
                  btn.disabled = !linkedinAnalysisSnapshot;
                  btn.textContent = "Gerar posts";
                }
                if (el) {
                  el.innerHTML = linkedinAnalysisSnapshot
                    ? '<div class="li-posts-loading">Análise concluída. Clica <strong>Gerar posts</strong> para criar publicações com IA.</div>'
                    : '<div class="li-posts-loading">Faz uma análise de perfil primeiro.</div>';
                }
              }"""

rs = h.find("function resetLinkedinPostsAfterAnalysis")
if rs >= 0:
    re = h.find("function linkedinPostTypeLabel", rs)
    if re > rs:
        h = h[:rs] + NEW_RESET + "\n\n              " + h[re:]

HOOK = "attachTabHandlers();"
if "resetLinkedinPostsAfterAnalysis();" not in h.split(HOOK, 1)[1][:250]:
    h = h.replace(
        HOOK + "\n                  if (autoAuthenticated)",
        HOOK + "\n                  setLinkedinAnalysisSnapshot(data);\n                  resetLinkedinPostsAfterAnalysis();\n                  if (autoAuthenticated)",
        1,
    )

OLD_GEN_END = """                  renderLinkedinPostsContainer();
                } catch (e) {
                  if (el) el.innerHTML = `<div class="err">Erro: ${escapeHtml(e.message || String(e))}</div>`;
                }
              }"""

NEW_GEN_END = """                  renderLinkedinPostsContainer();
                  const btnDone = document.getElementById("btnGenerateLinkedinPosts");
                  if (btnDone) { btnDone.disabled = false; btnDone.textContent = "Gerar novamente"; }
                } catch (e) {
                  if (el) el.innerHTML = `<motion class="err">Erro: ${escapeHtml(e.message || String(e))}</div>`;
                  const btnErr = document.getElementById("btnGenerateLinkedinPosts");
                  if (btnErr) { btnErr.disabled = false; btnErr.textContent = "Gerar posts"; }
                }
              }"""

NEW_GEN_END = NEW_GEN_END.replace('<motion class="err">', '<div class="err">').replace("</div>`;", "</div>`;")

if "btnDone.textContent" not in h and OLD_GEN_END in h:
    h = h.replace(OLD_GEN_END, NEW_GEN_END, 1)

h = h.replace(
    '}).join("").replace(/<div/g, "<motion").replace(/<\\/div>/g, "</motion>");',
    '}).join("");',
)
h = h.replace(
    '}).join("").replace(/<motion/g, "<motion").replace(/<\\/motion>/g, "</motion>");',
    '}).join("");',
)

h = h.replace("generateLinkedinPostsFromSnapshot();\n                  const resolvedUrl", "___NO_AUTO___")
h = h.replace(
    "setLinkedinAnalysisSnapshot(data);\n                  generateLinkedinPostsFromSnapshot();\n",
    "setLinkedinAnalysisSnapshot(data);\n                  resetLinkedinPostsAfterAnalysis();\n",
)

# Fix any remaining motion tags around posts container
h = h.replace('<motion id="linkedinPostsContainer"', '<div id="linkedinPostsContainer"')
h = h.replace("A gerar posts…", "Clica em <strong>Gerar posts</strong> para criar publicações com IA.", 1) if h.count("A gerar posts") > 1 else h

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")

i_actions = h.find('id="panel-actions"')
i_evo = h.find('id="panel-evolution"')
actions_chunk = h[i_actions:i_evo] if i_actions >= 0 and i_evo > i_actions else ""
checks = {
    "acoes in evolution": "acoes_prioritarias" in h[i_evo : i_evo + 800] if i_evo >= 0 else False,
    "acoes NOT in actions": "acoes_prioritarias" not in actions_chunk,
    "reset hook": "resetLinkedinPostsAfterAnalysis();" in h,
    "snapshot hook": h.count("setLinkedinAnalysisSnapshot(data)") >= 1,
    "div container": '<div id="linkedinPostsContainer"' in h,
    "btn restore": "btnDone.textContent" in h,
    "no auto gen": "generateLinkedinPostsFromSnapshot();\n                  const resolvedUrl" not in h,
}
print("ok", checks)
