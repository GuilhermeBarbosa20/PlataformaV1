"""Análise de performance de publicações LinkedIn para o Diretor.

Combina dados Apify (top posts, formatos, cadência), calendário editorial
e histórico diário para alimentar o briefing «ontem funcionou X» e o relatório
de optimização com revisão por post/formato/horário.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

# Fuso horário para apresentar horas/dias ao utilizador (pt-PT).
_DISPLAY_TZ = ZoneInfo("Europe/Lisbon")

_WEEKDAY_PT = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


def _apify_enrichment(analysis: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extrai o bloco ``apify_enrichment`` da análise LinkedIn."""

    if not isinstance(analysis, dict):
        return {}
    profile = analysis.get("public_profile_data")
    if isinstance(profile, dict):
        enrichment = profile.get("apify_enrichment")
        if isinstance(enrichment, dict):
            return enrichment
    enrichment = analysis.get("apify_enrichment")
    return enrichment if isinstance(enrichment, dict) else {}


def _parse_metric_number(value: Any) -> Optional[float]:
    """Converte métrica textual em número (evita import circular)."""

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    import re

    text = str(value).strip().lower()
    if not text or "sem dados" in text or text in {"n/d", "n/a", "-"}:
        return None
    text = text.replace("\u00a0", " ").replace(" ", "").replace(",", ".")
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


def _metrics_snapshot_from_analysis(analysis: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Extrai métricas legíveis da análise LinkedIn."""

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
    return out


def _post_score(post: Dict[str, Any]) -> float:
    """Calcula score simples de engagement para ordenar publicações."""

    likes = _parse_metric_number(post.get("likes") or post.get("likesCount")) or 0.0
    comments = _parse_metric_number(post.get("comments") or post.get("commentsCount")) or 0.0
    reactions = _parse_metric_number(post.get("reactions_total")) or 0.0
    return reactions if reactions > 0 else likes + comments


def _format_label(fmt: Any) -> str:
    """Normaliza etiqueta de formato de publicação."""

    text = str(fmt or "texto").strip().lower()
    mapping = {
        "text": "texto",
        "article": "artigo",
        "document": "documento",
        "carousel": "carrossel",
        "image": "imagem",
        "video": "vídeo",
        "poll": "sondagem",
    }
    return mapping.get(text, text or "texto")


def _parse_post_timestamp(ts_raw: Any) -> Optional[datetime]:
    """Converte timestamp Apify/LinkedIn para ``datetime`` UTC.

    Argumentos:
        ts_raw: ISO-8601, Unix (s/ms) ou data simples.

    Retorno:
        ``datetime`` com timezone UTC, ou ``None``.
    """

    if ts_raw is None:
        return None
    if isinstance(ts_raw, datetime):
        return ts_raw if ts_raw.tzinfo else ts_raw.replace(tzinfo=timezone.utc)
    if isinstance(ts_raw, (int, float)):
        try:
            val = float(ts_raw)
            if val > 1e12:
                val /= 1000.0
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return None
    text = str(ts_raw).strip()
    if not text or text.lower() in {"null", "none", "n/a"}:
        return None
    if text.isdigit():
        try:
            val = float(text)
            if val > 1e12:
                val /= 1000.0
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            parsed = datetime.strptime(text[:19], fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _collect_scored_posts(analysis: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reúne publicações com score e timestamp para análise temporal.

    Argumentos:
        analysis: Snapshot ``linkedin_analysis``.

    Retorno:
        Lista de dicts com ``score``, ``timestamp``, ``format``, ``preview``.
    """

    if not isinstance(analysis, dict):
        return []

    enrichment = _apify_enrichment(analysis)
    pools: List[Dict[str, Any]] = []
    for key in ("top_posts", "top_posts_by_reactions"):
        block = enrichment.get(key)
        if isinstance(block, list):
            pools.extend(block)
    recent = analysis.get("recent_posts")
    if isinstance(recent, list):
        pools.extend(recent)

    seen: set[str] = set()
    rows: List[Dict[str, Any]] = []
    for item in pools:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("post_url") or "").strip()
        preview = str(item.get("caption_preview") or item.get("snippet") or "")[:40]
        dedupe = url or preview
        if dedupe in seen:
            continue
        seen.add(dedupe)
        ts = _parse_post_timestamp(
            item.get("timestamp") or item.get("posted_at") or item.get("postedAt")
        )
        if ts is None:
            continue
        rows.append(
            {
                "score": _post_score(item),
                "timestamp": ts,
                "format": _format_label(item.get("type") or item.get("content_type")),
                "preview": preview,
            }
        )
    return rows


