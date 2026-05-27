# -*- coding: utf-8 -*-
"""Empresa: layout hero + certificações em lista; imagens logo/capa."""
import json
import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

EXTRA_CSS = """
              .li-cert-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
              .li-cert-item {
                padding: 12px 14px; border-radius: 12px; border: 1px solid var(--line);
                background: rgba(255,255,255,0.03); font-size: 0.86rem; line-height: 1.45;
                color: var(--text); word-break: break-word;
              }
              .li-cert-item strong { display: block; font-weight: 700; margin-bottom: 4px; }
              .li-tag-cloud { display: flex; flex-wrap: wrap; gap: 8px; }
              .li-tag {
                font-size: 0.78rem; padding: 5px 10px; border-radius: 999px;
                border: 1px solid var(--line); background: rgba(255,255,255,0.04);
                color: var(--muted); max-width: 100%; word-break: break-word;
              }
"""

if ".li-cert-list" not in h:
    h = h.replace(".li-profile-tech[open] summary::before", EXTRA_CSS + "\n              .li-profile-tech[open] summary::before", 1)

# Image keys
h = h.replace(
    'const LINKEDIN_METRIC_IMAGE_KEYS = new Set(["photo", "profilePicture", "coverPicture"]);',
    'const LINKEDIN_METRIC_IMAGE_KEYS = new Set(["photo", "profilePicture", "coverPicture", "logo", "backgroundCover"]);',
    1,
)

# Template: pass profile
h = h.replace(
    "${renderLinkedinHarvestProfileOverview(data.metricas_linkedin || data.metricas_instagram, data)}",
    "${renderLinkedinHarvestProfileOverview(data.metricas_linkedin || data.metricas_instagram, data, profile)}",
    1,
)

# Find and replace renderLinkedinHarvestProfileOverview through renderLinkedinPostMetrics (exclusive)
start = h.find("function renderLinkedinHarvestProfileOverview(obj, ctx)")
end = h.find("function renderLinkedinPostMetrics", start)
if start < 0 or end < 0:
    raise SystemExit("function anchors not found")

