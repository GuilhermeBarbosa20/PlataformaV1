# -*- coding: utf-8 -*-
"""UI: rótulos Seguidores/Ligações, mensagem de dado em falta, cadência com contexto."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD_LABELS_BLOCK = """              const LINKEDIN_METRIC_LABELS = {
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
                  return '<motion class="li-metrics-empty">Sem indicadores para este perfil.</div>';
                }
                const entries = Object.entries(obj).filter(([k]) => String(k).trim());
                if (!entries.length) {
                  return '<div class="li-metrics-empty">Sem indicadores para este perfil.</motion>';
                }
                return `
                  <motion class="li-metrics-grid">
                    ${entries.map(([k, v]) => {
                      const missing = isMetricValueMissing(v);
                      const display = missing ? "—" : String(v).trim();
                      const cls = missing ? "li-metric-card is-muted" : "li-metric-card";
                      return `
                        <div class="${cls}">
                          <div class="li-metric-value">${escapeHtml(display)}</div>
                          <motion class="li-metric-label">${escapeHtml(humanizeMetricKey(k))}</div>
                        </div>
                      `;
                    }).join("")}
                  </div>
                `;
              }"""

NEW_BLOCK = r"""              const METRIC_UNAVAILABLE_PUBLIC = "Dado não público no LinkedIn";

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

              function getLinkedinPageKind(ctx) {
                const data = ctx || linkedinAnalysisSnapshot || {};
                const kind = data.linkedin_page_kind;
                if (kind === "organization" || kind === "personal") return kind;
                const url = String(data.profile_url || "").toLowerCase();
                if (url.includes("/company/") || url.includes("/school/")) return "organization";
                return "personal";
              }

              function humanizeMetricKey(key, pageKind) {
                const k = String(key || "").trim();
                if (!k) return "";
                if (k === "ligacoes" && pageKind === "organization") return "Seguidores";
                if (LINKEDIN_METRIC_LABELS[k]) return LINKEDIN_METRIC_LABELS[k];
                return k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
              }

              function isMetricValueMissing(value) {
                const raw = String(value == null ? "" : value).trim();
                if (!raw) return true;
                const low = raw.toLowerCase();
                return (
                  low === "sem dados públicos disponíveis." ||
                  low === "sem dados públicos disponíveis" ||
                  low === "dado não público no linkedin" ||
                  low === "n/d" || low === "—" || low.includes("sem dados públicos") ||
                  low.includes("dado não público")
                );
              }

              function renderLinkedinMetricCards(obj, ctx) {
                const pageKind = getLinkedinPageKind(ctx);
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
                      const display = missing ? METRIC_UNAVAILABLE_PUBLIC : String(v).trim();
                      const cls = missing ? "li-metric-card is-muted is-unavailable" : "li-metric-card";
                      const title = missing ? "O LinkedIn não expõe este dado publicamente ou o scraper não o devolveu." : "";
                      return `
                        <div class="${cls}" title="${escapeHtml(title)}">
                          <div class="li-metric-value">${escapeHtml(display)}</motion>
                          <div class="li-metric-label">${escapeHtml(humanizeMetricKey(k, pageKind))}</div>
                        </div>
                      `;
                    }).join("")}
                  </div>
                `.replace(/<\/motion>/g, "</div>").replace(/<motion/g, "<motion").replace(/<motion class="li-metric-value">/g, '<div class="li-metric-value">');
              }"""

# Normalize broken motion tags in file - try flexible match
if OLD_LABELS_BLOCK not in h:
    # fallback: patch in pieces
    if "function getLinkedinPageKind" not in h:
        anchor = "const LINKEDIN_METRIC_LABELS = {"
        idx = h.find(anchor)
        if idx < 0:
            raise SystemExit("LINKEDIN_METRIC_LABELS not found")
        end = h.find("function renderLinkedinMetricCards", idx)
        end2 = h.find("}", h.find("`.replace", end) if end > 0 else end)
        # find closing of renderLinkedinMetricCards - after first `};` following entries.join
        marker = '                  </motion>\n                `;'
        if marker not in h:
            marker = "                  </motion>\n                `;"
        end_fn = h.find(marker, idx)
        if end_fn < 0:
            end_fn = h.find("              }\n\n              function", idx + 100)
        if end_fn < 0:
            raise SystemExit("renderLinkedinMetricCards end not found")
        end_fn = h.find("              }", end_fn) + len("              }")
        h = h[:idx] + NEW_BLOCK.split("              function renderLinkedinMetricCards")[0] + "              function renderLinkedinMetricCards" + NEW_BLOCK.split("              function renderLinkedinMetricCards", 1)[1]
else:
    h = h.replace(OLD_LABELS_BLOCK, NEW_BLOCK, 1)

# Fix motion typos in NEW_BLOCK application
h = h.replace('<motion class="li-metric-value">', '<motion class="li-metric-value">')
h = h.replace('</motion>\n                          <div class="li-metric-label">', '</div>\n                          <div class="li-metric-label">')
h = h.replace('<motion class="li-metrics-empty">', '<div class="li-metrics-empty">')
h = h.replace('<motion class="li-metrics-grid">', '<div class="li-metrics-grid">')

if "function getLinkedinPageKind" not in h:
    raise SystemExit("patch failed: getLinkedinPageKind missing")

h = h.replace(
    "${renderLinkedinMetricCards(data.metricas_linkedin || data.metricas_instagram)}",
    "${renderLinkedinMetricCards(data.metricas_linkedin || data.metricas_instagram, data)}",
)
h = h.replace(
    "${renderLinkedinMetricCards(data.metricas_universais)}",
    "${renderLinkedinMetricCards(data.metricas_universais, data)}",
)

# CSS for unavailable metrics
css_anchor = ".li-metric-card.is-muted .li-metric-value {"
if css_anchor in h and "is-unavailable" not in h:
    h = h.replace(
        css_anchor,
        ".li-metric-card.is-unavailable .li-metric-value {\n"
        "                font-size: 0.72rem;\n"
        "                line-height: 1.35;\n"
        "                font-weight: 500;\n"
        "                color: var(--muted);\n"
        "              }\n"
        "              .li-metric-card.is-muted .li-metric-value {",
        1,
    )

# Section description for organization pages
h = h.replace(
    "Resumo quantitativo do perfil e das publicações analisadas.",
    "Resumo quantitativo da página e das publicações analisadas. Campos sem dado público aparecem assinalados.",
)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "getLinkedinPageKind" in h, "METRIC_UNAVAILABLE_PUBLIC" in h)
