# -*- coding: utf-8 -*-
"""Calendário: dia clicável abre modal com post completo e acções."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

MODAL_CSS = """
              .li-calendar-day.is-clickable { cursor: pointer; transition: transform 0.15s ease, box-shadow 0.15s ease; }
              .li-calendar-day.is-clickable:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.35); }
              .li-calendar-day.is-clickable:focus-visible { outline: 2px solid rgba(251,113,133,0.7); outline-offset: 2px; }
              .li-calendar-day-body { max-height: none; overflow: visible; }
              .li-calendar-day-preview {
                display: flex; flex-direction: column; gap: 8px; padding: 4px 2px; min-height: 100px;
              }
              .li-calendar-preview-status {
                font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
                color: rgba(52,211,153,0.95);
              }
              .li-calendar-day:not(.has-post) .li-calendar-preview-status { color: var(--muted); }
              .li-calendar-preview-title {
                font-size: 0.82rem; line-height: 1.35; color: var(--text); margin: 0;
                display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
              }
              .li-calendar-preview-cta {
                margin-top: auto; font-size: 0.75rem; font-weight: 600; color: rgba(251,113,133,0.95);
              }
              .li-cal-modal {
                display: none; position: fixed; inset: 0; z-index: 1200;
                align-items: center; justify-content: center; padding: 20px;
              }
              .li-cal-modal.open { display: flex; }
              .li-cal-modal-backdrop {
                position: absolute; inset: 0; background: rgba(4,6,12,0.72); backdrop-filter: blur(4px);
              }
              .li-cal-modal-panel {
                position: relative; z-index: 1; width: min(640px, 100%); max-height: min(88vh, 900px);
                overflow-y: auto; background: var(--bg-1); border: 1px solid var(--line-strong);
                border-radius: 16px; padding: 18px 18px 22px; box-shadow: 0 24px 60px rgba(0,0,0,0.55);
              }
              .li-cal-modal-head {
                display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
                margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px solid var(--line);
              }
              .li-cal-modal-head h4 { margin: 0; font-size: 1.05rem; font-weight: 700; }
              .li-cal-modal-close {
                flex-shrink: 0; width: 36px; height: 36px; border-radius: 10px; border: 1px solid var(--line);
                background: var(--surface); color: var(--text); font-size: 1.4rem; line-height: 1; cursor: pointer;
              }
              .li-cal-modal-close:hover { border-color: rgba(251,113,133,0.5); }
              .li-cal-modal-body .li-post-card { margin: 0; }
