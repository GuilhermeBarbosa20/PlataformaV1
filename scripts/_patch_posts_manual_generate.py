# -*- coding: utf-8 -*-
"""Posts só ao clicar Gerar (não automático após análise)."""

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

# Remove auto-generate after analysis
h = h.replace(
    "                  setLinkedinAnalysisSnapshot(data);\n                  generateLinkedinPostsFromSnapshot();\n",
    "                  setLinkedinAnalysisSnapshot(data);\n                  resetLinkedinPostsAfterAnalysis();\n",
)

# Add resetLinkedinPostsAfterAnalysis if missing
if "function resetLinkedinPostsAfterAnalysis" not in h:
    h = h.replace(
        "              function setLinkedinAnalysisSnapshot(data) {\n"
        "                linkedinAnalysisSnapshot = data ? JSON.parse(JSON.stringify(data)) : null;\n"
        "              }",
        "              function setLinkedinAnalysisSnapshot(data) {\n"
        "                linkedinAnalysisSnapshot = data ? JSON.parse(JSON.stringify(data)) : null;\n"
        "              }\n\n"
        "              function resetLinkedinPostsAfterAnalysis() {\n"
        "                linkedinGeneratedPosts = [];\n"
        "                const el = document.getElementById(\"linkedinPostsContainer\");\n"
        "                const btn = document.getElementById(\"btnGenerateLinkedinPosts\");\n"
        "                if (btn) {\n"
        "                  btn.disabled = !linkedinAnalysisSnapshot;\n"
        "                }\n"
        "                if (el) {\n"
        "                  el.innerHTML = linkedinAnalysisSnapshot\n"
        "                    ? '<motion class=\"li-posts-loading\">Análise concluída. Clica <strong>Gerar posts</strong> para criar publicações com IA.</div>'\n"
        "                    : '<motion class=\"li-posts-loading\">Faz uma análise de perfil primeiro.</motion>';\n"
        "                }\n"
        "              }".replace("<motion", "<motion").replace("motion>", "motion>"),
    )
    h = h.replace(
        "                    ? '<motion class=\"li-posts-loading\">Análise concluída. Clica <strong>Gerar posts</strong> para criar publicações com IA.</motion>'\n"
        "                    : '<motion class=\"li-posts-loading\">Faz uma análise de perfil primeiro.</motion>';",
        "                    ? '<div class=\"li-posts-loading\">Análise concluída. Clica <strong>Gerar posts</strong> para criar publicações com IA.</motion>'\n"
        "                    : '<div class=\"li-posts-loading\">Faz uma análise de perfil primeiro.</motion>';",
    )
    h = h.replace("</motion>'", "</motion>'").replace("<motion", "<motion")
    # fix div
    h = h.replace(
        "Análise concluída. Clica <strong>Gerar posts</strong> para criar publicações com IA.</motion>'",
        "Análise concluída. Clica <strong>Gerar posts</strong> para criar publicações com IA.</motion>'",
    )

# Fix the reset function - do it cleanly with search replace
if "resetLinkedinPostsAfterAnalysis" in h and "Análise concluída" in h:
    pass
elif "resetLinkedinPostsAfterAnalysis" not in h:
    insert_after = """              function resetLinkedinPostsAfterAnalysis() {
                linkedinGeneratedPosts = [];
                const el = document.getElementById("linkedinPostsContainer");
                const btn = document.getElementById("btnGenerateLinkedinPosts");
                if (btn) btn.disabled = !linkedinAnalysisSnapshot;
                if (el) {
                  el.innerHTML = linkedinAnalysisSnapshot
                    ? '<motion class="li-posts-loading">Análise concluída. Clica <strong>Gerar posts</strong> para criar publicações com IA.</motion>'
                    : '<motion class="li-posts-loading">Faz uma análise de perfil primeiro.</motion>';
                }
              }

"""
    insert_after = insert_after.replace("<motion", "<div").replace("</motion>", "</div>")
    h = h.replace(
        "              function linkedinPostTypeLabel(t) {",
        insert_after + "              function linkedinPostTypeLabel(t) {",
    )

# Update generate function - don't auto-switch to actions tab; update button label
h = h.replace(
    'onclick="generateLinkedinPostsFromSnapshot()">Gerar novamente</button>',
    'id="btnGenerateLinkedinPosts" onclick="generateLinkedinPostsFromSnapshot()" disabled>Gerar posts</button>',
)

