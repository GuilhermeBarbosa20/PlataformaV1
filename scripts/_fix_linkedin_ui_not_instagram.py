"""UI da página LinkedIn: labels LinkedIn (não Instagram)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
h = json.loads((ROOT / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=", 1)[1].strip())

replacements = [
    ('formatNumber(profile.followers_count) + " seguidores"', 'formatNumber(profile.followers_count) + " ligações"'),
    ('"perfil Instagram"', '"perfil LinkedIn"'),
    ("abrir no Instagram ↗", "abrir no LinkedIn ↗"),
    ('data.plataforma_label || "Instagram"', 'data.plataforma_label || "LinkedIn"'),
    ('{ label: "Seguidores",', '{ label: "Ligações",'),
    ('{ label: "Posts", value: formatNumber(profile.posts_count),', '{ label: "Publicações", value: formatNumber(profile.posts_count || (profile.recent_posts || []).length),'),
    ('{ label: "Reels (avg plays)", value: reelsStats.avg_play_count !== undefined ? formatNumber(reelsStats.avg_play_count) : "—", sub: reelsStats.count ? `${reelsStats.count} reels analisados` : "" },', '{ label: "Engagement", value: profile.engagement_rate !== null && profile.engagement_rate !== undefined ? formatPct(profile.engagement_rate) : "—", sub: "posts recentes" },'),
    ("Top Reels <span class=\"pill violet\">plays</span>", "Destaques <span class=\"pill violet\">posts</span>"),
    ('renderTopCards(enrichment.top_reels, "top reels")', 'renderTopCards(enrichment.top_posts, "publicações")'),
    ("Cadência &amp; Reels", "Cadência de publicação"),
    ("enrichment.posting_cadence || {}, enrichment.reels_playcount_stats || {}", "enrichment.posting_cadence || {}, {}"),
    ("Top Posts <span class=\"pill cool\">likes</span>", "Top posts <span class=\"pill cool\">reações</span>"),
    ('LinkedIn — pode demorar alguns segundos', 'LinkedIn (Apify + OpenAI) — pode demorar'),
    ('sub: profile.following_count !== undefined ? `Segue ${formatNumber(profile.following_count)}` : "", accent: true }', 'sub: (profile.headline ? escapeHtml(String(profile.headline).slice(0, 50)) : ""), accent: true }'),
]

for old, new in replacements:
    if old in h:
        h = h.replace(old, new)

# posts_count on linkedin map
if "posts_count" not in h:
    pass

header = '''"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.

O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.
"""

from __future__ import annotations

LINKEDIN_PERFIL_PAGE_HTML: str = '''
footer = "\n"
(ROOT / "agents" / "linkedin_perfil_page.py").write_text(
    header + json.dumps(h, ensure_ascii=False) + footer,
    encoding="utf-8",
)
print("ok", "Instagram" in h, h.count("linkedin"))
