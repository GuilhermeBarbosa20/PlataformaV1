# -*- coding: utf-8 -*-
"""Move badges Confiança/Qualidade do analysis-header para o hero do perfil harvest."""

from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"

BADGES_HELPER = r"""
              function renderLinkedinAnalysisQualityBadges(ctx) {
                if (!ctx || typeof ctx !== "object") return "";
                const profile = ctx.public_profile_data || {};
                const confidence = (ctx.confianca_analise || "baixa").toLowerCase();
                const confCls = confidence === "alta" ? "ok" : (confidence === "media" ? "warn" : "bad");
                const quality = (profile.data_quality || "—").toString();
                const qCls = quality === "alta" ? "ok" : (quality === "media" ? "warn" : "bad");
                const method = profile.collection_method || ctx.source || "";
                const methodBadge =
                  method && String(method).toLowerCase().includes("apify")
                    ? `<span class="badge info"><span class="dot"></span> Dados: Apify (posts públicos)</span>`
                    : method
                      ? `<span class="badge"><span class="dot"></span> ${escapeHtml(String(method))}</span>`
                      : "";
                return `<div class="li-profile-hero-badges">
                  <span class="badge ${confCls}"><span class="dot"></span> Confiança: ${escapeHtml(confidence)}</span>
                  <span class="badge ${qCls}"><span class="dot"></span> Qualidade dados: ${escapeHtml(quality)}</span>
                  ${methodBadge}
                </div>`;
              }
"""

BADGES_CSS = """
              .li-profile-hero-badges {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-bottom: 12px;
              }
              .li-profile-hero-badges .badge {
                font-size: 0.78rem;
                padding: 6px 10px;
              }
"""

OLD_HEADER = """                return `
                  <div class="analysis-header">
                    <div class="who">
                      <div class="ig-avatar">${initial}</div>
                      <div>
                        <h2>@${escapeHtml(username)}</h2>
                        <small>${escapeHtml(subLine)}</small>
                        ${profileUrl ? `<small><a href="${escapeHtml(profileUrl)}" target="_blank" rel="noopener" style="color:var(--accent)">Ver perfil no LinkedIn ↗</a></small>` : ""}
                      </div>
                    </div>
                    <div class="header-badges">
                      <span class="badge ${confCls}"><span class="dot"></span> Confiança: ${escapeHtml(confidence)}</span>
                      <span class="badge ${qCls}"><span class="dot"></span> Qualidade dados: ${escapeHtml(quality)}</span>
                      ${methodBadge}
                    </div>
                  </div>
                `;"""

NEW_HEADER = """                return "";"""

OLD_PERSONAL_STATS = """                    ${statsPills.length ? `<div class="li-profile-hero-stats">${statsPills.join("")}</div>` : ""}
                    <div class="li-profile-hero-actions">${url ? `<a class="li-profile-btn" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Ver no LinkedIn</a>` : ""}</div>"""

NEW_PERSONAL_STATS = """                    ${statsPills.length ? `<div class="li-profile-hero-stats">${statsPills.join("")}</div>` : ""}
                    ${renderLinkedinAnalysisQualityBadges(ctx)}
                    <div class="li-profile-hero-actions">${url ? `<a class="li-profile-btn" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Ver no LinkedIn</a>` : ""}</div>"""

OLD_COMPANY_STATS = """                      ${statsPills.length ? `<div class="li-profile-hero-stats">${statsPills.join("")}</div>` : ""}
                      <div class="li-profile-hero-actions">"""

NEW_COMPANY_STATS = """                      ${statsPills.length ? `<div class="li-profile-hero-stats">${statsPills.join("")}</div>` : ""}
                      ${renderLinkedinAnalysisQualityBadges(ctx)}
                      <div class="li-profile-hero-actions">"""

OLD_INNER = """                  result.innerHTML = `
                    ${renderHeader(data)}
                    ${renderKpis(data)}"""

NEW_INNER = """                  result.innerHTML = `
                    ${renderKpis(data)}"""

raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

if "renderLinkedinAnalysisQualityBadges" not in h:
    anchor = "              function renderHeader(data) {"
    if anchor not in h:
        raise SystemExit("renderHeader anchor not found")
    h = h.replace(anchor, BADGES_HELPER + anchor, 1)
    print("added badges helper")

if ".li-profile-hero-badges" not in h:
    anchor = ".li-profile-hero-stats {"
    if anchor not in h:
        raise SystemExit("hero-stats css anchor not found")
    h = h.replace(anchor, BADGES_CSS + anchor, 1)
    print("added hero badges css")

for old, new, label in [
    (OLD_HEADER, NEW_HEADER, "renderHeader empty"),
    (OLD_PERSONAL_STATS, NEW_PERSONAL_STATS, "personal hero"),
    (OLD_COMPANY_STATS, NEW_COMPANY_STATS, "company hero"),
    (OLD_INNER, NEW_INNER, "innerHTML no header"),
]:
    if old in h:
        h = h.replace(old, new, 1)
        print("patched", label)
    else:
        print("MISSING", label)

PAGE.write_text(
    prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print("done", "renderLinkedinAnalysisQualityBadges" in h, "renderHeader(data)" not in h)
