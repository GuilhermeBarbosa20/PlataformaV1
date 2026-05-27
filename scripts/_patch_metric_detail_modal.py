# -*- coding: utf-8 -*-
"""Cartões da grelha de perfil clicáveis com modal quando o texto é longo."""

from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"

raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

METRIC_MODAL_CSS = """
              .li-metric-card.is-expandable {
                cursor: pointer;
                transition: border-color 0.15s ease, background 0.15s ease, transform 0.05s ease;
              }
              .li-metric-card.is-expandable:hover {
                border-color: rgba(56,189,248,0.45);
                background: rgba(56,189,248,0.06);
              }
              .li-metric-card.is-expandable:focus-visible {
                outline: 2px solid var(--accent);
                outline-offset: 2px;
              }
              .li-metric-value-preview {
                font-size: 0.88rem !important;
                font-weight: 600 !important;
                line-height: 1.4 !important;
                display: -webkit-box;
                -webkit-line-clamp: 3;
                -webkit-box-orient: vertical;
                overflow: hidden;
              }
              .li-metric-open-hint {
                display: block;
                margin-top: 8px;
                font-size: 0.72rem;
                font-weight: 600;
                color: var(--accent);
                letter-spacing: 0.02em;
              }
              .li-metric-modal {
                display: none;
                position: fixed;
                inset: 0;
                z-index: 1250;
                align-items: center;
                justify-content: center;
                padding: 20px;
              }
              .li-metric-modal.open { display: flex; }
              .li-metric-modal-backdrop {
                position: absolute;
                inset: 0;
                background: rgba(4,6,12,0.72);
                backdrop-filter: blur(4px);
              }
              .li-metric-modal-panel {
                position: relative;
                z-index: 1;
                width: min(720px, 100%);
                max-height: min(85vh, 820px);
                overflow: hidden;
                display: flex;
                flex-direction: column;
                background: var(--bg-1);
                border: 1px solid var(--line-strong);
                border-radius: 16px;
                box-shadow: 0 24px 60px rgba(0,0,0,0.55);
              }
              .li-metric-modal-head {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 12px;
                padding: 16px 18px;
                border-bottom: 1px solid var(--line);
                flex-shrink: 0;
              }
              .li-metric-modal-head h4 { margin: 0; font-size: 1.05rem; font-weight: 700; }
              .li-metric-modal-close {
                flex-shrink: 0;
                width: 36px;
                height: 36px;
                border-radius: 10px;
                border: 1px solid var(--line);
                background: var(--surface);
                color: var(--text);
                font-size: 1.4rem;
                line-height: 1;
                cursor: pointer;
              }
              .li-metric-modal-close:hover { border-color: rgba(251,113,133,0.5); }
              .li-metric-modal-body {
                padding: 16px 18px 22px;
                overflow-y: auto;
                font-size: 0.9rem;
                line-height: 1.55;
                color: var(--muted-soft);
              }
              .li-metric-detail-count {
                margin: 0 0 12px;
                font-size: 0.8rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                color: var(--muted);
              }
              .li-metric-detail-list {
                list-style: none;
                margin: 0;
                padding: 0;
                display: flex;
                flex-direction: column;
                gap: 10px;
              }
              .li-metric-detail-list li {
                padding: 12px 14px;
                border-radius: 10px;
                border: 1px solid var(--line);
                background: rgba(255,255,255,0.03);
                color: var(--text);
                word-break: break-word;
              }
              .li-metric-detail-prose {
                white-space: pre-wrap;
                word-break: break-word;
                color: var(--text);
              }
              .li-metric-detail-kv {
                display: grid;
                gap: 8px;
              }
              .li-metric-detail-kv dt {
                font-size: 0.72rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: var(--muted);
              }
              .li-metric-detail-kv dd {
                margin: 0 0 10px;
                color: var(--text);
                word-break: break-word;
              }
"""