if 'id="btnGenerateLinkedinPosts"' not in h:
    h = h.replace(
        "onclick=\"generateLinkedinPostsFromSnapshot()\">Gerar novamente</button>",
        'id="btnGenerateLinkedinPosts" onclick="generateLinkedinPostsFromSnapshot()" disabled>Gerar posts</button>',
    )

h = h.replace(
    "Sem posts. Clica «Gerar novamente».",
    "Sem posts. Clica «Gerar posts».",
)

h = h.replace(
    "                  const actionsTab = document.querySelector('.tab[data-target=\"actions\"]');\n"
    "                  if (actionsTab) actionsTab.click();\n",
    "",
)

# Update generateLinkedinPostsFromSnapshot - enable button during load, update btn text
old_gen_start = """                const el = document.getElementById("linkedinPostsContainer");
                if (el) el.innerHTML = '<div class="li-posts-loading">A gerar posts com IA…</motion>';"""

if old_gen_start.replace("motion", "div") in h or old_gen_start in h:
    new_gen_start = """                const el = document.getElementById("linkedinPostsContainer");
                const btn = document.getElementById("btnGenerateLinkedinPosts");
                if (btn) { btn.disabled = true; btn.textContent = "A gerar…"; }
                if (el) el.innerHTML = '<motion class="li-posts-loading">A gerar posts com IA…</motion>';"""
    new_gen_start = new_gen_start.replace("<motion", "<div").replace("</motion>", "</motion>")
    h = h.replace(old_gen_start.replace("motion", "motion"), new_gen_start)
    if "btn.textContent = \"A gerar…\"" not in h:
        h = h.replace(
            'if (el) el.innerHTML = \'<div class="li-posts-loading">A gerar posts com IA…</div>\';',
            'const btn = document.getElementById("btnGenerateLinkedinPosts");\n'
            '                if (btn) { btn.disabled = true; btn.textContent = "A gerar…"; }\n'
            '                if (el) el.innerHTML = \'<div class="li-posts-loading">A gerar posts com IA…</div>\';',
        )

# After success restore button
if "btn.textContent = \"Gerar posts\"" not in h:
    h = h.replace(
        "                  renderLinkedinPostsContainer();\n",
        "                  renderLinkedinPostsContainer();\n"
        "                  const btnDone = document.getElementById(\"btnGenerateLinkedinPosts\");\n"
        "                  if (btnDone) { btnDone.disabled = false; btnDone.textContent = \"Gerar novamente\"; }\n",
        1,
    )

# Initial container message
h = h.replace(
    "Os posts serão gerados após a análise…",
    "Faz uma análise e depois clica em «Gerar posts».",
)

# Remove duplicate attachTabHandlers generate if still there
h = h.replace(
    "attachTabHandlers();\n                  setLinkedinAnalysisSnapshot(data);\n                  generateLinkedinPostsFromSnapshot();",
    "attachTabHandlers();\n                  setLinkedinAnalysisSnapshot(data);\n                  resetLinkedinPostsAfterAnalysis();",
)

# finally block on generate error - restore button
if "btnDone" in h and "catch (e)" in h.split("generateLinkedinPostsFromSnapshot")[1][:2000]:
    pass
h = h.replace(
    '                  if (el) el.innerHTML = `<motion class="err">Erro: ${escapeHtml(e.message || String(e))}</motion>`;\n'
    "                }\n"
    "              }",
    '                  if (el) el.innerHTML = `<div class="err">Erro: ${escapeHtml(e.message || String(e))}</div>`;\n'
    "                }\n"
    '                const btnErr = document.getElementById("btnGenerateLinkedinPosts");\n'
    '                if (btnErr) { btnErr.disabled = false; btnErr.textContent = "Gerar posts"; }\n'
    "              }",
)
h = h.replace('<motion class="err">', '<div class="err">').replace('</motion>`;', '</motion>`;')

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok",
      "resetLinkedinPostsAfterAnalysis" in h,
      "generateLinkedinPostsFromSnapshot();\n                  const resolvedUrl" not in h,
      "btnGenerateLinkedinPosts" in h)
