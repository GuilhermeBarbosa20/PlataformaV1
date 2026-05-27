# -*- coding: utf-8 -*-
"""Visão Geral LinkedIn: layout hero + secções + chips (mais organizado)."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

NEW_CSS = """
              /* —— Visão geral perfil (harvestapi) —— */
              .li-profile-overview { display: flex; flex-direction: column; gap: 20px; margin-top: 8px; }
              .li-profile-hero {
                display: grid;
                grid-template-columns: 112px 1fr;
                gap: 20px 24px;
                padding: 22px 24px;
                border-radius: 18px;
                border: 1px solid var(--line-strong);
                background: linear-gradient(135deg, rgba(10,102,194,0.14) 0%, rgba(255,255,255,0.03) 55%);
                align-items: start;
              }
              @media (max-width: 560px) {
                .li-profile-hero { grid-template-columns: 1fr; text-align: center; }
                .li-profile-hero-avatar { margin: 0 auto; }
                .li-profile-hero-actions { justify-content: center; }
                .li-profile-hero-stats { justify-content: center; }
              }
              .li-profile-hero-avatar {
                width: 112px; height: 112px; border-radius: 16px;
                overflow: hidden; border: 2px solid rgba(255,255,255,0.12);
                background: rgba(0,0,0,0.35); flex-shrink: 0;
              }
              .li-profile-hero-avatar img {
                width: 100%; height: 100%; object-fit: cover; display: block;
              }
              .li-profile-hero-avatar.is-empty {
                display: flex; align-items: center; justify-content: center;
                color: var(--muted); font-size: 2rem; font-weight: 700;
              }
              .li-profile-hero-name {
                font-size: 1.45rem; font-weight: 800; color: var(--text);
                letter-spacing: -0.03em; line-height: 1.2; margin: 0 0 6px;
              }
              .li-profile-hero-headline {
                font-size: 0.92rem; color: var(--muted); line-height: 1.45;
                margin: 0 0 8px; max-height: 4.5em; overflow-y: auto;
              }
              .li-profile-hero-meta {
                font-size: 0.82rem; color: var(--muted-soft, var(--muted));
                margin: 0 0 12px;
              }
              .li-profile-hero-stats {
                display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px;
              }
              .li-profile-stat-pill {
                background: rgba(255,255,255,0.06);
                border: 1px solid var(--line);
                border-radius: 999px;
                padding: 6px 12px;
                font-size: 0.8rem;
              }
              .li-profile-stat-pill strong {
                color: var(--text); font-weight: 700; margin-right: 4px;
              }
              .li-profile-hero-actions { display: flex; flex-wrap: wrap; gap: 8px; }
              .li-profile-btn {
                display: inline-flex; align-items: center; gap: 6px;
                padding: 8px 14px; border-radius: 10px; font-size: 0.82rem;
                font-weight: 600; text-decoration: none;
                border: 1px solid rgba(10,102,194,0.45);
                background: rgba(10,102,194,0.18); color: #93c5fd;
              }
              .li-profile-btn:hover { background: rgba(10,102,194,0.28); }
              .li-profile-flags {
                display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
              }
              .li-profile-flags-label {
                font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em;
                color: var(--muted); margin-right: 4px; width: 100%;
              }
              .li-profile-flag {
                font-size: 0.78rem; padding: 5px 10px; border-radius: 8px;
                border: 1px solid var(--line); background: rgba(255,255,255,0.04);
                color: var(--muted);
              }
              .li-profile-flag.is-yes {
                border-color: rgba(52,211,153,0.35);
                background: rgba(52,211,153,0.1); color: #6ee7b7;
              }
              .li-profile-section {
                border: 1px solid var(--line);
                border-radius: 16px;
                padding: 16px 18px;
                background: rgba(255,255,255,0.02);
              }
              .li-profile-section-title {
                font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em;
                color: var(--muted); margin: 0 0 14px; font-weight: 600;
              }
              .li-profile-about {
                font-size: 0.88rem; line-height: 1.55; color: var(--text);
                max-height: 220px; overflow-y: auto; white-space: pre-wrap;
                word-break: break-word;
              }
              .li-profile-cover {
                border-radius: 12px; overflow: hidden; max-height: 160px;
                background: rgba(0,0,0,0.25);
              }
              .li-profile-cover img {
                width: 100%; height: auto; max-height: 160px;
                object-fit: cover; display: block;
              }
              .li-metrics-grid--compact {
                grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
                gap: 10px;
              }
              .li-metrics-grid--compact .li-metric-card {
                padding: 12px 14px; min-height: 72px;
              }
              .li-metrics-grid--compact .li-metric-value {
                font-size: 0.88rem; font-weight: 600;
              }
              .li-metrics-grid--posts {
                grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
              }
              .li-profile-tech {
                border: 1px dashed var(--line);
                border-radius: 12px; padding: 0;
                background: rgba(0,0,0,0.15);
              }
              .li-profile-tech summary {
                cursor: pointer; padding: 12px 16px;
                font-size: 0.82rem; color: var(--muted); font-weight: 600;
                list-style: none;
              }
              .li-profile-tech summary::-webkit-details-marker { display: none; }
              .li-profile-tech summary::before { content: "▸ "; }
              .li-profile-tech[open] summary::before { content: "▾ "; }
              .li-profile-tech .li-metrics-grid {
                padding: 0 14px 14px;
                grid-template-columns: 1fr;
              }
              .li-profile-tech .li-metric-card { min-height: auto; }