METRIC_MODAL_HTML = """
                        <div id="linkedinMetricDetailModal" class="li-metric-modal" aria-hidden="true" role="dialog" aria-labelledby="linkedinMetricDetailModalTitle">
                          <div class="li-metric-modal-backdrop" onclick="closeLinkedinMetricDetailModal()"></div>
                          <div class="li-metric-modal-panel" onclick="event.stopPropagation()">
                            <div class="li-metric-modal-head">
                              <h4 id="linkedinMetricDetailModalTitle">Detalhe</h4>
                              <button type="button" class="li-metric-modal-close" onclick="closeLinkedinMetricDetailModal()" aria-label="Fechar">&times;</button>
                            </div>
                            <div id="linkedinMetricDetailModalBody" class="li-metric-modal-body"></div>
                          </div>
                        </div>"""

METRIC_DETAIL_JS = r"""
              const linkedinMetricDetailStore = {};

              function linkedinMetricPlainText(value) {
                if (value === null || value === undefined) return "";
                if (typeof value === "string") return value.trim();
                if (Array.isArray(value)) {
                  return value
                    .map((item) => {
                      if (item === null || item === undefined) return "";
                      if (typeof item === "object") {
                        return Object.values(item)
                          .filter((x) => x !== null && x !== undefined && String(x).trim())
                          .map((x) => String(x).trim())
                          .join(" · ");
                      }
                      return String(item).trim();
                    })
                    .filter(Boolean)
                    .join("; ");
                }
                if (typeof value === "object") {
                  try {
                    return JSON.stringify(value, null, 2);
                  } catch (e) {
                    return String(value);
                  }
                }
                return String(value).trim();
              }

              function linkedinMetricNeedsDetailModal(value) {
                if (isMetricValueMissing(value)) return false;
                if (Array.isArray(value) && value.length > 1) return true;
                if (typeof value === "object" && value !== null && !Array.isArray(value)) {
                  const keys = Object.keys(value);
                  if (keys.length > 2) return true;
                  const joined = linkedinMetricPlainText(value);
                  return joined.length > 120;
                }
                const text = linkedinMetricPlainText(value);
                if (!text) return false;
                if (text.length > 130) return true;
                if (/\(\+\d+\s*mais\)/i.test(text)) return true;
                if ((text.match(/;/g) || []).length >= 2) return true;
                if (/^\d+\s*[—\-–]\s*/.test(text) && text.length > 70) return true;
                return false;
              }

              function linkedinMetricCardPreview(value) {
                const text = linkedinMetricPlainText(value);
                if (!text) return "Ver detalhes";
                const countMatch = text.match(/^(\d+)\s*[—\-–]\s*(.*)$/s);
                if (countMatch) {
                  const n = countMatch[1];
                  const rest = (countMatch[2] || "").trim();
                  const first = rest.split(";").map((s) => s.trim()).filter(Boolean)[0] || "";
                  const short = first.length > 72 ? first.slice(0, 72) + "…" : first;
                  return `${n} itens${short ? " · " + short : ""}`;
                }
                if (/\(\+\d+\s*mais\)/i.test(text)) {
                  const head = text.replace(/\s*\(\+\d+\s*mais\)\s*$/i, "").trim();
                  return head.length > 90 ? head.slice(0, 90) + "…" : head;
                }
                if (text.includes(";")) {
                  const first = text.split(";").map((s) => s.trim()).filter(Boolean)[0] || "";
                  const more = (text.match(/;/g) || []).length;
                  const short = first.length > 70 ? first.slice(0, 70) + "…" : first;
                  return more > 0 ? `${short} (+${more} mais)` : short;
                }
                return text.length > 110 ? text.slice(0, 110) + "…" : text;
              }

              function linkedinMetricDetailListHtml(parts) {
                const items = (parts || []).map((p) => String(p || "").trim()).filter(Boolean);
                if (!items.length) return '<p class="li-metric-detail-prose">Sem detalhes.</p>';
                return `<ul class="li-metric-detail-list">${items
                  .map((p) => `<li>${escapeHtml(p)}</li>`)
                  .join("")}</ul>`;
              }

              function linkedinMetricDetailBodyHtml(key, value, pageKind) {
                if (Array.isArray(value)) {
                  const lines = value.map((item) => {
                    if (item === null || item === undefined) return "";
                    if (typeof item === "object") {
                      return Object.entries(item)
                        .filter(([_, v]) => v !== null && v !== undefined && String(v).trim())
                        .map(([k, v]) => `${humanizeMetricKey(k, pageKind)}: ${String(v).trim()}`)
                        .join(" · ");
                    }
                    return String(item).trim();
                  }).filter(Boolean);
                  return linkedinMetricDetailListHtml(lines);
                }
                if (typeof value === "object" && value !== null) {
                  const rows = Object.entries(value).filter(
                    ([_, v]) => v !== null && v !== undefined && String(v).trim()
                  );
                  if (!rows.length) return '<p class="li-metric-detail-prose">Sem detalhes.</p>';
                  return `<dl class="li-metric-detail-kv">${rows
                    .map(
                      ([k, v]) =>
                        `<dt>${escapeHtml(humanizeMetricKey(k, pageKind))}</dt><dd>${escapeHtml(
                          linkedinMetricPlainText(v)
                        )}</dd>`
                    )
                    .join("")}</dl>`;
                }
                const text = linkedinMetricPlainText(value);
                const countMatch = text.match(/^(\d+)\s*[—\-–]\s*(.*)$/s);
                if (countMatch) {
                  const parts = (countMatch[2] || "")
                    .replace(/\s*\(\+\d+\s*mais\)\s*$/i, "")
                    .split(";")
                    .map((s) => s.trim())
                    .filter(Boolean);
                  return (
                    `<p class="li-metric-detail-count">${escapeHtml(countMatch[1])} registos</p>` +
                    linkedinMetricDetailListHtml(parts)
                  );
                }
                if (text.includes(";")) {
                  const parts = text
                    .replace(/\s*\(\+\d+\s*mais\)\s*$/i, "")
                    .split(";")
                    .map((s) => s.trim())
                    .filter(Boolean);
                  return linkedinMetricDetailListHtml(parts);
                }
                return `<div class="li-metric-detail-prose">${escapeHtml(text)}</div>`;
              }

              function linkedinMetricRegisterDetail(key, value, pageKind) {
                const id =
                  "lmd-" +
                  Date.now().toString(36) +
                  "-" +
                  Math.random().toString(36).slice(2, 8);
                linkedinMetricDetailStore[id] = {
                  key: String(key || ""),
                  value: value,
                  pageKind: pageKind || "personal",
                };
                return id;
              }

              function openLinkedinMetricDetailModal(detailId) {
                const entry = linkedinMetricDetailStore[detailId];
                if (!entry) return;
                const modal = document.getElementById("linkedinMetricDetailModal");
                const titleEl = document.getElementById("linkedinMetricDetailModalTitle");
                const bodyEl = document.getElementById("linkedinMetricDetailModalBody");
                if (!modal || !titleEl || !bodyEl) return;
                titleEl.textContent = humanizeMetricKey(entry.key, entry.pageKind);
                bodyEl.innerHTML = linkedinMetricDetailBodyHtml(
                  entry.key,
                  entry.value,
                  entry.pageKind
                );
                modal.classList.add("open");
                modal.setAttribute("aria-hidden", "false");
                document.body.style.overflow = "hidden";
              }

              function closeLinkedinMetricDetailModal() {
                const modal = document.getElementById("linkedinMetricDetailModal");
                if (!modal) return;
                modal.classList.remove("open");
                modal.setAttribute("aria-hidden", "true");
                if (!linkedinCalendarModalDateKey) document.body.style.overflow = "";
              }

              function renderLinkedinProfileGridCard(k, v, pageKind) {
                const missing = isMetricValueMissing(v);
                const cls = linkedinMetricCardClasses(k, v, missing);
                const label = escapeHtml(humanizeMetricKey(k, pageKind));
                if (missing || !linkedinMetricNeedsDetailModal(v)) {
                  const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                  return `<div class="${cls}"><div class="li-metric-value">${valueHtml}</div><div class="li-metric-label">${label}</div></div>`;
                }
                const detailId = linkedinMetricRegisterDetail(k, v, pageKind);
                const preview = escapeHtml(linkedinMetricCardPreview(v) || "Ver detalhes");
                return `<div class="${cls} is-expandable" role="button" tabindex="0" title="Clique para ver todos os detalhes" onclick="openLinkedinMetricDetailModal('${detailId}')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openLinkedinMetricDetailModal('${detailId}');}"><div class="li-metric-value li-metric-value-preview">${preview}</div><div class="li-metric-label">${label}</div><span class="li-metric-open-hint">Clique para ver tudo →</span></div>`;
              }

"""

