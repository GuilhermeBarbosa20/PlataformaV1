# -*- coding: utf-8 -*-
"""Corrige modal de métricas: DOM estático + delegação de cliques (fora do bloco autoAuthenticated)."""

from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"

METRIC_MODAL_HTML = """
            <div id="linkedinMetricDetailModal" class="li-metric-modal" aria-hidden="true" role="dialog" aria-labelledby="linkedinMetricDetailModalTitle">
              <div class="li-metric-modal-backdrop" data-action="close-metric-detail"></div>
              <div class="li-metric-modal-panel">
                <div class="li-metric-modal-head">
                  <h4 id="linkedinMetricDetailModalTitle">Detalhe</h4>
                  <button type="button" class="li-metric-modal-close" data-action="close-metric-detail" aria-label="Fechar">&times;</button>
                </div>
                <div id="linkedinMetricDetailModalBody" class="li-metric-modal-body"></div>
              </div>
            </div>"""

# Modal inserido erroneamente no template autoAuthenticated (versão com onclick inline)
METRIC_MODAL_IN_TEMPLATE = """
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

OLD_NEEDS = """              function linkedinMetricNeedsDetailModal(value) {
                if (isMetricValueMissing(value)) return false;"""

NEW_NEEDS = """              const LINKEDIN_EXPANDABLE_METRIC_KEYS = new Set([
                "experience", "education", "skills", "certifications", "certifications_extra",
                "publications", "projects", "volunteering", "honors", "languages",
                "recommendations", "courses", "patents", "organizations", "interests",
                "causes", "testScores", "featured", "highlights", "similarProfiles",
              ]);

              function linkedinMetricNeedsDetailModal(value, metricKey) {
                if (metricKey && LINKEDIN_EXPANDABLE_METRIC_KEYS.has(String(metricKey).trim())) {
                  return !isMetricValueMissing(value);
                }
                if (isMetricValueMissing(value)) return false;"""

OLD_GRID_CARD = """              function renderLinkedinProfileGridCard(k, v, pageKind) {
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
              }"""

NEW_GRID_CARD = """              function renderLinkedinProfileGridCard(k, v, pageKind) {
                const missing = isMetricValueMissing(v);
                const cls = linkedinMetricCardClasses(k, v, missing);
                const label = escapeHtml(humanizeMetricKey(k, pageKind));
                if (missing || !linkedinMetricNeedsDetailModal(v, k)) {
                  const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                  return `<div class="${cls}"><div class="li-metric-value">${valueHtml}</div><div class="li-metric-label">${label}</div></div>`;
                }
                const detailId = linkedinMetricRegisterDetail(k, v, pageKind);
                const preview = escapeHtml(linkedinMetricCardPreview(v) || "Ver detalhes");
                return `<div class="${cls} is-expandable" role="button" tabindex="0" data-detail-id="${detailId}" title="Clique para ver todos os detalhes"><div class="li-metric-value li-metric-value-preview">${preview}</div><div class="li-metric-label">${label}</div><span class="li-metric-open-hint">Clique para ver tudo →</span></div>`;
              }"""

DELEGATION_JS = r"""
              function ensureLinkedinMetricDetailModal() {
                return !!document.getElementById("linkedinMetricDetailModal");
              }

              function initLinkedinMetricDetailInteractions() {
                if (window.__linkedinMetricDetailInit) return;
                window.__linkedinMetricDetailInit = true;
                document.addEventListener("click", (e) => {
                  const closeBtn = e.target.closest("[data-action=\"close-metric-detail\"]");
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
                });
                document.addEventListener("keydown", (e) => {
                  const card = e.target.closest(".li-metric-card.is-expandable[data-detail-id]");
                  if (!card || (e.key !== "Enter" && e.key !== " ")) return;
                  e.preventDefault();
                  const detailId = card.getAttribute("data-detail-id");
                  if (detailId) openLinkedinMetricDetailModal(detailId);
                });
              }
              initLinkedinMetricDetailInteractions();
"""

OLD_OPEN = """              function openLinkedinMetricDetailModal(detailId) {
                const entry = linkedinMetricDetailStore[detailId];
                if (!entry) return;
                const modal = document.getElementById("linkedinMetricDetailModal");"""

NEW_OPEN = """              function openLinkedinMetricDetailModal(detailId) {
                if (!ensureLinkedinMetricDetailModal()) return;
                const entry = linkedinMetricDetailStore[detailId];
                if (!entry) return;
                const modal = document.getElementById("linkedinMetricDetailModal");"""

# renderLinkedinMetricCards may call linkedinMetricNeedsDetailModal(v) only — patch if exists
OLD_METRIC_CARDS_CHECK = "linkedinMetricNeedsDetailModal(v)"
NEW_METRIC_CARDS_CHECK = "linkedinMetricNeedsDetailModal(v, k)"

raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

# 1) Remove modal from dynamic template (inside autoAuthenticated)
if METRIC_MODAL_IN_TEMPLATE.strip() in h:
    h = h.replace(METRIC_MODAL_IN_TEMPLATE, "", 1)
    print("removed modal from autoAuthenticated template")
elif h.count('id="linkedinMetricDetailModal"') > 1:
    print("warn: multiple modals, manual check needed")
else:
    print("modal template block not found (maybe already removed)")

# 2) Static modal before first <script>
if 'id="linkedinMetricDetailModal"' not in h.split("<script")[0]:
    anchor = "\n            <script>"
    if anchor not in h:
        anchor = "<script>"
    if anchor not in h:
        raise SystemExit("script anchor not found")
    h = h.replace(anchor, METRIC_MODAL_HTML + anchor, 1)
    print("inserted static modal before script")
else:
    print("static modal already present")

# 3) JS updates
for old, new, label in [
    (OLD_NEEDS, NEW_NEEDS, "needsDetailModal"),
    (OLD_GRID_CARD, NEW_GRID_CARD, "gridCard"),
    (OLD_OPEN, NEW_OPEN, "openModal"),
]:
    if old in h:
        h = h.replace(old, new, 1)
        print("patched", label)
    else:
        print("skip", label, "(not found)")

if "initLinkedinMetricDetailInteractions" not in h:
    anchor = "              const linkedinMetricDetailStore = {};"
    if anchor not in h:
        raise SystemExit("linkedinMetricDetailStore anchor not found")
    h = h.replace(anchor, anchor + DELEGATION_JS, 1)
    print("added click delegation")
else:
    print("delegation already present")

# metric cards in posts tab
if OLD_METRIC_CARDS_CHECK in h:
    h = h.replace(OLD_METRIC_CARDS_CHECK, NEW_METRIC_CARDS_CHECK)

# pointer-events on expandable cards
if ".li-metric-card.is-expandable {" in h and "pointer-events" not in h.split(".li-metric-card.is-expandable {")[1][:200]:
    h = h.replace(
        ".li-metric-card.is-expandable {\n                cursor: pointer;",
        ".li-metric-card.is-expandable {\n                cursor: pointer;\n                pointer-events: auto;\n                position: relative;\n                z-index: 1;",
        1,
    )

PAGE.write_text(
    prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

h2 = json.loads(PAGE.read_text(encoding="utf-8").split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1])
static = h2.split("<script")[0]
print(
    "verify:",
    "static modal" in static and 'linkedinMetricDetailModal' in static,
    "modal count", h2.count('id="linkedinMetricDetailModal"'),
    "data-detail-id", "data-detail-id" in h2,
    "delegation", "initLinkedinMetricDetailInteractions" in h2,
)
