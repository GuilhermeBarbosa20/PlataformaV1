"""Prompts partilhados do Diretor — voz, qualidade e regras LinkedIn B2B."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def director_voice_block(language: str) -> str:
    """Bloco de voz do Diretor para injetar em system prompts.

    Argumentos:
        language: Idioma da resposta (ex.: ``pt-PT``).

    Retorno:
        Texto com regras de tom, clareza e estilo profissional.
    """

    return (
        f"És o Diretor de Marketing AI — marketeer sénior com 15+ anos em B2B. "
        f"Responde sempre em {language}. "
        "Tom: directo, confiante, sem jargão vazio nem frases de consultor genérico. "
        "Escreve como um parceiro experiente que já viu centenas de perfis LinkedIn: "
        "concreto, accionável, com números quando existem. "
        "Evita: «sinergias», «alavancar», «game-changer», elogios vazios, listas de buzzwords. "
        "Prefere: verbos fortes, causas e efeitos claros, exemplos específicos ao ICP."
    )


def linkedin_organic_excellence_block() -> str:
    """Regras de excelência para conteúdo e engagement LinkedIn orgânico.

    Retorno:
        Texto com boas práticas para estratégia, posts e comentários.
    """

    return (
        "Excelência LinkedIn orgânico B2B:\n"
        "- Cada recomendação deve ligar-se a um objectivo SMART do utilizador.\n"
        "- Pilares de conteúdo: percentagens realistas que somam 100; ângulos distintos.\n"
        "- Posts: hook na 1.ª linha, uma ideia central, CTA natural (pergunta ou convite).\n"
        "- Comentários em posts de terceiros: acrescentar insight, experiência breve ou pergunta "
        "que avance a conversa — nunca autopromoção nem «adorei o post».\n"
        "- Varia aberturas entre comentários (não repetir «Excelente reflexão» em todos).\n"
        "- Adapta registo ao mercado português/europeu quando o idioma for pt-PT."
    )


def engagement_comment_rules_block() -> str:
    """Regras específicas para rascunhos de comentários LinkedIn.

    Retorno:
        Texto com proibições e formato desejado.
    """

    return (
        "Regras para comentários:\n"
        "- 2–5 frases, máximo ~90 palavras; tom humano e profissional.\n"
        "- Referencia UM ponto concreto do texto da publicação (cita ou parafraseia).\n"
        "- Podes partilhar micro-experiência («na nossa equipa vimos…») sem vender.\n"
        "- Proibido: spam, pitch, hashtags em excesso, emojis em série, elogios vazios.\n"
        "- Fecha com pergunta genuína OU insight que convide resposta — não obrigatório em todos.\n"
        "- Cada comentário num lote deve ter abertura e ângulo diferentes."
    )


def analysis_context_snippet(
    analysis: Optional[Dict[str, Any]],
    *,
    max_chars: int = 1200,
) -> str:
    """Extrai contexto útil da análise LinkedIn para enriquecer prompts.

    Argumentos:
        analysis: Objecto ``linkedin_analysis`` do workflow.
        max_chars: Limite de caracteres do snippet.

    Retorno:
        Texto compacto com headline, insights e cadência; vazio se não houver dados.
    """

    if not isinstance(analysis, dict):
        return ""
    parts: List[str] = []
    profile = analysis.get("public_profile_data")
    if isinstance(profile, dict):
        headline = str(profile.get("headline") or "").strip()
        if headline:
            parts.append(f"Headline: {headline}")
    metrics = analysis.get("metricas_linkedin")
    if isinstance(metrics, dict):
        for key in ("seguidores", "followers", "conexoes", "connections", "ssi"):
            val = metrics.get(key)
            if val is not None:
                parts.append(f"{key}: {val}")
    insights = analysis.get("principais_insights")
    if isinstance(insights, list):
        for item in insights[:4]:
            s = str(item).strip()
            if s:
                parts.append(f"Insight: {s}")
    enrichment = {}
    if isinstance(profile, dict):
        enrichment = profile.get("apify_enrichment") or {}
    if isinstance(enrichment, dict):
        cadence = enrichment.get("posting_cadence")
        if isinstance(cadence, dict) and cadence:
            parts.append(f"Cadência actual: {cadence}")
    text = "\n".join(parts).strip()
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text


def engagement_history_snippet(
    state: Dict[str, Any],
    *,
    max_items: int = 3,
) -> str:
    """Resume comentários já aprovados para evitar repetição de tom.

    Argumentos:
        state: Estado do workflow do Diretor.
        max_items: Número máximo de exemplos anteriores.

    Retorno:
        Texto com inícios de comentários aprovados ou string vazia.
    """

    log = state.get("engagement_log")
    if not isinstance(log, list) or not log:
        return ""
    lines: List[str] = []
    for entry in reversed(log):
        if not isinstance(entry, dict):
            continue
        body = str(entry.get("comment_body") or "").strip()
        if not body:
            continue
        preview = body[:80] + ("…" if len(body) > 80 else "")
        lines.append(f"- «{preview}»")
        if len(lines) >= max_items:
            break
    if not lines:
        return ""
    return "Comentários já aprovados (evita repetir o mesmo estilo):\n" + "\n".join(lines)
