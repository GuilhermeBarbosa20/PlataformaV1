"""Definição de estratégia orgânica LinkedIn pelo Diretor de Marketing.

O utilizador fala apenas com o Diretor; este módulo gera e normaliza o plano
estratégico (objetivos SMART, ICP, pilares de conteúdo com percentagens, etc.)
antes de delegar copy e design aos subagentes.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence

from openai import OpenAI

STRATEGY_MARKERS = (
    "estrategia",
    "estratégia",
    "objetivo",
    "objetivos",
    "meta",
    "metas",
    "seguidores",
    "follower",
    "ssi",
    "ranking",
    "top 10",
    "top10",
    "icp",
    "publico alvo",
    "público alvo",
    "publico-alvo",
    "público-alvo",
    "audiencia",
    "audiência",
    "crescimento organico",
    "crescimento orgânico",
    "organico linkedin",
    "orgânico linkedin",
    "plano linkedin",
    "pilares",
    "temas de conteudo",
    "temas de conteúdo",
)

LINKEDIN_MARKERS = (
    "linkedin",
    "linked in",
)


def _normalize_for_match(text: str) -> str:
    """Compacta texto para comparação insensível a acentos básicos."""

    lowered = text.casefold()
    replacements = (
        ("á", "a"),
        ("à", "a"),
        ("â", "a"),
        ("ã", "a"),
        ("é", "e"),
        ("ê", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ô", "o"),
        ("õ", "o"),
        ("ú", "u"),
        ("ç", "c"),
    )
    for src, dst in replacements:
        lowered = lowered.replace(src, dst)
    return lowered


def is_linkedin_strategy_intent(text: str) -> bool:
    """Indica se o utilizador está a pedir definição de estratégia LinkedIn.

    Deteta combinações de menção a LinkedIn com objetivos, métricas ou
    planeamento estratégico (seguidores, SSI, ranking, ICP, pilares, etc.).

    Argumentos:
        text: Última mensagem do utilizador (ou brief agregado).

    Retorno:
        ``True`` quando o pedido deve entrar no fluxo de estratégia do Diretor
        em vez de redireccionar para o agente LinkedIn operacional.
    """

    normalized = _normalize_for_match(text.strip())
    if not normalized:
        return False

    has_linkedin = any(marker in normalized for marker in LINKEDIN_MARKERS)
    has_strategy = any(marker in normalized for marker in STRATEGY_MARKERS)

    # Padrões típicos sem dizer "LinkedIn" explicitamente
    has_follower_goal = bool(
        re.search(r"\b\d{3,6}\b", normalized)
        and ("seguidor" in normalized or "follower" in normalized)
    )
    has_smart_deadline = bool(
        re.search(r"\b(ate|até|final de|ate ao)\s+\w+", normalized)
        and has_strategy
    )

    if has_linkedin and (has_strategy or has_follower_goal):
        return True
    if has_follower_goal and has_smart_deadline:
        return True
    if "ssi" in normalized and (has_linkedin or has_strategy):
        return True
    if "ranking" in normalized and "top" in normalized:
        return True
    return False


def build_conversation_context(messages: Sequence[Dict[str, str]]) -> str:
    """Junta o histórico recente da chatroom num único contexto.

    Argumentos:
        messages: Lista de mensagens com ``role`` e ``content``.

    Retorno:
        Texto com os últimos turnos formatados para o modelo.
    """

    lines: List[str] = []
    for message in messages[-12:]:
        role = str(message.get("role", "")).strip()
        content = str(message.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        label = "Utilizador" if role == "user" else "Diretor"
        lines.append(f"{label}: {content}")
    return "\n".join(lines).strip()


def _default_strategy() -> Dict[str, Any]:
    """Devolve estrutura vazia normalizada de estratégia."""

    return {
        "platform": "linkedin",
        "summary": "",
        "icp": {
            "persona_label": "",
            "description": "",
            "pain_points": [],
            "desired_outcomes": [],
        },
        "smart_objectives": [],
        "content_pillars": [],
        "cadence": {
            "posts_per_week": 0,
            "best_days": [],
            "best_times": [],
        },
        "formats_mix": {},
        "scenarios": [],
        "weekly_kpis": {},
        "organic_tactics": [],
        "risks": [],
        "next_steps": [],
    }


def _normalize_pillar(raw: Any) -> Optional[Dict[str, Any]]:
    """Normaliza um pilar de conteúdo."""

    if not isinstance(raw, dict):
        return None
    theme = str(raw.get("theme") or raw.get("tema") or "").strip()
    if not theme:
        return None
    try:
        pct = int(float(raw.get("weekly_percentage") or raw.get("percentagem") or 0))
    except (TypeError, ValueError):
        pct = 0
    pct = max(0, min(100, pct))
    angles = raw.get("example_angles") or raw.get("angulos") or []
    if not isinstance(angles, list):
        angles = []
    return {
        "theme": theme,
        "weekly_percentage": pct,
        "description": str(raw.get("description") or raw.get("descricao") or "").strip(),
        "example_angles": [str(a).strip() for a in angles if str(a).strip()][:5],
    }


def _normalize_objective(raw: Any) -> Optional[Dict[str, Any]]:
    """Normaliza um objetivo SMART."""

    if not isinstance(raw, dict):
        return None
    metric = str(raw.get("metric") or raw.get("metrica") or "").strip()
    if not metric:
        return None
    return {
        "metric": metric,
        "current_value": raw.get("current_value") or raw.get("valor_atual"),
        "target_value": raw.get("target_value") or raw.get("valor_alvo"),
        "deadline": str(raw.get("deadline") or raw.get("prazo") or "").strip(),
        "specific": str(raw.get("specific") or raw.get("especifico") or "").strip(),
        "measurable": str(raw.get("measurable") or raw.get("mensuravel") or "").strip(),
        "achievable_rationale": str(
            raw.get("achievable_rationale") or raw.get("atingivel") or ""
        ).strip(),
    }


def normalize_strategy(raw: Any) -> Dict[str, Any]:
    """Valida e normaliza o JSON de estratégia devolvido pelo modelo.

    Argumentos:
        raw: Dicionário cru (ou ``None``) vindo do LLM.

    Retorno:
        Estratégia com campos obrigatórios preenchidos e listas saneadas.
    """

    base = _default_strategy()
    if not isinstance(raw, dict):
        return base

    base["platform"] = str(raw.get("platform") or "linkedin").strip() or "linkedin"
    base["summary"] = str(raw.get("summary") or raw.get("resumo") or "").strip()

    icp_raw = raw.get("icp") if isinstance(raw.get("icp"), dict) else {}
    base["icp"] = {
        "persona_label": str(
            icp_raw.get("persona_label") or icp_raw.get("persona") or ""
        ).strip(),
        "description": str(
            icp_raw.get("description") or icp_raw.get("descricao") or ""
        ).strip(),
        "pain_points": [
            str(p).strip()
            for p in (icp_raw.get("pain_points") or icp_raw.get("dores") or [])
            if str(p).strip()
        ][:8],
        "desired_outcomes": [
            str(o).strip()
            for o in (icp_raw.get("desired_outcomes") or icp_raw.get("ganhos") or [])
            if str(o).strip()
        ][:8],
    }

    objectives: List[Dict[str, Any]] = []
    for item in raw.get("smart_objectives") or raw.get("objetivos_smart") or []:
        normalized = _normalize_objective(item)
        if normalized:
            objectives.append(normalized)
    base["smart_objectives"] = objectives[:6]

    pillars: List[Dict[str, Any]] = []
    for item in raw.get("content_pillars") or raw.get("pilares_conteudo") or []:
        normalized = _normalize_pillar(item)
        if normalized:
            pillars.append(normalized)
    base["content_pillars"] = pillars[:8]

    cadence_raw = raw.get("cadence") if isinstance(raw.get("cadence"), dict) else {}
    try:
        posts_pw = int(float(cadence_raw.get("posts_per_week") or 0))
    except (TypeError, ValueError):
        posts_pw = 0
    days = cadence_raw.get("best_days") or cadence_raw.get("melhores_dias") or []
    times = cadence_raw.get("best_times") or cadence_raw.get("melhores_horas") or []
    base["cadence"] = {
        "posts_per_week": max(0, posts_pw),
        "best_days": [str(d).strip() for d in days if str(d).strip()][:7],
        "best_times": [str(t).strip() for t in times if str(t).strip()][:6],
    }

    formats_raw = raw.get("formats_mix") or raw.get("mix_formatos") or {}
    if isinstance(formats_raw, dict):
        mix: Dict[str, int] = {}
        for key, val in formats_raw.items():
            try:
                mix[str(key)] = max(0, min(100, int(float(val))))
            except (TypeError, ValueError):
                continue
        base["formats_mix"] = mix

    scenarios: List[Dict[str, Any]] = []
    for item in raw.get("scenarios") or raw.get("cenarios") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("nome") or "").strip()
        if not name:
            continue
        scenarios.append(
            {
                "name": name,
                "description": str(item.get("description") or item.get("descricao") or "").strip(),
                "weekly_follower_gain": item.get("weekly_follower_gain")
                or item.get("ganho_seguidores_semana"),
            }
        )
    base["scenarios"] = scenarios[:4]

    weekly = raw.get("weekly_kpis") or raw.get("kpis_semanais") or {}
    base["weekly_kpis"] = weekly if isinstance(weekly, dict) else {}

    base["organic_tactics"] = [
        str(t).strip()
        for t in (raw.get("organic_tactics") or raw.get("taticas_organicas") or [])
        if str(t).strip()
    ][:12]
    base["risks"] = [
        str(r).strip() for r in (raw.get("risks") or raw.get("riscos") or []) if str(r).strip()
    ][:8]
    base["next_steps"] = [
        str(s).strip()
        for s in (raw.get("next_steps") or raw.get("proximos_passos") or [])
        if str(s).strip()
    ][:8]

    return base


def generate_linkedin_strategy(
    client: OpenAI,
    model: str,
    messages: Sequence[Dict[str, str]],
    language: str,
    *,
    previous_strategy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Gera plano estratégico LinkedIn orgânico com base na conversa.

    O Diretor (via LLM) define ICP, objetivos SMART, pilares com percentagem
    semanal, cadência, mix de formatos e cenários de crescimento.

    Argumentos:
        client: Cliente OpenAI já autenticado.
        model: Identificador do modelo (ex.: ``gpt-4o-mini``).
        messages: Histórico da chatroom do Diretor.
        language: Idioma da resposta (ex.: ``pt-PT``).
        previous_strategy: Estratégia anterior para refinamento iterativo.

    Retorno:
        Dicionário com chaves ``strategy`` (normalizada), ``reply`` (mensagem ao
        utilizador) e ``needs_clarification`` (bool).
    """

    conversation = build_conversation_context(messages)
    prev_block = ""
    if previous_strategy:
        prev_block = (
            "\n\nEstratégia anterior (refina com o feedback do utilizador):\n"
            + json.dumps(previous_strategy, ensure_ascii=False)
        )

    system_prompt = (
        f"És o Diretor de Marketing AI — marketeer sénior especializado em LinkedIn orgânico. "
        f"Responde ao utilizador em {language}. "
        "O utilizador define objetivos; tu defines a ESTRATÉGIA completa antes de qualquer post. "
        "Inclui sempre: ICP (para quem comunicamos), objetivos SMART com valores e prazos, "
        "pilares de conteúdo com percentagem semanal (soma dos pilares = 100), "
        "cadência de publicação, mix de formatos (%), cenários (conservador/realista/agressivo), "
        "KPIs semanais intermédios e táticas orgânicas. "
        "Se faltarem dados críticos (ex.: ICP ou prazo), needs_clarification=true "
        "e faz no máximo 2 perguntas curtas em reply. "
        "Se já tiveres informação suficiente, needs_clarification=false. "
        "Responde APENAS com JSON válido: "
        '{"reply":"<mensagem ao utilizador apresentando a estratégia>",'
        '"needs_clarification":true|false,'
        '"strategy":{'
        '"platform":"linkedin",'
        '"summary":"<resumo executivo 2-4 frases>",'
        '"icp":{"persona_label":"","description":"","pain_points":[],"desired_outcomes":[]},'
        '"smart_objectives":[{"metric":"","current_value":null,"target_value":null,'
        '"deadline":"","specific":"","measurable":"","achievable_rationale":""}],'
        '"content_pillars":[{"theme":"","weekly_percentage":0,"description":"",'
        '"example_angles":[]}],'
        '"cadence":{"posts_per_week":0,"best_days":[],"best_times":[]},'
        '"formats_mix":{"carrossel":0,"texto":0,"imagem":0,"video":0},'
        '"scenarios":[{"name":"","description":"","weekly_follower_gain":null}],'
        '"weekly_kpis":{},"organic_tactics":[],"risks":[],"next_steps":[]}}'
    )

    response = client.chat.completions.create(
        model=model,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Histórico da conversa:\n{conversation}{prev_block}",
            },
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "strategy": _default_strategy(),
            "reply": raw or "Preciso de mais detalhes sobre os teus objetivos LinkedIn.",
            "needs_clarification": True,
        }

    strategy = normalize_strategy(data.get("strategy"))
    return {
        "strategy": strategy,
        "reply": str(data.get("reply") or "").strip(),
        "needs_clarification": bool(data.get("needs_clarification", False)),
    }