def analyze_timing_performance(
    analysis: Optional[Dict[str, Any]],
    *,
    min_posts_per_bucket: int = 1,
) -> Dict[str, Any]:
    """Identifica dias da semana e horas com melhor engagement médio.

    Agrupa publicações históricas (Apify) por dia da semana e hora (fuso
    Europe/Lisbon) e calcula score médio de reacções+comentários por bucket.

    Argumentos:
        analysis: Snapshot ``linkedin_analysis`` com posts e timestamps.
        min_posts_per_bucket: Mínimo de posts num bucket para incluir no ranking.

    Retorno:
        ``best_weekdays``, ``best_hours``, ``timing_insights`` (frases prontas
        para UI), ``timezone`` e ``posts_with_time`` (contagem).
    """

    posts = _collect_scored_posts(analysis)
    if not posts:
        return {
            "best_weekdays": [],
            "best_hours": [],
            "best_day": None,
            "best_hour_range": None,
            "timing_insights": [],
            "timezone": "Europe/Lisbon",
            "posts_with_time": 0,
        }

    by_weekday: Dict[int, List[float]] = defaultdict(list)
    by_hour: Dict[int, List[float]] = defaultdict(list)

    for row in posts:
        local_dt = row["timestamp"].astimezone(_DISPLAY_TZ)
        by_weekday[local_dt.weekday()].append(row["score"])
        by_hour[local_dt.hour].append(row["score"])

    weekday_rows: List[Dict[str, Any]] = []
    for wd in range(7):
        scores = by_weekday.get(wd) or []
        if len(scores) < min_posts_per_bucket:
            continue
        avg = round(sum(scores) / len(scores), 1)
        weekday_rows.append(
            {
                "weekday_index": wd,
                "day": _WEEKDAY_PT[wd],
                "day_short": _WEEKDAY_PT[wd].split("-")[0],
                "post_count": len(scores),
                "avg_score": avg,
            }
        )
    weekday_rows.sort(key=lambda r: r["avg_score"], reverse=True)

    hour_rows: List[Dict[str, Any]] = []
    for hour in range(24):
        scores = by_hour.get(hour) or []
        if len(scores) < min_posts_per_bucket:
            continue
        avg = round(sum(scores) / len(scores), 1)
        hour_rows.append(
            {
                "hour": hour,
                "hour_label": f"{hour:02d}h00",
                "hour_range": f"{hour:02d}h00-{((hour + 1) % 24):02d}h00",
                "post_count": len(scores),
                "avg_score": avg,
            }
        )
    hour_rows.sort(key=lambda r: r["avg_score"], reverse=True)

    insights: List[str] = []
    if weekday_rows:
        top_days = weekday_rows[:3]
        days_txt = ", ".join(
            f"{d['day_short']} ({d['avg_score']} reacções médias, {d['post_count']} posts)"
            for d in top_days
        )
        insights.append(f"Melhores dias da semana: {days_txt}.")
    if hour_rows:
        top_hours = hour_rows[:3]
        hours_txt = ", ".join(
            f"{h['hour_label']} ({h['avg_score']} score médio, {h['post_count']} posts)"
            for h in top_hours
        )
        insights.append(f"Melhores horários (hora de Lisboa): {hours_txt}.")
    if weekday_rows and hour_rows:
        insights.append(
            f"Sugestão: publicar às {hour_rows[0]['hour_label']} às "
            f"{weekday_rows[0]['day_short']}s quando possível."
        )

    best_day = weekday_rows[0]["day"] if weekday_rows else None
    best_hour = hour_rows[0]["hour_label"] if hour_rows else None
    best_hour_range = hour_rows[0]["hour_range"] if hour_rows else None

    return {
        "best_weekdays": weekday_rows[:5],
        "best_hours": hour_rows[:6],
        "best_day": best_day,
        "best_hour_range": best_hour_range,
        "best_hour": best_hour,
        "timing_insights": insights,
        "timezone": "Europe/Lisbon",
        "posts_with_time": len(posts),
    }