"""

CSS_ANCHOR = "              /* —— Visão geral perfil (harvestapi) —— */"
if CSS_ANCHOR not in h:
    anchor = "              .li-metrics-empty {"
    if anchor not in h:
        raise SystemExit("css anchor not found")
    h = h.replace(anchor, NEW_CSS + "\n" + anchor, 1)
else:
    pass  # already patched

if "li-profile-overview" not in h:
    anchor = "              .li-metrics-empty {"
    h = h.replace(anchor, NEW_CSS + "\n" + anchor, 1)

NEW_RENDER_BLOCK = r"""
              const LI_PROFILE_HERO_KEYS = new Set([
                "photo", "profilePicture", "firstName", "lastName", "headline", "location",
                "linkedinUrl", "connectionsCount", "followerCount", "publicIdentifier"
              ]);
              const LI_PROFILE_SKIP_GRID = new Set([
                "photo", "profilePicture", "firstName", "lastName", "headline", "location",
                "linkedinUrl", "connectionsCount", "followerCount", "publicIdentifier", "about", "coverPicture"
              ]);
              const LI_PROFILE_BOOL_KEYS = [
                "openToWork", "hiring", "premium", "verified", "creator", "influencer", "memorialized"
              ];
              const LI_PROFILE_TECH_KEYS = new Set([
                "id", "objectUrn", "originalQuery", "composeOptionType", "multiLocaleHeadline",
                "primaryLocale", "profileLocales", "registeredAt"
              ]);

              function linkedinProfileMetricRaw(obj, key) {
                if (!obj || obj[key] === undefined || obj[key] === null) return null;
                const v = String(obj[key]).trim();
                if (!v || isMetricValueMissing(v)) return null;
                return v;
              }

              function linkedinProfileHeroInitials(first, last) {
                const a = (first || "").trim().charAt(0);
                const b = (last || "").trim().charAt(0);
                return (a + b).toUpperCase() || "?";
              }

              function renderLinkedinHarvestProfileOverview(obj, ctx) {
                const pageKind = getLinkedinPageKind(ctx);
                if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
                  return '<div class="li-metrics-empty">Sem dados de perfil.</div>';
                }
                const first = linkedinProfileMetricRaw(obj, "firstName");
                const last = linkedinProfileMetricRaw(obj, "lastName");
                const name = [first, last].filter(Boolean).join(" ") || "Perfil LinkedIn";
                const headline = linkedinProfileMetricRaw(obj, "headline");
                const location = linkedinProfileMetricRaw(obj, "location");
                const url = linkedinProfileMetricRaw(obj, "linkedinUrl");
                const connections = linkedinProfileMetricRaw(obj, "connectionsCount");
                const followers = linkedinProfileMetricRaw(obj, "followerCount");
                const slug = linkedinProfileMetricRaw(obj, "publicIdentifier");
                const about = linkedinProfileMetricRaw(obj, "about");
                const avatar =
                  extractLinkedinMetricImageUrl("photo", obj.photo) ||
                  extractLinkedinMetricImageUrl("profilePicture", obj.profilePicture);
                const coverUrl = extractLinkedinMetricImageUrl("coverPicture", obj.coverPicture);

                const connLabel = pageKind === "organization" ? "Seguidores" : "Ligações";
                const statsPills = [];
                if (connections) statsPills.push(`<span class="li-profile-stat-pill"><strong>${escapeHtml(connLabel)}</strong>${escapeHtml(connections)}</span>`);
                if (followers && followers !== connections) {
                  statsPills.push(`<span class="li-profile-stat-pill"><strong>Seguidores</strong>${escapeHtml(followers)}</span>`);
                }
                if (slug) statsPills.push(`<span class="li-profile-stat-pill"><strong>ID público</strong>${escapeHtml(slug)}</span>`);

                const avatarHtml = avatar
                  ? `<div class="li-profile-hero-avatar"><img src="${escapeHtml(avatar)}" alt="" loading="lazy" referrerpolicy="no-referrer" /></div>`
                  : `<div class="li-profile-hero-avatar is-empty">${escapeHtml(linkedinProfileHeroInitials(first, last))}</div>`;

                const flagsHtml = LI_PROFILE_BOOL_KEYS.filter((k) => k in obj).map((k) => {
                  const v = linkedinProfileMetricRaw(obj, k) || "—";
                  const yes = v.toLowerCase() === "sim";
                  return `<span class="li-profile-flag${yes ? " is-yes" : ""}">${escapeHtml(humanizeMetricKey(k, pageKind))}: ${escapeHtml(v)}</span>`;
                }).join("");

                const gridEntries = Object.entries(obj).filter(([k]) => {
                  const key = String(k).trim();
                  return key && !LI_PROFILE_SKIP_GRID.has(key) && !LI_PROFILE_BOOL_KEYS.includes(key) && !LI_PROFILE_TECH_KEYS.has(key);
                });

                const techEntries = Object.entries(obj).filter(([k]) => LI_PROFILE_TECH_KEYS.has(String(k).trim()));

                const gridHtml = gridEntries.length
                  ? `<div class="li-profile-section">
                      <h5 class="li-profile-section-title">Experiência, formação e mais</h5>
                      <div class="li-metrics-grid li-metrics-grid--compact">
                        ${gridEntries.map(([k, v]) => {
                          const missing = isMetricValueMissing(v);
                          const cls = linkedinMetricCardClasses(k, v, missing);
                          const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                          return `<div class="${cls}"><div class="li-metric-value">${valueHtml}</div><div class="li-metric-label">${escapeHtml(humanizeMetricKey(k, pageKind))}</div></div>`;
                        }).join("")}
                      </div>
                    </div>`
                  : "";

                const techHtml = techEntries.length
                  ? `<details class="li-profile-tech">
                      <summary>Detalhes técnicos (${techEntries.length})</summary>
                      <div class="li-metrics-grid">
                        ${techEntries.map(([k, v]) => {
                          const missing = isMetricValueMissing(v);
                          const cls = linkedinMetricCardClasses(k, v, missing) + " is-id";
                          const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                          return `<div class="${cls}"><div class="li-metric-value">${valueHtml}</div><div class="li-metric-label">${escapeHtml(humanizeMetricKey(k, pageKind))}</div></div>`;
                        }).join("")}
                      </div>
                    </details>`
                  : "";

                return `
                  <div class="li-profile-overview">
                    <div class="li-profile-hero">
                      ${avatarHtml}
                      <div class="li-profile-hero-body">
                        <h4 class="li-profile-hero-name">${escapeHtml(name)}</h4>
                        ${headline ? `<p class="li-profile-hero-headline">${escapeHtml(headline)}</p>` : ""}
                        ${location ? `<p class="li-profile-hero-meta">📍 ${escapeHtml(location)}</p>` : ""}
                        ${statsPills.length ? `<div class="li-profile-hero-stats">${statsPills.join("")}</div>` : ""}
                        <div class="li-profile-hero-actions">
                          ${url ? `<a class="li-profile-btn" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Ver no LinkedIn</a>` : ""}
                        </div>
                      </div>
                    </div>
                    ${flagsHtml ? `<div class="li-profile-flags"><span class="li-profile-flags-label">Estado do perfil</span>${flagsHtml}</div>` : ""}
                    ${about ? `<div class="li-profile-section"><h5 class="li-profile-section-title">Sobre</h5><div class="li-profile-about">${escapeHtml(about)}</div></div>` : ""}
                    ${coverUrl ? `<div class="li-profile-section"><h5 class="li-profile-section-title">Capa</h5><div class="li-profile-cover"><img src="${escapeHtml(coverUrl)}" alt="Capa" loading="lazy" referrerpolicy="no-referrer" /></div></div>` : ""}
                    ${gridHtml}
                    ${techHtml}
                  </div>
                `;
              }