def strategy_brief_for_execution(strategy: Dict[str, Any]) -> str:
    """Compacta a estratégia aprovada num brief para copy e calendário.

    Argumentos:
        strategy: Estratégia normalizada e aprovada pelo utilizador.

    Retorno:
        Texto estruturado para injetar no brief do Copywriter ou gerador de posts.
    """

    if not strategy:
        return ""

    lines = [
        "ESTRATÉGIA LINKEDIN APROVADA (seguir rigorosamente):",
        strategy.get("summary") or "",
        "",
        f"ICP: {strategy.get('icp', {}).get('persona_label', '')} — "
        f"{strategy.get('icp', {}).get('description', '')}",
    ]

    objectives = strategy.get("smart_objectives") or []
    if objectives:
        lines.append("\nObjetivos SMART:")
        for obj in objectives:
            lines.append(
                f"- {obj.get('metric')}: {obj.get('current_value')} → "
                f"{obj.get('target_value')} até {obj.get('deadline')}"
            )

    pillars = strategy.get("content_pillars") or []
    if pillars:
        lines.append("\nPilares de conteúdo (% semanal):")
        for pillar in pillars:
            lines.append(
                f"- {pillar.get('theme')} ({pillar.get('weekly_percentage')}%): "
                f"{pillar.get('description')}"
            )

    cadence = strategy.get("cadence") or {}
    if cadence.get("posts_per_week"):
        lines.append(
            f"\nCadência: {cadence.get('posts_per_week')} posts/semana; "
            f"dias: {', '.join(cadence.get('best_days') or [])}; "
            f"horas: {', '.join(cadence.get('best_times') or [])}"
        )

    mix = strategy.get("formats_mix") or {}
    if mix:
        mix_parts = [f"{k} {v}%" for k, v in mix.items()]
        lines.append(f"\nMix de formatos: {', '.join(mix_parts)}")

    tactics = strategy.get("organic_tactics") or []
    if tactics:
        lines.append("\nTáticas orgânicas: " + "; ".join(tactics[:6]))

    return "\n".join(line for line in lines if line).strip()


