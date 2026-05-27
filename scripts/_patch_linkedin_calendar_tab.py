# -*- coding: utf-8 -*-
"""Adiciona aba Calendário (semana a partir de hoje) com o mesmo fluxo de posts/imagens."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

CALENDAR_CSS = """
              .li-calendar-wrap { margin-top: 8px; }
              .li-calendar-title {
                font-size: 1.05rem; font-weight: 700; margin: 0 0 12px;
                padding: 10px 14px; border-radius: 10px;
                background: linear-gradient(90deg, rgba(16,185,129,0.25), rgba(56,189,248,0.2));
                border: 1px solid rgba(52,211,153,0.35); color: var(--text);
              }
              .li-calendar-grid {
                display: grid;
                grid-template-columns: repeat(7, minmax(0, 1fr));
                gap: 10px;
              }
              @media (max-width: 1100px) {
                .li-calendar-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
              }
              @media (max-width: 640px) {
                .li-calendar-grid { grid-template-columns: 1fr; }
              }
              .li-calendar-day {
                border: 1px solid var(--line);
                border-radius: 12px;
                overflow: hidden;
                background: var(--surface);
                min-height: 220px;
                display: flex;
                flex-direction: column;
              }
              .li-calendar-day.is-today {
                border-color: rgba(251,113,133,0.55);
                box-shadow: 0 0 0 1px rgba(251,113,133,0.2);
              }
              .li-calendar-day-head {
                padding: 8px 10px;
                background: linear-gradient(90deg, rgba(52,211,153,0.35), rgba(56,189,248,0.28));
                border-bottom: 1px solid var(--line);
                display: flex;
                flex-direction: column;
                gap: 2px;
              }
              .li-calendar-day.is-today .li-calendar-day-head {
                background: linear-gradient(90deg, rgba(251,113,133,0.45), rgba(251,191,36,0.35));
              }
              .li-calendar-dow { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.9; }
              .li-calendar-day-num { font-size: 0.95rem; font-weight: 800; }
              .li-calendar-day-body {
                padding: 8px;
                flex: 1;
                display: flex;
                flex-direction: column;
                gap: 8px;
                overflow-y: auto;
                max-height: 520px;
              }
              .li-calendar-empty {
                color: var(--muted);
                font-size: 0.78rem;
                padding: 16px 8px;
                text-align: center;
                border: 1px dashed var(--line);
                border-radius: 8px;
                background: rgba(255,255,255,0.02);
              }
              .li-post-card.li-post-card-compact .li-post-body {
                max-height: 88px;
                overflow: hidden;
                font-size: 0.82rem;
              }
              .li-post-card.li-post-card-compact .li-post-title { font-size: 0.9rem; }
              .li-post-card.li-post-card-compact .li-post-actions { flex-wrap: wrap; gap: 4px; }
              .li-post-card.li-post-card-compact .btn-post-ok,
              .li-post-card.li-post-card-compact .btn-post-edit,
              .li-post-card.li-post-card-compact .btn-post-redo,
              .li-post-card.li-post-card-compact .btn-post-del,
              .li-post-card.li-post-card-compact .btn-post-publish {
                font-size: 0.72rem;
                padding: 4px 8px;
              }