"""

# Insert new render before renderLinkedinMetricCards if not present
if "renderLinkedinHarvestProfileOverview" not in h:
    anchor = "              function renderLinkedinMetricCards(obj, ctx) {"
    if anchor not in h:
        raise SystemExit("renderLinkedinMetricCards anchor missing")
    h = h.replace(anchor, NEW_RENDER_BLOCK + anchor, 1)

# Update template calls
OLD_PROFILE_RENDER = "${renderLinkedinMetricCards(data.metricas_linkedin || data.metricas_instagram, data)}"
NEW_PROFILE_RENDER = "${renderLinkedinHarvestProfileOverview(data.metricas_linkedin || data.metricas_instagram, data)}"
if OLD_PROFILE_RENDER in h:
    h = h.replace(OLD_PROFILE_RENDER, NEW_PROFILE_RENDER, 1)

OLD_POSTS_GROUP = """                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Desempenho das publicações</h4>
                          ${renderLinkedinMetricCards(data.metricas_universais, data)}
                        </div>"""

NEW_POSTS_GROUP = """                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Desempenho das publicações</h4>
                          <div class="li-metrics-grid li-metrics-grid--posts">
                            ${renderLinkedinMetricCards(data.metricas_universais, data).replace('class="li-metrics-grid"', 'class="li-metrics-grid li-metrics-grid--posts"')}
                          </div>
                        </div>"""

# Simpler: add class in renderLinkedinMetricCards when compact - actually wrap is messy
# Better add optional third param or detect small obj - for posts use separate wrapper in template

NEW_POSTS_SIMPLE = """                        <div class="li-metrics-group li-metrics-group--posts">
                          <h4 class="li-metrics-group-title">Desempenho das publicações</h4>
                          ${renderLinkedinPostMetrics(data.metricas_universais, data)}
                        </div>"""

POST_RENDER_FN = r"""
              function renderLinkedinPostMetrics(obj, ctx) {
                const inner = renderLinkedinMetricCards(obj, ctx);
                if (inner.includes("li-metrics-empty")) return inner;
                return inner.replace('class="li-metrics-grid"', 'class="li-metrics-grid li-metrics-grid--posts"');
              }