def format_strategy_summary_markdown(strategy: Dict[str, Any]) -> str:
    """Formata estratégia para exibição legível no painel do Diretor.

    Argumentos:
        strategy: Estratégia normalizada.

    Retorno:
        Texto markdown curto para a UI (sem HTML).
    """

    if not strategy:
        return ""

    parts: List[str] = []
    if strategy.get("summary"):
        parts.append(strategy["summary"])

    icp = strategy.get("icp") or {}
    if icp.get("persona_label") or icp.get("description"):
        parts.append(
            f"\n**ICP:** {icp.get('persona_label', '')} — {icp.get('description', '')}"
        )

    objectives = strategy.get("smart_objectives") or []
    if objectives:
        parts.append("\n**Objetivos SMART:**")
        for obj in objectives:
            parts.append(
                f"• {obj.get('metric')}: {obj.get('current_value')} → "
                f"{obj.get('target_value')} (até {obj.get('deadline')})"
            )

    pillars = strategy.get("content_pillars") or []
    if pillars:
        parts.append("\n**Pilares de conteúdo:**")
        for pillar in pillars:
            angles = pillar.get("example_angles") or []
            angle_hint = f" — ex.: {angles[0]}" if angles else ""
            parts.append(
                f"• {pillar.get('theme')} ({pillar.get('weekly_percentage')}%){angle_hint}"
            )

    cadence = strategy.get("cadence") or {}
    if cadence.get("posts_per_week"):
        parts.append(
            f"\n**Cadência:** {cadence.get('posts_per_week')} posts/semana"
        )

    scenarios = strategy.get("scenarios") or []
    if scenarios:
        parts.append("\n**Cenários:**")
        for sc in scenarios:
            gain = sc.get("weekly_follower_gain")
            gain_txt = f" (+{gain}/sem)" if gain is not None else ""
            parts.append(f"• {sc.get('name')}{gain_txt}: {sc.get('description', '')}")

    return "\n".join(parts).strip()
