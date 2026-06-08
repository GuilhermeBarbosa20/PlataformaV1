"""Integração LinkedIn no chat do Diretor (B1: login + análise interna).

Reutiliza a análise de perfil existente e expõe um resumo compacto para o
Diretor definir estratégia com base em métricas reais — independentemente
dos objetivos que o utilizador definir (seguidores, leads, marca, etc.).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from agents.director_strategy import strategy_brief_for_execution
from agents.social_media import social_media_agent


def slim_linkedin_analysis_for_director(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Reduz a análise LinkedIn ao essencial para o estado do Diretor.

    Evita guardar no browser payloads enormes (HTML Apify, posts completos).
    Mantém métricas, insights e URL do perfil para alimentar a estratégia.

    Argumentos:
        analysis: Resposta completa de ``POST /agents/social-media/profile-analyze``.

    Retorno:
        Dicionário compacto com perfil, métricas e listas curtas de insights.
    """

    if not isinstance(analysis, dict):
        return {}

    profile = analysis.get("public_profile_data")
    profile = profile if isinstance(profile, dict) else {}
    enrichment = profile.get("apify_enrichment")
    enrichment = enrichment if isinstance(enrichment, dict) else {}

    metricas_li = analysis.get("metricas_linkedin") or analysis.get("metricas_instagram") or {}
    metricas_uni = analysis.get("metricas_universais") or {}

    return {
        "profile_url": analysis.get("profile_url") or profile.get("profile_url"),
        "linkedin_own_profile": bool(analysis.get("linkedin_own_profile")),
        "linkedin_page_kind": analysis.get("linkedin_page_kind"),
        "metricas_linkedin": metricas_li if isinstance(metricas_li, dict) else {},
        "metricas_universais": metricas_uni if isinstance(metricas_uni, dict) else {},
        "principais_insights": _short_list(analysis.get("principais_insights"), 6),
        "problemas_identificados": _short_list(analysis.get("problemas_identificados"), 5),
        "oportunidades": _short_list(analysis.get("oportunidades"), 6),
        "acoes_prioritarias": _short_list(analysis.get("acoes_prioritarias"), 5),
        "ideias_conteudo": _short_list(analysis.get("ideias_conteudo"), 8),
        "plano_crescimento_curto_prazo": _short_list(analysis.get("plano_crescimento_curto_prazo"), 6),
        "posting_cadence": enrichment.get("posting_cadence") if isinstance(enrichment.get("posting_cadence"), dict) else {},
        "content_type_distribution": enrichment.get("content_type_distribution")
        or enrichment.get("format_distribution")
        or {},
        "public_profile_data": _slim_public_profile_for_posts(profile),
    }


