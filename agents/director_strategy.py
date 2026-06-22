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

from agents.director_prompts import director_voice_block, linkedin_organic_excellence_block

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
    "linkdin",
    "linkddin",
    "likedin",
    "linkedim",
)

LINKEDIN_GOAL_VERBS = (
    "quero",
    "preciso",
    "pretendo",
    "gostava",
    "objetivo",
    "objetivos",
    "meta",
    "metas",
    "aumentar",
    "crescer",
    "melhorar",
    "atingir",
    "chegar",
    "conseguir",
    "gerar",
    "construir",
    "posicionar",
    "autoridade",
    "visibilidade",
    "leads",
    "vendas",
    "notoriedade",
    "marca",
    "engagement",
    "alcance",
    "impressoes",
    "impressões",
    "reputacao",
    "reputação",
    "networking",
    "comentarios",
    "comentários",
)


def normalize_text(text: str) -> str:
    """Normaliza texto do utilizador para comparação de intenções e keywords.

    Converte para minúsculas, remove acentos portugueses comuns e comprime
    espaços, para que termos como «publicação» e «publicacao» sejam tratados
    de forma equivalente no routing do Diretor.

    Argumentos:
        text: Mensagem original do utilizador ou fragmento de brief.

    Retorno:
        String normalizada pronta para ``in``/regex em detecção de intenção.
    """

    return _normalize_for_match(str(text or "").strip())


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


def text_mentions_linkedin(text: str) -> bool:
    """Indica se o texto menciona LinkedIn explicitamente.

    Argumentos:
        text: Mensagem ou brief do utilizador.

    Retorno:
        ``True`` quando há referência clara ao LinkedIn (não por login ligado).
    """

    normalized = _normalize_for_match(str(text or "").strip())
    if not normalized:
        return False
    if any(marker in normalized for marker in LINKEDIN_MARKERS):
        return True
    return "linkedin.com" in normalized.replace(" ", "")


def is_linkedin_strategy_intent(
    text: str,
    *,
    workflow_channels: Optional[List[str]] = None,
    continue_linkedin_strategy: bool = False,
) -> bool:
    """Indica se o utilizador pede estratégia LinkedIn com objetivos próprios.

    O utilizador pode definir qualquer meta (seguidores, SSI, leads, marca,
    autoridade, ranking, etc.). Esta função só deteta a *intenção* de planear
    no LinkedIn — o conteúdo concreto dos objetivos é tratado pelo LLM.

    Não assume LinkedIn só porque o utilizador tem sessão ligada: é obrigatório
    mencionar LinkedIn no pedido, excepto quando já está a responder perguntas
    dentro do fluxo de estratégia LinkedIn (``continue_linkedin_strategy``).

    Argumentos:
        text: Última mensagem do utilizador (ou brief agregado).
        workflow_channels: Canais já activos no fluxo (ex.: ``linkedin``).
        continue_linkedin_strategy: ``True`` quando o estágio actual já é brief
            ou revisão de estratégia LinkedIn (respostas sem repetir a palavra).

    Retorno:
        ``True`` quando o pedido deve entrar no fluxo de estratégia do Diretor.
    """

    normalized = _normalize_for_match(text.strip())
    if not normalized:
        return False

    if is_daily_digest_intent(normalized):
        return False

    has_linkedin = text_mentions_linkedin(normalized)
    if not has_linkedin and not continue_linkedin_strategy:
        return False

    has_strategy = any(marker in normalized for marker in STRATEGY_MARKERS)
    has_goal = any(marker in normalized for marker in LINKEDIN_GOAL_VERBS)

    has_numeric_target = bool(re.search(r"\b\d{2,6}\b", normalized))
    has_deadline = bool(
        re.search(r"\b(ate|até|final de|ate ao|prazo|deadline)\b", normalized)
    )

    if has_linkedin and (has_strategy or has_goal or has_numeric_target):
        return True
    if continue_linkedin_strategy and (has_goal or has_strategy or has_numeric_target):
        return True
    if has_linkedin and has_deadline:
        return True
    if has_numeric_target and has_deadline and (has_goal or has_strategy):
        return True
    return False


def is_daily_digest_intent(text: str) -> bool:
    """Deteta pedido de briefing diário / análise de ontem no LinkedIn.

    Tem prioridade sobre estratégia quando o utilizador está em revisão de
    plano mas pede explicitamente briefing, resumo ou melhores horas/dias.

    Argumentos:
        text: Última mensagem do utilizador.

    Retorno:
        ``True`` quando o pedido é digest/performance e não criação de estratégia.
    """

    normalized = _normalize_for_match(str(text or "").strip())
    if not normalized:
        return False
    markers = (
        "briefing",
        "briefing diario",
        "briefing diário",
        "analise diaria",
        "análise diária",
        "analise de ontem",
        "análise de ontem",
        "ontem funcionou",
        "o que funcionou ontem",
        "o que funcionou",
        "resumo do dia",
        "melhores horas",
        "melhores horarios",
        "melhores horários",
        "melhores dias",
        "que dias publicar",
        "que horas publicar",
        "quando devo publicar",
    )
    if any(marker in normalized for marker in markers):
        return True
    if text_mentions_linkedin(normalized) and any(
        token in normalized for token in ("ontem", "hoje", "diario", "diário", "resumo")
    ):
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


