# -*- coding: utf-8 -*-
"""Cartões de métricas: overflow legível + imagens photo/profilePicture/coverPicture."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD_CSS = """              .li-metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(188px, 1fr));
                gap: 12px;
              }
              .li-metric-card {
                background: linear-gradient(165deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
                border: 1px solid var(--line);
                border-radius: 14px;
                padding: 16px 18px;
                min-height: 88px;
                display: flex; flex-direction: column; justify-content: center;
                transition: border-color 0.15s ease;
              }
              .li-metric-card:hover { border-color: var(--line-strong); }
              .li-metric-card.is-muted { opacity: 0.72; }
              .li-metric-card.is-unavailable .li-metric-value {
                font-size: 0.72rem;
                line-height: 1.35;
                font-weight: 500;
                color: var(--muted);
              }
              .li-metric-card.is-muted .li-metric-value { color: var(--muted); font-weight: 600; }
              .li-metric-value {
                font-size: 1.28rem; font-weight: 800; color: var(--text);
                line-height: 1.2; letter-spacing: -0.02em;
              }
              .li-metric-label {
                font-size: 0.8rem; color: var(--muted-soft, var(--muted));
                margin-top: 8px; line-height: 1.35;
              }"""

NEW_CSS = """              .li-metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 12px;
                align-items: stretch;
              }
              .li-metric-card {
                background: linear-gradient(165deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
                border: 1px solid var(--line);
                border-radius: 14px;
                padding: 14px 16px;
                min-height: 88px;
                min-width: 0;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                justify-content: flex-start;
                transition: border-color 0.15s ease;
              }
              .li-metric-card:hover { border-color: var(--line-strong); }
              .li-metric-card.is-muted { opacity: 0.72; }
              .li-metric-card.is-long-text { grid-column: span 2; }
              .li-metric-card.is-cover { grid-column: span 2; }
              @media (max-width: 720px) {
                .li-metric-card.is-long-text,
                .li-metric-card.is-cover { grid-column: span 1; }
              }
              .li-metric-card.is-unavailable .li-metric-value {
                font-size: 0.72rem;
                line-height: 1.35;
                font-weight: 500;
                color: var(--muted);
              }
              .li-metric-card.is-muted .li-metric-value { color: var(--muted); font-weight: 600; }
              .li-metric-value {
                font-size: 1.05rem;
                font-weight: 700;
                color: var(--text);
                line-height: 1.35;
                letter-spacing: -0.01em;
                min-width: 0;
                max-width: 100%;
                overflow: hidden;
                word-break: break-word;
                overflow-wrap: anywhere;
                flex: 1 1 auto;
              }
              .li-metric-card.is-long-text .li-metric-value,
              .li-metric-card.is-id .li-metric-value {
                font-size: 0.8rem;
                font-weight: 500;
                line-height: 1.45;
                max-height: 140px;
                overflow-y: auto;
                overflow-x: hidden;
                padding-right: 4px;
              }
              .li-metric-card.is-about .li-metric-value { max-height: 200px; }
              .li-metric-card.is-image .li-metric-value {
                font-size: inherit;
                font-weight: inherit;
                max-height: none;
                overflow: visible;
              }
              .li-metric-media {
                width: 100%;
                max-height: 168px;
                border-radius: 10px;
                overflow: hidden;
                background: rgba(0,0,0,0.25);
                display: flex;
                align-items: center;
                justify-content: center;
                flex: 1 1 auto;
                min-height: 80px;
              }
              .li-metric-media img {
                width: 100%;
                height: auto;
                max-height: 168px;
                object-fit: contain;
                display: block;
              }
              .li-metric-card.is-cover .li-metric-media img { object-fit: cover; max-height: 120px; }
              .li-metric-link {
                color: var(--accent, #7c9cff);
                font-size: 0.85rem;
                font-weight: 600;
                text-decoration: none;
                word-break: break-all;
              }
              .li-metric-link:hover { text-decoration: underline; }
              .li-metric-label {
                font-size: 0.78rem;
                color: var(--muted-soft, var(--muted));
                margin-top: auto;
                padding-top: 10px;
                line-height: 1.35;
                flex-shrink: 0;
              }"""

OLD_RENDER = """              function renderLinkedinMetricCards(obj, ctx) {
                const pageKind = getLinkedinPageKind(ctx);
                if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
                  return '<div class="li-metrics-empty">Sem indicadores para este perfil.</div>';
                }
                const entries = Object.entries(obj).filter(([k]) => String(k).trim());
                if (!entries.length) {
                  return '<div class="li-metrics-empty">Sem indicadores para este perfil.</div>';
                }
                return `
                  <div class="li-metrics-grid">
                    ${entries.map(([k, v]) => {
                      const missing = isMetricValueMissing(v);
                      const display = missing ? METRIC_UNAVAILABLE_PUBLIC : String(v).trim();
                      const cls = missing ? "li-metric-card is-muted is-unavailable" : "li-metric-card";
                      const title = missing ? "O LinkedIn não expõe este dado publicamente ou o scraper não o devolveu." : "";
                      return `
                        <div class="${cls}" title="${escapeHtml(title)}">
                          <div class="li-metric-value">${escapeHtml(display)}</div>
                          <div class="li-metric-label">${escapeHtml(humanizeMetricKey(k, pageKind))}</div>
                        </div>
                      `;
                    }).join("")}
                  </div>
                `.replace(/<\\/motion>/g, "</div>").replace(/<div/g, "<div").replace(/<div class="li-metric-value">/g, '<div class="li-metric-value">');
              }"""

NEW_HELPERS = """              const LINKEDIN_METRIC_IMAGE_KEYS = new Set(["photo", "profilePicture", "coverPicture"]);
              const LINKEDIN_METRIC_URL_KEYS = new Set(["linkedinUrl"]);
              const LINKEDIN_METRIC_LONG_TEXT_KEYS = new Set([
                "about", "headline", "topSkills", "skills", "multiLocaleHeadline",
                "experience", "education", "certifications", "emails"
              ]);
              const LINKEDIN_METRIC_ID_KEYS = new Set(["id", "objectUrn"]);

              function extractLinkedinMetricImageUrl(key, value) {
                const k = String(key || "").trim();
                if (!LINKEDIN_METRIC_IMAGE_KEYS.has(k)) return "";
                const raw = String(value == null ? "" : value).trim();
                if (!raw || isMetricValueMissing(raw)) return "";
                if (/^https?:\\/\\//i.test(raw)) return raw;
                return "";
              }

              function linkedinMetricCardClasses(key, value, missing) {
                const k = String(key || "").trim();
                const parts = ["li-metric-card"];
                if (missing) {
                  parts.push("is-muted", "is-unavailable");
                  return parts.join(" ");
                }
                if (extractLinkedinMetricImageUrl(k, value)) {
                  parts.push("is-image");
                  if (k === "coverPicture") parts.push("is-cover");
                } else if (k === "about") {
                  parts.push("is-long-text", "is-about");
                } else if (LINKEDIN_METRIC_LONG_TEXT_KEYS.has(k) || String(value || "").length > 72) {
                  parts.push("is-long-text");
                }
                if (LINKEDIN_METRIC_ID_KEYS.has(k)) parts.push("is-id");
                return parts.join(" ");
              }

              function renderLinkedinMetricValueHtml(key, value, missing, pageKind) {
                if (missing) return escapeHtml(METRIC_UNAVAILABLE_PUBLIC);
                const k = String(key || "").trim();
                const raw = String(value == null ? "" : value).trim();
                const imgUrl = extractLinkedinMetricImageUrl(k, raw);
                if (imgUrl) {
                  const alt = escapeHtml(humanizeMetricKey(k, pageKind));
                  return `<div class="li-metric-media"><img src="${escapeHtml(imgUrl)}" alt="${alt}" loading="lazy" referrerpolicy="no-referrer" /></div>`;
                }
                if (LINKEDIN_METRIC_URL_KEYS.has(k) && /^https?:\\/\\//i.test(raw)) {
                  return `<a class="li-metric-link" href="${escapeHtml(raw)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(raw)}">Abrir perfil</a>`;
                }
                return escapeHtml(raw);
              }

"""

NEW_RENDER = (
    NEW_HELPERS
    + """              function renderLinkedinMetricCards(obj, ctx) {
                const pageKind = getLinkedinPageKind(ctx);
                if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
                  return '<div class="li-metrics-empty">Sem indicadores para este perfil.</div>';
                }
                const entries = Object.entries(obj).filter(([k]) => String(k).trim());
                if (!entries.length) {
                  return '<div class="li-metrics-empty">Sem indicadores para este perfil.</div>';
                }
                return `
                  <div class="li-metrics-grid">
                    ${entries.map(([k, v]) => {
                      const missing = isMetricValueMissing(v);
                      const cls = linkedinMetricCardClasses(k, v, missing);
                      const title = missing
                        ? "O LinkedIn não expõe este dado publicamente ou o scraper não o devolveu."
                        : "";
                      const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                      return `
                        <div class="${cls}" title="${escapeHtml(title)}">
                          <div class="li-metric-value">${valueHtml}</div>
                          <div class="li-metric-label">${escapeHtml(humanizeMetricKey(k, pageKind))}</div>
                        </div>
                      `;
                    }).join("")}
                  </div>
                `;
              }"""
)

if OLD_CSS not in h:
    raise SystemExit("CSS block not found")
h = h.replace(OLD_CSS, NEW_CSS, 1)

# Try without broken replace at end of OLD_RENDER
OLD_RENDER_SIMPLE = OLD_RENDER.split(".replace")[0] + "              }"
if OLD_RENDER_SIMPLE not in h:
    # alternate ending from file
    idx = h.find("function renderLinkedinMetricCards(obj, ctx)")
    if idx < 0:
        raise SystemExit("renderLinkedinMetricCards not found")
    end = h.find("\n              function renderCadence", idx)
    if end < 0:
        raise SystemExit("renderCadence anchor not found")
    h = h[:idx] + NEW_RENDER + h[end:]
else:
    h = h.replace(OLD_RENDER_SIMPLE, NEW_RENDER, 1)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print(
    "ok",
    "extractLinkedinMetricImageUrl" in h,
    "li-metric-media" in h,
    "linkedinMetricCardClasses" in h,
)