OLD_GRID_MAP_PERSONAL = """                const gridHtml = gridEntries.length
                  ? `<div class="li-profile-section"><h5 class="li-profile-section-title">Experiência, formação e mais</h5><div class="li-metrics-grid li-metrics-grid--compact">${gridEntries.map(([k, v]) => {
                      const missing = isMetricValueMissing(v);
                      const cls = linkedinMetricCardClasses(k, v, missing);
                      const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                      return `<div class="${cls}"><div class="li-metric-value">${valueHtml}</div><div class="li-metric-label">${escapeHtml(humanizeMetricKey(k, pageKind))}</div></div>`;
                    }).join("")}</div></div>` : "";"""

NEW_GRID_MAP_PERSONAL = """                const gridHtml = gridEntries.length
                  ? `<div class="li-profile-section"><h5 class="li-profile-section-title">Experiência, formação e mais</h5><div class="li-metrics-grid li-metrics-grid--compact">${gridEntries.map(([k, v]) => renderLinkedinProfileGridCard(k, v, pageKind)).join("")}</div></div>` : "";"""

OLD_GRID_MAP_COMPANY = """                const gridHtml = gridEntries.length
                  ? `<div class="li-profile-section"><h5 class="li-profile-section-title">Mais informações</h5><div class="li-metrics-grid li-metrics-grid--compact">${gridEntries.map(([k, v]) => {
                      const missing = isMetricValueMissing(v);
                      const cls = linkedinMetricCardClasses(k, v, missing);
                      const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                      return `<div class="${cls}"><div class="li-metric-value">${valueHtml}</div><div class="li-metric-label">${escapeHtml(humanizeMetricKey(k, pageKind))}</div></div>`;
                    }).join("")}</div></div>`
                  : "";"""