"""

if "renderLinkedinPostMetrics" not in h:
    h = h.replace(
        "              function renderLinkedinMetricCards(obj, ctx) {",
        POST_RENDER_FN + "              function renderLinkedinMetricCards(obj, ctx) {",
        1,
    )

if OLD_POSTS_GROUP.split("Desempenho")[0] in h and "renderLinkedinPostMetrics" not in h.split("panel-overview")[1].split("panel-posts")[0]:
    idx = h.find(OLD_POSTS_GROUP)
    if idx >= 0:
        h = h.replace(OLD_POSTS_GROUP, NEW_POSTS_SIMPLE, 1)
elif "li-metrics-group--posts" not in h:
    h = h.replace(
        '<h4 class="li-metrics-group-title">Desempenho das publicações</h4>\n                          ${renderLinkedinMetricCards(data.metricas_universais, data)}',
        '<h4 class="li-metrics-group-title">Desempenho das publicações</h4>\n                          ${renderLinkedinPostMetrics(data.metricas_universais, data)}',
        1,
    )

# Remove redundant group title wrapper text - update section title
h = h.replace(
    '<h4 class="li-metrics-group-title">Perfil LinkedIn (Apify harvestapi)</h4>\n                          ${renderLinkedinHarvestProfileOverview',
    "${renderLinkedinHarvestProfileOverview",
    1,
)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "li-profile-hero" in h, "renderLinkedinHarvestProfileOverview" in h)