def _slim_public_profile_for_posts(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Compacta dados do perfil para geração de posts (sem posts brutos)."""

    if not profile:
        return {}
    enrichment = profile.get("apify_enrichment") if isinstance(profile.get("apify_enrichment"), dict) else {}
    slim_enrichment: Dict[str, Any] = {}
    for key in (
        "content_type_distribution",
        "format_distribution",
        "posting_cadence",
        "top_posts",
        "headline",
        "summary",
    ):
        if key in enrichment:
            slim_enrichment[key] = enrichment[key]
    return {
        "profile_url": profile.get("profile_url"),
        "headline": profile.get("headline") or enrichment.get("headline"),
        "summary": profile.get("summary") or enrichment.get("summary"),
        "apify_enrichment": slim_enrichment,
    }


def _short_list(raw: Any, limit: int) -> List[str]:
    """Normaliza listas de strings para tamanho máximo."""

    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for item in raw:
        text = str(item).strip()
        if text:
            out.append(text[:500])
        if len(out) >= limit:
            break
    return out


def profile_context_markdown(snapshot: Optional[Dict[str, Any]]) -> str:
    """Formata dados do perfil analisado para o LLM de estratégia.

    O Diretor usa estes dados como ponto de partida real (métricas actuais),
    mas deve inventar a estratégia para os objetivos que o utilizador pediu —
    não assumir metas fixas.

    Argumentos:
        snapshot: Análise compacta (``slim_linkedin_analysis_for_director``).

    Retorno:
        Texto markdown com métricas e insights; string vazia se não houver dados.
    """

    if not snapshot:
        return ""

    lines: List[str] = ["CONTEXTO DO PERFIL LINKEDIN ANALISADO (dados reais):"]
    url = snapshot.get("profile_url")
    if url:
        lines.append(f"- URL: {url}")

    metrics = snapshot.get("metricas_linkedin") or {}
    if isinstance(metrics, dict):
        for key, val in list(metrics.items())[:12]:
            if val is not None and str(val).strip():
                lines.append(f"- {key}: {val}")

    uni = snapshot.get("metricas_universais") or {}
    if isinstance(uni, dict):
        for key, val in list(uni.items())[:8]:
            if val is not None and str(val).strip():
                lines.append(f"- {key}: {val}")

    cadence = snapshot.get("posting_cadence") or {}
    if isinstance(cadence, dict) and cadence:
        lines.append(f"- Cadência actual: {cadence}")

    for label, field in (
        ("Insights", "principais_insights"),
        ("Problemas", "problemas_identificados"),
        ("Oportunidades", "oportunidades"),
    ):
        items = snapshot.get(field) or []
        if items:
            lines.append(f"- {label}: " + "; ".join(str(i) for i in items[:4]))

    lines.append(
        "Usa estes dados como baseline. Os objetivos SMART vêm do utilizador — "
        "não inventes metas que ele não pediu; cria a estratégia para atingir o que ele disse."
    )
    return "\n".join(lines).strip()


def format_profile_summary_for_ui(snapshot: Optional[Dict[str, Any]]) -> str:
    """Resumo curto do perfil para o painel inferior do Diretor.

    Argumentos:
        snapshot: Análise compacta do perfil.

    Retorno:
        Texto legível com URL e métricas principais.
    """

    if not snapshot:
        return ""

    parts: List[str] = []
    if snapshot.get("profile_url"):
        parts.append(f"Perfil: {snapshot['profile_url']}")

    metrics = snapshot.get("metricas_linkedin") or {}
    if isinstance(metrics, dict):
        for key in ("seguidores", "followers", "connections", "ligações", "ligacoes"):
            if metrics.get(key):
                parts.append(f"{key}: {metrics[key]}")
                break
        if not any(k in metrics for k in ("seguidores", "followers")):
            for key, val in list(metrics.items())[:4]:
                if val is not None and str(val).strip():
                    parts.append(f"{key}: {val}")

    insights = snapshot.get("principais_insights") or []
    if insights:
        parts.append(f"Insight: {insights[0][:120]}")

    return " · ".join(parts) if parts else "Perfil analisado."


def analysis_payload_for_posts(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Reconstrói payload de análise para o gerador de posts LinkedIn.

    Argumentos:
        snapshot: Estado ``linkedin_analysis`` guardado no workflow do Diretor.

    Retorno:
        Dicionário compatível com ``generate_linkedin_posts_from_analysis``.
    """

    if not isinstance(snapshot, dict):
        return {"linkedin_own_profile": True}
    return {
        "linkedin_own_profile": bool(snapshot.get("linkedin_own_profile", True)),
        "profile_url": snapshot.get("profile_url"),
        "principais_insights": snapshot.get("principais_insights") or [],
        "problemas_identificados": snapshot.get("problemas_identificados") or [],
        "oportunidades": snapshot.get("oportunidades") or [],
        "acoes_prioritarias": snapshot.get("acoes_prioritarias") or [],
        "ideias_conteudo": snapshot.get("ideias_conteudo") or [],
        "plano_crescimento_curto_prazo": snapshot.get("plano_crescimento_curto_prazo") or [],
        "metricas_linkedin": snapshot.get("metricas_linkedin") or {},
        "metricas_universais": snapshot.get("metricas_universais") or {},
        "public_profile_data": snapshot.get("public_profile_data") or {},
    }


def posts_count_from_strategy(strategy: Dict[str, Any]) -> int:
    """Calcula quantos posts gerar com base na cadência da estratégia.

    Argumentos:
        strategy: Estratégia aprovada.

    Retorno:
        Número de posts (1–7) para a semana.
    """

    cadence = strategy.get("cadence") if isinstance(strategy.get("cadence"), dict) else {}
    try:
        n = int(float(cadence.get("posts_per_week") or 0))
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        n = 5
    return max(1, min(7, n))


_PT_WEEKDAYS = {
    "segunda": 0,
    "segunda-feira": 0,
    "terca": 1,
    "terça": 1,
    "terca-feira": 1,
    "terça-feira": 1,
    "quarta": 2,
    "quarta-feira": 2,
    "quinta": 3,
    "quinta-feira": 3,
    "sexta": 4,
    "sexta-feira": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}


def _next_weekday_dates(count: int, preferred_days: Optional[List[str]] = None) -> List[date]:
    """Gera datas futuras para calendário editorial (a partir de amanhã)."""

    today = date.today()
    start = today + timedelta(days=1)
    if preferred_days:
        targets: List[int] = []
        for label in preferred_days:
            key = str(label).strip().lower()
            if key in _PT_WEEKDAYS:
                targets.append(_PT_WEEKDAYS[key])
        if targets:
            out: List[date] = []
            cursor = start
            while len(out) < count:
                if cursor.weekday() in targets:
                    out.append(cursor)
                cursor += timedelta(days=1)
                if (cursor - start).days > 60:
                    break
            if len(out) >= count:
                return out[:count]
    return [start + timedelta(days=i) for i in range(count)]


def build_weekly_calendar(
    posts: List[Dict[str, Any]],
    strategy: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Associa posts a dias da semana segundo a estratégia aprovada.

    Argumentos:
        posts: Lista de posts LinkedIn normalizados.
        strategy: Estratégia com cadência e pilares.

    Retorno:
        Entradas de calendário com data, post e estado ``draft``.
    """

    cadence = strategy.get("cadence") if isinstance(strategy.get("cadence"), dict) else {}
    preferred = cadence.get("best_days") if isinstance(cadence.get("best_days"), list) else []
    pillars = strategy.get("content_pillars") or []
    dates = _next_weekday_dates(len(posts), preferred)

    calendar: List[Dict[str, Any]] = []
    for idx, post in enumerate(posts):
        if not isinstance(post, dict):
            continue
        scheduled = dates[idx] if idx < len(dates) else dates[-1] + timedelta(days=idx)
        pillar = pillars[idx % len(pillars)] if pillars else {}
        calendar.append(
            {
                "post_id": str(post.get("id") or f"post-{idx}"),
                "scheduled_date": scheduled.isoformat(),
                "scheduled_label": scheduled.strftime("%a %d %b").replace("Mon", "Seg")
                .replace("Tue", "Ter")
                .replace("Wed", "Qua")
                .replace("Thu", "Qui")
                .replace("Fri", "Sex")
                .replace("Sat", "Sáb")
                .replace("Sun", "Dom"),
                "pillar_theme": str(pillar.get("theme") or "").strip() if isinstance(pillar, dict) else "",
                "status": "draft",
                "post": post,
            }
        )
    return calendar


def editor_post_from_linkedin(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Converte post LinkedIn para o editor de aprovação do Diretor.

    Argumentos:
        raw: Post normalizado do especialista LinkedIn.

    Retorno:
        Objecto ``post`` usado no fluxo copy → imagem.
    """

    return {
        "id": str(raw.get("id") or ""),
        "channel": "linkedin",
        "title": str(raw.get("title") or "Post LinkedIn"),
        "hook": str(raw.get("hook") or ""),
        "body": str(raw.get("body") or "(sem texto)"),
        "cta": str(raw.get("cta") or ""),
        "content_type": str(raw.get("content_type") or "texto"),
        "angle": str(raw.get("angle") or ""),
        "status": "draft",
    }


def generate_director_linkedin_posts(
    state: Dict[str, Any],
    language: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Gera posts da semana alinhados à estratégia e análise do perfil.

    Argumentos:
        state: Estado do workflow (estratégia + ``linkedin_analysis``).
        language: Idioma dos posts.

    Retorno:
        Tuplo ``(posts, calendar)``.

    Raises:
        RuntimeError: Sem análise de perfil ou OpenAI indisponível.
    """

    strategy = state.get("strategy") or {}
    snapshot = state.get("linkedin_analysis") or {}
    if not snapshot.get("profile_url"):
        raise RuntimeError(
            "Analisa o teu perfil LinkedIn no painel antes de gerar posts da semana."
        )
    if not social_media_agent.is_configured():
        raise RuntimeError("OPENAI_API_KEY em falta para gerar posts.")

    analysis = analysis_payload_for_posts(snapshot)
    profile_data = snapshot.get("public_profile_data") if isinstance(snapshot.get("public_profile_data"), dict) else {}
    count = posts_count_from_strategy(strategy)
    strategy_brief = strategy_brief_for_execution(strategy)

    result = social_media_agent.generate_linkedin_posts_from_analysis(
        analysis,
        public_profile_data=profile_data,
        profile_url=str(snapshot.get("profile_url") or ""),
        count=count,
        language=language,
        strategy_brief=strategy_brief,
    )
    posts = result.get("posts") if isinstance(result, dict) else []
    if not isinstance(posts, list):
        posts = []
    calendar = build_weekly_calendar(posts, strategy)
    return posts, calendar


def regenerate_director_linkedin_post(
    state: Dict[str, Any],
    post: Dict[str, Any],
    *,
    edit_instructions: Optional[str] = None,
    language: str = "pt-PT",
) -> Dict[str, Any]:
    """Regera um post do calendário com contexto de estratégia e análise.

    Argumentos:
        state: Estado do workflow do Diretor.
        post: Post actual a substituir.
        edit_instructions: Feedback do utilizador (opcional).
        language: Idioma do post.

    Retorno:
        Post normalizado actualizado.

    Raises:
        RuntimeError: Sem configuração OpenAI ou análise em falta.
    """

    snapshot = state.get("linkedin_analysis") or {}
    strategy = state.get("strategy") or {}
    analysis = analysis_payload_for_posts(snapshot)
    brief = strategy_brief_for_execution(strategy)
    if brief:
        analysis = dict(analysis)
        analysis["estrategia_aprovada"] = brief

    if not social_media_agent.is_configured():
        raise RuntimeError("OPENAI_API_KEY em falta.")

    result = social_media_agent.regenerate_linkedin_post(
        analysis,
        post,
        public_profile_data=snapshot.get("public_profile_data"),
        profile_url=snapshot.get("profile_url"),
        edit_instructions=edit_instructions,
        language=language,
    )
    item = result.get("post") if isinstance(result, dict) else {}
    return item if isinstance(item, dict) else post