def _weekday_label_for_post(item: Dict[str, Any]) -> str:
    """Etiqueta do dia da semana (Lisboa) para um post Apify."""

    ts = _parse_post_timestamp(
        item.get("timestamp") or item.get("posted_at") or item.get("postedAt")
    )
    if ts is None:
        return ""
    return _WEEKDAY_PT[ts.astimezone(_DISPLAY_TZ).weekday()]


def _hour_label_for_post(item: Dict[str, Any]) -> str:
    """Etiqueta da hora (Lisboa) para um post Apify."""

    ts = _parse_post_timestamp(
        item.get("timestamp") or item.get("posted_at") or item.get("postedAt")
    )
    if ts is None:
        return ""
    h = ts.astimezone(_DISPLAY_TZ).hour
    return f"{h:02d}h00"


def timing_insights_from_analysis(timing: Dict[str, Any]) -> List[str]:
    """Devolve frases de horário/dia prontas para painéis (fallback se LLM vazio).

    Argumentos:
        timing: Resultado de ``analyze_timing_performance``.

    Retorno:
        Lista de strings para ``timing_insights`` no digest/relatório.
    """

    if not isinstance(timing, dict):
        return []
    existing = timing.get("timing_insights")
    if isinstance(existing, list) and existing:
        return [str(x).strip() for x in existing if str(x).strip()]
    return []


