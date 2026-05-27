# -*- coding: utf-8 -*-
"""Perfil pessoal: certificações sempre em lista legível, nunca na grelha amontoada."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD_SKIP = """              const LI_PROFILE_SKIP_GRID = new Set([
                "photo", "profilePicture", "firstName", "lastName", "headline", "location",
                "linkedinUrl", "connectionsCount", "followerCount", "publicIdentifier", "about", "coverPicture"
              ]);"""

NEW_SKIP = """              const LI_PROFILE_SKIP_GRID = new Set([
                "photo", "profilePicture", "firstName", "lastName", "headline", "location",
                "linkedinUrl", "connectionsCount", "followerCount", "publicIdentifier", "about", "coverPicture",
                "certifications", "certifications_extra"
              ]);"""

if OLD_SKIP in h:
    h = h.replace(OLD_SKIP, NEW_SKIP, 1)
else:
    raise SystemExit("LI_PROFILE_SKIP_GRID not found")

OLD_CERT_FN = """              function renderLinkedinCertificationsSection(rawProfile, obj) {
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
                    const linkHtml = link && /^https?:\\/\\//i.test(link)
                      ? `<a class="li-metric-link" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Ver credencial</a>`
                      : "";
                    return `<li class="li-cert-item"><strong>${escapeHtml(title)}</strong>${meta ? `<span>${escapeHtml(meta)}</span>` : ""}${linkHtml ? `<div style="margin-top:6px">${linkHtml}</div>` : ""}</li>`;
                  }).join("");
                } else {
                  itemsHtml = fromMetrics.map(([, v]) => `<li class="li-cert-item">${escapeHtml(String(v))}</li>`).join("");
                }
                const count = rawList.length || fromMetrics.length;
                return `<div class="li-profile-section"><h5 class="li-profile-section-title">Certificações (${count})</h5><ul class="li-cert-list">${itemsHtml}</ul></div>`;
              }"""

NEW_CERT_FN = r"""              function parseBundledCertificationText(value) {
                const text = String(value == null ? "" : value).trim();
                if (!text || isMetricValueMissing(text)) return [];
                const parts = text.split(/[;|•\n]+/).map((p) => p.trim()).filter(Boolean);
                if (parts.length <= 1 && /^\d+\s*[—–-]\s*/.test(text)) {
                  const body = text.replace(/^\d+\s*[—–-]\s*/, "").trim();
                  return body.split(";").map((p) => p.trim()).filter(Boolean);
                }
                return parts.length > 1 ? parts : (text ? [text] : []);
              }

              function renderLinkedinCertificationItem(cert, idx) {
                if (typeof cert === "string") {
                  const t = cert.trim();
                  return t ? `<li class="li-cert-item"><strong>${escapeHtml(t)}</strong></li>` : "";
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
                return `<li class="li-cert-item"><strong>${escapeHtml(title)}</strong>${meta ? `<div class="li-cert-meta">${escapeHtml(meta)}</div>` : ""}${linkHtml ? `<div class="li-cert-link">${linkHtml}</div>` : ""}</li>`;
              }

              function renderLinkedinCertificationsSection(rawProfile, obj) {
                rawProfile = rawProfile && typeof rawProfile === "object" ? rawProfile : {};
                obj = obj && typeof obj === "object" ? obj : {};
                let rawList = Array.isArray(rawProfile.certifications) ? rawProfile.certifications : [];
                if (!rawList.length && obj.certifications) {
                  rawList = parseBundledCertificationText(obj.certifications);
                }
                const fromMetrics = Object.entries(obj)
                  .filter(([k]) => String(k).startsWith("certification_"))
                  .sort(([a], [b]) => String(a).localeCompare(String(b), undefined, { numeric: true }));

                if (!rawList.length && !fromMetrics.length) return "";

                let itemsHtml = "";
                if (rawList.length) {
                  itemsHtml = rawList.map((cert, idx) => renderLinkedinCertificationItem(cert, idx)).filter(Boolean).join("");
                } else {
                  itemsHtml = fromMetrics.map(([, v]) => {
                    const t = String(v).trim();
                    return t ? `<li class="li-cert-item"><strong>${escapeHtml(t)}</strong></li>` : "";
                  }).join("");
                }
                const extra = obj.certifications_extra ? `<li class="li-cert-item is-more">${escapeHtml(String(obj.certifications_extra))}</li>` : "";
                const count = rawList.length || fromMetrics.length;
                return `<div class="li-profile-section li-profile-section--certs">
                  <h5 class="li-profile-section-title">Certificações (${count})</h5>
                  <ul class="li-cert-list">${itemsHtml}${extra}</ul>
                </div>`;
              }"""

if OLD_CERT_FN not in h:
    raise SystemExit("renderLinkedinCertificationsSection block not found")
h = h.replace(OLD_CERT_FN, NEW_CERT_FN, 1)

# Grid filter: exclude cert keys
h = h.replace(
    "return key && !LI_PROFILE_SKIP_GRID.has(key) && !key.startsWith(\"certification_\") && !LI_PROFILE_BOOL_KEYS.includes(key) && !LI_PROFILE_TECH_KEYS.has(key);",
    "return key && !LI_PROFILE_SKIP_GRID.has(key) && !key.startsWith(\"certification_\") && key !== \"certifications_extra\" && !LI_PROFILE_BOOL_KEYS.includes(key) && !LI_PROFILE_TECH_KEYS.has(key);",
    1,
)

# Move certs section before experience grid in personal overview (after about/cover)
h = h.replace(
    "${coverUrl ? `<div class=\"li-profile-section\"><h5 class=\"li-profile-section-title\">Capa</h5><div class=\"li-profile-cover\"><img src=\"${escapeHtml(coverUrl)}\" alt=\"Capa\" loading=\"lazy\" referrerpolicy=\"no-referrer\" /></div></div>` : \"\"}\n                  ${renderLinkedinCertificationsSection(rawProfile, obj)}",
    "${coverUrl ? `<div class=\"li-profile-section\"><h5 class=\"li-profile-section-title\">Capa</h5><div class=\"li-profile-cover\"><img src=\"${escapeHtml(coverUrl)}\" alt=\"Capa\" loading=\"lazy\" referrerpolicy=\"no-referrer\" /></div></div>` : \"\"}\n                  ${renderLinkedinCertificationsSection(rawProfile, obj)}",
    1,
)

# CSS for cert meta
if ".li-cert-meta" not in h:
    h = h.replace(
        ".li-cert-item strong { display: block;",
        ".li-cert-meta { font-size: 0.8rem; color: var(--muted); margin-top: 4px; }\n              .li-cert-link { margin-top: 8px; }\n              .li-cert-item.is-more { font-style: italic; color: var(--muted); }\n              .li-profile-section--certs { border-color: rgba(10,102,194,0.25); }\n              .li-cert-item strong { display: block;",
        1,
    )

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "parseBundledCertificationText" in h, "certifications_extra" in h)
