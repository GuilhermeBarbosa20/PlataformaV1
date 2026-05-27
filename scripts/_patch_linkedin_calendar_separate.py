# -*- coding: utf-8 -*-
"""Separa posts da aba Posts e do Calendário (estado e geração independentes)."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

HELPERS = """
              let linkedinPostsTabPosts = [];
              let linkedinCalendarPosts = [];

              function getLinkedinPostsArray(scope) {
                return scope === "calendar" ? linkedinCalendarPosts : linkedinPostsTabPosts;
              }

              function findLinkedinPostEntry(id) {
                let p = linkedinPostsTabPosts.find((x) => x.id === id);
                if (p) return { post: p, scope: "posts" };
                p = linkedinCalendarPosts.find((x) => x.id === id);
                if (p) return { post: p, scope: "calendar" };
                return { post: null, scope: "posts" };
              }

              function refreshLinkedinPostScope(scope) {
                if (!scope || scope === "posts") renderLinkedinPostsContainer();
                if (!scope || scope === "calendar") renderLinkedinCalendarContainer();
              }
"""

if "let linkedinPostsTabPosts" not in h:
    h = h.replace("let linkedinGeneratedPosts = [];", HELPERS.strip() + "\n", 1)
else:
    print("helpers already present")

# enableGeneratePostsButton
OLD_ENABLE = """                            function enableGeneratePostsButton() {
                const enabled = Boolean(linkedinAnalysisSnapshot) && linkedinAnalysisIsOwnProfile;
                const label = linkedinGeneratedPosts.length ? "Gerar novamente" : "Gerar posts";
                const calLabel = linkedinGeneratedPosts.length ? "Gerar semana novamente" : "Gerar posts da semana";
                ["btnGenerateLinkedinPosts", "btnGenerateLinkedinCalendarPosts"].forEach((id) => {
                  const btn = document.getElementById(id);
                  if (!btn) return;
                  btn.disabled = !enabled;
                  if (id === "btnGenerateLinkedinCalendarPosts") {
                    btn.textContent = calLabel;
                  } else {
                    btn.textContent = label;
                  }
                });
                document.querySelectorAll("[data-action=generate-linkedin-posts]").forEach((btn) => {
                  btn.disabled = !enabled;
                  if (!btn.textContent || btn.textContent.includes("Gerar")) btn.textContent = label;
                });
              }"""

NEW_ENABLE = """                            function enableGeneratePostsButton() {
                const enabled = Boolean(linkedinAnalysisSnapshot) && linkedinAnalysisIsOwnProfile;
                const label = linkedinPostsTabPosts.length ? "Gerar novamente" : "Gerar posts";
                const calLabel = linkedinCalendarPosts.length ? "Gerar semana novamente" : "Gerar posts da semana";
                const postsBtn = document.getElementById("btnGenerateLinkedinPosts");
                const calBtn = document.getElementById("btnGenerateLinkedinCalendarPosts");
                if (postsBtn) {
                  postsBtn.disabled = !enabled;
                  postsBtn.textContent = label;
                }
                if (calBtn) {
                  calBtn.disabled = !enabled;
                  calBtn.textContent = calLabel;
                }
                document.querySelectorAll("[data-action=generate-linkedin-posts]").forEach((btn) => {
                  btn.disabled = !enabled;
                  if (!btn.textContent || btn.textContent.includes("Gerar")) btn.textContent = label;
                });
              }"""

if OLD_ENABLE in h:
    h = h.replace(OLD_ENABLE, NEW_ENABLE, 1)
elif "linkedinPostsTabPosts.length" in h:
    print("enableGeneratePostsButton already patched")
else:
    raise SystemExit("enableGeneratePostsButton not found")

# reset
h = h.replace("linkedinGeneratedPosts = [];", "linkedinPostsTabPosts = [];\n                linkedinCalendarPosts = [];", 1)

# ensureLinkedinPostsWeekDates
OLD_ENSURE = """              function ensureLinkedinPostsWeekDates() {
                if (!linkedinGeneratedPosts.length) return;
                const weekDays = getLinkedinWeekDays();
                let idx = 0;
                linkedinGeneratedPosts.forEach((p) => {
                  if (!p.scheduled_date && weekDays[idx]) {
                    p.scheduled_date = formatLinkedinDateKey(weekDays[idx]);
                    idx += 1;
                  }
                });
              }"""

NEW_ENSURE = """              function ensureLinkedinPostsWeekDates(scope) {
                const list = getLinkedinPostsArray(scope || "calendar");
                if (!list.length) return;
                const weekDays = getLinkedinWeekDays();
                let idx = 0;
                list.forEach((p) => {
                  if (!p.scheduled_date && weekDays[idx]) {
                    p.scheduled_date = formatLinkedinDateKey(weekDays[idx]);
                    idx += 1;
                  }
                });
              }"""

if OLD_ENSURE in h:
    h = h.replace(OLD_ENSURE, NEW_ENSURE, 1)

# refreshLinkedinPostsUI - keep both renders (different data)
# renderLinkedinPostCardHtml - add scope param
h = h.replace(
    "function renderLinkedinPostCardHtml(p, compact) {",
    "function renderLinkedinPostCardHtml(p, compact, scope) {",
    1,
)
h = h.replace(
    "const st = p.status || \"draft\";\n                const cls = [\"li-post-card\", compact ? \"li-post-card-compact\" : \"\"",
    "const postScope = scope || \"posts\";\n                const st = p.status || \"draft\";\n                const cls = [\"li-post-card\", compact ? \"li-post-card-compact\" : \"\"",
    1,
)

# onclick handlers - add scope as second arg
onclick_replacements = [
    ("saveLinkedinPostEdit('${escapeHtml(p.id)}')", "saveLinkedinPostEdit('${escapeHtml(p.id)}', '${postScope}')"),
    ("cancelLinkedinPostEdit('${escapeHtml(p.id)}')", "cancelLinkedinPostEdit('${escapeHtml(p.id)}', '${postScope}')"),
    ("deleteLinkedinPost('${escapeHtml(p.id)}')", "deleteLinkedinPost('${escapeHtml(p.id)}', '${postScope}')"),
    ("approveLinkedinPost('${escapeHtml(p.id)}')", "approveLinkedinPost('${escapeHtml(p.id)}', '${postScope}')"),
    ("startLinkedinPostEdit('${escapeHtml(p.id)}')", "startLinkedinPostEdit('${escapeHtml(p.id)}', '${postScope}')"),
    ("regenerateLinkedinPost('${escapeHtml(p.id)}')", "regenerateLinkedinPost('${escapeHtml(p.id)}', '${postScope}')"),
    ("approveLinkedinPostImage('${escapeHtml(p.id)}')", "approveLinkedinPostImage('${escapeHtml(p.id)}', '${postScope}')"),
    ("regenerateLinkedinPostImage('${escapeHtml(p.id)}')", "regenerateLinkedinPostImage('${escapeHtml(p.id)}', '${postScope}')"),
    ("publishLinkedinPost('${escapeHtml(p.id)}', true)", "publishLinkedinPost('${escapeHtml(p.id)}', true, '${postScope}')"),
    ("publishLinkedinPost('${escapeHtml(p.id)}', false)", "publishLinkedinPost('${escapeHtml(p.id)}', false, '${postScope}')"),
]
for old, new in onclick_replacements:
    if old in h and new not in h:
        h = h.replace(old, new)

# renderLinkedinPostsContainer
h = h.replace(
    """              function renderLinkedinPostsContainer() {
                const el = document.getElementById("linkedinPostsContainer");
                if (!el) return;
                if (!linkedinGeneratedPosts.length) {
                  el.innerHTML = '<div class="li-posts-loading">Sem posts. Clica «Gerar posts».</div>';
                  return;
                }
                el.innerHTML = linkedinGeneratedPosts.map((p) => renderLinkedinPostCardHtml(p, false)).join("");
              }""",
    """              function renderLinkedinPostsContainer() {
                const el = document.getElementById("linkedinPostsContainer");
                if (!el) return;
                if (!linkedinPostsTabPosts.length) {
                  el.innerHTML = '<div class="li-posts-loading">Sem posts. Clica «Gerar posts».</div>';
                  return;
                }
                el.innerHTML = linkedinPostsTabPosts.map((p) => renderLinkedinPostCardHtml(p, false, "posts")).join("");
              }""",
    1,
)

# renderLinkedinCalendarContainer - use calendar array only
h = h.replace("ensureLinkedinPostsWeekDates();", "ensureLinkedinPostsWeekDates(\"calendar\");", 1)
h = h.replace(
    "if (!linkedinGeneratedPosts.length) {\n                  const emptyDays = weekDays.map",
    "if (!linkedinCalendarPosts.length) {\n                  const emptyDays = weekDays.map",
    1,
)
h = h.replace(
    "linkedinGeneratedPosts.forEach((p) => {\n                  const key = p.scheduled_date",
    "linkedinCalendarPosts.forEach((p) => {\n                  const key = p.scheduled_date",
    1,
)
h = h.replace(
    ".map((p) => renderLinkedinPostCardHtml(p, true)).join(\"\");",
    ".map((p) => renderLinkedinPostCardHtml(p, true, \"calendar\")).join(\"\");",
    1,
)

# generate functions - full replace
OLD_GEN = """async function generateLinkedinPostsFromSnapshot(postCount) {
                if (!linkedinAnalysisSnapshot) {
                  alert("Faz primeiro uma análise de perfil.");
                  return;
                }
                if (!linkedinAnalysisIsOwnProfile) {
                  alert("Gerar posts está disponível apenas na Auto-análise do teu perfil (login + perfil guardado).");
                  return;
                }
                const count = typeof postCount === "number" ? Math.max(1, Math.min(7, postCount)) : 3;
                const el = document.getElementById("linkedinPostsContainer");
                const calEl = document.getElementById("linkedinCalendarContainer");
                const btnIds = ["btnGenerateLinkedinPosts", "btnGenerateLinkedinCalendarPosts"];
                btnIds.forEach((id) => {
                  const b = document.getElementById(id);
                  if (b) { b.disabled = true; b.textContent = "A gerar…"; }
                });
                const loadingHtml = '<div class="li-posts-loading">A gerar posts com IA…</div>';
                if (el) el.innerHTML = loadingHtml;
                if (calEl) calEl.innerHTML = loadingHtml;
                try {
                  const res = await fetch("/agents/linkedin/generate-posts", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      analysis: linkedinAnalysisSnapshot,
                      public_profile_data: linkedinAnalysisSnapshot.public_profile_data || {},
                      profile_url: linkedinAnalysisSnapshot.profile_url || "",
                      count: count,
                      language: "pt-PT",
                    }),
                  });
                  const json = await res.json();
                  if (!res.ok) throw new Error(json.detail || JSON.stringify(json));
                  linkedinGeneratedPosts = assignLinkedinPostsToWeek((json.posts || []).map((row) => ({
                    ...row,
                    status: "draft",
                  })));
                  refreshLinkedinPostsUI();
                  enableGeneratePostsButton();
                } catch (e) {
                  const errHtml = `<div class="err">Erro: ${escapeHtml(e.message || String(e))}</div>`;
                  if (el) el.innerHTML = errHtml;
                  if (calEl) calEl.innerHTML = errHtml;
                  enableGeneratePostsButton();
                }
              }

              async function generateLinkedinPostsForCalendar() {
                return generateLinkedinPostsFromSnapshot(7);
              }"""

NEW_GEN = """async function linkedinFetchGeneratedPosts(count) {
                const res = await fetch("/agents/linkedin/generate-posts", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    analysis: linkedinAnalysisSnapshot,
                    public_profile_data: linkedinAnalysisSnapshot.public_profile_data || {},
                    profile_url: linkedinAnalysisSnapshot.profile_url || "",
                    count: count,
                    language: "pt-PT",
                  }),
                });
                const json = await res.json();
                if (!res.ok) throw new Error(json.detail || JSON.stringify(json));
                return (json.posts || []).map((row) => ({ ...row, status: "draft" }));
              }

              async function generateLinkedinPostsFromSnapshot() {
                if (!linkedinAnalysisSnapshot) {
                  alert("Faz primeiro uma análise de perfil.");
                  return;
                }
                if (!linkedinAnalysisIsOwnProfile) {
                  alert("Gerar posts está disponível apenas na Auto-análise do teu perfil (login + perfil guardado).");
                  return;
                }
                const el = document.getElementById("linkedinPostsContainer");
                const btn = document.getElementById("btnGenerateLinkedinPosts");
                if (btn) { btn.disabled = true; btn.textContent = "A gerar…"; }
                if (el) el.innerHTML = '<div class="li-posts-loading">A gerar posts com IA…</div>';
                try {
                  linkedinPostsTabPosts = (await linkedinFetchGeneratedPosts(3));
                  renderLinkedinPostsContainer();
                  enableGeneratePostsButton();
                } catch (e) {
                  if (el) el.innerHTML = `<div class="err">Erro: ${escapeHtml(e.message || String(e))}</div>`;
                  enableGeneratePostsButton();
                }
              }

              async function generateLinkedinPostsForCalendar() {
                if (!linkedinAnalysisSnapshot) {
                  alert("Faz primeiro uma análise de perfil.");
                  return;
                }
                if (!linkedinAnalysisIsOwnProfile) {
                  alert("Gerar posts está disponível apenas na Auto-análise do teu perfil (login + perfil guardado).");
                  return;
                }
                const el = document.getElementById("linkedinCalendarContainer");
                const btn = document.getElementById("btnGenerateLinkedinCalendarPosts");
                if (btn) { btn.disabled = true; btn.textContent = "A gerar…"; }
                if (el) el.innerHTML = '<div class="li-posts-loading">A gerar posts da semana com IA…</div>';
                try {
                  linkedinCalendarPosts = assignLinkedinPostsToWeek(await linkedinFetchGeneratedPosts(7));
                  renderLinkedinCalendarContainer();
                  enableGeneratePostsButton();
                } catch (e) {
                  if (el) el.innerHTML = `<div class="err">Erro: ${escapeHtml(e.message || String(e))}</div>`;
                  enableGeneratePostsButton();
                }
              }"""

if OLD_GEN in h:
    h = h.replace(OLD_GEN, NEW_GEN, 1)
else:
    raise SystemExit("generate block not found")

# Post action handlers
h = h.replace(
    "async function approveLinkedinPost(id) {\n                const p = linkedinGeneratedPosts.find((x) => x.id === id);",
    "async function approveLinkedinPost(id, scope) {\n                const entry = findLinkedinPostEntry(id);\n                const p = entry.post;\n                scope = scope || entry.scope;",
    1,
)
h = h.replace(
    "                refreshLinkedinPostsUI();\n                const wantImage = confirm(",
    "                refreshLinkedinPostScope(scope);\n                const wantImage = confirm(",
    1,
)
h = h.replace(
    "await linkedinGeneratePostImage(p, null);",
    "await linkedinGeneratePostImage(p, null, scope);",
    1,
)

h = h.replace(
    "async function linkedinGeneratePostImage(p, editInstructions) {\n                if (!p) return;\n                p.image_generating = true;\n                p.image_status = \"draft\";\n                refreshLinkedinPostsUI();",
    "async function linkedinGeneratePostImage(p, editInstructions, scope) {\n                if (!p) return;\n                const entry = findLinkedinPostEntry(p.id);\n                scope = scope || entry.scope;\n                p.image_generating = true;\n                p.image_status = \"draft\";\n                refreshLinkedinPostScope(scope);",
    1,
)
h = h.replace(
    "                  refreshLinkedinPostsUI();\n                }\n              }\n\n              function approveLinkedinPostImage(id) {",
    "                  refreshLinkedinPostScope(scope);\n                }\n              }\n\n              function approveLinkedinPostImage(id, scope) {",
    1,
)
h = h.replace(
    "function approveLinkedinPostImage(id, scope) {\n                const p = linkedinGeneratedPosts.find((x) => x.id === id);",
    "function approveLinkedinPostImage(id, scope) {\n                const entry = findLinkedinPostEntry(id);\n                const p = entry.post;\n                scope = scope || entry.scope;",
    1,
)
h = h.replace(
    "                p.image_status = \"approved\";\n                refreshLinkedinPostsUI();\n              }\n\n              \n              \n              function getPersistedLinkedinPublishToken",
    "                p.image_status = \"approved\";\n                refreshLinkedinPostScope(scope);\n              }\n\n              \n              \n              function getPersistedLinkedinPublishToken",
    1,
)

h = h.replace(
    "async function publishLinkedinPost(id, includeImage) {\n                const p = linkedinGeneratedPosts.find((x) => x.id === id);",
    "async function publishLinkedinPost(id, includeImage, scope) {\n                const entry = findLinkedinPostEntry(id);\n                const p = entry.post;\n                scope = scope || entry.scope;",
    1,
)
# publish refresh calls - replace remaining in publish function only via targeted
pub_start = h.find("async function publishLinkedinPost")
pub_end = h.find("async function regenerateLinkedinPostImage", pub_start)
pub_block = h[pub_start:pub_end]
pub_block = pub_block.replace("refreshLinkedinPostsUI()", "refreshLinkedinPostScope(scope)")
h = h[:pub_start] + pub_block + h[pub_end:]

h = h.replace(
    "async function regenerateLinkedinPostImage(id) {\n                const p = linkedinGeneratedPosts.find((x) => x.id === id);",
    "async function regenerateLinkedinPostImage(id, scope) {\n                const entry = findLinkedinPostEntry(id);\n                const p = entry.post;\n                scope = scope || entry.scope;",
    1,
)
h = h.replace(
    "await linkedinGeneratePostImage(p, instr || null);",
    "await linkedinGeneratePostImage(p, instr || null, scope);",
    1,
)

h = h.replace(
    "function startLinkedinPostEdit(id) {\n                linkedinGeneratedPosts.forEach((x) => { if (x.status === \"editing\") x.status = \"draft\"; });\n                const p = linkedinGeneratedPosts.find((x) => x.id === id);",
    "function startLinkedinPostEdit(id, scope) {\n                scope = scope || findLinkedinPostEntry(id).scope;\n                getLinkedinPostsArray(scope).forEach((x) => { if (x.status === \"editing\") x.status = \"draft\"; });\n                const p = getLinkedinPostsArray(scope).find((x) => x.id === id);",
    1,
)
h = h.replace(
    "                p.status = \"editing\";\n                refreshLinkedinPostsUI();\n              }\n\n              function cancelLinkedinPostEdit(id) {",
    "                p.status = \"editing\";\n                refreshLinkedinPostScope(scope);\n              }\n\n              function cancelLinkedinPostEdit(id, scope) {",
    1,
)
h = h.replace(
    "function cancelLinkedinPostEdit(id, scope) {\n                const p = linkedinGeneratedPosts.find((x) => x.id === id);",
    "function cancelLinkedinPostEdit(id, scope) {\n                scope = scope || findLinkedinPostEntry(id).scope;\n                const p = getLinkedinPostsArray(scope).find((x) => x.id === id);",
    1,
)
h = h.replace(
    "                delete p.bodyEdit;\n                refreshLinkedinPostsUI();\n              }\n\n              function saveLinkedinPostEdit(id) {",
    "                delete p.bodyEdit;\n                refreshLinkedinPostScope(scope);\n              }\n\n              function saveLinkedinPostEdit(id, scope) {",
    1,
)
h = h.replace(
    "function saveLinkedinPostEdit(id, scope) {\n                const p = linkedinGeneratedPosts.find((x) => x.id === id);",
    "function saveLinkedinPostEdit(id, scope) {\n                scope = scope || findLinkedinPostEntry(id).scope;\n                const p = getLinkedinPostsArray(scope).find((x) => x.id === id);",
    1,
)
h = h.replace(
    "                p.status = \"draft\";\n                refreshLinkedinPostsUI();\n              }\n\n              function deleteLinkedinPost(id) {",
    "                p.status = \"draft\";\n                refreshLinkedinPostScope(scope);\n              }\n\n              function deleteLinkedinPost(id, scope) {",
    1,
)
h = h.replace(
    """              function deleteLinkedinPost(id, scope) {
                if (!confirm("Apagar este post?")) return;
                linkedinGeneratedPosts = linkedinGeneratedPosts.filter((x) => x.id !== id);
                refreshLinkedinPostsUI();
              }""",
    """              function deleteLinkedinPost(id, scope) {
                if (!confirm("Apagar este post?")) return;
                scope = scope || findLinkedinPostEntry(id).scope;
                const list = getLinkedinPostsArray(scope);
                if (scope === "calendar") {
                  linkedinCalendarPosts = list.filter((x) => x.id !== id);
                } else {
                  linkedinPostsTabPosts = list.filter((x) => x.id !== id);
                }
                refreshLinkedinPostScope(scope);
              }""",
    1,
)

h = h.replace(
    "async function regenerateLinkedinPost(id) {\n                const p = linkedinGeneratedPosts.find((x) => x.id === id);",
    "async function regenerateLinkedinPost(id, scope) {\n                scope = scope || findLinkedinPostEntry(id).scope;\n                const p = getLinkedinPostsArray(scope).find((x) => x.id === id);",
    1,
)
regen_start = h.find("async function regenerateLinkedinPost(id, scope)")
regen_end = h.find("const profileInput = document.getElementById", regen_start)
regen_block = h[regen_start:regen_end]
regen_block = regen_block.replace("refreshLinkedinPostsUI();", "refreshLinkedinPostScope(scope);")
h = h[:regen_start] + regen_block + h[regen_end:]

# refreshLinkedinPostsUI - keep for any legacy calls but fix body
h = h.replace(
    """              function refreshLinkedinPostsUI() {
                renderLinkedinPostsContainer();
                renderLinkedinCalendarContainer();
              }""",
    """              function refreshLinkedinPostsUI() {
                renderLinkedinPostsContainer();
                renderLinkedinCalendarContainer();
              }""",
)

# Remove any leftover linkedinGeneratedPosts references
if "linkedinGeneratedPosts" in h:
    count = h.count("linkedinGeneratedPosts")
    print("WARN: still has linkedinGeneratedPosts x", count)
    # try generic cleanup for stray references
    h = h.replace("linkedinGeneratedPosts", "linkedinPostsTabPosts")

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")

checks = {
    "tab_posts": "linkedinPostsTabPosts" in h,
    "tab_cal": "linkedinCalendarPosts" in h,
    "fetch_helper": "linkedinFetchGeneratedPosts" in h,
    "cal_gen_7": "linkedinFetchGeneratedPosts(7)" in h,
    "posts_gen_3": "linkedinFetchGeneratedPosts(3)" in h,
    "no_shared": "linkedinGeneratedPosts" not in h,
    "scope_card": "renderLinkedinPostCardHtml(p, false, \"posts\")" in h,
}
print("ok", checks)
if not all(checks.values()):
    raise SystemExit("verification failed")
