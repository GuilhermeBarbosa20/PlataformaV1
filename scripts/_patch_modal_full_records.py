# -*- coding: utf-8 -*-
"""Modal de métricas: usar harvest_profile bruto (lista completa) em vez do texto resumido."""

from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"

RESOLVE_JS = r"""
              function resolveLinkedinMetricDetailValue(metricKey, displayValue, rawProfile) {
                const raw = rawProfile && typeof rawProfile === "object" ? rawProfile : {};
                const key = String(metricKey || "").trim();
                if (!key || !(key in raw)) return displayValue;
                const rv = raw[key];
                if (rv === null || rv === undefined) return displayValue;
                if (Array.isArray(rv)) return rv.length ? rv : displayValue;
                if (typeof rv === "object") return rv;
                return displayValue;
              }

              function linkedinHarvestListItemLine(item, pageKind) {
                if (item === null || item === undefined) return "";
                if (typeof item === "string") return item.trim();
                if (typeof item !== "object" || Array.isArray(item)) return String(item).trim();
                const title = String(
                  item.title ||
                    item.name ||
                    item.companyName ||
                    item.schoolName ||
                    item.position ||
                    item.headline ||
                    ""
                ).trim();
                const sub = String(
                  item.subtitle ||
                    item.publisher ||
                    item.issuedBy ||
                    item.authority ||
                    item.company ||
                    item.degree ||
                    item.fieldOfStudy ||
                    item.industry ||
                    ""
                ).trim();
                let when = "";
                if (item.publishedOn && typeof item.publishedOn === "object") {
                  const y = item.publishedOn.year;
                  const m = item.publishedOn.month;
                  if (y) when = m ? `${m}/${y}` : String(y);
                }
                if (!when) {
                  when = String(
                    item.issuedAt ||
                      item.issuedOn ||
                      item.date ||
                      item.startDate ||
                      item.endDate ||
                      ""
                  ).trim();
                }
                if (item.timePeriod && typeof item.timePeriod === "object") {
                  const s = item.timePeriod.startDate;
                  const e = item.timePeriod.endDate;
                  const fmt = (d) => {
                    if (!d || typeof d !== "object") return "";
                    const y = d.year;
                    const mo = d.month;
                    return y ? (mo ? `${mo}/${y}` : String(y)) : "";
                  };
                  const a = fmt(s);
                  const b = fmt(e);
                  if (a || b) when = [a, b].filter(Boolean).join(" – ");
                }
                const bits = [];
                if (title) bits.push(title);
                if (sub && sub !== title) bits.push(sub);
                if (when) bits.push(when);
                if (bits.length) return bits.join(" · ");
                return Object.entries(item)
                  .filter(([_, v]) => v !== null && v !== undefined && String(v).trim())
                  .slice(0, 8)
                  .map(([k, v]) => `${humanizeMetricKey(k, pageKind)}: ${String(v).trim()}`)
                  .join(" · ");
              }
"""

OLD_DETAIL_BODY_ARRAY = """                if (Array.isArray(value)) {
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
                }"""

NEW_DETAIL_BODY_ARRAY = """                if (Array.isArray(value)) {
                  const lines = value
                    .map((item) => linkedinHarvestListItemLine(item, pageKind))
                    .filter(Boolean);
                  const countHtml = value.length
                    ? `<p class="li-metric-detail-count">${escapeHtml(String(value.length))} registos</p>`
                    : "";
                  return countHtml + linkedinMetricDetailListHtml(lines);
                }"""

OLD_GRID_CARD = """              function renderLinkedinProfileGridCard(k, v, pageKind) {
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

NEW_GRID_CARD = """              function renderLinkedinProfileGridCard(k, v, pageKind, rawProfile) {
                const missing = isMetricValueMissing(v);
                const cls = linkedinMetricCardClasses(k, v, missing);
                const label = escapeHtml(humanizeMetricKey(k, pageKind));
                if (missing || !linkedinMetricNeedsDetailModal(v, k)) {
                  const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                  return `<div class="${cls}"><div class="li-metric-value">${valueHtml}</div><div class="li-metric-label">${label}</div></div>`;
                }
                const detailValue = resolveLinkedinMetricDetailValue(k, v, rawProfile);
                const detailId = linkedinMetricRegisterDetail(k, detailValue, pageKind);
                const preview = escapeHtml(linkedinMetricCardPreview(v) || "Ver detalhes");
                return `<div class="${cls} is-expandable" role="button" tabindex="0" data-detail-id="${detailId}" title="Clique para ver todos os detalhes"><div class="li-metric-value li-metric-value-preview">${preview}</div><div class="li-metric-label">${label}</div><span class="li-metric-open-hint">Clique para ver tudo →</span></div>`;
              }"""

# personal + company grid/tech maps
REPLACEMENTS = [
    (
        "renderLinkedinProfileGridCard(k, v, pageKind)).join(\"\")}</div></div>`\n                  : \"\";",
        "renderLinkedinProfileGridCard(k, v, pageKind, rawProfile)).join(\"\")}</div></div>`\n                  : \"\";",
    ),
    (
        "const card = renderLinkedinProfileGridCard(k, v, pageKind);\n                  return card.replace('class=\"li-metric-card",
        "const card = renderLinkedinProfileGridCard(k, v, pageKind, rawProfile);\n                  return card.replace('class=\"li-metric-card",
    ),
    (
        "renderLinkedinProfileGridCard(k, v, pageKind)).join(\"\")}</div></div>` : \"\";",
        "renderLinkedinProfileGridCard(k, v, pageKind, rawProfile)).join(\"\")}</div></div>` : \"\";",
    ),
]

raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

if "resolveLinkedinMetricDetailValue" not in h:
    anchor = "              function linkedinMetricRegisterDetail(key, value, pageKind) {"
    if anchor not in h:
        raise SystemExit("register anchor not found")
    h = h.replace(anchor, RESOLVE_JS + anchor, 1)
    print("added resolve + list line helpers")

if OLD_DETAIL_BODY_ARRAY in h:
    h = h.replace(OLD_DETAIL_BODY_ARRAY, NEW_DETAIL_BODY_ARRAY, 1)
    print("patched detail body array branch")
else:
    print("WARN: array branch not found")

if OLD_GRID_CARD in h:
    h = h.replace(OLD_GRID_CARD, NEW_GRID_CARD, 1)
    print("patched grid card")
else:
    print("WARN: grid card not found")

for old, new in REPLACEMENTS:
    n = h.count(old)
    if n:
        h = h.replace(old, new)
        print("replaced call sites", repr(old[:50]), "x", n)

# posts metrics grid (no raw profile)
old_posts = "${entries.map(([k, v]) => renderLinkedinProfileGridCard(k, v, pageKind)).join(\"\")}"
new_posts = "${entries.map(([k, v]) => renderLinkedinProfileGridCard(k, v, pageKind, null)).join(\"\")}"
if old_posts in h:
    h = h.replace(old_posts, new_posts, 1)
    print("patched posts metrics")

PAGE.write_text(
    prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print(
    "done",
    "resolveLinkedinMetricDetailValue" in h,
    "rawProfile)" in h,
    h.count("renderLinkedinProfileGridCard(k, v, pageKind, rawProfile)"),
)