NEW_GRID_MAP_COMPANY = """                const gridHtml = gridEntries.length
                  ? `<div class="li-profile-section"><h5 class="li-profile-section-title">Mais informações</h5><div class="li-metrics-grid li-metrics-grid--compact">${gridEntries.map(([k, v]) => renderLinkedinProfileGridCard(k, v, pageKind)).join("")}</div></div>`
                  : "";"""

OLD_TECH_MAP = """                const techHtml = techEntries.length ? `<details class="li-profile-tech"><summary>Detalhes técnicos (${techEntries.length})</summary><div class="li-metrics-grid">${techEntries.map(([k, v]) => {
                  const missing = isMetricValueMissing(v);
                  const cls = linkedinMetricCardClasses(k, v, missing) + " is-id";
                  const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                  return `<div class="${cls}"><div class="li-metric-value">${valueHtml}</div><div class="li-metric-label">${escapeHtml(humanizeMetricKey(k, pageKind))}</div></div>`;
                }).join("")}</div></details>` : "";"""

NEW_TECH_MAP = """                const techHtml = techEntries.length ? `<details class="li-profile-tech"><summary>Detalhes técnicos (${techEntries.length})</summary><div class="li-metrics-grid">${techEntries.map(([k, v]) => {
                  const card = renderLinkedinProfileGridCard(k, v, pageKind);
                  return card.replace('class="li-metric-card', 'class="li-metric-card is-id');
                }).join("")}</div></details>` : "";"""