"""

if ".li-calendar-grid" not in h:
    anchor = ".li-posts-wrap { display: grid; gap: 12px; margin-top: 8px; }"
    if anchor not in h:
        raise SystemExit("CSS anchor .li-posts-wrap not found")
    h = h.replace(anchor, anchor + CALENDAR_CSS)

# --- renderTabs ---
OLD_TABS = """              function renderTabs(showPostsTab) {
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
              }"""

NEW_TABS = """              function renderTabs(showPostsTab) {
                const postsTab = showPostsTab
                  ? '<div class="tab" data-target="posts">Posts</div>'
                  : "";
                const calendarTab = showPostsTab
                  ? '<div class="tab" data-target="calendar">Calendário</div>'
                  : "";
                return `
                  <div class="tabs">
                    <div class="tab active" data-target="overview">Visão Geral</div>
                    ${postsTab}
                    ${calendarTab}
                    <div class="tab" data-target="content">Tipos de conteúdo</div>
                    <div class="tab" data-target="evolution">Plano &amp; Ações</div>
                  </div>
                `;
              }"""

if OLD_TABS not in h:
    raise SystemExit("renderTabs block not found")
h = h.replace(OLD_TABS, NEW_TABS)

# --- panel calendar ---
PANEL_POSTS_END = """                    </div>
                    ` : ""}

                    <div id="panel-content" class="panel">"""

PANEL_WITH_CAL = """                    </div>

                    <div id="panel-calendar" class="panel">
                      <div class="section" data-section="posts-calendario">
                        <h3>Calendário semanal <span class="pill cool">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Planeamento da semana a partir de hoje — um post por dia. Aprova texto, gera imagem e publica com o mesmo fluxo da aba Posts.</p>
                        <div id="linkedinCalendarContainer" class="li-calendar-wrap"><div class="li-posts-loading">Clica em <strong>Gerar posts da semana</strong> para planear publicações com IA.</div></div>
                        <button type="button" class="btn-analyze" style="margin-top:12px;max-width:300px" id="btnGenerateLinkedinCalendarPosts" data-action="generate-linkedin-calendar-posts" onclick="generateLinkedinPostsForCalendar()" disabled>Gerar posts da semana</button>
                      </div>
                    </div>
                    ` : ""}

                    <div id="panel-content" class="panel">"""

if PANEL_POSTS_END not in h:
    raise SystemExit("panel-posts end marker not found")
h = h.replace(PANEL_POSTS_END, PANEL_WITH_CAL, 1)

# --- replace renderLinkedinPostsContainer block ---
start = h.find("function renderLinkedinPostsContainer()")
end = h.find("async function approveLinkedinPost", start)
if start < 0 or end < 0:
    raise SystemExit("renderLinkedinPostsContainer block not found")

NEW_POSTS_JS = r'''function formatLinkedinDateKey(d) {
                const dt = d instanceof Date ? d : new Date(d);
                const y = dt.getFullYear();
                const m = String(dt.getMonth() + 1).padStart(2, "0");
                const day = String(dt.getDate()).padStart(2, "0");
                return `${y}-${m}-${day}`;
              }

              function getLinkedinWeekDays() {
                const days = [];
                const now = new Date();
                now.setHours(0, 0, 0, 0);
                for (let i = 0; i < 7; i++) {
                  const d = new Date(now);
                  d.setDate(d.getDate() + i);
                  days.push(d);
                }
                return days;
              }

              function assignLinkedinPostsToWeek(posts) {
                const weekDays = getLinkedinWeekDays();
                return (posts || []).map((p, i) => ({
                  ...p,
                  scheduled_date: weekDays[i]
                    ? formatLinkedinDateKey(weekDays[i])
                    : (p.scheduled_date || formatLinkedinDateKey(weekDays[0])),
                }));
              }

              function ensureLinkedinPostsWeekDates() {
                if (!linkedinGeneratedPosts.length) return;
                const weekDays = getLinkedinWeekDays();
                let idx = 0;
                linkedinGeneratedPosts.forEach((p) => {
                  if (!p.scheduled_date && weekDays[idx]) {
                    p.scheduled_date = formatLinkedinDateKey(weekDays[idx]);
                    idx += 1;
                  }
                });
              }

              function linkedinWeekTitle() {
                const weekDays = getLinkedinWeekDays();
                const months = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
                const start = weekDays[0];
                const end = weekDays[6];
                if (!start || !end) return "Semana actual";
                const sameMonth = start.getMonth() === end.getMonth();
                const range = sameMonth
                  ? `${start.getDate()} – ${end.getDate()} ${months[start.getMonth()]} ${end.getFullYear()}`
                  : `${start.getDate()} ${months[start.getMonth()]} – ${end.getDate()} ${months[end.getMonth()]} ${end.getFullYear()}`;
                return `Planeamento semanal · ${range}`;
              }

              function refreshLinkedinPostsUI() {
                renderLinkedinPostsContainer();
                renderLinkedinCalendarContainer();
              }

              function renderLinkedinPostCardHtml(p, compact) {
                const st = p.status || "draft";
                const cls = ["li-post-card", compact ? "li-post-card-compact" : "", st === "approved" ? "approved" : "", st === "editing" ? "editing" : ""].filter(Boolean).join(" ");
                const statusLabel = st === "approved" ? '<span class="li-post-status ok">Aprovado</span>' : (st === "editing" ? '<span class="li-post-status">A editar</span>' : '<span class="li-post-status">Rascunho</span>');
                const bodyBlock = st === "editing"
                  ? `<textarea class="li-post-edit-area" id="edit-area-${escapeHtml(p.id)}">${escapeHtml(p.bodyEdit != null ? p.bodyEdit : p.body)}</textarea>`
                  : `<p class="li-post-body">${escapeHtml(p.body)}</p>`;
                const actions = st === "editing"
                  ? `<button type="button" class="btn-post-ok" onclick="saveLinkedinPostEdit('${escapeHtml(p.id)}')">Guardar</button>
                     <button type="button" class="btn-post-edit" onclick="cancelLinkedinPostEdit('${escapeHtml(p.id)}')">Cancelar</button>
                     <button type="button" class="btn-post-del" onclick="deleteLinkedinPost('${escapeHtml(p.id)}')">Apagar</button>`
                  : `<button type="button" class="btn-post-ok" onclick="approveLinkedinPost('${escapeHtml(p.id)}')" ${st === "approved" ? "disabled" : ""}>Aprovado</button>
                     <button type="button" class="btn-post-edit" onclick="startLinkedinPostEdit('${escapeHtml(p.id)}')">Editar</button>
                     <button type="button" class="btn-post-redo" onclick="regenerateLinkedinPost('${escapeHtml(p.id)}')">Refazer</button>`;
                const imgSt = p.image_status || "draft";
                let imageBlock = "";
                if (p.image_generating) {
                  imageBlock = '<div class="li-post-image-loading">A gerar imagem…</div>';
                } else if (p.generated_image_url) {
                  const imgStatusLabel = imgSt === "approved"
                    ? '<span class="li-post-status ok">Imagem aprovada</span>'
                    : '<span class="li-post-status">Imagem em rascunho</span>';
                  const imgActions = imgSt === "approved"
                    ? `<button type="button" class="btn-post-ok" disabled>Aprovado</button>`
                    : `<button type="button" class="btn-post-ok" onclick="approveLinkedinPostImage('${escapeHtml(p.id)}')">Aprovado</button>
                       <button type="button" class="btn-post-redo" onclick="regenerateLinkedinPostImage('${escapeHtml(p.id)}')">Refazer</button>`;
                  imageBlock = `
                    <div class="li-post-image-section">
                      <div class="li-post-image-head">
                        <span class="li-post-image-label">Imagem</span>
                        ${imgStatusLabel}
                      </div>
                      <div class="li-post-image-wrap">
                        <img src="${escapeHtml(p.generated_image_url)}" alt="Imagem do post" class="li-post-image" />
                        <a class="li-post-image-link" href="${escapeHtml(p.generated_image_url)}" target="_blank" rel="noopener noreferrer">Abrir imagem</a>
                      </div>
                      <div class="li-post-image-actions">${imgActions}</div>
                    </div>`;
                }
                let publishBlock = "";
                const publishAuthOk = hasLinkedinPublishAuthorization();
                const publishAuthBtn = publishAuthOk
                  ? '<span class="li-post-status ok" style="margin-left:8px">Publicação autorizada</span>'
                  : '<button type="button" class="btn-post-publish secondary" onclick="connectLinkedinPublish()">Autorizar publicação no LinkedIn</button>';
                if (p.publishing_linkedin) {
                  publishBlock = '<div class="li-post-publish-loading">A publicar no LinkedIn…</div>';
                } else if (p.published_on_linkedin) {
                  publishBlock = '<div class="li-post-publish-section"><div class="li-post-published-msg">Publicado no LinkedIn</div></div>';
                } else if (st === "approved") {
                  const canPublishImage = p.image_status === "approved" && p.generated_image_url;
                  const pubDisabled = publishAuthOk ? "" : " disabled";
                  if (canPublishImage) {
                    publishBlock = `
                      <div class="li-post-publish-section">
                        <div class="li-post-publish-label">Publicar no LinkedIn ${publishAuthBtn}</div>
                        <p style="font-size:0.78rem;color:var(--muted);margin:0 0 8px">O login Supabase analisa o perfil; autoriza aqui para publicar posts.</p>
                        <div class="li-post-publish-actions">
                          <button type="button" class="btn-post-publish" onclick="publishLinkedinPost('${escapeHtml(p.id)}', true)"${pubDisabled}>Publicar texto + imagem</button>
                          <button type="button" class="btn-post-publish secondary" onclick="publishLinkedinPost('${escapeHtml(p.id)}', false)"${pubDisabled}>Publicar só texto</button>
                        </div>
                      </div>`;
                  } else {
                    publishBlock = `
                      <div class="li-post-publish-section">
                        <div class="li-post-publish-label">Publicar no LinkedIn ${publishAuthBtn}</div>
                        <p style="font-size:0.78rem;color:var(--muted);margin:0 0 8px">O login Supabase analisa o perfil; autoriza aqui para publicar posts.</p>
                        <div class="li-post-publish-actions">
                          <button type="button" class="btn-post-publish" onclick="publishLinkedinPost('${escapeHtml(p.id)}', false)"${pubDisabled}>Publicar no LinkedIn</button>
                        </div>
                      </div>`;
                  }
                }
                const cardCls = [cls, imgSt === "approved" && p.generated_image_url ? "image-approved" : ""].filter(Boolean).join(" ");
                return `
                  <div class="${cardCls}" data-post-id="${escapeHtml(p.id)}">
                    <div class="li-post-head">
                      <span class="li-post-type">${escapeHtml(linkedinPostTypeLabel(p.content_type))}</span>
                      ${statusLabel}
                    </div>
                    <h4 class="li-post-title">${escapeHtml(p.title || "")}</h4>
                    ${bodyBlock}
                    ${p.hook ? `<div class="li-post-meta"><strong>Gancho:</strong> ${escapeHtml(p.hook)}</div>` : ""}
                    ${p.cta ? `<div class="li-post-meta"><strong>CTA:</strong> ${escapeHtml(p.cta)}</div>` : ""}
                    ${imageBlock}
                    ${p.angle ? `<div class="li-post-meta"><strong>Ângulo:</strong> ${escapeHtml(p.angle)}</div>` : ""}
                    ${publishBlock}
                    <div class="li-post-actions">${actions}</div>
                  </div>
                `;
              }

              function renderLinkedinPostsContainer() {
                const el = document.getElementById("linkedinPostsContainer");
                if (!el) return;
                if (!linkedinGeneratedPosts.length) {
                  el.innerHTML = '<div class="li-posts-loading">Sem posts. Clica «Gerar posts».</div>';
                  return;
                }
                el.innerHTML = linkedinGeneratedPosts.map((p) => renderLinkedinPostCardHtml(p, false)).join("");
              }

              function renderLinkedinCalendarContainer() {
                const el = document.getElementById("linkedinCalendarContainer");
                if (!el) return;
                ensureLinkedinPostsWeekDates();
                const weekDays = getLinkedinWeekDays();
                const dowNames = ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"];
                const todayKey = formatLinkedinDateKey(new Date());
                if (!linkedinGeneratedPosts.length) {
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
                linkedinGeneratedPosts.forEach((p) => {
                  const key = p.scheduled_date || formatLinkedinDateKey(weekDays[0]);
                  if (!postsByDate[key]) postsByDate[key] = [];
                  postsByDate[key].push(p);
                });
                const grid = weekDays.map((d) => {
                  const key = formatLinkedinDateKey(d);
                  const isToday = key === todayKey;
                  const dayPosts = (postsByDate[key] || []).map((p) => renderLinkedinPostCardHtml(p, true)).join("");
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
              }

              '''

h = h[:start] + NEW_POSTS_JS + h[end:]

# --- generate posts ---
OLD_GEN = """async function generateLinkedinPostsFromSnapshot() {
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
                  const res = await fetch("/agents/linkedin/generate-posts", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      analysis: linkedinAnalysisSnapshot,
                      public_profile_data: linkedinAnalysisSnapshot.public_profile_data || {},
                      profile_url: linkedinAnalysisSnapshot.profile_url || "",
                      count: 3,
                      language: "pt-PT",
                    }),
                  });
                  const json = await res.json();
                  if (!res.ok) throw new Error(json.detail || JSON.stringify(json));
                  linkedinGeneratedPosts = (json.posts || []).map((row) => ({
                    ...row,
                    status: "draft",
                  }));
                  renderLinkedinPostsContainer();
                  enableGeneratePostsButton();
                } catch (e) {
                  if (el) el.innerHTML = `<div class="err">Erro: ${escapeHtml(e.message || String(e))}</div>`;
                  const btnErr = document.getElementById("btnGenerateLinkedinPosts");
                  if (btnErr) { btnErr.disabled = false; btnErr.textContent = "Gerar posts"; }
                }
              }"""

NEW_GEN = """async function generateLinkedinPostsFromSnapshot(postCount) {
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

if OLD_GEN not in h:
    raise SystemExit("generateLinkedinPostsFromSnapshot block not found")
h = h.replace(OLD_GEN, NEW_GEN, 1)

# --- enable buttons ---
h = h.replace(
    '["btnGenerateLinkedinPosts"].forEach((id) => {',
    '["btnGenerateLinkedinPosts", "btnGenerateLinkedinCalendarPosts"].forEach((id) => {',
)
h = h.replace(
    'const label = linkedinGeneratedPosts.length ? "Gerar novamente" : "Gerar posts";',
    """const label = linkedinGeneratedPosts.length ? "Gerar novamente" : "Gerar posts";
                const calLabel = linkedinGeneratedPosts.length ? "Gerar semana novamente" : "Gerar posts da semana";""",
)
h = h.replace(
    """                  btn.disabled = !enabled;
                  btn.textContent = label;""",
    """                  btn.disabled = !enabled;
                  if (id === "btnGenerateLinkedinCalendarPosts") {
                    btn.textContent = calLabel;
                  } else {
                    btn.textContent = label;
                  }""",
)

# --- reset after analysis ---
OLD_RESET = """function resetLinkedinPostsAfterAnalysis() {
                linkedinGeneratedPosts = [];
                const el = document.getElementById("linkedinPostsContainer");
                enableGeneratePostsButton();
                if (el) {
                  el.innerHTML = linkedinAnalysisSnapshot
                    ? '<div class="li-posts-loading">Análise concluída. Clica <strong>Gerar posts</strong> para criar publicações com IA.</div>'
                    : '<div class="li-posts-loading">Faz uma análise de perfil primeiro.</div>';
                }
              }"""

NEW_RESET = """function resetLinkedinPostsAfterAnalysis() {
                linkedinGeneratedPosts = [];
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

if OLD_RESET in h:
    h = h.replace(OLD_RESET, NEW_RESET, 1)
else:
    print("warn: resetLinkedinPostsAfterAnalysis block not matched exactly")

# --- refresh all render calls (except inside refreshLinkedinPostsUI) ---
h = h.replace(
    """function refreshLinkedinPostsUI() {
                refreshLinkedinPostsUI();
                renderLinkedinCalendarContainer();
              }""",
    """function refreshLinkedinPostsUI() {
                renderLinkedinPostsContainer();
                renderLinkedinCalendarContainer();
              }""",
)
h = h.replace("renderLinkedinPostsContainer();", "refreshLinkedinPostsUI();")
h = h.replace(
    """function refreshLinkedinPostsUI() {
                refreshLinkedinPostsUI();
                renderLinkedinCalendarContainer();
              }""",
    """function refreshLinkedinPostsUI() {
                renderLinkedinPostsContainer();
                renderLinkedinCalendarContainer();
              }""",
)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")

checks = {
    "tab_calendar": 'data-target="calendar">Calendário' in h,
    "panel_calendar": "panel-calendar" in h,
    "render_calendar_fn": "function renderLinkedinCalendarContainer" in h,
    "gen_calendar": "generateLinkedinPostsForCalendar" in h,
    "refresh_ui": "function refreshLinkedinPostsUI" in h,
    "css_calendar": ".li-calendar-grid" in h,
}
print("ok", checks)
if not all(checks.values()):
    raise SystemExit("patch verification failed")
