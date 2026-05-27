# -*- coding: utf-8 -*-
"""Corrige [object Object] em experiência e abre modal de detalhe por registo."""

from __future__ import annotations

import json
import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"

ITEM_MODAL_HTML = """
            <div id="linkedinMetricItemDetailModal" class="li-metric-modal li-metric-item-modal" aria-hidden="true" role="dialog" aria-labelledby="linkedinMetricItemDetailModalTitle">
              <div class="li-metric-modal-backdrop" data-action="close-metric-item-detail"></div>
              <div class="li-metric-modal-panel">
                <div class="li-metric-modal-head">
                  <h4 id="linkedinMetricItemDetailModalTitle">Detalhe</h4>
                  <button type="button" class="li-metric-modal-close" data-action="close-metric-item-detail" aria-label="Fechar">&times;</button>
                </div>
                <div id="linkedinMetricItemDetailModalBody" class="li-metric-modal-body"></div>
              </div>
            </div>"""

ITEM_MODAL_CSS = """
              .li-metric-item-modal { z-index: 1310; }
              .li-metric-detail-list .li-metric-detail-item.is-expandable {
                cursor: pointer;
                transition: border-color 0.15s ease, background 0.15s ease;
              }
              .li-metric-detail-list .li-metric-detail-item.is-expandable:hover {
                border-color: rgba(56,189,248,0.45);
                background: rgba(56,189,248,0.06);
              }
              .li-metric-detail-item-label { display: block; color: var(--text); font-weight: 600; }
              .li-metric-detail-item-hint {
                display: block;
                margin-top: 6px;
                font-size: 0.72rem;
                font-weight: 600;
                color: var(--accent);
              }
              .li-metric-detail-desc {
                margin-bottom: 16px;
                padding: 14px 16px;
                border-radius: 10px;
                border: 1px solid var(--line);
                background: rgba(255,255,255,0.03);
                white-space: pre-wrap;
                color: var(--text);
                line-height: 1.55;
              }
"""

# Read current linkedinHarvestListItemLine from file and replace whole block from resolveLinkedin... through renderLinkedinProfileGridCard? 
# Safer: replace function by function using regex extract