NEW_FUNCTIONS = r"""
              function harvestRawProfile(publicProfile) {
                if (publicProfile && typeof publicProfile.harvest_profile === "object" && publicProfile.harvest_profile) {
                  return publicProfile.harvest_profile;
                }
                return {};
              }

              function renderLinkedinCertificationsSection(rawProfile, obj) {
                const rawList = Array.isArray(rawProfile.certifications) ? rawProfile.certifications : [];
                const fromMetrics = Object.entries(obj || {})
                  .filter(([k]) => String(k).startsWith("certification_"))
                  .sort(([a], [b]) => String(a).localeCompare(String(b), undefined, { numeric: true }));
                if (!rawList.length && !fromMetrics.length) return "";

                let itemsHtml = "";
                if (rawList.length) {
                  itemsHtml = rawList.map((cert, idx) => {
                    if (typeof cert === "string") {
                      return `<li class="li-cert-item">${escapeHtml(cert)}</li>`;
                    }
                    if (!cert || typeof cert !== "object") return "";
                    const title = String(cert.title || cert.name || `Certificação ${idx + 1}`).trim();
                    const issuer = String(cert.issuedBy || cert.authority || "").trim();
                    const when = String(cert.issuedAt || cert.issuedOn || "").trim();
                    const link = String(cert.link || cert.url || "").trim();
                    const meta = [issuer, when].filter(Boolean).join(" · ");
                    const linkHtml = link && /^https?:\/\//i.test(link)
                      ? `<a class="li-metric-link" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Ver credencial</a>`
                      : "";
                    return `<li class="li-cert-item"><strong>${escapeHtml(title)}</strong>${meta ? `<span>${escapeHtml(meta)}</span>` : ""}${linkHtml ? `<div style="margin-top:6px">${linkHtml}</div>` : ""}</li>`;
                  }).join("");
                } else {
                  itemsHtml = fromMetrics.map(([, v]) => `<li class="li-cert-item">${escapeHtml(String(v))}</li>`).join("");
                }
                const count = rawList.length || fromMetrics.length;
                return `<div class="li-profile-section"><h5 class="li-profile-section-title">Certificações (${count})</h5><ul class="li-cert-list">${itemsHtml}</ul></div>`;
              }

              function renderLinkedinTagSection(title, rawValue, metricValue) {
                const text = metricValue || (typeof rawValue === "string" ? rawValue : "");
                const tags = String(text || "").split("·").map((t) => t.replace(/\(\+\d+.*\)$/, "").trim()).filter(Boolean);
                if (!tags.length && Array.isArray(rawValue)) {
                  rawValue.forEach((t) => { if (typeof t === "string" && t.trim()) tags.push(t.trim()); });
                }
                if (!tags.length) return "";
                return `<div class="li-profile-section"><h5 class="li-profile-section-title">${escapeHtml(title)}</h5><div class="li-tag-cloud">${tags.map((t) => `<span class="li-tag">${escapeHtml(t)}</span>`).join("")}</div></div>`;
              }

              function renderLinkedinCompanyProfileOverview(obj, ctx, rawProfile) {
                const pageKind = "organization";
                const name = linkedinProfileMetricRaw(obj, "name") || linkedinProfileMetricRaw(obj, "universalName") || "Empresa";
                const tagline = linkedinProfileMetricRaw(obj, "tagline");
                const website = linkedinProfileMetricRaw(obj, "website");
                const url = linkedinProfileMetricRaw(obj, "linkedinUrl") || linkedinProfileMetricRaw(obj, "url");
                const description = linkedinProfileMetricRaw(obj, "description");
                const employees = linkedinProfileMetricRaw(obj, "employeeCount");
                const employeeRange = linkedinProfileMetricRaw(obj, "employeeCountRange");
                const followers = linkedinProfileMetricRaw(obj, "followerCount");
                const phone = linkedinProfileMetricRaw(obj, "phone");
                const founded = linkedinProfileMetricRaw(obj, "foundedOn");
                const logo = extractLinkedinMetricImageUrl("logo", obj.logo) || extractLinkedinMetricImageUrl("logo", rawProfile.logo);
                const coverUrl = extractLinkedinMetricImageUrl("backgroundCover", obj.backgroundCover) || extractLinkedinMetricImageUrl("backgroundCover", rawProfile.backgroundCover);

                const LI_COMPANY_SKIP = new Set([
                  "name", "universalName", "tagline", "website", "linkedinUrl", "url", "description",
                  "logo", "backgroundCover", "backgroundCovers", "logos", "employeeCount", "employeeCountRange",
                  "followerCount", "phone", "foundedOn", "specialities", "industries", "locations", "certifications"
                ]);

                const statsPills = [];
                if (employees) statsPills.push(`<span class="li-profile-stat-pill"><strong>Colaboradores</strong>${escapeHtml(employees)}</span>`);
                if (employeeRange) statsPills.push(`<span class="li-profile-stat-pill"><strong>Dimensão</strong>${escapeHtml(employeeRange)}</span>`);
                if (followers) statsPills.push(`<span class="li-profile-stat-pill"><strong>Seguidores</strong>${escapeHtml(followers)}</span>`);
                if (founded) statsPills.push(`<span class="li-profile-stat-pill"><strong>Fundação</strong>${escapeHtml(founded)}</span>`);
                if (phone) statsPills.push(`<span class="li-profile-stat-pill"><strong>Telefone</strong>${escapeHtml(phone)}</span>`);

                const avatarHtml = logo
                  ? `<div class="li-profile-hero-avatar"><img src="${escapeHtml(logo)}" alt="" loading="lazy" referrerpolicy="no-referrer" /></div>`
                  : `<div class="li-profile-hero-avatar is-empty">${escapeHtml(String(name).slice(0, 2).toUpperCase())}</div>`;

                const gridEntries = Object.entries(obj || {}).filter(([k]) => {
                  const key = String(k).trim();
                  return key && !LI_COMPANY_SKIP.has(key) && !key.startsWith("certification_") && !LI_PROFILE_TECH_KEYS.has(key);
                });

                const gridHtml = gridEntries.length
                  ? `<div class="li-profile-section"><h5 class="li-profile-section-title">Mais informações</h5><div class="li-metrics-grid li-metrics-grid--compact">${gridEntries.map(([k, v]) => {
                      const missing = isMetricValueMissing(v);
                      const cls = linkedinMetricCardClasses(k, v, missing);
                      const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                      return `<div class="${cls}"><div class="li-metric-value">${valueHtml}</div><div class="li-metric-label">${escapeHtml(humanizeMetricKey(k, pageKind))}</div></div>`;
                    }).join("")}</div></div>`
                  : "";

                const techEntries = Object.entries(obj || {}).filter(([k]) => LI_PROFILE_TECH_KEYS.has(String(k).trim()));
                const techHtml = techEntries.length ? `<details class="li-profile-tech"><summary>Detalhes técnicos (${techEntries.length})</summary><div class="li-metrics-grid">${techEntries.map(([k, v]) => {
                  const missing = isMetricValueMissing(v);
                  const cls = linkedinMetricCardClasses(k, v, missing) + " is-id";
                  const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                  return `<div class="${cls}"><div class="li-metric-value">${valueHtml}</div><div class="li-metric-label">${escapeHtml(humanizeMetricKey(k, pageKind))}</div></div>`;
                }).join("")}</div></details>` : "";

                return `<div class="li-profile-overview">
                  ${coverUrl ? `<div class="li-profile-cover" style="margin-bottom:12px;border-radius:16px;overflow:hidden;max-height:140px"><img src="${escapeHtml(coverUrl)}" alt="Capa" loading="lazy" referrerpolicy="no-referrer" style="width:100%;object-fit:cover;max-height:140px" /></div>` : ""}
                  <div class="li-profile-hero">
                    ${avatarHtml}
                    <div class="li-profile-hero-body">
                      <h4 class="li-profile-hero-name">${escapeHtml(name)}</h4>
                      ${tagline ? `<p class="li-profile-hero-headline">${escapeHtml(tagline)}</p>` : ""}
                      ${statsPills.length ? `<div class="li-profile-hero-stats">${statsPills.join("")}</div>` : ""}
                      <div class="li-profile-hero-actions">
                        ${url ? `<a class="li-profile-btn" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Ver no LinkedIn</a>` : ""}
                        ${website && /^https?:\/\//i.test(website) ? `<a class="li-profile-btn" href="${escapeHtml(website)}" target="_blank" rel="noopener noreferrer">Website</a>` : ""}
                      </div>
                    </div>
                  </div>
                  ${description ? `<div class="li-profile-section"><h5 class="li-profile-section-title">Descrição</h5><div class="li-profile-about">${escapeHtml(description)}</div></div>` : ""}
                  ${renderLinkedinTagSection("Especialidades", rawProfile.specialities, obj.specialities)}
                  ${renderLinkedinTagSection("Indústrias", rawProfile.industries, obj.industries)}
                  ${renderLinkedinCertificationsSection(rawProfile, obj)}
                  ${gridHtml}
                  ${techHtml}
                </div>`;
              }

              function renderLinkedinPersonalProfileOverview(obj, ctx, rawProfile) {
                const pageKind = getLinkedinPageKind(ctx);
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
                const avatar = extractLinkedinMetricImageUrl("photo", obj.photo) || extractLinkedinMetricImageUrl("profilePicture", obj.profilePicture);
                const coverUrl = extractLinkedinMetricImageUrl("coverPicture", obj.coverPicture);

                const statsPills = [];
                if (connections) statsPills.push(`<span class="li-profile-stat-pill"><strong>Ligações</strong>${escapeHtml(connections)}</span>`);
                if (followers && followers !== connections) statsPills.push(`<span class="li-profile-stat-pill"><strong>Seguidores</strong>${escapeHtml(followers)}</span>`);
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
                  return key && !LI_PROFILE_SKIP_GRID.has(key) && !key.startsWith("certification_") && !LI_PROFILE_BOOL_KEYS.includes(key) && !LI_PROFILE_TECH_KEYS.has(key);
                });

                const techEntries = Object.entries(obj).filter(([k]) => LI_PROFILE_TECH_KEYS.has(String(k).trim()));

                const gridHtml = gridEntries.length
                  ? `<div class="li-profile-section"><h5 class="li-profile-section-title">Experiência, formação e mais</h5><div class="li-metrics-grid li-metrics-grid--compact">${gridEntries.map(([k, v]) => {
                      const missing = isMetricValueMissing(v);
                      const cls = linkedinMetricCardClasses(k, v, missing);
                      const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                      return `<div class="${cls}"><div class="li-metric-value">${valueHtml}</div><div class="li-metric-label">${escapeHtml(humanizeMetricKey(k, pageKind))}</div></div>`;
                    }).join("")}</div></div>` : "";

                const techHtml = techEntries.length ? `<details class="li-profile-tech"><summary>Detalhes técnicos (${techEntries.length})</summary><div class="li-metrics-grid">${techEntries.map(([k, v]) => {
                  const missing = isMetricValueMissing(v);
                  const cls = linkedinMetricCardClasses(k, v, missing) + " is-id";
                  const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                  return `<div class="${cls}"><div class="li-metric-value">${valueHtml}</div><div class="li-metric-label">${escapeHtml(humanizeMetricKey(k, pageKind))}</div></div>`;
                }).join("")}</div></details>` : "";

                return `<div class="li-profile-overview">
                  <div class="li-profile-hero">${avatarHtml}<div class="li-profile-hero-body">
                    <h4 class="li-profile-hero-name">${escapeHtml(name)}</h4>
                    ${headline ? `<p class="li-profile-hero-headline">${escapeHtml(headline)}</p>` : ""}
                    ${location ? `<p class="li-profile-hero-meta">${escapeHtml(location)}</p>` : ""}
                    ${statsPills.length ? `<div class="li-profile-hero-stats">${statsPills.join("")}</div>` : ""}
                    <div class="li-profile-hero-actions">${url ? `<a class="li-profile-btn" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Ver no LinkedIn</a>` : ""}</div>
                  </div></div>
                  ${flagsHtml ? `<div class="li-profile-flags"><span class="li-profile-flags-label">Estado do perfil</span>${flagsHtml}</div>` : ""}
                  ${about ? `<div class="li-profile-section"><h5 class="li-profile-section-title">Sobre</h5><div class="li-profile-about">${escapeHtml(about)}</div></div>` : ""}
                  ${coverUrl ? `<div class="li-profile-section"><h5 class="li-profile-section-title">Capa</h5><div class="li-profile-cover"><img src="${escapeHtml(coverUrl)}" alt="Capa" loading="lazy" referrerpolicy="no-referrer" /></div></div>` : ""}
                  ${renderLinkedinCertificationsSection(rawProfile, obj)}
                  ${gridHtml}
                  ${techHtml}
                </div>`;
              }

              function renderLinkedinHarvestProfileOverview(obj, ctx, publicProfile) {
                if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
                  return '<div class="li-metrics-empty">Sem dados de perfil.</div>';
                }
                const rawProfile = harvestRawProfile(publicProfile);
                const pageKind = getLinkedinPageKind(ctx);
                const isCompany = pageKind === "organization" || linkedinProfileMetricRaw(obj, "universalName") || linkedinProfileMetricRaw(obj, "tagline") || (rawProfile && (rawProfile.universalName || rawProfile.tagline));
                if (isCompany && pageKind !== "personal") {
                  return renderLinkedinCompanyProfileOverview(obj, ctx, rawProfile);
                }
                return renderLinkedinPersonalProfileOverview(obj, ctx, rawProfile);
              }

"""

h = h[:start] + NEW_FUNCTIONS + h[end:]

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "renderLinkedinCompanyProfileOverview" in h, "renderLinkedinCertificationsSection" in h)
