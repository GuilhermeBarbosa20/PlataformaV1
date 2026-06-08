"""Integração LinkedIn no chat do Diretor (B1: login + análise interna).

Reutiliza a análise de perfil existente e expõe um resumo compacto para o
Diretor definir estratégia com base em métricas reais — independentemente
dos objetivos que o utilizador definir (seguidores, leads, marca, etc.).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


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
        "oportunidades": _short_list(analysis.get("oportunidades"), 5),
        "acoes_prioritarias": _short_list(analysis.get("acoes_prioritarias"), 5),
        "posting_cadence": enrichment.get("posting_cadence") if isinstance(enrichment.get("posting_cadence"), dict) else {},
        "content_type_distribution": enrichment.get("content_type_distribution")
        or enrichment.get("format_distribution")
        or {},
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
