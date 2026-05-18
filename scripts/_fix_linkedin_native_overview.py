# -*- coding: utf-8 -*-
"""Visão geral e UI orientadas a LinkedIn."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

replacements = [
    (
        'const followers = profile.followers_count !== undefined && profile.followers_count !== null\n'
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
    ),
    (
        '<small>${escapeHtml(followers)}</small>',
        '<small>${escapeHtml(subLine)}</small>\n'
        '                        ${profileUrl ? `<small><a href="${escapeHtml(profileUrl)}" target="_blank" rel="noopener" style="color:var(--accent)">Ver perfil no LinkedIn ↗</a></small>` : ""}',
    ),
    (
        '<span class="badge ${qCls}"><span class="dot"></span> Qualidade dados: ${escapeHtml(quality)}</span>\n'
        '                    </motion>',
        '<span class="badge ${qCls}"><span class="dot"></span> Qualidade dados: ${escapeHtml(quality)}</span>\n'
        '                      ${methodBadge}\n'
        '                    </div>',
    ),
    (
        'function renderKpis(data) {\n'
        '                const profile = data.public_profile_data || {};\n'
        '                const enrichment = profile.apify_enrichment || {};\n'
        '                const cadence = enrichment.posting_cadence || {};\n'
        '                const reelsStats = enrichment.reels_playcount_stats || {};\n\n'
        '                const kpis = [\n'
        '                  { label: "Ligações", value: formatNumber(profile.followers_count), sub: (profile.headline ? escapeHtml(String(profile.headline).slice(0, 50)) : ""), accent: true },\n'
        '                  { label: "Publicações", value: formatNumber(profile.posts_count || (profile.recent_posts || []).length), sub: cadence.posts_last_30_days !== undefined ? `${cadence.posts_last_30_days} nos últimos 30d` : "" },\n'
        '                  { label: "Engagement", value: profile.engagement_rate !== null && profile.engagement_rate !== undefined ? formatPct(profile.engagement_rate) : "—", sub: "média recente" },\n'
        '                  { label: "Engagement", value: profile.engagement_rate !== null && profile.engagement_rate !== undefined ? formatPct(profile.engagement_rate) : "—", sub: "posts recentes" },\n'
        '                ];',
        'function renderKpis(data) {\n'
        '                const profile = data.public_profile_data || {};\n'
        '                const enrichment = profile.apify_enrichment || {};\n'
        '                const cadence = enrichment.posting_cadence || {};\n'
        '                const avgReact = enrichment.avg_reactions_per_post;\n'
        '                const avgComm = enrichment.avg_comments_per_post;\n'
        '                const engPct = enrichment.avg_engagement_pct ?? profile.engagement_rate;\n'
        '                const kpis = [\n'
        '                  { label: "Ligações", value: formatNumber(profile.followers_count), sub: profile.employer ? String(profile.employer).slice(0, 40) : "", accent: true },\n'
        '                  { label: "Publicações", value: formatNumber(profile.posts_count || enrichment.posts_analyzed || (profile.recent_posts || []).length), sub: cadence.posts_last_30_days !== undefined ? `${cadence.posts_last_30_days} nos últimos 30d` : "" },\n'
        '                  { label: "Reações médias", value: avgReact !== undefined ? formatNumber(avgReact) : "—", sub: "por publicação" },\n'
        '                  { label: "Comentários médios", value: avgComm !== undefined ? formatNumber(avgComm) : "—", sub: engPct !== null && engPct !== undefined ? `eng. ${formatPct(engPct)}` : "por publicação" },\n'
        '                ];',
    ),
    (
        'function renderFormatBars(distribution) {',
        'const LINKEDIN_FMT_LABELS = { texto: "Post texto", artigo: "Artigo", documento: "Documento/PDF", poll: "Sondagem", imagem: "Imagem", video: "Vídeo", evento: "Evento", partilha: "Partilha", desconhecido: "Outro" };\n'
        '              function linkedinFormatLabel(key) { return LINKEDIN_FMT_LABELS[key] || key; }\n\n'
        '              function renderFormatBars(distribution) {',
    ),
    (
        '<motion class="format-label">${escapeHtml(fmt)}</motion>',
        '<div class="format-label">${escapeHtml(linkedinFormatLabel(fmt))}</motion>',
    ),
    (
        '${er !== null && er !== undefined ? `<div class="format-er">engagement médio ${Number(er).toFixed(2)}%</motion>` : ""}',
        '${er !== null && er !== undefined ? `<motion class="format-er">interações médias ${Number(er).toFixed(1)}</motion>` : ""}',
    ),
    (
        '<span>likes ${formatNumber(item.likes)}</span>\n'
        '                            <span>com. ${formatNumber(item.comments)}</span>\n'
        '                            ${item.playCount !== null && item.playCount !== undefined ? `<span>plays ${formatNumber(item.playCount)}</span>` : ""}',
        '<span>reações ${formatNumber(item.likes ?? item.reactions_total)}</span>\n'
        '                            <span>com. ${formatNumber(item.comments ?? item.commentsCount)}</span>\n'
        '                            ${item.type ? `<span>${escapeHtml(linkedinFormatLabel(item.type))}</span>` : ""}',
    ),
    (
        '<div>Followers <span class="delta ${df.cls}">${arrow(df.cls)} ${df.text}</span></div>\n'
        '                            <motion>Engagement <span class="delta ${de.cls}">${arrow(de.cls)} ${de.text}</span></motion>\n'
        '                            <div>Posts <span class="delta ${dp.cls}">${arrow(dp.cls)} ${dp.text}</span></div>',
        '<div>Ligações <span class="delta ${df.cls}">${arrow(df.cls)} ${df.text}</span></div>\n'
        '                            <div>Engagement <span class="delta ${de.cls}">${arrow(de.cls)} ${de.text}</span></motion>\n'
        '                            <div>Publicações <span class="delta ${dp.cls}">${arrow(dp.cls)} ${dp.text}</span></div>',
    ),
    (
        'if (cadence.posts_last_30_days !== undefined) pills.push(["Posts (30d)", cadence.posts_last_30_days]);',
        'if (cadence.posts_last_30_days !== undefined) pills.push(["Publicações (30d)", cadence.posts_last_30_days]);',
    ),
    (
        'if (cadence.last_post_at) {\n'
        '                  const d = new Date(cadence.last_post_at);\n'
        '                  pills.push(["Último post", isNaN(d) ? cadence.last_post_at : d.toLocaleDateString("pt-PT")]);\n'
        '                }\n'
        '                if (reelsStats && reelsStats.count !== undefined) {\n'
        '                  pills.push(["Reels analisados", reelsStats.count]);\n'
        '                  pills.push(["Plays mediano", formatNumber(reelsStats.median_play_count)]);\n'
        '                  pills.push(["Plays máximo", formatNumber(reelsStats.max_play_count)]);\n'
        '                }',
        'if (cadence.last_post_at) {\n'
        '                  const d = new Date(cadence.last_post_at);\n'
        '                  pills.push(["Última publicação", isNaN(d) ? cadence.last_post_at : d.toLocaleDateString("pt-PT")]);\n'
        '                }\n'
        '                if (cadence.avg_days_between_posts !== undefined) {\n'
        '                  pills.push(["Cadência", `~${cadence.avg_days_between_posts} dias entre posts`]);\n'
        '                }',
    ),
    (
        '<div class="tab" data-target="content">Conteúdo</div>',
        '<div class="tab" data-target="content">Tipos de conteúdo</motion>',
    ),
    (
        '<h3>Métricas Universais</h3>\n'
        '                        ${renderMetricPills(data.metricas_universais)}',
        '<h3>Performance (LinkedIn) <span class="pill cool">métricas</span></h3>\n'
        '                        ${renderMetricPills(data.metricas_universais)}',
    ),
    (
        '${renderMetricPills(data.metricas_instagram)}',
        '${renderMetricPills(data.metricas_linkedin || data.metricas_instagram)}',
    ),
    (
        '<h3>Distribuição por Formato</h3>\n'
        '                        ${renderFormatBars(enrichment.format_distribution)}',
        '<h3>Tipos de conteúdo LinkedIn</h3>\n'
        '                        ${renderFormatBars(enrichment.content_type_distribution || enrichment.format_distribution)}',
    ),
    (
        '                      <div class="section">\n'
        '                        <h3>Destaques <span class="pill violet">posts</span></h3>\n'
        '                        ${renderTopCards(enrichment.top_posts, "publicações")}\n'
        '                      </div>\n'
        '                      <motion class="section">\n'
        '                        <h3>Cadência de publicação</h3>',
        '                      <div class="section">\n'
        '                        <h3>Cadência de publicação</h3>',
    ),
    (
        '                      <div class="section">\n'
        '                        <h3>Top Hashtags</h3>\n'
        '                        ${renderHashtags(enrichment.top_hashtags)}\n'
        '                      </div>',
        '',
    ),
    (
        '<h3>Ideias de Conteúdo <span class="pill violet">criativo</span></h3>',
        '<h3>Ideias por tipo de conteúdo <span class="pill violet">LinkedIn</span></h3>\n'
        '                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Formatos: post texto, artigo, documento/PDF, sondagem, vídeo nativo.</p>',
    ),
]

# Fix typos I introduced with motion -> should be div
for old, new in replacements:
    if old and old not in h:
        print("MISSING:", old[:80])
    elif old:
        h = h.replace(old, new)

h = h.replace("</motion>", "</motion>").replace("<motion", "<motion")  # noop cleanup
h = h.replace("linkedinFormatLabel(fmt))}</motion>", "linkedinFormatLabel(fmt))}</div>")
h = h.replace('class="format-er">interações médias', 'class="format-er">interações médias')
h = h.replace("Tipos de conteúdo</motion>", "Tipos de conteúdo</motion>")
h = h.replace('data-target="content">Tipos de conteúdo</motion>', 'data-target="content">Tipos de conteúdo</div>')
h = h.replace("Engagement <span", "Engagement <span").replace("</motion>\n                            <motion>Publicações", "</div>\n                            <motion>Publicações")
# fix compare row
h = h.replace(
    '<motion>Engagement <span class="delta ${de.cls}">${arrow(de.cls)} ${de.text}</span></motion>\n'
    '                            <motion>Publicações',
    '<div>Engagement <span class="delta ${de.cls}">${arrow(de.cls)} ${de.text}</span></div>\n'
    '                            <div>Publicações',
)

out = prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n"
PAGE.write_text(out, encoding="utf-8")
print("ok", "Reels analisados" in h, "Apify (posts" in h)
