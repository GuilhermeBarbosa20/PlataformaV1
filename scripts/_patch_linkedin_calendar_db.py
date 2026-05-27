# -*- coding: utf-8 -*-
"""Persistência do calendário LinkedIn na Supabase + carregar ao abrir."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

CAL_DB_JS = r"""
              let linkedinCalendarDbLoaded = false;
              let linkedinCalendarSaveTimer = null;

              function linkedinCalendarWeekStartKey() {
                const days = getLinkedinWeekDays();
                return days[0] ? formatLinkedinDateKey(days[0]) : formatLinkedinDateKey(new Date());
              }

              async function loadLinkedinCalendarPostsFromDatabase() {
                const ctx = await getLinkedinSupabaseSession();
                if (!ctx || !ctx.session) {
                  linkedinCalendarDbLoaded = false;
                  return false;
                }
                try {
                  const res = await fetch("/agents/linkedin/calendar-posts/load", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ supabase_access_token: ctx.session.access_token }),
                  });
                  const json = await res.json().catch(() => ({}));
                  if (!res.ok) return false;
                  if (json.found && Array.isArray(json.posts) && json.posts.length) {
                    linkedinCalendarPosts = json.posts.map((row) => ({
                      ...row,
                      status: row.status || "draft",
                    }));
                    ensureLinkedinPostsWeekDates("calendar");
                    linkedinCalendarDbLoaded = true;
                    renderLinkedinCalendarContainer();
                    enableGeneratePostsButton();
                    return true;
                  }
                  linkedinCalendarDbLoaded = true;
                  return false;
                } catch (e) {
                  console.warn("loadLinkedinCalendarPostsFromDatabase:", e);
                  return false;
                }
              }

              function scheduleSaveLinkedinCalendarPostsToDatabase() {
                if (linkedinCalendarSaveTimer) clearTimeout(linkedinCalendarSaveTimer);
                linkedinCalendarSaveTimer = setTimeout(() => {
                  saveLinkedinCalendarPostsToDatabase();
                }, 600);
              }

              async function saveLinkedinCalendarPostsToDatabase() {
                const ctx = await getLinkedinSupabaseSession();
                if (!ctx || !ctx.session) return;
                try {
                  await fetch("/agents/linkedin/calendar-posts/save", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      supabase_access_token: ctx.session.access_token,
                      posts: linkedinCalendarPosts,
                      week_start: linkedinCalendarWeekStartKey(),
                    }),
                  });
                } catch (e) {
                  console.warn("saveLinkedinCalendarPostsToDatabase:", e);
                }
              }
