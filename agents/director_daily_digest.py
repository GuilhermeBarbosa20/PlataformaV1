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

    system_prompt = (
        f"És o Diretor de Marketing AI. Responde em {language}. "
        "Gera um briefing matinal curto para o utilizador com base na estratégia "
        "e no progresso editorial. Tom: profissional, directo, sem jargão vazio. "
        "JSON: "
        '{"headline":"...","summary":"2-4 frases","priorities":["..."],"focus_today":"uma acção concreta"}'
    )
    user_prompt = (
        f"Estratégia:\n{brief[:4000]}\n\n"
        f"Calendário: {cal.get('posts_ready', 0)}/{cal.get('posts_total', 0)} posts prontos "
        f"({cal.get('completion_pct', 0)}%).\n"
        f"Perfis seguidos: {profiles}. Publicações na fila para comentar: {pending_comments}.\n"
        "O que deve o utilizador priorizar hoje?"
    )
    response = client.chat.completions.create(
        model=model,
        temperature=0.35,
        max_tokens=900,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    data = _parse_llm_json(raw) or {}
    return {
        "headline": str(data.get("headline") or "Briefing do dia").strip(),
        "summary": str(data.get("summary") or "").strip(),
        "priorities": [
            str(p).strip() for p in (data.get("priorities") or []) if str(p).strip()
        ][:5],
        "focus_today": str(data.get("focus_today") or "").strip(),
        "execution_summary": cal,
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
    has_analysis = isinstance(state.get("linkedin_analysis"), dict)

    if has_analysis and strategy_has_core_content(state.get("strategy") or {}):
        opt = generate_optimization_report(client, model, state, language)
        report = opt.get("report") if isinstance(opt.get("report"), dict) else {}
        if optimization_has_content(report):
            state["optimization_report"] = report
            state["daily_digest"] = {
                "headline": str(report.get("headline") or "Análise diária").strip(),
                "summary": str(opt.get("reply") or "").strip(),
                "priorities": [
                    str(r.get("action") or "").strip()
                    for r in (report.get("recommendations") or [])
                    if isinstance(r, dict) and r.get("action")
                ][:5],
                "focus_today": str((report.get("strategy_adjustments") or {}).get("summary") or "").strip(),
                "execution_summary": report.get("execution_summary") or {},
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": "optimization",
            }
            state["stage"] = "optimization_review"
            state["pending_actions"] = [
                "approve_optimization",
                "dismiss_optimization",
            ]
            headline = state["daily_digest"].get("headline") or "Análise diária"
            reply = (
                f"**Bom dia.** Analisei o progresso face à estratégia — {headline}. "
                "Revê o relatório no painel; podes aplicar optimizações ou manter o plano actual."
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
    prio_text = ""
    if priorities:
        prio_text = "\n\n**Prioridades:**\n" + "\n".join(f"• {p}" for p in priorities[:3])
    focus = digest.get("focus_today")
    focus_text = f"\n\n**Foco de hoje:** {focus}" if focus else ""
    reply = (
        f"**Bom dia.** {digest.get('summary') or 'Revê o painel para o plano do dia.'}"
        f"{prio_text}{focus_text}"
    ).strip()
    return {
        "reply": reply,
        "orchestration_mode": "daily_digest_review",
        "workflow_state": state,
        "pending_actions": [],
    }
