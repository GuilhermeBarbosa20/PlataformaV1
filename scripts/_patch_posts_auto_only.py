# -*- coding: utf-8 -*-
"""Gerar posts só disponível na Auto-análise (perfil próprio)."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

# 1) Flag global
if "linkedinAnalysisIsOwnProfile" not in h:
    h = h.replace(
        "              let linkedinAnalysisSnapshot = null;\n              let linkedinGeneratedPosts = [];",
        "              let linkedinAnalysisSnapshot = null;\n              let linkedinGeneratedPosts = [];\n              let linkedinAnalysisIsOwnProfile = false;",
    )

# 2) setSnapshot preserva flag
h = h.replace(
    """              function setLinkedinAnalysisSnapshot(data) {
                linkedinAnalysisSnapshot = data ? JSON.parse(JSON.stringify(data)) : null;
              }""",
    """              function setLinkedinAnalysisSnapshot(data, isOwnProfile) {
                linkedinAnalysisSnapshot = data ? JSON.parse(JSON.stringify(data)) : null;
                if (typeof isOwnProfile === "boolean") {
                  linkedinAnalysisIsOwnProfile = isOwnProfile;
                } else if (data && typeof data.linkedin_own_profile === "boolean") {
                  linkedinAnalysisIsOwnProfile = data.linkedin_own_profile;
                }
              }""",
)

# 3) enableGeneratePostsButton só com auto-análise
h = h.replace(
    "                const enabled = Boolean(linkedinAnalysisSnapshot);",
    "                const enabled = Boolean(linkedinAnalysisSnapshot) && linkedinAnalysisIsOwnProfile;",
)

# 4) generateLinkedinPostsFromSnapshot guard
h = h.replace(
    """              async function generateLinkedinPostsFromSnapshot() {
                if (!linkedinAnalysisSnapshot) {
                  alert("Faz primeiro uma análise de perfil.");
                  return;
                }""",
    """              async function generateLinkedinPostsFromSnapshot() {
                if (!linkedinAnalysisSnapshot) {
                  alert("Faz primeiro uma análise de perfil.");
                  return;
                }
                if (!linkedinAnalysisIsOwnProfile) {
                  alert("Gerar posts está disponível apenas na Auto-análise do teu perfil (login + perfil guardado).");
                  return;
                }""",
)

# 5) setSnapshot call with autoAuthenticated
h = h.replace(
    "                  setLinkedinAnalysisSnapshot(data);",
    "                  setLinkedinAnalysisSnapshot(data, autoAuthenticated);",
)

# 6) Remover banner fixo — usar condicional no template
BANNER_BLOCK = """                      <div class="section li-posts-cta-banner">
                        <h3>Posts com IA <span class="pill violet">publicar</span></h3>
                        <p class="section-desc">Gera rascunhos a partir desta análise. Na aba <strong>Plano &amp; Ações</strong> podes aprovar, editar e refazer cada post.</p>
                        <button type="button" class="btn-analyze" style="margin-top:8px;max-width:260px" data-action="generate-linkedin-posts" onclick="generateLinkedinPostsFromSnapshot()">Gerar posts</button>
                      </div>"""

if BANNER_BLOCK in h:
    h = h.replace(
        BANNER_BLOCK,
        "${autoAuthenticated ? `\n                      <div class=\"section li-posts-cta-banner\">\n                        <h3>Posts com IA <span class=\"pill violet\">publicar</span></h3>\n                        <p class=\"section-desc\">Gera rascunhos do teu perfil. Na aba <strong>Plano &amp; Ações</strong> podes aprovar, editar e refazer.</p>\n                        <button type=\"button\" class=\"btn-analyze\" style=\"margin-top:8px;max-width:260px\" data-action=\"generate-linkedin-posts\" onclick=\"generateLinkedinPostsFromSnapshot()\">Gerar posts</button>\n                      </motion>\n                    ` : \"\"}".replace("</motion>", "</div>").replace("<motion", "<motion"),
    )

# 7) Secção posts em Plano & Ações só para auto
POSTS_SECTION = """                      <div class="section" data-section="posts-publicar">
                        <h3>Posts para publicar <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Gerados com IA a partir da análise. Aprova, edita ou refaz cada post.</p>
                        <motion id="linkedinPostsContainer" class="li-posts-wrap"><div class="li-posts-loading">Clica em <strong>Gerar posts</strong> para criar publicações com IA.</div></div>
                        <button type="button" class="btn-save-profile" style="margin-top:10px" id="btnGenerateLinkedinPosts" data-action="generate-linkedin-posts" onclick="generateLinkedinPostsFromSnapshot()" disabled>Gerar posts</button>
                      </div>"""

POSTS_SECTION_ALT = POSTS_SECTION.replace(
    '<motion id="linkedinPostsContainer"',
    '<div id="linkedinPostsContainer"',
).replace("</motion>", "</div>")

for block in (POSTS_SECTION, POSTS_SECTION_ALT):
    if block in h:
        replacement = """${autoAuthenticated ? `
                      <div class="section" data-section="posts-publicar">
                        <h3>Posts para publicar <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Gerados com IA a partir do teu perfil. Aprova, edita ou refaz cada post.</p>
                        <div id="linkedinPostsContainer" class="li-posts-wrap"><motion class="li-posts-loading">Clica em <strong>Gerar posts</strong> para criar publicações com IA.</div></div>
                        <button type="button" class="btn-save-profile" style="margin-top:10px" id="btnGenerateLinkedinPosts" data-action="generate-linkedin-posts" onclick="generateLinkedinPostsFromSnapshot()" disabled>Gerar posts</button>
                      </div>
                    ` : ""}""".replace("<motion class=", '<div class="').replace("</motion>", "</div>")
        h = h.replace(block, replacement, 1)
        break

# 8) resetLinkedinPostsAfterAnalysis — mensagem diferente se não for own
h = h.replace(
    """                if (el) {
                  el.innerHTML = linkedinAnalysisSnapshot
                    ? '<motion class="li-posts-loading">Análise concluída. Clica <strong>Gerar posts</strong> para criar publicações com IA.</div>'
                    : '<div class="li-posts-loading">Faz uma análise de perfil primeiro.</div>';
                }""",
    """                if (el) {
                  if (!linkedinAnalysisSnapshot) {
                    el.innerHTML = '<div class="li-posts-loading">Faz uma análise de perfil primeiro.</div>';
                  } else if (!linkedinAnalysisIsOwnProfile) {
                    el.innerHTML = '<div class="li-posts-loading">Gerar posts só está disponível na <strong>Auto-análise</strong> do teu perfil.</div>';
                  } else {
                    el.innerHTML = '<div class="li-posts-loading">Clica em <strong>Gerar posts</strong> para criar publicações com IA.</motion>';
                  }
                }""",
)
h = h.replace(
    "el.innerHTML = '<div class=\"li-posts-loading\">Clica em <strong>Gerar posts</strong> para criar publicações com IA.</motion>';",
    "el.innerHTML = '<div class=\"li-posts-loading\">Clica em <strong>Gerar posts</strong> para criar publicações com IA.</motion>';".replace("</motion>", "</motion>"),
)
# fix motion typo if introduced
h = h.replace(
    "criar publicações com IA.</motion>';",
    "criar publicações com IA.</motion>';".replace("</motion>", "</div>"),
)

# 9) Backend: flag na resposta + validação generate-posts
# Skip if already in app - add to profile-analyze response and generate-posts check

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("page", "linkedinAnalysisIsOwnProfile" in h, "autoAuthenticated ?" in h)
