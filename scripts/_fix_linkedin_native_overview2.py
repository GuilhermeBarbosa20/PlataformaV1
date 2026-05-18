# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

pairs = [
    (
        '<div class="format-label">${escapeHtml(fmt)}</div>',
        '<div class="format-label">${escapeHtml(linkedinFormatLabel(fmt))}</div>',
    ),
    (
        'engagement médio ${Number(er).toFixed(2)}%',
        'interações médias ${Number(er).toFixed(1)}',
    ),
    (
        '<div>Followers <span class="delta ${df.cls}">',
        '<div>Ligações <span class="delta ${df.cls}">',
    ),
    (
        '<div>Posts <span class="delta ${dp.cls}">',
        '<div>Publicações <span class="delta ${dp.cls}">',
    ),
    (
        'Qualidade dados: ${escapeHtml(quality)}</span>\n                    </div>',
        'Qualidade dados: ${escapeHtml(quality)}</span>\n                      ${methodBadge}\n                    </div>',
    ),
    (
        '<small>${escapeHtml(followers)}</small>',
        '<small>${escapeHtml(subLine)}</small>\n                        ${profileUrl ? `<small><a href="${escapeHtml(profileUrl)}" target="_blank" rel="noopener" style="color:var(--accent)">Ver perfil no LinkedIn ↗</a></small>` : ""}',
    ),
]

# header vars - only if not yet applied
if "methodBadge" not in h and "const followers = profile.followers_count" in h:
    h = h.replace(
        "const followers = profile.followers_count !== undefined && profile.followers_count !== null\n"
        '                  ? formatNumber(profile.followers_count) + " ligações"\n'
        '                  : "perfil LinkedIn";',
        'const headline = profile.headline ? String(profile.headline) : "";\n'
        '                const employer = profile.employer ? String(profile.employer) : "";\n'
        '                const subParts = [];\n'
        '                if (headline) subParts.push(headline);\n'
        '                if (employer) subParts.push(employer);\n'
        '                const subLine = subParts.length ? subParts.join(" · ") : "perfil LinkedIn";\n'
        '                const profileUrl = profile.profile_url || data.profile_url || "";\n'
        '                const method = profile.collection_method || data.source || "";\n'
        '                const methodBadge = method && String(method).toLowerCase().includes("apify")\n'
        '                  ? `<span class="badge info"><span class="dot"></span> Dados: Apify (posts públicos)</span>`\n'
        '                  : (method ? `<span class="badge"><span class="dot"></span> ${escapeHtml(String(method))}</span>` : "");',
    )

for old, new in pairs:
    old2 = old.replace("<motion>", "<div>").replace("motion>", "div>")
    if old in h:
        h = h.replace(old, new.replace("<motion>", "<motion>").replace("motion>", "motion>"))
    elif old2 in h:
        h = h.replace(old2, new.replace("<motion>", "<motion>").replace("motion>", "motion>"))

h = h.replace('<motion>Ligações', '<div>Ligações')

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("linkedinFormatLabel in format-row", "linkedinFormatLabel(fmt)" in h)
print("methodBadge", "methodBadge" in h)
print("Followers", "Followers" in h)
