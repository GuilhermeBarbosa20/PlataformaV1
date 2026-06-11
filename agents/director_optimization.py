"""Ciclo análise → otimização do Diretor (Fase C).

Compara métricas actuais com a estratégia aprovada, mede progresso nos
objetivos SMART e propõe ajustes de pilares, cadência e táticas — tudo
visível no painel do Diretor, sem expor subagentes ao utilizador.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from openai import OpenAI

from agents.director_linkedin import profile_context_markdown
from agents.director_strategy import (
    _parse_llm_json,
    normalize_strategy,
    strategy_brief_for_execution,
)

_METRIC_ALIASES: Dict[str, tuple[str, ...]] = {
    "seguidores": ("seguidores", "followers", "ligacoes", "ligações", "connections"),
    "ssi": ("ssi", "social selling index", "social_selling"),
    "engagement": (
        "engagement",
        "taxa_engagement",
        "taxa_engagement_publicacoes",
        "taxa de engagement",
    ),
    "publicacoes": (
        "publicacoes",
        "publicações",
        "publicacoes_analisadas",
        "publicacoes_no_periodo",
        "posts",
    ),
    "reacoes": ("reacoes", "reações", "reacoes_medias_por_publicacao"),
    "comentarios": ("comentarios", "comentários", "comentarios_medios_por_publicacao"),
    "impressoes": ("impressoes", "impressões", "impressions", "alcance"),
    "leads": ("leads", "lead"),
}


def parse_metric_number(value: Any) -> Optional[float]:
    """Converte valores de métrica (texto ou número) num float comparável.

    Aceita formatos comuns em análises LinkedIn: ``4300``, ``4 300``,
    ``4.3k``, ``70``, ``12,5%``.

    Argumentos:
        value: Valor bruto da métrica (string, int ou float).

    Retorno:
        Número normalizado ou ``None`` se não for interpretável.
    """

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    if not text or "sem dados" in text or text in {"n/d", "n/a", "-"}:
        return None
    text = text.replace("\u00a0", " ").replace(" ", "")
    text = text.replace(",", ".")
    multiplier = 1.0
    if text.endswith("k"):
        multiplier = 1000.0
        text = text[:-1]
    elif text.endswith("m"):
        multiplier = 1_000_000.0
        text = text[:-1]
    if text.endswith("%"):
        text = text[:-1]
    match = re.search(r"[\d.]+", text)
    if not match:
        return None
    try:
        return float(match.group()) * multiplier
    except ValueError:
        return None


def metrics_snapshot_from_analysis(analysis: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Extrai métricas legíveis a partir da análise compacta do Diretor.

    Argumentos:
        analysis: Snapshot ``linkedin_analysis`` (slim).

    Retorno:
        Mapa chave normalizada → valor em texto para comparação e UI.
    """

    if not isinstance(analysis, dict):
        return {}

    out: Dict[str, str] = {}
    for block_key in ("metricas_linkedin", "metricas_universais"):
        block = analysis.get(block_key)
        if not isinstance(block, dict):
            continue
        for key, val in block.items():
            text = str(val).strip()
            if text:
                out[str(key).strip().lower()] = text

    profile = analysis.get("public_profile_data")
    if isinstance(profile, dict):
        enrichment = profile.get("apify_enrichment")
        if isinstance(enrichment, dict):
            cadence = enrichment.get("posting_cadence")
            if isinstance(cadence, dict) and cadence.get("avg_days_between_posts") is not None:
                out["cadencia_dias_entre_posts"] = f"{cadence.get('avg_days_between_posts')} dias"

    return out


def _find_metric_in_snapshot(snapshot: Dict[str, str], *needles: str) -> Optional[str]:
    """Procura valor de métrica por chave ou alias parcial."""

    if not snapshot:
        return None
    lowered_needles = [n.casefold() for n in needles]
    for key, val in snapshot.items():
        key_l = key.casefold()
        if any(n in key_l or key_l in n for n in lowered_needles):
            return val
    for canonical, aliases in _METRIC_ALIASES.items():
        if any(n in aliases or canonical in n for n in lowered_needles):
            for alias in aliases:
                for key, val in snapshot.items():
                    if alias in key.casefold():
                        return val
    return None


