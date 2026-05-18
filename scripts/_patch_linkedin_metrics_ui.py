# -*- coding: utf-8 -*-
"""Renomeia aba Evolução → Plano & Ações; métricas em cards profissionais."""

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

# --- CSS ---
CSS_INSERT = """
              /* LinkedIn metric cards (overview) */
              .li-metrics-section { margin-top: 4px; }
              .li-metrics-group { margin-top: 16px; }
              .li-metrics-group:first-of-type { margin-top: 8px; }
              .li-metrics-group-title {
                font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
                letter-spacing: 0.1em; color: var(--muted); margin: 0 0 10px;
              }
              .li-metrics-grid {
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
              .li-metric-card.is-muted .li-metric-value { color: var(--muted); font-weight: 600; }
              .li-metric-value {
                font-size: 1.28rem; font-weight: 800; color: var(--text);
                line-height: 1.2; letter-spacing: -0.02em;
              }
              .li-metric-label {
                font-size: 0.8rem; color: var(--muted-soft, var(--muted));
                margin-top: 8px; line-height: 1.35;
              }
              .li-metrics-empty {
                color: var(--muted); font-size: 0.88rem; padding: 12px 0;
              }
              .section-desc {
                color: var(--muted); font-size: 0.85rem; margin: -4px 0 0;
                line-height: 1.45;
              }
"""

if ".li-metrics-grid" not in h:
    h = h.replace(
        "              /* Metric pills */",
        CSS_INSERT + "\n              /* Metric pills */",
        1,
    )

# --- JS: labels + renderLinkedinMetricCards ---
NEW_METRICS_FN = r"""
              const LINKEDIN_METRIC_LABELS = {
                taxa_engagement_publicacoes: "Taxa de engagement",
                publicacoes_no_periodo: "Publicações no período",
                cadencia_dias_entre_posts: "Intervalo entre posts",
                ligacoes: "Ligações",
                seguidores: "Seguidores",
                publicacoes_analisadas: "Publicações analisadas",
                reacoes_medias_por_publicacao: "Reações médias",
                comentarios_medios_por_publicacao: "Comentários médios",
                cadencia_publicacao: "Cadência de publicação",
                tipo_conteudo_mais_eficaz: "Formato mais eficaz",
                alcance_medio: "Alcance médio",
                impressoes: "Impressões",
                visualizacoes_perfil: "Visualizações do perfil",
              };

              function humanizeMetricKey(key) {
                const k = String(key || "").trim();
                if (!k) return "";
                if (LINKEDIN_METRIC_LABELS[k]) return LINKEDIN_METRIC_LABELS[k];
                return k
                  .replace(/_/g, " ")
                  .replace(/\b\w/g, (c) => c.toUpperCase());
              }

              function isMetricValueMissing(value) {
                const raw = String(value == null ? "" : value).trim();
                if (!raw) return true;
                const low = raw.toLowerCase();
                return (
                  low === "sem dados públicos disponíveis." ||
                  low === "sem dados públicos disponíveis" ||
                  low === "n/d" ||
                  low === "—" ||
                  low.includes("sem dados públicos")
                );
              }

              function renderLinkedinMetricCards(obj) {
                if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
                  return '<motion class="li-metrics-empty">Sem indicadores para este perfil.</div>';
                }
                const entries = Object.entries(obj).filter(([k]) => String(k).trim());
                if (!entries.length) {
                  return '<div class="li-metrics-empty">Sem indicadores para este perfil.</div>';
                }
                return `
                  <div class="li-metrics-grid">
                    ${entries.map(([k, v]) => {
                      const missing = isMetricValueMissing(v);
                      const display = missing ? "—" : String(v).trim();
                      const cls = missing ? "li-metric-card is-muted" : "li-metric-card";
                      return `
                        <div class="${cls}">
                          <motion class="li-metric-value">${escapeHtml(display)}</motion>
                          <div class="li-metric-label">${escapeHtml(humanizeMetricKey(k))}</div>
                        </div>
                      `;
                    }).join("")}
                  </div>
                `.replace(/<motion class="li-metric-value">/g, '<div class="li-metric-value">')
                  .replace(/<\/motion>\s*<div class="li-metric-label">/g, '</motion><div class="li-metric-label">')
                  .replace("</motion><motion", "</div><div")
                  .replace('<motion class="li-metrics-empty">', '<div class="li-metrics-empty">')
                  .replace("</motion>", "</div>", 1);
              }

""".replace("<motion", "<div").replace("</motion>", "</motion>")