"""

if "loadLinkedinCalendarPostsFromDatabase" not in h:
    h = h.replace(
        "let linkedinCalendarPosts = [];\n\n              function getLinkedinPostsArray",
        "let linkedinCalendarPosts = [];\n" + CAL_DB_JS + "\n              function getLinkedinPostsArray",
        1,
    )

# refreshLinkedinPostScope - save after calendar updates
OLD_REFRESH = """              function refreshLinkedinPostScope(scope) {
                if (!scope || scope === "posts") renderLinkedinPostsContainer();
                if (!scope || scope === "calendar") {
                  renderLinkedinCalendarContainer();
                  if (linkedinCalendarModalDateKey) renderLinkedinCalendarModalContent();
                }
              }"""

NEW_REFRESH = """              function refreshLinkedinPostScope(scope) {
                if (!scope || scope === "posts") renderLinkedinPostsContainer();
                if (!scope || scope === "calendar") {
                  renderLinkedinCalendarContainer();
                  if (linkedinCalendarModalDateKey) renderLinkedinCalendarModalContent();
                  if (linkedinCalendarPosts.length) scheduleSaveLinkedinCalendarPostsToDatabase();
                }
              }"""

if OLD_REFRESH in h:
    h = h.replace(OLD_REFRESH, NEW_REFRESH, 1)

# reset - don't wipe calendar from memory; reload from DB
OLD_RESET = """              function resetLinkedinPostsAfterAnalysis() {
                linkedinPostsTabPosts = [];
                linkedinCalendarPosts = [];
                const el = document.getElementById("linkedinPostsContainer");
                const calEl = document.getElementById("linkedinCalendarContainer");
                enableGeneratePostsButton();
                const postsHint = linkedinAnalysisSnapshot
                  ? '<div class="li-posts-loading">Análise concluída. Clica <strong>Gerar posts</strong> para criar publicações com IA.</div>'
                  : '<div class="li-posts-loading">Faz uma análise de perfil primeiro.</div>';
                const calHint = linkedinAnalysisSnapshot
                  ? '<div class="li-posts-loading">Análise concluída. Clica <strong>Gerar posts da semana</strong> para planear no calendário.</div>'
                  : '<div class="li-posts-loading">Faz uma análise de perfil primeiro.</div>';
                if (el) el.innerHTML = postsHint;
                if (calEl) calEl.innerHTML = calHint;
              }"""

NEW_RESET = """              function resetLinkedinPostsAfterAnalysis() {
                linkedinPostsTabPosts = [];
                const el = document.getElementById("linkedinPostsContainer");
                enableGeneratePostsButton();
                const postsHint = linkedinAnalysisSnapshot
                  ? '<div class="li-posts-loading">Análise concluída. Clica <strong>Gerar posts</strong> para criar publicações com IA.</div>'
                  : '<div class="li-posts-loading">Faz uma análise de perfil primeiro.</div>';
                if (el) el.innerHTML = postsHint;
                loadLinkedinCalendarPostsFromDatabase();
              }"""

if OLD_RESET in h:
    h = h.replace(OLD_RESET, NEW_RESET, 1)

# generate calendar - save after generate
h = h.replace(
    "linkedinCalendarPosts = assignLinkedinPostsToWeek(await linkedinFetchGeneratedPosts(7));\n                  renderLinkedinCalendarContainer();\n                  enableGeneratePostsButton();",
    "linkedinCalendarPosts = assignLinkedinPostsToWeek(await linkedinFetchGeneratedPosts(7));\n                  renderLinkedinCalendarContainer();\n                  enableGeneratePostsButton();\n                  await saveLinkedinCalendarPostsToDatabase();",
    1,
)

# refreshLinkedinSupabaseSession - load calendar on login
OLD_SESS = """async function refreshLinkedinSupabaseSession() {
                const ctx = await getLinkedinSupabaseSession();
                updateLinkedinAuthButtons(Boolean(ctx));
                if (ctx) {
                  captureLinkedinOAuthTokens(ctx.session);
                  await loadLinkedinProfileForSession(ctx.session);
                  await tryResolveLinkedinProfileUrl(ctx.sb);
                }
                updateAutoAnalyzeButton();
              }"""

NEW_SESS = """async function refreshLinkedinSupabaseSession() {
                const ctx = await getLinkedinSupabaseSession();
                updateLinkedinAuthButtons(Boolean(ctx));
                if (ctx) {
                  captureLinkedinOAuthTokens(ctx.session);
                  await loadLinkedinProfileForSession(ctx.session);
                  await tryResolveLinkedinProfileUrl(ctx.sb);
                  await loadLinkedinCalendarPostsFromDatabase();
                } else {
                  linkedinCalendarPosts = [];
                  linkedinCalendarDbLoaded = false;
                  renderLinkedinCalendarContainer();
                  enableGeneratePostsButton();
                }
                updateAutoAnalyzeButton();
              }"""

if OLD_SESS in h:
    h = h.replace(OLD_SESS, NEW_SESS, 1)

# attachTabHandlers - load when opening calendar tab
OLD_TABS = """              function attachTabHandlers() {
                document.querySelectorAll(".tab").forEach(tab => {
                  tab.addEventListener("click", () => {
                    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
                    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
                    tab.classList.add("active");
                    const target = tab.getAttribute("data-target");
                    const panel = document.getElementById("panel-" + target);
                    if (panel) panel.classList.add("active");
                  });
                });
              }"""

NEW_TABS = """              function attachTabHandlers() {
                document.querySelectorAll(".tab").forEach(tab => {
                  tab.addEventListener("click", () => {
                    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
                    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
                    tab.classList.add("active");
                    const target = tab.getAttribute("data-target");
                    const panel = document.getElementById("panel-" + target);
                    if (panel) panel.classList.add("active");
                    if (target === "calendar") loadLinkedinCalendarPostsFromDatabase();
                  });
                });
              }"""

if OLD_TABS in h:
    h = h.replace(OLD_TABS, NEW_TABS, 1)

# delete post - save empty if no posts left
if "await saveLinkedinCalendarPostsToDatabase();" not in h.split("function deleteLinkedinPost")[1].split("async function regenerateLinkedinPost")[0]:
    h = h.replace(
        """                refreshLinkedinPostScope(scope);
                if (scope === "calendar" && linkedinCalendarModalDateKey) {
                  const still = linkedinCalendarPosts.some((x) => x.scheduled_date === linkedinCalendarModalDateKey);
                  if (!still) closeLinkedinCalendarDayModal();
                }
              }

              async function regenerateLinkedinPost(id, scope) {""",
        """                refreshLinkedinPostScope(scope);
                if (scope === "calendar") {
                  if (!linkedinCalendarPosts.length) {
                    const calEl = document.getElementById("linkedinCalendarContainer");
                    if (calEl) calEl.innerHTML = '<div class="li-posts-loading">Clica em <strong>Gerar posts da semana</strong> para planear publicações com IA.</div>';
                  }
                  await saveLinkedinCalendarPostsToDatabase();
                  if (linkedinCalendarModalDateKey) {
                    const still = linkedinCalendarPosts.some((x) => x.scheduled_date === linkedinCalendarModalDateKey);
                    if (!still) closeLinkedinCalendarDayModal();
                  }
                }
              }

              async function regenerateLinkedinPost(id, scope) {""",
        1,
    )

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
checks = {
    "load": "loadLinkedinCalendarPostsFromDatabase" in h,
    "save": "saveLinkedinCalendarPostsToDatabase" in h,
    "schedule": "scheduleSaveLinkedinCalendarPostsToDatabase" in h,
    "tab_load": 'target === "calendar"' in h,
    "reset_no_clear": "linkedinCalendarPosts = [];" not in h.split("resetLinkedinPostsAfterAnalysis")[1].split("function linkedinPostTypeLabel")[0],
}
print("ok", checks)
