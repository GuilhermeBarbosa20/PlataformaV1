# -*- coding: utf-8 -*-
"""UI: rótulos para todos os campos harvestapi/linkedin-profile-scraper."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.linkedin_harvest_profile import HARVEST_LINKEDIN_PROFILE_LABELS_PT

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

# Build JS object entries
post_metrics = {
    "taxa_engagement_publicacoes": "Taxa de engagement",
    "publicacoes_no_periodo": "Publicações no período",
    "cadencia_dias_entre_posts": "Intervalo entre posts",
    "ligacoes": "Ligações",
    "seguidores": "Seguidores",
    "publicacoes_analisadas": "Publicações analisadas",
    "reacoes_medias_por_publicacao": "Reações médias",
    "comentarios_medios_por_publicacao": "Comentários médios",
    "cadencia_publicacao": "Cadência de publicação",
    "tipo_conteudo_mais_eficaz": "Formato mais eficaz",
    "alcance_medio": "Alcance médio",
    "impressoes": "Impressões",
    "visualizacoes_perfil": "Visualizações do perfil",
}
all_labels = {**HARVEST_LINKEDIN_PROFILE_LABELS_PT, **post_metrics}

lines = ["              const LINKEDIN_METRIC_LABELS = {"]
for key, label in all_labels.items():
    safe_key = key.replace("-", "_")
    safe_label = label.replace("\\", "\\\\").replace('"', '\\"')
    lines.append(f'                {safe_key}: "{safe_label}",')
lines.append("              };")
NEW_LABELS = "\n".join(lines)

start = h.find("const LINKEDIN_METRIC_LABELS = {")
if start < 0:
    raise SystemExit("LINKEDIN_METRIC_LABELS not found")
end = h.find("};", start)
if end < 0:
    raise SystemExit("end of LINKEDIN_METRIC_LABELS not found")
end = h.find("\n", end) + 1
h = h[:start] + NEW_LABELS + "\n" + h[end:]

# humanizeMetricKey: harvest keys first
OLD_HUMANIZE = """              function humanizeMetricKey(key, pageKind) {
                const k = String(key || "").trim();
                if (!k) return "";
                if (k === "ligacoes" && pageKind === "organization") return "Seguidores";
                if (LINKEDIN_METRIC_LABELS[k]) return LINKEDIN_METRIC_LABELS[k];
                return k.replace(/_/g, " ").replace(/\\b\\w/g, (c) => c.toUpperCase());
              }"""

NEW_HUMANIZE = """              function humanizeMetricKey(key, pageKind) {
                const k = String(key || "").trim();
                if (!k) return "";
                if (k === "ligacoes" && pageKind === "organization") return "Seguidores";
                if (LINKEDIN_METRIC_LABELS[k]) return LINKEDIN_METRIC_LABELS[k];
                return k.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/_/g, " ").replace(/\\b\\w/g, (c) => c.toUpperCase());
              }"""

if OLD_HUMANIZE not in h:
    raise SystemExit("humanizeMetricKey block not found")
h = h.replace(OLD_HUMANIZE, NEW_HUMANIZE, 1)

# Overview: two groups - profile (harvest) vs posts
OLD_GROUPS = """                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Métricas específicas (LinkedIn)</h4>
                          ${renderLinkedinMetricCards(data.metricas_linkedin || data.metricas_instagram, data)}
                        </div>
                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Desempenho geral</h4>
                          ${renderLinkedinMetricCards(data.metricas_universais, data)}
                        </div>"""

NEW_GROUPS = """                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Perfil LinkedIn (Apify harvestapi)</h4>
                          ${renderLinkedinMetricCards(data.metricas_linkedin || data.metricas_instagram, data)}
                        </div>
                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Desempenho das publicações</h4>
                          ${renderLinkedinMetricCards(data.metricas_universais, data)}
                        </div>"""

if OLD_GROUPS not in h:
    raise SystemExit("metrics groups not found")
h = h.replace(OLD_GROUPS, NEW_GROUPS, 1)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "connectionsCount" in h, "Perfil LinkedIn (Apify harvestapi)" in h)