# CSS
if ".li-metric-modal" not in h:
    anchor = ".li-cal-modal-body .li-post-card"
    if anchor not in h:
        anchor = ".li-cal-modal-close:hover"
    h = h.replace(anchor, anchor + METRIC_MODAL_CSS, 1)

# HTML modal (após modal do calendário)
if "linkedinMetricDetailModal" not in h:
    anchor = 'class="li-cal-modal-body"></div>\n                          </div>\n                        </div>'
    if anchor not in h:
        anchor = "linkedinCalendarModalBody"
        idx = h.find(anchor)
        if idx < 0:
            raise SystemExit("calendar modal anchor not found")
        idx = h.find("</div>", idx)
        for _ in range(3):
            idx = h.find("</div>", idx + 1)
        h = h[: idx + len("</div>")] + METRIC_MODAL_HTML + h[idx + len("</div>") :]
    else:
        h = h.replace(anchor, anchor + METRIC_MODAL_HTML, 1)

# JS
if "function renderLinkedinProfileGridCard" not in h:
    anchor = "              function renderLinkedinHarvestProfileOverview(obj, ctx, publicProfile) {"
    if anchor not in h:
        raise SystemExit("renderLinkedinHarvestProfileOverview anchor not found")
    h = h.replace(anchor, METRIC_DETAIL_JS + anchor, 1)

# Escape key
if "closeLinkedinMetricDetailModal" in h and "linkedinMetricDetailModal" not in h.split("keydown")[0][-500:]:
    old_key = """              document.addEventListener("keydown", (e) => {
                if (e.key === "Escape" && linkedinCalendarModalDateKey) closeLinkedinCalendarDayModal();
              });"""
    new_key = """              document.addEventListener("keydown", (e) => {
                if (e.key !== "Escape") return;
                const metricModal = document.getElementById("linkedinMetricDetailModal");
                if (metricModal && metricModal.classList.contains("open")) {
                  closeLinkedinMetricDetailModal();
                  return;
                }
                if (linkedinCalendarModalDateKey) closeLinkedinCalendarDayModal();
              });"""
    if old_key in h:
        h = h.replace(old_key, new_key, 1)

# Grid replacements
if OLD_GRID_MAP_PERSONAL in h:
    h = h.replace(OLD_GRID_MAP_PERSONAL, NEW_GRID_MAP_PERSONAL, 1)
else:
    raise SystemExit("personal grid map not found")

if OLD_GRID_MAP_COMPANY in h:
    h = h.replace(OLD_GRID_MAP_COMPANY, NEW_GRID_MAP_COMPANY, 1)
else:
    raise SystemExit("company grid map not found")

# Tech maps appear twice (company + personal) - replace all
if OLD_TECH_MAP not in h:
    raise SystemExit("tech map not found")
h = h.replace(OLD_TECH_MAP, NEW_TECH_MAP)

# Fix body overflow when calendar open + metric modal
if "if (!linkedinCalendarModalDateKey) document.body.style.overflow" not in h:
    h = h.replace(
        "document.body.style.overflow = \"\";",
        "if (!document.getElementById(\"linkedinCalendarModal\")?.classList.contains(\"open\")) document.body.style.overflow = \"\";",
        1,
    )

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print(
    "ok",
    "renderLinkedinProfileGridCard" in h,
    "linkedinMetricDetailModal" in h,
    h.count("renderLinkedinProfileGridCard(k, v, pageKind)") >= 2,
)
