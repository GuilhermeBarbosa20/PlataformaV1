# -*- coding: utf-8 -*-
"""UI: etiquetas harvest profile scraper + badge na Visão Geral."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD_LABELS = """              const LINKEDIN_METRIC_LABELS = {
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
              };"""

NEW_LABELS = """              const LINKEDIN_METRIC_LABELS = {
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
                nome_completo: "Nome",
                headline_profissional: "Headline",
                localizacao: "Localização",
                empresa_atual: "Empresa actual",
                experiencias_registadas: "Experiências",
                formacoes_registadas: "Formações",
                certificacoes: "Certificações",
                skills_destaque: "Skills em destaque",
                conta_premium: "Premium",
                aberto_a_oportunidades: "Open to work",
                perfil_verificado: "Verificado",
                membro_desde: "Membro desde",
                criador_linkedin: "Criador LinkedIn",
              };"""

OLD_OVERVIEW = """                      <div class="section li-metrics-section">
                        <h3>Indicadores de desempenho <span class="pill cool">LinkedIn</span></h3>
                        <p class="section-desc">Resumo quantitativo da página e das publicações analisadas. Campos sem dado público aparecem assinalados.</p>"""

NEW_OVERVIEW = """                      <div class="section li-metrics-section">
                        <h3>Indicadores de desempenho <span class="pill cool">LinkedIn</span></h3>
                        <p class="section-desc">Perfil via <strong>harvestapi/linkedin-profile-scraper</strong> (ligações, experiência, formação) e publicações via Apify. Campos sem dado público aparecem assinalados.</p>
                        ${(data.overview_data_source || (profile && profile.overview_source)) ? `<p class="section-desc" style="margin-top:6px"><span class="badge info"><span class="dot"></span> Visão geral: ${escapeHtml(String(data.overview_data_source || profile.overview_source || "harvestapi/linkedin-profile-scraper"))}</span></p>` : ""}"""

if OLD_LABELS not in h:
    raise SystemExit("LINKEDIN_METRIC_LABELS block not found")
h = h.replace(OLD_LABELS, NEW_LABELS, 1)

if OLD_OVERVIEW not in h:
    raise SystemExit("overview section not found")
h = h.replace(OLD_OVERVIEW, NEW_OVERVIEW, 1)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "nome_completo" in h, "harvestapi/linkedin-profile-scraper" in h)