HARVEST_JS = r"""
              const linkedinMetricItemDetailStore = {};

              function linkedinHarvestCoerceText(value, depth) {
                if (depth === undefined) depth = 0;
                if (value === null || value === undefined) return "";
                if (typeof value === "string") return value.trim();
                if (typeof value === "number") return String(value);
                if (typeof value === "boolean") return value ? "Sim" : "Não";
                if (depth > 6) return "";
                if (Array.isArray(value)) {
                  return value
                    .map((v) => linkedinHarvestCoerceText(v, depth + 1))
                    .filter(Boolean)
                    .join("; ");
                }
                if (typeof value !== "object") return "";
                if (value.year != null && value.year !== "") {
                  const y = value.year;
                  const m = value.month;
                  const d = value.day;
                  if (d && m && y) return `${d}/${m}/${y}`;
                  if (m && y) return `${m}/${y}`;
                  return String(y);
                }
                for (const k of [
                  "text",
                  "title",
                  "name",
                  "localizedName",
                  "value",
                  "description",
                  "accessibilityText",
                  "caption",
                ]) {
                  if (value[k] != null && value[k] !== "") {
                    const t = linkedinHarvestCoerceText(value[k], depth + 1);
                    if (t) return t;
                  }
                }
                if (value.companyName) {
                  const t = linkedinHarvestCoerceText(value.companyName, depth + 1);
                  if (t) return t;
                }
                if (value.timePeriod) {
                  const t = linkedinHarvestFormatTimePeriod(value.timePeriod);
                  if (t) return t;
                }
                return "";
              }

              function linkedinHarvestFormatTimePeriod(tp) {
                if (!tp || typeof tp !== "object") return "";
                const fmt = (d) => {
                  if (!d || typeof d !== "object") return "";
                  const y = d.year;
                  const mo = d.month;
                  return y ? (mo ? `${mo}/${y}` : String(y)) : "";
                };
                const a = fmt(tp.startDate);
                const b = fmt(tp.endDate);
                if (a && b) return `${a} – ${b}`;
                return a || b || "";
              }

              function linkedinHarvestListItemLine(item, pageKind) {
                if (item === null || item === undefined) return "";
                if (typeof item === "string") return item.trim();
                if (typeof item !== "object" || Array.isArray(item)) return String(item).trim();

                const company =
                  linkedinHarvestCoerceText(item.companyName) ||
                  linkedinHarvestCoerceText(item.company) ||
                  linkedinHarvestCoerceText(item.schoolName) ||
                  linkedinHarvestCoerceText(item.organizationName);
                const role =
                  linkedinHarvestCoerceText(item.title) ||
                  linkedinHarvestCoerceText(item.position) ||
                  linkedinHarvestCoerceText(item.subtitle) ||
                  linkedinHarvestCoerceText(item.degree) ||
                  linkedinHarvestCoerceText(item.fieldOfStudy);
                const extra =
                  linkedinHarvestCoerceText(item.publisher) ||
                  linkedinHarvestCoerceText(item.issuedBy) ||
                  linkedinHarvestCoerceText(item.industry);
                let when = linkedinHarvestFormatTimePeriod(item.timePeriod);
                if (!when) {
                  when =
                    linkedinHarvestCoerceText(item.startDate) ||
                    linkedinHarvestCoerceText(item.endDate) ||
                    linkedinHarvestCoerceText(item.issuedAt) ||
                    linkedinHarvestCoerceText(item.issuedOn) ||
                    linkedinHarvestCoerceText(item.date) ||
                    linkedinHarvestCoerceText(item.publishedOn);
                }

                const bits = [];
                if (company) bits.push(company);
                if (role && role !== company) bits.push(role);
                else if (extra && extra !== company) bits.push(extra);
                if (when) bits.push(when);
                if (bits.length) return bits.join(" · ");

                return Object.entries(item)
                  .filter(([_, v]) => {
                    if (v === null || v === undefined) return false;
                    if (typeof v === "object") return false;
                    return String(v).trim();
                  })
                  .slice(0, 6)
                  .map(([k, v]) => `${humanizeMetricKey(k, pageKind)}: ${String(v).trim()}`)
                  .join(" · ");
              }

              function linkedinHarvestItemHasDetail(item) {
                if (!item || typeof item !== "object" || Array.isArray(item)) return false;
                const desc = linkedinHarvestCoerceText(item.description) || linkedinHarvestCoerceText(item.summary);
                if (desc.length > 10) return true;
                const keys = Object.keys(item).filter((k) => !k.startsWith("_") && k !== "$recipe");
                return keys.length > 2;
              }

              function linkedinHarvestFormatDetailFieldValue(v, pageKind) {
                if (v === null || v === undefined) return "";
                if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
                  return linkedinHarvestCoerceText(v);
                }
                if (Array.isArray(v)) {
                  return v
                    .map((x) => linkedinHarvestListItemLine(x, pageKind) || linkedinHarvestCoerceText(x))
                    .filter(Boolean)
                    .join("\n");
                }
                if (typeof v === "object") {
                  const tp = linkedinHarvestFormatTimePeriod(v);
                  if (tp) return tp;
                  const text = linkedinHarvestCoerceText(v);
                  if (text) return text;
                  try {
                    return JSON.stringify(v, null, 2);
                  } catch (e) {
                    return "";
                  }
                }
                return "";
              }

              function linkedinHarvestItemDetailBodyHtml(item, pageKind, metricKey) {
                if (!item || typeof item !== "object") {
                  return '<p class="li-metric-detail-prose">Sem detalhes.</p>';
                }
                const skip = new Set(["$recipe", "$type", "_type"]);
                const priority = [
                  "title",
                  "subtitle",
                  "companyName",
                  "company",
                  "schoolName",
                  "position",
                  "degree",
                  "fieldOfStudy",
                  "timePeriod",
                  "location",
                  "description",
                  "summary",
                  "grade",
                  "publisher",
                  "issuedBy",
                  "industry",
                  "employmentType",
                  "url",
                ];
                let html = "";
                const desc =
                  linkedinHarvestCoerceText(item.description) || linkedinHarvestCoerceText(item.summary);
                if (desc) {
                  html += `<div class="li-metric-detail-desc">${escapeHtml(desc)}</div>`;
                }
                const rows = [];
                const seen = new Set();
                const pushRow = (k) => {
                  if (seen.has(k) || skip.has(k) || !(k in item)) return;
                  if (k === "description" || k === "summary") return;
                  const text = linkedinHarvestFormatDetailFieldValue(item[k], pageKind);
                  if (!text) return;
                  seen.add(k);
                  rows.push(
                    `<dt>${escapeHtml(humanizeMetricKey(k, pageKind))}</dt><dd>${escapeHtml(text)}</dd>`
                  );
                };
                priority.forEach(pushRow);
                Object.keys(item).forEach((k) => pushRow(k));
                if (rows.length) {
                  html += `<dl class="li-metric-detail-kv">${rows.join("")}</dl>`;
                } else if (!desc) {
                  html += '<p class="li-metric-detail-prose">Sem detalhes adicionais.</p>';
                }
                return html;
              }

              function linkedinMetricItemRegisterDetail(item, pageKind, metricKey, index) {
                const id =
                  "lmi-" +
                  Date.now().toString(36) +
                  "-" +
                  Math.random().toString(36).slice(2, 8);
                linkedinMetricItemDetailStore[id] = {
                  item: item,
                  pageKind: pageKind || "personal",
                  metricKey: String(metricKey || ""),
                  index: index,
                };
                return id;
              }

              function openLinkedinMetricItemDetailModal(itemDetailId) {
                const entry = linkedinMetricItemDetailStore[itemDetailId];
                if (!entry) return;
                const modal = document.getElementById("linkedinMetricItemDetailModal");
                const titleEl = document.getElementById("linkedinMetricItemDetailModalTitle");
                const bodyEl = document.getElementById("linkedinMetricItemDetailModalBody");
                if (!modal || !titleEl || !bodyEl) return;
                const line = linkedinHarvestListItemLine(entry.item, entry.pageKind) || "Registo";
                titleEl.textContent = line.length > 90 ? line.slice(0, 90) + "…" : line;
                bodyEl.innerHTML = linkedinHarvestItemDetailBodyHtml(
                  entry.item,
                  entry.pageKind,
                  entry.metricKey
                );
                modal.classList.add("open");
                modal.setAttribute("aria-hidden", "false");
                document.body.style.overflow = "hidden";
              }

              function closeLinkedinMetricItemDetailModal() {
                const modal = document.getElementById("linkedinMetricItemDetailModal");
                if (!modal) return;
                modal.classList.remove("open");
                modal.setAttribute("aria-hidden", "true");
                const metricModal = document.getElementById("linkedinMetricDetailModal");
                const metricOpen = metricModal && metricModal.classList.contains("open");
                const calModal = document.getElementById("linkedinCalendarModal");
                const calOpen = calModal && calModal.classList.contains("open");
                if (!metricOpen && !linkedinCalendarModalDateKey && !calOpen) {
                  document.body.style.overflow = "";
                }
              }

              function linkedinMetricDetailListHtmlFromObjects(items, pageKind, metricKey) {
                const lis = (items || [])
                  .map((item, index) => {
                    const line = linkedinHarvestListItemLine(item, pageKind);
                    if (!line) return "";
                    const expandable =
                      item && typeof item === "object" && linkedinHarvestItemHasDetail(item);
                    if (!expandable) {
                      return `<li>${escapeHtml(line)}</li>`;
                    }
                    const itemId = linkedinMetricItemRegisterDetail(item, pageKind, metricKey, index);
                    return `<li class="li-metric-detail-item is-expandable" role="button" tabindex="0" data-item-detail-id="${itemId}" title="Clique para ver a descrição completa"><span class="li-metric-detail-item-label">${escapeHtml(line)}</span><span class="li-metric-detail-item-hint">Ver descrição →</span></li>`;
                  })
                  .filter(Boolean);
                if (!lis.length) return '<p class="li-metric-detail-prose">Sem detalhes.</p>';
                return `<ul class="li-metric-detail-list">${lis.join("")}</ul>`;
              }
"""