def compare_analysis_snapshots(
    baseline: Optional[Dict[str, Any]],
    current: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Calcula deltas entre duas análises LinkedIn.

    Argumentos:
        baseline: Análise anterior (antes da re-análise).
        current: Análise actual.

    Retorno:
        Lista de entradas ``{metric, before, after, change, direction}``.
    """

    before = metrics_snapshot_from_analysis(baseline)
    after = metrics_snapshot_from_analysis(current)
    keys = sorted(set(before.keys()) | set(after.keys()))
    deltas: List[Dict[str, Any]] = []
    for key in keys:
        b_raw = before.get(key)
        a_raw = after.get(key)
        if b_raw == a_raw:
            continue
        b_num = parse_metric_number(b_raw)
        a_num = parse_metric_number(a_raw)
        direction = "stable"
        change: Any = None
        if b_num is not None and a_num is not None:
            change = round(a_num - b_num, 2)
            if change > 0:
                direction = "up"
            elif change < 0:
                direction = "down"
        deltas.append(
            {
                "metric": key.replace("_", " "),
                "before": b_raw or "—",
                "after": a_raw or "—",
                "change": change if change is not None else f"{b_raw or '—'} → {a_raw or '—'}",
                "direction": direction,
            }
        )
    return deltas[:12]


def calendar_execution_summary(calendar: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Resume execução editorial da semana no calendário do Diretor.

    Argumentos:
        calendar: Lista de entradas do calendário LinkedIn.

    Retorno:
        Contagens de posts prontos, rascunho e percentagem de conclusão.
    """

    entries = calendar if isinstance(calendar, list) else []
    total = len(entries)
    ready = sum(1 for e in entries if isinstance(e, dict) and e.get("status") == "ready")
    draft = total - ready
    pct = round((ready / total) * 100) if total else 0
    return {
        "posts_total": total,
        "posts_ready": ready,
        "posts_draft": draft,
        "completion_pct": pct,
    }


def _objective_status(
    current_num: Optional[float],
    target_num: Optional[float],
    baseline_num: Optional[float],
) -> str:
    """Classifica progresso de um objetivo SMART."""

    if target_num is None or current_num is None:
        return "insufficient_data"
    if baseline_num is not None and target_num != baseline_num:
        span = target_num - baseline_num
        if span == 0:
            return "on_track" if current_num >= target_num else "behind"
        progress = (current_num - baseline_num) / span
        if progress >= 1.0:
            return "ahead"
        if progress >= 0.45:
            return "on_track"
        if progress >= 0.15:
            return "behind"
        return "critical"
    if current_num >= target_num:
        return "ahead"
    return "behind"


def build_objective_progress(
    strategy: Dict[str, Any],
    baseline_analysis: Optional[Dict[str, Any]],
    current_analysis: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Avalia cada objetivo SMART face às métricas disponíveis.

    Argumentos:
        strategy: Estratégia aprovada com ``smart_objectives``.
        baseline_analysis: Análise no momento da aprovação (opcional).
        current_analysis: Análise mais recente.

    Retorno:
        Lista com progresso por objetivo para o painel de otimização.
    """

    objectives = strategy.get("smart_objectives") if isinstance(strategy, dict) else []
    if not isinstance(objectives, list):
        return []

    before_snap = metrics_snapshot_from_analysis(baseline_analysis)
    after_snap = metrics_snapshot_from_analysis(current_analysis)
    rows: List[Dict[str, Any]] = []

    for obj in objectives:
        if not isinstance(obj, dict):
            continue
        metric = str(obj.get("metric") or "").strip()
        if not metric:
            continue
        metric_key = metric.casefold()
        before_val = _find_metric_in_snapshot(before_snap, metric_key) or obj.get("current_value")
        after_val = _find_metric_in_snapshot(after_snap, metric_key) or obj.get("current_value")
        target_val = obj.get("target_value")
        before_num = parse_metric_number(before_val)
        after_num = parse_metric_number(after_val)
        target_num = parse_metric_number(target_val)
        status = _objective_status(after_num, target_num, before_num)
        note = ""
        if after_num is not None and target_num is not None:
            gap = target_num - after_num
            if gap > 0:
                note = f"Faltam ~{gap:g} para a meta."
            else:
                note = "Meta atingida ou ultrapassada."
        rows.append(
            {
                "metric": metric,
                "baseline": before_val if before_val is not None else "—",
                "current": after_val if after_val is not None else "—",
                "target": target_val if target_val is not None else "—",
                "deadline": str(obj.get("deadline") or "").strip(),
                "status": status,
                "note": note,
            }
        )
    return rows


def optimization_has_content(report: Optional[Dict[str, Any]]) -> bool:
    """Indica se o relatório de otimização tem dados para mostrar no painel.

    Argumentos:
        report: Relatório gerado por ``generate_optimization_report``.

    Retorno:
        ``True`` quando há insights, recomendações ou progresso utilizável.
    """

    if not isinstance(report, dict):
        return False
    if report.get("headline") or report.get("insights") or report.get("recommendations"):
        return True
    return bool(report.get("objective_progress") or report.get("metric_deltas"))


def apply_optimization_to_strategy(
    strategy: Dict[str, Any],
    report: Dict[str, Any],
    *,
    current_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Funde ajustes aprovados do relatório na estratégia existente.

    Actualiza ``current_value`` dos objetivos SMART com métricas recentes
    quando possível e aplica pilares, cadência, mix e táticas sugeridos.

    Argumentos:
        strategy: Estratégia aprovada actual.
        report: Relatório de otimização com ``strategy_adjustments``.
        current_analysis: Análise LinkedIn mais recente (opcional).

    Retorno:
        Estratégia normalizada actualizada.
    """

    merged = normalize_strategy(strategy)
    adjustments = report.get("strategy_adjustments")
    if not isinstance(adjustments, dict):
        adjustments = {}

    if adjustments.get("summary"):
        extra = str(adjustments["summary"]).strip()
        base = str(merged.get("summary") or "").strip()
        if extra and extra not in base:
            merged["summary"] = f"{base}\n\n[Otimização] {extra}".strip() if base else extra

    pillars = adjustments.get("content_pillars")
    if isinstance(pillars, list) and pillars:
        merged["content_pillars"] = pillars

    cadence = adjustments.get("cadence")
    if isinstance(cadence, dict) and cadence:
        existing = merged.get("cadence") if isinstance(merged.get("cadence"), dict) else {}
        existing.update({k: v for k, v in cadence.items() if v is not None})
        merged["cadence"] = existing

    mix = adjustments.get("formats_mix")
    if isinstance(mix, dict) and mix:
        merged["formats_mix"] = mix

    tactics = adjustments.get("organic_tactics")
    if isinstance(tactics, list) and tactics:
        merged["organic_tactics"] = [str(t).strip() for t in tactics if str(t).strip()][:10]

    next_steps = adjustments.get("next_steps")
    if isinstance(next_steps, list) and next_steps:
        merged["next_steps"] = [str(s).strip() for s in next_steps if str(s).strip()][:8]

    if current_analysis:
        snap = metrics_snapshot_from_analysis(current_analysis)
        for obj in merged.get("smart_objectives") or []:
            if not isinstance(obj, dict):
                continue
            metric = str(obj.get("metric") or "").strip()
            if not metric:
                continue
            fresh = _find_metric_in_snapshot(snap, metric.casefold())
            if fresh is not None:
                obj["current_value"] = fresh

    return normalize_strategy(merged)


def generate_optimization_report(
    client: OpenAI,
    model: str,
    state: Dict[str, Any],
    language: str,
) -> Dict[str, Any]:
    """Gera relatório de progresso e recomendações de otimização LinkedIn.

    Cruza estratégia aprovada, análise anterior, análise actual e calendário
    editorial; o LLM propõe ajustes concretos mantendo os objetivos do user.

    Argumentos:
        client: Cliente OpenAI autenticado.
        model: Modelo de chat.
        state: Estado do workflow (estratégia, análises, calendário).
        language: Idioma da resposta (ex.: ``pt-PT``).

    Retorno:
        Relatório estruturado para o painel e para ``apply_optimization_to_strategy``.
    """

    strategy = state.get("strategy") if isinstance(state.get("strategy"), dict) else {}
    baseline = state.get("linkedin_analysis_baseline")
    current = state.get("linkedin_analysis")
    calendar = state.get("linkedin_calendar")

    objective_progress = build_objective_progress(strategy, baseline, current)
    metric_deltas = compare_analysis_snapshots(baseline, current)
    execution = calendar_execution_summary(calendar)

    profile_ctx = profile_context_markdown(current)
    strategy_brief = strategy_brief_for_execution(strategy)

    deterministic_block = json.dumps(
        {
            "objective_progress": objective_progress,
            "metric_deltas": metric_deltas,
            "execution_summary": execution,
        },
        ensure_ascii=False,
        indent=2,
    )

    system_prompt = (
        f"És o Diretor de Marketing AI — analista de performance LinkedIn orgânico. "
        f"Responde em {language}. "
        "Compara progresso real com a estratégia aprovada e propõe otimizações práticas "
        "(pilares, cadência, formatos, táticas) sem mudar os objetivos finais do utilizador "
        "a menos que os dados mostrem que são irrealistas — nesse caso explica no relatório. "
        "O campo reply deve ter NO MÁXIMO 3 frases para o chat; detalhes só no objecto report. "
        "Responde APENAS JSON válido:\n"
        '{"reply":"<mensagem curta ao utilizador>",'
        '"report":{'
        '"headline":"<título do relatório>",'
        '"overall_status":"on_track|behind|ahead|insufficient_data",'
        '"insights":["..."],'
        '"recommendations":[{"area":"","action":"","priority":"alta|media|baixa"}],'
        '"strategy_adjustments":{'
        '"summary":"<o que mudar e porquê>",'
        '"content_pillars":[{"theme":"","weekly_percentage":0,"description":"","example_angles":[]}],'
        '"cadence":{"posts_per_week":0,"best_days":[],"best_times":[]},'
        '"formats_mix":{"texto":0,"carrossel":0,"imagem":0,"video":0},'
        '"organic_tactics":["..."],'
        '"next_steps":["..."]'
        "}}}"
    )

    user_prompt = (
        f"Estratégia aprovada:\n{strategy_brief or json.dumps(strategy, ensure_ascii=False)}\n\n"
        f"Contexto perfil actual:\n{profile_ctx or 'n/d'}\n\n"
        f"Dados determinísticos já calculados (usa como base, não contradigas números):\n"
        f"{deterministic_block}\n\n"
        "Gera recomendações accionáveis para a próxima semana. "
        "Em strategy_adjustments inclui pilares/cadência/táticas concretos quando fizer sentido; "
        "se não houver dados suficientes, deixa listas vazias e overall_status=insufficient_data."
    )

    response = client.chat.completions.create(
        model=model,
        temperature=0.35,
        max_tokens=4096,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    data = _parse_llm_json(raw)
    if not data:
        return _fallback_optimization_report(
            objective_progress, metric_deltas, execution, language
        )

    report = data.get("report") if isinstance(data.get("report"), dict) else {}
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["objective_progress"] = objective_progress
    report["metric_deltas"] = metric_deltas
    report["execution_summary"] = execution
    if not report.get("headline"):
        report["headline"] = "Relatório de progresso e otimização"
    reply = str(data.get("reply") or "").strip()
    return {"report": report, "reply": reply}


def _fallback_optimization_report(
    objective_progress: List[Dict[str, Any]],
    metric_deltas: List[Dict[str, Any]],
    execution: Dict[str, Any],
    language: str,
) -> Dict[str, Any]:
    """Relatório mínimo quando o LLM falha."""

    _ = language
    status = "insufficient_data"
    if objective_progress:
        statuses = {r.get("status") for r in objective_progress}
        if "critical" in statuses or "behind" in statuses:
            status = "behind"
        elif "ahead" in statuses:
            status = "ahead"
        else:
            status = "on_track"

    return {
        "reply": "Comparei as métricas com a tua estratégia. Revê o relatório no painel.",
        "report": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "headline": "Progresso vs objetivos",
            "overall_status": status,
            "objective_progress": objective_progress,
            "metric_deltas": metric_deltas,
            "execution_summary": execution,
            "insights": [],
            "recommendations": [],
            "strategy_adjustments": {},
        },
    }


def optimization_status_label_pt(status: str) -> str:
    """Traduz código de estado de progresso para português.

    Argumentos:
        status: Código interno (``on_track``, ``behind``, etc.).

    Retorno:
        Etiqueta legível para a UI.
    """

    labels = {
        "on_track": "No caminho",
        "behind": "Atrasado",
        "ahead": "À frente",
        "critical": "Crítico",
        "insufficient_data": "Dados insuficientes",
    }
    return labels.get(str(status).strip().lower(), status)