def analyze_format_performance(analysis: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compara performance média por formato (texto, carrossel, imagem, etc.).

    Argumentos:
        analysis: Snapshot ``linkedin_analysis`` do workflow.

    Retorno:
        Lista ordenada por engagement médio com veredito ``strong|weak|neutral``.
    """

    enrichment = _apify_enrichment(analysis)
    dist = enrichment.get("content_type_distribution") or enrichment.get("format_distribution")
    if not isinstance(dist, dict) or not dist:
        return []

    rows: List[Dict[str, Any]] = []
    for fmt, data in dist.items():
        if not isinstance(data, dict):
            continue
        avg = _parse_metric_number(data.get("avg_engagement_pct"))
        share = _parse_metric_number(data.get("share_pct"))
        count = data.get("count")
        verdict = "neutral"
        if avg is not None:
            if avg >= 2.5:
                verdict = "strong"
            elif avg < 1.0:
                verdict = "weak"
        rows.append(
            {
                "format": _format_label(fmt),
                "count": count,
                "share_pct": share,
                "avg_engagement_pct": avg,
                "verdict": verdict,
            }
        )
    rows.sort(
        key=lambda r: (r.get("avg_engagement_pct") is not None, r.get("avg_engagement_pct") or 0),
        reverse=True,
    )
    return rows


def analyze_top_and_weak_posts(
    analysis: Optional[Dict[str, Any]],
    *,
    top_n: int = 3,
    weak_n: int = 2,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Separa publicações com melhor e pior engagement no histórico Apify.

    Argumentos:
        analysis: Snapshot ``linkedin_analysis``.
        top_n: Número de melhores posts a devolver.
        weak_n: Número de piores posts a devolver.

    Retorno:
        Tuplo ``(top_performers, underperformers)`` com metadados legíveis.
    """

    enrichment = _apify_enrichment(analysis)
    posts_raw = enrichment.get("top_posts") or enrichment.get("top_posts_by_reactions") or []
    if not isinstance(posts_raw, list):
        posts_raw = []

    scored: List[Tuple[Dict[str, Any], float]] = []
    for item in posts_raw:
        if not isinstance(item, dict):
            continue
        scored.append((item, _post_score(item)))

    # Se top_posts só tiver vencedores, incluir recent_posts para piores
    if isinstance(analysis, dict):
        recent = analysis.get("recent_posts")
        if isinstance(recent, list):
            for item in recent:
                if isinstance(item, dict):
                    scored.append((item, _post_score(item)))

    if not scored:
        return [], []

    seen_urls: set[str] = set()
    unique: List[Tuple[Dict[str, Any], float]] = []
    for item, score in scored:
        url = str(item.get("url") or item.get("post_url") or "").strip()
        key = url or str(item.get("caption_preview") or item.get("snippet") or "")[:40]
        if key in seen_urls:
            continue
        seen_urls.add(key)
        unique.append((item, score))

    unique.sort(key=lambda pair: pair[1], reverse=True)
    avg_score = sum(s for _, s in unique) / len(unique) if unique else 0.0

    def _normalize(item: Dict[str, Any], score: float, bucket: str) -> Dict[str, Any]:
        preview = str(
            item.get("caption_preview")
            or item.get("snippet")
            or item.get("text")
            or ""
        ).strip()[:160]
        return {
            "format": _format_label(item.get("type") or item.get("content_type")),
            "likes": item.get("likes") or item.get("likesCount"),
            "comments": item.get("comments") or item.get("commentsCount"),
            "reactions_total": score,
            "preview": preview or "(sem texto)",
            "url": str(item.get("url") or item.get("post_url") or "").strip(),
            "timestamp": str(item.get("timestamp") or item.get("posted_at") or "").strip(),
            "posted_weekday": _weekday_label_for_post(item),
            "posted_hour": _hour_label_for_post(item),
            "bucket": bucket,
        }

    tops = [_normalize(item, score, "top") for item, score in unique[:top_n]]
    if len(unique) <= top_n:
        return tops, []

    weak_candidates = unique[top_n:]
    weak_sorted = sorted(weak_candidates, key=lambda pair: pair[1])
    under = []
    for item, score in weak_sorted[:weak_n]:
        if score < avg_score * 0.6 or score <= 1:
            under.append(_normalize(item, score, "weak"))
    return tops, under


def analyze_calendar_posts(calendar: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Resume execução editorial e lista posts publicados no calendário.

    Argumentos:
        calendar: Lista ``linkedin_calendar`` do workflow.

    Retorno:
        Resumo com contagens e detalhes dos posts publicados/prontos.
    """

    entries = calendar if isinstance(calendar, list) else []
    published: List[Dict[str, Any]] = []
    ready: List[Dict[str, Any]] = []
    draft: List[Dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        row = {
            "id": str(entry.get("id") or ""),
            "title": str(entry.get("title") or entry.get("hook") or "Post").strip()[:80],
            "content_type": _format_label(entry.get("content_type")),
            "scheduled_date": str(entry.get("scheduled_date") or "").strip(),
            "status": str(entry.get("status") or "draft"),
            "with_image": bool(entry.get("generated_image_url")),
            "published_on_linkedin": bool(entry.get("published_on_linkedin")),
        }
        if row["published_on_linkedin"]:
            published.append(row)
        elif row["status"] == "ready":
            ready.append(row)
        else:
            draft.append(row)

    total = len(entries)
    ready_count = len(ready) + len(published)
    summary = {
        "posts_total": total,
        "posts_ready": ready_count,
        "posts_draft": len(draft),
        "completion_pct": round((ready_count / total) * 100) if total else 0,
    }
    summary["published_count"] = len(published)
    summary["published_posts"] = published[:7]
    summary["ready_posts"] = ready[:5]
    summary["draft_posts"] = draft[:5]
    return summary


def record_performance_snapshot(state: Dict[str, Any]) -> Dict[str, Any]:
    """Grava snapshot diário de métricas para comparar «ontem vs hoje».

    Argumentos:
        state: Estado mutável do workflow.

    Retorno:
        Snapshot gravado com data ISO e métricas principais.
    """

    analysis = state.get("linkedin_analysis")
    metrics = _metrics_snapshot_from_analysis(analysis if isinstance(analysis, dict) else None)
    cal = analyze_calendar_posts(state.get("linkedin_calendar"))
    snapshot = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "calendar": {
            "published_count": cal.get("published_count", 0),
            "posts_ready": cal.get("posts_ready", 0),
            "posts_total": cal.get("posts_total", 0),
        },
    }
    history = state.get("performance_history")
    if not isinstance(history, list):
        history = []
    today = snapshot["date"]
    history = [h for h in history if isinstance(h, dict) and h.get("date") != today]
    history.append(snapshot)
    state["performance_history"] = history[-14:]
    return snapshot


def compare_with_yesterday_snapshot(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compara métricas de hoje com o snapshot do dia anterior.

    Argumentos:
        state: Estado do workflow com ``performance_history``.

    Retorno:
        Lista de deltas legíveis para o briefing diário.
    """

    history = state.get("performance_history")
    if not isinstance(history, list) or len(history) < 2:
        return []

    today = history[-1] if isinstance(history[-1], dict) else {}
    yesterday = history[-2] if isinstance(history[-2], dict) else {}
    before = yesterday.get("metrics") if isinstance(yesterday.get("metrics"), dict) else {}
    after = today.get("metrics") if isinstance(today.get("metrics"), dict) else {}

    deltas: List[Dict[str, Any]] = []
    keys = sorted(set(before.keys()) | set(after.keys()))
    for key in keys:
        b_raw = before.get(key)
        a_raw = after.get(key)
        if b_raw == a_raw:
            continue
        b_num = _parse_metric_number(b_raw)
        a_num = _parse_metric_number(a_raw)
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
                "yesterday": b_raw or "—",
                "today": a_raw or "—",
                "change": change if change is not None else f"{b_raw or '—'} → {a_raw or '—'}",
                "direction": direction,
            }
        )
    return deltas[:8]