def _parse_llm_json(raw: str) -> Dict[str, Any]:
    """Interpreta JSON devolvido pelo modelo, tolerando markdown ou ruído.

    Argumentos:
        raw: Texto bruto da resposta do LLM.

    Retorno:
        Dicionário parseado; dicionário vazio se não for possível interpretar.
    """

    text = (raw or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def sanitize_strategy_chat_reply(text: str) -> str:
    """Garante que o chat nunca mostra JSON cru ao utilizador.

    Se o modelo devolver o objecto JSON inteiro no campo de mensagem, extrai
    apenas o texto legível em ``reply`` ou devolve uma frase curta por defeito.

    Argumentos:
        text: Texto candidato a mostrar na bolha do chat.

    Retorno:
        Mensagem curta e legível para o utilizador.
    """

    cleaned = (text or "").strip()
    if not cleaned:
        return "Defini a estratégia LinkedIn. Revê o plano completo no painel abaixo."

    if cleaned.startswith("{") and ("\"strategy\"" in cleaned or "'strategy'" in cleaned):
        data = _parse_llm_json(cleaned)
        inner = str(data.get("reply") or "").strip()
        if inner and not inner.startswith("{"):
            return inner

    if cleaned.startswith("{") and len(cleaned) > 120:
        return "Defini a estratégia LinkedIn. Revê o plano completo no painel abaixo."

    if len(cleaned) > 900:
        return cleaned[:320].rstrip() + "…\n\n(Detalhes completos no painel abaixo.)"

    return cleaned


def strategy_has_core_content(strategy: Dict[str, Any]) -> bool:
    """Indica se a estratégia tem dados suficientes para mostrar no painel.

    Argumentos:
        strategy: Estratégia normalizada.

    Retorno:
        ``True`` quando há objetivos, pilares ou ICP/resumo utilizáveis.
    """

    if not strategy:
        return False
    if strategy.get("smart_objectives") or strategy.get("content_pillars"):
        return True
    icp = strategy.get("icp") if isinstance(strategy.get("icp"), dict) else {}
    return bool(strategy.get("summary") and (icp.get("persona_label") or icp.get("description")))


def generate_linkedin_strategy(
    client: OpenAI,
    model: str,
    messages: Sequence[Dict[str, str]],
    language: str,
    *,
    previous_strategy: Optional[Dict[str, Any]] = None,
    profile_context: Optional[str] = None,
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
        profile_context: Resumo markdown da análise do perfil LinkedIn (opcional).

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

    profile_block = ""
    if profile_context:
        profile_block = f"\n\nDados do perfil analisado:\n{profile_context}"

    system_prompt = (
        f"{director_voice_block(language)}\n"
        f"{linkedin_organic_excellence_block()}\n"
        "Especialização: LinkedIn orgânico B2B. "
        "O utilizador define os SEUS objetivos (podem ser seguidores, SSI, ranking, leads, "
        "autoridade, marca, engagement, vendas, ou qualquer combinação). "
        "Tu inventas a ESTRATÉGIA completa para atingir exactamente o que ele pediu — "
        "não assumes metas genéricas nem copies exemplos anteriores. "
        "Inclui sempre: ICP (para quem comunicamos), objetivos SMART com valores e prazos "
        "extraídos do pedido do utilizador, "
        "pilares de conteúdo com percentagem semanal (soma dos pilares = 100), "
        "cadência de publicação, mix de formatos (%), cenários (conservador/realista/agressivo), "
        "KPIs semanais intermédios e táticas orgânicas. "
        "Se faltarem dados críticos (ex.: ICP ou prazo), needs_clarification=true "
        "e faz no máximo 2 perguntas curtas em reply. "
        "Se já tiveres informação suficiente, needs_clarification=false. "
        "O campo reply deve ter NO MÁXIMO 3 frases curtas em linguagem natural — "
        "NUNCA incluas JSON, listas longas nem o conteúdo de strategy no reply; "
        "os detalhes ficam só no objecto strategy. "
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
        temperature=0.38,
        max_tokens=5000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Histórico da conversa:\n{conversation}{prev_block}{profile_block}",
            },
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    data = _parse_llm_json(raw)
    if not data:
        return {
            "strategy": _default_strategy(),
            "reply": "Preciso de mais detalhes sobre os teus objetivos LinkedIn.",
            "needs_clarification": True,
        }

    strategy = normalize_strategy(data.get("strategy"))
    if not strategy_has_core_content(strategy) and isinstance(data.get("strategy"), dict):
        strategy = normalize_strategy(data)

    reply = sanitize_strategy_chat_reply(str(data.get("reply") or "").strip())
    return {
        "strategy": strategy,
        "reply": reply,
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