"""

if ".li-cal-modal" not in h:
    anchor = ".li-calendar-empty {"
    if anchor not in h:
        raise SystemExit("calendar CSS anchor not found")
    h = h.replace(anchor, MODAL_CSS.strip() + "\n              " + anchor, 1)

MODAL_HTML = """
                        <div id="linkedinCalendarModal" class="li-cal-modal" aria-hidden="true" role="dialog" aria-labelledby="linkedinCalendarModalTitle">
                          <div class="li-cal-modal-backdrop" onclick="closeLinkedinCalendarDayModal()"></div>
                          <div class="li-cal-modal-panel" onclick="event.stopPropagation()">
                            <div class="li-cal-modal-head">
                              <h4 id="linkedinCalendarModalTitle">Post do dia</h4>
                              <button type="button" class="li-cal-modal-close" onclick="closeLinkedinCalendarDayModal()" aria-label="Fechar">&times;</button>
                            </div>
                            <div id="linkedinCalendarModalBody" class="li-cal-modal-body"></div>
                          </div>
                        </div>"""

if "linkedinCalendarModal" not in h:
    anchor = 'id="btnGenerateLinkedinCalendarPosts"'
    idx = h.find(anchor)
    if idx < 0:
        raise SystemExit("calendar button not found")
    close_btn = h.find("</button>", idx)
    h = h[: close_btn + len("</button>")] + MODAL_HTML + h[close_btn + len("</button>") :]

# refreshLinkedinPostScope - update calendar branch
OLD_REFRESH = """              function refreshLinkedinPostScope(scope) {
                if (!scope || scope === "posts") renderLinkedinPostsContainer();
                if (!scope || scope === "calendar") renderLinkedinCalendarContainer();
              }"""

NEW_REFRESH = """              function refreshLinkedinPostScope(scope) {
                if (!scope || scope === "posts") renderLinkedinPostsContainer();
                if (!scope || scope === "calendar") {
                  renderLinkedinCalendarContainer();
                  if (linkedinCalendarModalDateKey) renderLinkedinCalendarModalContent();
                }
              }

              let linkedinCalendarModalDateKey = null;

              function linkedinCalendarDayLabel(dateKey) {
                const d = new Date(dateKey + "T12:00:00");
                if (isNaN(d.getTime())) return dateKey;
                const dowNames = ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"];
                return dowNames[d.getDay()] + " · Dia " + d.getDate();
              }

              function renderLinkedinCalendarDayPreview(p) {
                const st = p.status || "draft";
                const statusText = st === "approved" ? "Aprovado" : (st === "editing" ? "A editar" : "Rascunho");
                const rawTitle = String(p.title || p.body || "").trim();
                const short = rawTitle.length > 72 ? rawTitle.slice(0, 72) + "…" : rawTitle;
                const imgHint = p.generated_image_url ? " · com imagem" : "";
                return `
                  <div class="li-calendar-day-preview">
                    <span class="li-calendar-preview-status">${escapeHtml(statusText)}${imgHint ? " · imagem" : ""}</span>
                    <p class="li-calendar-preview-title">${escapeHtml(short || "Post planeado")}</p>
                    <span class="li-calendar-preview-cta">Abrir post →</span>
                  </div>`;
              }

              function renderLinkedinCalendarModalContent() {
                const body = document.getElementById("linkedinCalendarModalBody");
                const titleEl = document.getElementById("linkedinCalendarModalTitle");
                if (!body || !linkedinCalendarModalDateKey) return;
                const key = linkedinCalendarModalDateKey;
                if (titleEl) titleEl.textContent = linkedinCalendarDayLabel(key);
                const posts = linkedinCalendarPosts.filter((p) => p.scheduled_date === key);
                if (!posts.length) {
                  body.innerHTML = '<div class="li-calendar-empty">Sem post neste dia.</div>';
                  return;
                }
                body.innerHTML = posts.map((p) => renderLinkedinPostCardHtml(p, false, "calendar")).join("");
              }

              function openLinkedinCalendarDayModal(dateKey) {
                linkedinCalendarModalDateKey = dateKey;
                const modal = document.getElementById("linkedinCalendarModal");
                if (!modal) return;
                renderLinkedinCalendarModalContent();
                modal.classList.add("open");
                modal.setAttribute("aria-hidden", "false");
                document.body.style.overflow = "hidden";
              }

              function closeLinkedinCalendarDayModal() {
                linkedinCalendarModalDateKey = null;
                const modal = document.getElementById("linkedinCalendarModal");
                if (modal) {
                  modal.classList.remove("open");
                  modal.setAttribute("aria-hidden", "true");
                }
                document.body.style.overflow = "";
              }

              document.addEventListener("keydown", (e) => {
                if (e.key === "Escape" && linkedinCalendarModalDateKey) closeLinkedinCalendarDayModal();
              });"""

if OLD_REFRESH in h:
    h = h.replace(OLD_REFRESH, NEW_REFRESH, 1)
elif "openLinkedinCalendarDayModal" in h:
    print("modal JS already present")
else:
    raise SystemExit("refreshLinkedinPostScope not found")

# Replace renderLinkedinCalendarContainer entirely
OLD_CAL = """              function renderLinkedinCalendarContainer() {
                const el = document.getElementById("linkedinCalendarContainer");
                if (!el) return;
                ensureLinkedinPostsWeekDates("calendar");
                const weekDays = getLinkedinWeekDays();
                const dowNames = ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"];
                const todayKey = formatLinkedinDateKey(new Date());
                if (!linkedinCalendarPosts.length) {
                  const emptyDays = weekDays.map((d) => {
                    const key = formatLinkedinDateKey(d);
                    const isToday = key === todayKey;
                    return `
                      <div class="li-calendar-day${isToday ? " is-today" : ""}">
                        <div class="li-calendar-day-head">
                          <span class="li-calendar-dow">${dowNames[d.getDay()]}</span>
                          <span class="li-calendar-day-num">Dia ${d.getDate()}</span>
                        </div>
                        <div class="li-calendar-day-body">
                          <div class="li-calendar-empty">Sem post planeado</div>
                        </div>
                      </div>`;
                  }).join("");
                  el.innerHTML = `<div class="li-calendar-title">${linkedinWeekTitle()}</div><div class="li-calendar-grid">${emptyDays}</div>`;
                  return;
                }
                const postsByDate = {};
                linkedinCalendarPosts.forEach((p) => {
                  const key = p.scheduled_date || formatLinkedinDateKey(weekDays[0]);
                  if (!postsByDate[key]) postsByDate[key] = [];
                  postsByDate[key].push(p);
                });
                const grid = weekDays.map((d) => {
                  const key = formatLinkedinDateKey(d);
                  const isToday = key === todayKey;
                  const dayPosts = (postsByDate[key] || []).map((p) => renderLinkedinPostCardHtml(p, true, "calendar")).join("");
                  return `
                    <div class="li-calendar-day${isToday ? " is-today" : ""}">
                      <div class="li-calendar-day-head">
                        <span class="li-calendar-dow">${dowNames[d.getDay()]}</span>
                        <span class="li-calendar-day-num">Dia ${d.getDate()}</span>
                      </div>
                      <div class="li-calendar-day-body">
                        ${dayPosts || '<div class="li-calendar-empty">Sem post planeado</div>'}
                      </div>
                    </div>`;
                }).join("");
                el.innerHTML = `<div class="li-calendar-title">${linkedinWeekTitle()}</div><div class="li-calendar-grid">${grid}</div>`;
              }"""

NEW_CAL = """              function renderLinkedinCalendarContainer() {
                const el = document.getElementById("linkedinCalendarContainer");
                if (!el) return;
                ensureLinkedinPostsWeekDates("calendar");
                const weekDays = getLinkedinWeekDays();
                const dowNames = ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"];
                const todayKey = formatLinkedinDateKey(new Date());
                const postsByDate = {};
                linkedinCalendarPosts.forEach((p) => {
                  const key = p.scheduled_date || formatLinkedinDateKey(weekDays[0]);
                  if (!postsByDate[key]) postsByDate[key] = [];
                  postsByDate[key].push(p);
                });
                const grid = weekDays.map((d) => {
                  const key = formatLinkedinDateKey(d);
                  const isToday = key === todayKey;
                  const dayList = postsByDate[key] || [];
                  const hasPost = dayList.length > 0;
                  const preview = hasPost
                    ? renderLinkedinCalendarDayPreview(dayList[0])
                    : '<div class="li-calendar-empty">Sem post planeado</div>';
                  const clickAttr = hasPost
                    ? ` class="li-calendar-day is-clickable has-post${isToday ? " is-today" : ""}" role="button" tabindex="0" onclick="openLinkedinCalendarDayModal('${key}')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openLinkedinCalendarDayModal('${key}');}"`
                    : ` class="li-calendar-day${isToday ? " is-today" : ""}"`;
                  return `
                    <div${clickAttr}>
                      <div class="li-calendar-day-head">
                        <span class="li-calendar-dow">${dowNames[d.getDay()]}</span>
                        <span class="li-calendar-day-num">Dia ${d.getDate()}</span>
                      </div>
                      <div class="li-calendar-day-body">${preview}</div>
                    </div>`;
                }).join("");
                el.innerHTML = `<div class="li-calendar-title">${linkedinWeekTitle()}</div><div class="li-calendar-grid">${grid}</div>`;
              }"""

if OLD_CAL in h:
    h = h.replace(OLD_CAL, NEW_CAL, 1)
elif "openLinkedinCalendarDayModal" in h and "renderLinkedinCalendarDayPreview" in h:
    print("calendar render already patched")
else:
    raise SystemExit("renderLinkedinCalendarContainer block not found")

# Close modal when deleting last post on that day
if "closeLinkedinCalendarDayModal();" not in h.split("function deleteLinkedinPost")[1].split("async function regenerateLinkedinPost")[0]:
    h = h.replace(
        """                refreshLinkedinPostScope(scope);
              }

              async function regenerateLinkedinPost(id, scope) {""",
        """                refreshLinkedinPostScope(scope);
                if (scope === "calendar" && linkedinCalendarModalDateKey) {
                  const still = linkedinCalendarPosts.some((x) => x.scheduled_date === linkedinCalendarModalDateKey);
                  if (!still) closeLinkedinCalendarDayModal();
                }
              }

              async function regenerateLinkedinPost(id, scope) {""",
        1,
    )

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
checks = {
    "modal": "linkedinCalendarModal" in h,
    "open_fn": "openLinkedinCalendarDayModal" in h,
    "preview": "renderLinkedinCalendarDayPreview" in h,
    "no_inline_card": "renderLinkedinPostCardHtml(p, true, \"calendar\")" not in h.split("renderLinkedinCalendarContainer")[1].split("async function approveLinkedinPost")[0],
}
print("ok", checks)