# Fix the NEW_METRICS_FN - I made errors with replace. Let me use clean version:
NEW_METRICS_FN = """
              const LINKEDIN_METRIC_LABELS = {
                taxa_engagement_publicacoes: "Taxa de engagement",
                publicacoes_no_periodo: "Publicações no período",
                cadencia_dias_entre_posts: "Intervalo entre posts",
                ligacoes: "Ligações",
                seguidores: "Seguidores",
                publicacoes_analisadas: "Publicações analisadas",
                reacoes_medias_por_publicacao: "Reações médias",
                comentarios_medios_por_publicacao: "Comentários médios",
                cadencia_publicacao: "Cadência de publicação",
                tipo_conteudo_mais_eficaz: "Formato mais eficaz",
                alcance_medio: "Alcance médio",
                impressoes: "Impressões",
                visualizacoes_perfil: "Visualizações do perfil",
              };

              function humanizeMetricKey(key) {
                const k = String(key || "").trim();
                if (!k) return "";
                if (LINKEDIN_METRIC_LABELS[k]) return LINKEDIN_METRIC_LABELS[k];
                return k.replace(/_/g, " ").replace(/\\b\\w/g, (c) => c.toUpperCase());
              }

              function isMetricValueMissing(value) {
                const raw = String(value == null ? "" : value).trim();
                if (!raw) return true;
                const low = raw.toLowerCase();
                return (
                  low === "sem dados públicos disponíveis." ||
                  low === "sem dados públicos disponíveis" ||
                  low === "n/d" || low === "—" || low.includes("sem dados públicos")
                );
              }

              function renderLinkedinMetricCards(obj) {
                if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
                  return '<div class="li-metrics-empty">Sem indicadores para este perfil.</motion>';
                }
                const entries = Object.entries(obj).filter(([k]) => String(k).trim());
                if (!entries.length) {
                  return '<div class="li-metrics-empty">Sem indicadores para este perfil.</motion>';
                }
                return `
                  <div class="li-metrics-grid">
                    ${entries.map(([k, v]) => {
                      const missing = isMetricValueMissing(v);
                      const display = missing ? "—" : String(v).trim();
                      const cls = missing ? "li-metric-card is-muted" : "li-metric-card";
                      return `
                        <div class="${cls}">
                          <div class="li-metric-value">${escapeHtml(display)}</div>
                          <div class="li-metric-label">${escapeHtml(humanizeMetricKey(k))}</div>
                        </div>
                      `;
                    }).join("")}
                  </div>
                `;
              }

"""

NEW_METRICS_FN = NEW_METRICS_FN.replace("</motion>", "</div>")

if "function renderLinkedinMetricCards" not in h:
    h = h.replace(
        "              function renderMetricPills(obj) {",
        NEW_METRICS_FN + "              function renderMetricPills(obj) {",
        1,
    )

# --- Tab rename ---
h = h.replace(
    'data-target="evolution">Evolução</div>',
    'data-target="evolution">Plano &amp; Ações</div>',
)
h = h.replace(
    "data-target=\"evolution\">Evolução</div>",
    "data-target=\"evolution\">Plano &amp; Ações</div>",
)

# --- Overview metrics sections ---
OLD_METRICS_SECTIONS = """                      <div class="section">
                        <h3>Performance (LinkedIn) <span class="pill cool">métricas</span></h3>
                        ${renderMetricPills(data.metricas_universais)}
                      </div>
                      <div class="section">
                        <h3>Métricas específicas (${escapeHtml(data.plataforma_label || "LinkedIn")})</h3>
                        ${renderMetricPills(data.metricas_linkedin || data.metricas_instagram)}
                      </div>"""

NEW_METRICS_SECTIONS = """                      <div class="section li-metrics-section">
                        <h3>Indicadores de desempenho <span class="pill cool">LinkedIn</span></h3>
                        <p class="section-desc">Resumo quantitativo do perfil e das publicações analisadas.</p>
                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Desempenho geral</h4>
                          ${renderLinkedinMetricCards(data.metricas_universais)}
                        </div>
                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Atividade no perfil</h4>
                          ${renderLinkedinMetricCards(data.metricas_linkedin || data.metricas_instagram)}
                        </div>
                      </div>"""

if OLD_METRICS_SECTIONS in h:
    h = h.replace(OLD_METRICS_SECTIONS, NEW_METRICS_SECTIONS, 1)
else:
    h = h.replace(
        "${renderMetricPills(data.metricas_universais)}",
        """<motion class="li-metrics-group"><h4 class="li-metrics-group-title">Desempenho geral</h4>${renderLinkedinMetricCards(data.metricas_universais)}</div>""".replace("<motion", "<div"),
        1,
    )

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")

checks = {
    "tab": "Plano &amp; Ações" in h or "Plano & Ações" in h,
    "renderLinkedinMetricCards": "renderLinkedinMetricCards" in h,
    "css": ".li-metrics-grid" in h,
    "overview": "Indicadores de desempenho" in h,
    "no raw pills in overview": "renderMetricPills(data.metricas_universais)" not in h,
}
print("ok", checks)