OLD_ARRAY_BRANCH = """                if (Array.isArray(value)) {
                  const lines = value
                    .map((item) => linkedinHarvestListItemLine(item, pageKind))
                    .filter(Boolean);
                  const countHtml = value.length
                    ? `<p class="li-metric-detail-count">${escapeHtml(String(value.length))} registos</p>`
                    : "";
                  return countHtml + linkedinMetricDetailListHtml(lines);
                }"""

NEW_ARRAY_BRANCH = """                if (Array.isArray(value)) {
                  const countHtml = value.length
                    ? `<p class="li-metric-detail-count">${escapeHtml(String(value.length))} registos</p>`
                    : "";
                  const hasObjects = value.some(
                    (item) => item && typeof item === "object" && !Array.isArray(item)
                  );
                  if (hasObjects) {
                    return countHtml + linkedinMetricDetailListHtmlFromObjects(value, pageKind, key);
                  }
                  const lines = value
                    .map((item) => linkedinHarvestListItemLine(item, pageKind))
                    .filter(Boolean);
                  return countHtml + linkedinMetricDetailListHtml(lines);
                }"""

OLD_INIT_CLICK = """                document.addEventListener("click", (e) => {
                  const closeBtn = e.target.closest("[data-action=\\"close-metric-detail\\"]");
                  if (closeBtn) {
                    e.preventDefault();
                    closeLinkedinMetricDetailModal();
                    return;
                  }
                  const card = e.target.closest(".li-metric-card.is-expandable[data-detail-id]");
                  if (!card) return;
                  const detailId = card.getAttribute("data-detail-id");
                  if (!detailId) return;
                  openLinkedinMetricDetailModal(detailId);
                });"""