def build_post_performance_review(state: Dict[str, Any]) -> Dict[str, Any]:
    """Monta revisão completa de performance para digest e optimização.

    Cruza análise LinkedIn, calendário editorial e histórico diário para
    identificar o que funcionou, o que ficou aquém e hipóteses de causa
    (formato, cadência, execução).

    Argumentos:
        state: Estado completo do workflow do Diretor.

    Retorno:
        Dicionário com ``top_performers``, ``underperformers``, ``format_performance``,
        ``calendar_review``, ``daily_metric_deltas`` e ``cadence``.
    """

    from agents.director_optimization import compare_analysis_snapshots

    analysis = state.get("linkedin_analysis") if isinstance(state.get("linkedin_analysis"), dict) else None
    baseline = state.get("linkedin_analysis_baseline")
    enrichment = _apify_enrichment(analysis)

    top_posts, weak_posts = analyze_top_and_weak_posts(analysis)
    format_perf = analyze_format_performance(analysis)
    timing_perf = analyze_timing_performance(analysis)
    calendar_review = analyze_calendar_posts(state.get("linkedin_calendar"))

    cadence = enrichment.get("posting_cadence") if isinstance(enrichment.get("posting_cadence"), dict) else {}
    analysis_deltas = compare_analysis_snapshots(baseline, analysis)
    daily_deltas = compare_with_yesterday_snapshot(state)

    avg_eng = _parse_metric_number(enrichment.get("avg_engagement_pct"))
    posts_analyzed = enrichment.get("posts_analyzed")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "top_performers": top_posts,
        "underperformers": weak_posts,
        "format_performance": format_perf,
        "timing_analysis": timing_perf,
        "calendar_review": calendar_review,
        "analysis_metric_deltas": analysis_deltas[:8],
        "daily_metric_deltas": daily_deltas,
        "cadence": cadence,
        "avg_engagement_pct": avg_eng,
        "posts_analyzed": posts_analyzed,
        "data_quality": "alta" if top_posts and format_perf else ("media" if top_posts else "baixa"),
    }


def performance_review_for_llm(review: Dict[str, Any]) -> str:
    """Serializa a revisão de performance para injetar no prompt LLM.

    Argumentos:
        review: Resultado de ``build_post_performance_review``.

    Retorno:
        Texto JSON compacto para o modelo.
    """

    return json.dumps(review, ensure_ascii=False, indent=2)[:6000]
