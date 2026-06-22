"""Digest diário do Diretor — análise de progresso e propostas do dia.

Corre automaticamente na primeira visita de cada dia (browser) ou via
``run_daily_digest`` quando o utilizador tem estratégia activa. Com análise
LinkedIn recente, reutiliza o relatório de optimização (Fase C).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from openai import OpenAI

from agents.director_post_performance import (
    build_post_performance_review,
    performance_review_for_llm,
    record_performance_snapshot,
    timing_insights_from_analysis,
)
from agents.director_prompts import analysis_context_snippet, director_voice_block
from agents.director_optimization import (
    calendar_execution_summary,
    generate_optimization_report,
    optimization_has_content,
)
from agents.director_strategy import (
    _parse_llm_json,
    strategy_brief_for_execution,
    strategy_has_core_content,
)


def today_utc_date() -> str:
    """Devolve a data actual em UTC no formato ``YYYY-MM-DD``.

    Retorno:
        String ISO de data para comparar execuções diárias.
    """

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def should_run_daily_digest(state: Dict[str, Any]) -> bool:
    """Indica se o digest diário deve correr nesta sessão.

    Argumentos:
        state: Estado do workflow do Diretor.

    Retorno:
        ``True`` quando há estratégia com conteúdo e ainda não houve digest hoje.
    """

    if not strategy_has_core_content(state.get("strategy") or {}):
        return False
    last = str(state.get("last_daily_digest_at") or "").strip()
    return last != today_utc_date()


def _build_light_digest_with_llm(
    client: OpenAI,
    model: str,
    state: Dict[str, Any],
    language: str,
) -> Dict[str, Any]:
    """Gera briefing leve quando não há re-análise LinkedIn disponível.

    Argumentos:
        client: Cliente OpenAI.
        model: Modelo LLM.
        state: Estado do workflow.
        language: Idioma da resposta.

    Retorno:
        Objecto ``daily_digest`` com headline, summary, priorities e focus_today.
    """

    strategy = state.get("strategy") or {}
    brief = strategy_brief_for_execution(strategy if isinstance(strategy, dict) else {})
    cal = calendar_execution_summary(state.get("linkedin_calendar"))
    queue = state.get("followed_posts_queue") or []
    pending_comments = sum(
        1
        for p in queue
        if isinstance(p, dict) and (p.get("status") or "pending") == "pending"
    )
    profiles = len(state.get("followed_profiles") or [])

    record_performance_snapshot(state)
    performance = build_post_performance_review(state)
    performance_block = performance_review_for_llm(performance)

    analysis_ctx = analysis_context_snippet(state.get("linkedin_analysis"))
    engagement_log = state.get("engagement_log") or []
    approved_comments = sum(
        1 for e in engagement_log if isinstance(e, dict) and e.get("status") == "approved"
    )
    system_prompt = (
        f"{director_voice_block(language)}\n"
        "É o briefing matinal do director de marketing. O utilizador quer saber "
        "O QUE FUNCIONOU ONTEM / NA ÚLTIMA ANÁLISE e O QUE FICOU AQUÉM — como um "
        "analista que reviu posts, formatos e métricas face aos objectivos SMART.\n"
        "Usa os dados de performance fornecidos; se faltarem dados por post, diz-o "
        "claramente mas infere padrões (formato, cadência, execução do calendário).\n"
        "JSON:\n"
        '{"headline":"título tipo «Ontem X funcionou; hoje foca em Y»",'
        '"summary":"2-4 frases directas sobre ontem/último período",'
        '"worked_well":["o que funcionou — específico"],'
        '"underperformed":["o que ficou aquém — específico"],'
        '"post_insights":[{"post_preview":"...","format":"...","verdict":"funcionou|fraco|neutro",'
        '"likely_reason":"hora/formato/texto/valor entregue"}],'
        '"format_insights":["carrossel vs texto etc."],'
        '"timing_insights":["cadência/horário se aplicável"],'
        '"priorities":["máx 5 accionáveis para hoje"],'
        '"focus_today":"uma acção concreta",'
        '"next_posts_adjustment":"como ajustar os próximos posts do calendário"}'
    )
    user_prompt = (
        f"Estratégia:\n{brief[:4000]}\n\n"
        f"Calendário: {cal.get('posts_ready', 0)}/{cal.get('posts_total', 0)} posts prontos "
        f"({cal.get('completion_pct', 0)}%). Publicados: "
        f"{(performance.get('calendar_review') or {}).get('published_count', 0)}.\n"
        f"Perfis seguidos: {profiles}. Fila comentários: {pending_comments}. "
        f"Comentários aprovados: {approved_comments}.\n\n"
        f"Dados de performance (posts, formatos, deltas):\n{performance_block}\n"
    )
    if analysis_ctx:
        user_prompt += f"\nContexto perfil:\n{analysis_ctx}\n"
    user_prompt += (
        "\nResponde como se estivesses a dizer ao cliente: «Ontem/analisámos o período recente "
        "e isto é o que funcionou vs o que não funcionou». Sê concreto."
    )
    response = client.chat.completions.create(
        model=model,
        temperature=0.42,
        max_tokens=2200,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    data = _parse_llm_json(raw) or {}
    return {
        "headline": str(data.get("headline") or "Análise de ontem").strip(),
        "summary": str(data.get("summary") or "").strip(),
        "worked_well": [
            str(w).strip() for w in (data.get("worked_well") or []) if str(w).strip()
        ][:5],
        "underperformed": [
            str(u).strip() for u in (data.get("underperformed") or []) if str(u).strip()
        ][:5],
        "post_insights": [
            p for p in (data.get("post_insights") or []) if isinstance(p, dict)
        ][:6],
        "format_insights": [
            str(f).strip() for f in (data.get("format_insights") or []) if str(f).strip()
        ][:5],
        "timing_insights": [
            str(t).strip() for t in (data.get("timing_insights") or []) if str(t).strip()
        ][:4],
        "priorities": [
            str(p).strip() for p in (data.get("priorities") or []) if str(p).strip()
        ][:5],
        "focus_today": str(data.get("focus_today") or "").strip(),
        "next_posts_adjustment": str(data.get("next_posts_adjustment") or "").strip(),
        "timing_analysis": performance.get("timing_analysis") or {},
        "timing_insights": timing_insights_from_analysis(performance.get("timing_analysis") or {})
        or [
            str(t).strip() for t in (data.get("timing_insights") or []) if str(t).strip()
        ][:5],
        "execution_summary": cal,
        "post_performance": performance,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "light",
    }


def run_daily_digest(
    client: OpenAI,
    model: str,
    state: Dict[str, Any],
    language: str,
) -> Dict[str, Any]:
    """Executa o digest diário e actualiza o estado do workflow.

    Com análise LinkedIn e baseline, gera relatório de optimização completo.
    Caso contrário, produz briefing leve a partir da estratégia e calendário.

    Argumentos:
        client: Cliente OpenAI autenticado.
        model: Modelo LLM.
        state: Estado mutável do Diretor.
        language: Idioma (ex.: ``pt-PT``).

    Retorno:
        ``reply``, ``orchestration_mode``, ``workflow_state``, ``deliverables``,
        ``pending_actions`` prontos para fundir em ``base_response``.
    """

    state["last_daily_digest_at"] = today_utc_date()
    record_performance_snapshot(state)
    performance = build_post_performance_review(state)
    has_analysis = isinstance(state.get("linkedin_analysis"), dict)

    if has_analysis and strategy_has_core_content(state.get("strategy") or {}):
        opt = generate_optimization_report(client, model, state, language)
        report = opt.get("report") if isinstance(opt.get("report"), dict) else {}
        if optimization_has_content(report):
            state["optimization_report"] = report
            worked = report.get("worked_well") or []
            under = report.get("underperformed") or []
            state["daily_digest"] = {
                "headline": str(report.get("headline") or "Análise de ontem").strip(),
                "summary": str(opt.get("reply") or report.get("yesterday_summary") or "").strip(),
                "worked_well": worked if isinstance(worked, list) else [],
                "underperformed": under if isinstance(under, list) else [],
                "post_insights": report.get("post_insights") or [],
                "format_insights": report.get("format_insights") or [],
                "timing_insights": report.get("timing_insights")
                or timing_insights_from_analysis(report.get("timing_analysis") or performance),
                "timing_analysis": report.get("timing_analysis") or performance.get("timing_analysis") or {},
                "priorities": [
                    str(r.get("action") or "").strip()
                    for r in (report.get("recommendations") or [])
                    if isinstance(r, dict) and r.get("action")
                ][:5],
                "focus_today": str((report.get("strategy_adjustments") or {}).get("summary") or "").strip(),
                "next_posts_adjustment": str(report.get("next_posts_adjustment") or "").strip(),
                "execution_summary": report.get("execution_summary") or {},
                "post_performance": report.get("post_performance") or performance,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": "optimization",
            }
            state["stage"] = "optimization_review"
            state["pending_actions"] = [
                "approve_optimization",
                "dismiss_optimization",
            ]
            headline = state["daily_digest"].get("headline") or "Análise de ontem"
            worked = state["daily_digest"].get("worked_well") or []
            worked_hint = ""
            if worked:
                worked_hint = f" Destaque: {worked[0]}."
            reply = (
                f"**Bom dia.** Revisei o que funcionou ontem/no período recente — {headline}.{worked_hint} "
                "Vê o detalhe por post e formato no painel; podes aplicar optimizações ou manter o plano."
            )
            return {
                "reply": reply,
                "orchestration_mode": "optimization_review",
                "workflow_state": state,
                "pending_actions": state["pending_actions"],
            }

    digest = _build_light_digest_with_llm(client, model, state, language)
    state["daily_digest"] = digest
    state["stage"] = "daily_digest_review"
    state["pending_actions"] = []
    priorities = digest.get("priorities") or []
    worked = digest.get("worked_well") or []
    under = digest.get("underperformed") or []
    prio_text = ""
    if priorities:
        prio_text = "\n\n**Prioridades hoje:**\n" + "\n".join(f"• {p}" for p in priorities[:3])
    worked_text = ""
    if worked:
        worked_text = "\n\n**O que funcionou:**\n" + "\n".join(f"• {w}" for w in worked[:3])
    under_text = ""
    if under:
        under_text = "\n\n**O que ficou aquém:**\n" + "\n".join(f"• {u}" for u in under[:2])
    focus = digest.get("focus_today")
    focus_text = f"\n\n**Foco de hoje:** {focus}" if focus else ""
    adjust = digest.get("next_posts_adjustment")
    adjust_text = f"\n\n**Próximos posts:** {adjust}" if adjust else ""
    reply = (
        f"**Bom dia.** {digest.get('summary') or 'Revê o painel para a análise de ontem.'}"
        f"{worked_text}{under_text}{prio_text}{focus_text}{adjust_text}"
    ).strip()
    return {
        "reply": reply,
        "orchestration_mode": "daily_digest_review",
        "workflow_state": state,
        "pending_actions": [],
    }