NEW_INIT_CLICK = """                document.addEventListener("click", (e) => {
                  const closeItemBtn = e.target.closest("[data-action=\\"close-metric-item-detail\\"]");
                  if (closeItemBtn) {
                    e.preventDefault();
                    closeLinkedinMetricItemDetailModal();
                    return;
                  }
                  const closeBtn = e.target.closest("[data-action=\\"close-metric-detail\\"]");
                  if (closeBtn) {
                    e.preventDefault();
                    closeLinkedinMetricDetailModal();
                    return;
                  }
                  const listItem = e.target.closest(".li-metric-detail-item.is-expandable[data-item-detail-id]");
                  if (listItem) {
                    const itemId = listItem.getAttribute("data-item-detail-id");
                    if (itemId) openLinkedinMetricItemDetailModal(itemId);
                    return;
                  }
                  const card = e.target.closest(".li-metric-card.is-expandable[data-detail-id]");
                  if (!card) return;
                  const detailId = card.getAttribute("data-detail-id");
                  if (!detailId) return;
                  openLinkedinMetricDetailModal(detailId);
                });"""

OLD_INIT_KEY = """                document.addEventListener("keydown", (e) => {
                  const card = e.target.closest(".li-metric-card.is-expandable[data-detail-id]");
                  if (!card || (e.key !== "Enter" && e.key !== " ")) return;
                  e.preventDefault();
                  const detailId = card.getAttribute("data-detail-id");
                  if (detailId) openLinkedinMetricDetailModal(detailId);
                });"""

NEW_INIT_KEY = """                document.addEventListener("keydown", (e) => {
                  const listItem = e.target.closest(".li-metric-detail-item.is-expandable[data-item-detail-id]");
                  if (listItem && (e.key === "Enter" || e.key === " ")) {
                    e.preventDefault();
                    const itemId = listItem.getAttribute("data-item-detail-id");
                    if (itemId) openLinkedinMetricItemDetailModal(itemId);
                    return;
                  }
                  const card = e.target.closest(".li-metric-card.is-expandable[data-detail-id]");
                  if (!card || (e.key !== "Enter" && e.key !== " ")) return;
                  e.preventDefault();
                  const detailId = card.getAttribute("data-detail-id");
                  if (detailId) openLinkedinMetricDetailModal(detailId);
                });"""

OLD_ESCAPE = """              document.addEventListener("keydown", (e) => {
                if (e.key !== "Escape") return;
                const metricModal = document.getElementById("linkedinMetricDetailModal");
                if (metricModal && metricModal.classList.contains("open")) {
                  closeLinkedinMetricDetailModal();
                  return;
                }
                if (linkedinCalendarModalDateKey) closeLinkedinCalendarDayModal();
              });"""

NEW_ESCAPE = """              document.addEventListener("keydown", (e) => {
                if (e.key !== "Escape") return;
                const itemModal = document.getElementById("linkedinMetricItemDetailModal");
                if (itemModal && itemModal.classList.contains("open")) {
                  closeLinkedinMetricItemDetailModal();
                  return;
                }
                const metricModal = document.getElementById("linkedinMetricDetailModal");
                if (metricModal && metricModal.classList.contains("open")) {
                  closeLinkedinMetricDetailModal();
                  return;
                }
                if (linkedinCalendarModalDateKey) closeLinkedinCalendarDayModal();
              });"""

OLD_CLOSE_METRIC = """              function closeLinkedinMetricDetailModal() {
                const modal = document.getElementById("linkedinMetricDetailModal");
                if (!modal) return;
                modal.classList.remove("open");
                modal.setAttribute("aria-hidden", "true");
                const calModal = document.getElementById("linkedinCalendarModal");
                const calOpen = calModal && calModal.classList.contains("open");
                if (!linkedinCalendarModalDateKey && !calOpen) document.body.style.overflow = "";
              }"""

NEW_CLOSE_METRIC = """              function closeLinkedinMetricDetailModal() {
                closeLinkedinMetricItemDetailModal();
                const modal = document.getElementById("linkedinMetricDetailModal");
                if (!modal) return;
                modal.classList.remove("open");
                modal.setAttribute("aria-hidden", "true");
                const calModal = document.getElementById("linkedinCalendarModal");
                const calOpen = calModal && calModal.classList.contains("open");
                if (!linkedinCalendarModalDateKey && !calOpen) document.body.style.overflow = "";
              }"""

raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

# Remove old linkedinHarvestListItemLine through linkedinMetricItemRegister if partial
m = re.search(
    r"function resolveLinkedinMetricDetailValue\(metricKey, displayValue, rawProfile\) \{",
    h,
)
m2 = re.search(r"function linkedinMetricRegisterDetail\(key, value, pageKind\) \{", h)
if not m or not m2:
    raise SystemExit("anchors not found for harvest block replace")
# Keep resolveLinkedinMetricDetailValue, replace everything until registerDetail
h = h[: m.start()] + h[m.start() : m2.start()] + HARVEST_JS + h[m2.start() :]

# But wait - HARVEST_JS doesn't include resolveLinkedinMetricDetailValue - good, we kept it

if OLD_ARRAY_BRANCH not in h:
    raise SystemExit("array branch not found")
h = h.replace(OLD_ARRAY_BRANCH, NEW_ARRAY_BRANCH, 1)

for old, new, label in [
    (OLD_INIT_CLICK, NEW_INIT_CLICK, "init click"),
    (OLD_INIT_KEY, NEW_INIT_KEY, "init keydown"),
    (OLD_ESCAPE, NEW_ESCAPE, "escape"),
    (OLD_CLOSE_METRIC, NEW_CLOSE_METRIC, "close metric"),
]:
    if old in h:
        h = h.replace(old, new, 1)
        print("patched", label)
    else:
        print("MISSING", label)

if "linkedinMetricItemDetailModal" not in h.split("<script")[0]:
    anchor = 'id="linkedinMetricDetailModal"'
    idx = h.find(anchor)
    if idx < 0:
        raise SystemExit("metric modal not found")
    end = h.find("</div>", h.find("linkedinMetricDetailModalBody", idx))
    # find closing of modal - after body div, panel, modal (3 closing divs)
    for _ in range(3):
        end = h.find("</div>", end + 1)
    h = h[: end + len("</div>")] + ITEM_MODAL_HTML + h[end + len("</div>") :]
    print("inserted item modal html")

if ".li-metric-item-modal" not in h:
    anchor = ".li-metric-modal.open { display: flex; }"
    if anchor not in h:
        anchor = ".li-metric-modal.open"
    h = h.replace(anchor, anchor + ITEM_MODAL_CSS, 1)
    print("inserted item modal css")

PAGE.write_text(
    prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print(
    "done",
    "linkedinHarvestCoerceText" in h,
    "openLinkedinMetricItemDetailModal" in h,
    "linkedinMetricItemDetailModal" in h,
)
