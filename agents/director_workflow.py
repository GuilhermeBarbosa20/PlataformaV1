"""Fluxo operacional do Diretor: estratégia → copy → imagem → aprovações.

Toda a execução acontece na chatroom do Diretor (`/`), sem obrigar o utilizador
a mudar de página. O utilizador fala só com o Diretor; este define estratégia
LinkedIn (objetivos SMART, ICP, pilares) e depois delega copy e design.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence

from openai import OpenAI

from agents.copywriter import copywriter_agent
from agents.designer import designer_agent
from agents.director_linkedin import profile_context_markdown
from agents.director_strategy import (
    generate_linkedin_strategy,
    is_linkedin_strategy_intent,
    sanitize_strategy_chat_reply,
    strategy_brief_for_execution,
    strategy_has_core_content,
)
from agents.director_team import (
    build_conversation_brief,
    build_team_task_payload,
    infer_team_agents_from_keywords,
    plan_team_with_llm,
)

STAGE_IDLE = "idle"
STAGE_STRATEGY_BRIEF = "strategy_brief"
STAGE_STRATEGY_REVIEW = "strategy_review"
STAGE_STRATEGY_APPROVED = "strategy_approved"
STAGE_PLANNING = "planning"
STAGE_COPY_REVIEW = "copy_review"
STAGE_IMAGE_CONFIRM = "image_confirm"
STAGE_IMAGE_REVIEW = "image_review"
STAGE_COMPLETED = "completed"

ACTION_APPROVE_STRATEGY = "approve_strategy"
ACTION_START_EXECUTION = "start_execution"
ACTION_ANALYZE_LINKEDIN = "analyze_linkedin_profile"
ACTION_APPROVE_COPY = "approve_copy"
ACTION_EDIT_COPY = "edit_copy"
ACTION_GENERATE_IMAGE = "generate_image"
ACTION_SKIP_IMAGE = "skip_image"
ACTION_APPROVE_IMAGE = "approve_image"
ACTION_REGENERATE_IMAGE = "regenerate_image"
ACTION_START_CAMPAIGN = "start_campaign"

DIRECTOR_INTERNAL_AGENTS = ("Agente Copywriter", "Agente Designer")

INSTAGRAM_REDIRECT_AGENT = "Agente Redes sociais"
LINKEDIN_REDIRECT_AGENTS = frozenset({"Agente LinkedIn (perfil)", "Agente Linkedin Ads"})

_PLATFORM_OPERATION_MARKERS = (
    "analisar",
    "analise",
    "auditar",
    "auditoria",
    "publicar",
    "publicacao",
    "calendario",
    "oauth",
    "login",
    "ligar",
    "conectar",
    "perfil",
    "metricas",
    "indicadores",
    "seguidores",
    "engagement",
    "conta",
    "harvest",
    "linkedin.com",
)

_INSTAGRAM_MARKERS = (
    "instagram",
    "insta",
    "reels",
    "stories",
    "tiktok",
    "meta ads",
    "facebook ads",
    "facebook",
    "business manager",
)


def _new_workflow_state() -> Dict[str, Any]:
    """Inicializa estado vazio do fluxo do Diretor."""

    return {
        "stage": STAGE_IDLE,
        "execution_plan": "",
        "channels": [],
        "strategy": None,
        "linkedin_connected": False,
        "linkedin_profile_url": "",
        "linkedin_analysis": None,
        "post": None,
        "copy": None,
        "image": None,
        "pending_actions": [],
    }


def normalize_workflow_state(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normaliza estado enviado pelo frontend."""

    state = _new_workflow_state()
    if not isinstance(raw, dict):
        return state
    stage = str(raw.get("stage", STAGE_IDLE)).strip() or STAGE_IDLE
    if stage in {
        STAGE_IDLE,
        STAGE_STRATEGY_BRIEF,
        STAGE_STRATEGY_REVIEW,
        STAGE_STRATEGY_APPROVED,
        STAGE_PLANNING,
        STAGE_COPY_REVIEW,
        STAGE_IMAGE_CONFIRM,
        STAGE_IMAGE_REVIEW,
        STAGE_COMPLETED,
    }:
        state["stage"] = stage
    state["execution_plan"] = str(raw.get("execution_plan", "")).strip()
    state["channels"] = raw.get("channels") if isinstance(raw.get("channels"), list) else []
    if isinstance(raw.get("strategy"), dict):
        state["strategy"] = raw["strategy"]
    state["linkedin_connected"] = bool(raw.get("linkedin_connected"))
    state["linkedin_profile_url"] = str(raw.get("linkedin_profile_url") or "").strip()
    if isinstance(raw.get("linkedin_analysis"), dict):
        state["linkedin_analysis"] = raw["linkedin_analysis"]
    if isinstance(raw.get("post"), dict):
        state["post"] = raw["post"]
    if isinstance(raw.get("copy"), dict):
        state["copy"] = raw["copy"]
    if isinstance(raw.get("image"), dict):
        state["image"] = raw["image"]
    actions = raw.get("pending_actions")
    state["pending_actions"] = actions if isinstance(actions, list) else []
    return state


def detect_action_from_text(text: str) -> Optional[str]:
    """Infere acção do utilizador a partir de linguagem natural."""

    normalized = text.lower().strip()
    if not normalized:
        return None
    if re.search(r"\b(aprovo|aprovar)\s+(a\s+)?estrat[eé]gia\b", normalized):
        return ACTION_APPROVE_STRATEGY
    if re.search(
        r"\b(iniciar|come[cç]ar|comecar)\s+(a\s+)?execu[cç][aã]o\b",
        normalized,
    ):
        return ACTION_START_EXECUTION
    if re.search(r"\b(aprovo|aprovado|aprovar|está bem|esta bem|ok para copy|copy ok)\b", normalized):
        return ACTION_APPROVE_COPY
    if re.search(r"\b(gera(r)?\s+(a\s+)?imagem|cria(r)?\s+(a\s+)?imagem|imagem sim)\b", normalized):
        return ACTION_GENERATE_IMAGE
    if re.search(r"\b(aprovo\s+(a\s+)?imagem|imagem ok|imagem aprovada)\b", normalized):
        return ACTION_APPROVE_IMAGE
    if re.search(r"\b(sem imagem|não quero imagem|nao quero imagem|saltar imagem)\b", normalized):
        return ACTION_SKIP_IMAGE
    return None


def post_from_copywriter(copy_payload: Dict[str, Any], channel: str = "linkedin") -> Dict[str, Any]:
    """Constrói objecto de post editável a partir da copy gerada."""

    primary = ""
    variations = copy_payload.get("main_text_variations") or []
    if variations and isinstance(variations[0], dict):
        primary = str(variations[0].get("text", "")).strip()
    if not primary:
        primary = str(copy_payload.get("primary_text", "")).strip()
    headlines = copy_payload.get("headlines") or []
    ctas = copy_payload.get("ctas") or []
    return {
        "id": str(uuid.uuid4()),
        "channel": channel,
        "title": str(headlines[0]).strip() if headlines else "Post",
        "hook": str(headlines[1]).strip() if len(headlines) > 1 else "",
        "body": primary or "(sem texto)",
        "cta": str(ctas[0]).strip() if ctas else "",
        "content_type": "texto",
        "status": "draft",
    }


def _copy_summary_for_ui(copy_payload: Dict[str, Any], post: Dict[str, Any]) -> str:
    """Texto legível da copy para o painel do Diretor."""

    lines = [f"**{post.get('title', 'Post')}**", "", post.get("body", "")]
    if post.get("cta"):
        lines.extend(["", f"CTA: {post['cta']}"])
    headlines = copy_payload.get("headlines") or []
    if len(headlines) > 1:
        lines.extend(["", "Outras headlines: " + " | ".join(str(h) for h in headlines[1:4])])
    return "\n".join(lines).strip()


def _channels_from_assignments(assignments: Sequence[Dict[str, str]], conversation: str) -> List[str]:
    """Infere canal alvo a partir do brief (sem mobilizar agentes de rede)."""

    normalized = conversation.lower()
    channels: List[str] = []
    if "linkedin" in normalized:
        channels.append("linkedin")
    if any(m in normalized for m in ("instagram", "insta", "meta", "facebook", "reels")):
        channels.append("meta")
    if not channels:
        channels.append("geral")
    return channels


def _is_copy_or_design_request(normalized: str) -> bool:
    """Deteta pedidos de copy/criativo sem operação de plataforma."""

    creative_markers = (
        "copy",
        "texto",
        "legenda",
        "headline",
        "imagem",
        "criativo",
        "campanha",
        "post",
        "anuncio",
        "publicidade",
        "slogan",
    )
    has_creative = any(marker in normalized for marker in creative_markers)
    has_platform_ops = any(marker in normalized for marker in _PLATFORM_OPERATION_MARKERS)
    return has_creative and not has_platform_ops


def resolve_specialist_redirect(
    normalized: str,
    raw_text: str,
    keyword_agents: Sequence[str],
    resolve_linkedin: Callable[[str], Any],
    correct_linkedin_agent: Callable[[str, str], str],
) -> Optional[str]:
    """Decide se o pedido deve ir para Instagram/LinkedIn em vez do fluxo copy+design.

    Argumentos:
        normalized: Última mensagem do utilizador normalizada.
        raw_text: Texto original do utilizador.
        keyword_agents: Agentes sugeridos por keywords.
        resolve_linkedin: Função de desambiguação LinkedIn.
        correct_linkedin_agent: Correcção perfil vs ads LinkedIn.

    Retorno:
        Nome do agente especializado para redireccionamento, ou ``None``.
    """

    if _is_copy_or_design_request(normalized):
        return None

    for agent in keyword_agents:
        if agent == INSTAGRAM_REDIRECT_AGENT:
            return INSTAGRAM_REDIRECT_AGENT

    linkedin_route = resolve_linkedin(normalized)
    if linkedin_route is not None:
        agent_name, _ = linkedin_route
        return correct_linkedin_agent(raw_text, agent_name)

    for agent in keyword_agents:
        if agent in LINKEDIN_REDIRECT_AGENTS:
            return correct_linkedin_agent(raw_text, agent)

    if any(marker in normalized for marker in _INSTAGRAM_MARKERS):
        if any(marker in normalized for marker in _PLATFORM_OPERATION_MARKERS):
            return INSTAGRAM_REDIRECT_AGENT
        if not _is_copy_or_design_request(normalized):
            return INSTAGRAM_REDIRECT_AGENT

    if "linkedin" in normalized and any(marker in normalized for marker in _PLATFORM_OPERATION_MARKERS):
        return correct_linkedin_agent(raw_text, "Agente LinkedIn (perfil)")

    return None


def _build_redirect_response(
    agent_name: str,
    agent_page_url: Callable[[str], str],
) -> Dict[str, Any]:
    """Monta resposta de encaminhamento para agente Instagram ou LinkedIn Ads."""

    labels = {
        INSTAGRAM_REDIRECT_AGENT: "Instagram / redes sociais",
        "Agente Linkedin Ads": "LinkedIn Ads",
    }
    label = labels.get(agent_name, agent_name)
    return {
        "reply": (
            f"Para {label}, o trabalho operacional fica no agente especializado. "
            "Clica no botão abaixo para continuar com o especialista certo."
        ),
        "orchestration_mode": "redirect",
        "execution_plan": "",
        "team_tasks": [],
        "agents_involved": [agent_name],
        "ready_to_route": True,
        "agent_name": agent_name,
        "workflow_state": _new_workflow_state(),
        "deliverables": _deliverables_from_state(_new_workflow_state()),
        "pending_actions": [],
    }


def _build_linkedin_director_response(
    state: Dict[str, Any],
    last_user_text: str,
) -> Dict[str, Any]:
    """Mantém operações LinkedIn orgânicas no Diretor (sem mudar de página)."""

    connected = bool(state.get("linkedin_connected"))
    has_analysis = bool(state.get("linkedin_analysis"))
    if not connected:
        reply = (
            "Para LinkedIn orgânico, fica aqui comigo. Primeiro **liga o LinkedIn** "
            "no painel acima (botão «Ligar LinkedIn»). Depois diz-me os teus objetivos "
            "— eu defino a estratégia para o que quiseres atingir."
        )
    elif not has_analysis:
        reply = (
            "Sessão LinkedIn activa. Clica em **«Analisar perfil»** no painel para eu "
            "ter métricas reais. Em seguida descreve os teus objetivos e monto a estratégia."
        )
        state["pending_actions"] = [ACTION_ANALYZE_LINKEDIN]
    else:
        reply = (
            "Perfil LinkedIn já analisado. Descreve os teus objetivos (o que quiseres "
            "atingir e até quando) e eu defino a estratégia personalizada."
        )
        state["pending_actions"] = []
    return {
        "reply": reply,
        "orchestration_mode": state.get("stage") or STAGE_IDLE,
        "workflow_state": state,
        "deliverables": _deliverables_from_state(state),
        "pending_actions": state.get("pending_actions") or [],
        "agents_involved": [],
        "ready_to_route": False,
    }


def _generate_campaign_copy(
    conversation: str,
    task_brief: str,
    language: str,
) -> Dict[str, Any]:
    """Gera copy via Copywriter para o fluxo do Diretor."""

    if not copywriter_agent.is_configured():
        raise RuntimeError("OPENAI_API_KEY em falta para gerar copy.")
    brief = f"{task_brief}\n\nContexto:\n{conversation}"
    return copywriter_agent.generate_marketing_copy(brief=brief, language=language)


def _generate_post_image(
    post: Dict[str, Any],
    edit_instructions: Optional[str] = None,
) -> Dict[str, str]:
    """Gera imagem alinhada ao post aprovado."""

    if not designer_agent.is_configured():
        raise RuntimeError(
            "Geração de imagem indisponível: configure OPENAI_API_KEY ou NANO_BANANA no servidor."
        )
    return designer_agent.generate_image_for_linkedin_post(
        post,
        edit_instructions=edit_instructions,
    )


def _deliverables_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Monta pacote de entregáveis visível no painel do Diretor."""

    return {
        "strategy": state.get("strategy"),
        "linkedin_analysis": state.get("linkedin_analysis"),
        "linkedin_connected": state.get("linkedin_connected"),
        "linkedin_profile_url": state.get("linkedin_profile_url"),
        "post": state.get("post"),
        "copy": state.get("copy"),
        "image": state.get("image"),
    }


def _strategy_chat_reply(intro: str) -> str:
    """Mensagem curta no chat; detalhes ficam só no painel inferior."""

    text = sanitize_strategy_chat_reply(intro)
    if "painel" in text.casefold():
        return text
    return f"{text}\n\nRevê o plano completo no painel abaixo.".strip()


def _generate_and_review_strategy(
    *,
    client: OpenAI,
    model: str,
    messages: Sequence[Dict[str, str]],
    language: str,
    state: Dict[str, Any],
    previous_strategy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Gera estratégia LinkedIn e prepara estado para revisão pelo utilizador.

    Argumentos:
        client: Cliente OpenAI.
        model: Modelo LLM.
        messages: Histórico da conversa.
        language: Idioma da resposta.
        state: Estado mutável do workflow.
        previous_strategy: Estratégia anterior para refinamento.

    Retorno:
        Payload parcial com ``reply``, ``workflow_state`` e ``deliverables``.
    """

    profile_ctx = profile_context_markdown(state.get("linkedin_analysis"))
    result = generate_linkedin_strategy(
        client,
        model,
        messages,
        language,
        previous_strategy=previous_strategy,
        profile_context=profile_ctx or None,
    )
    strategy = result.get("strategy") or {}
    needs_clarification = bool(result.get("needs_clarification"))
    reply = _strategy_chat_reply(str(result.get("reply") or "").strip())

    if not strategy_has_core_content(strategy):
        state["stage"] = STAGE_STRATEGY_BRIEF
        state["strategy"] = None
        state["pending_actions"] = []
        if not reply or reply.startswith("{"):
            reply = "Preciso de mais detalhes: objetivos com prazo, ICP e métricas actuais."
        return {
            "reply": reply,
            "orchestration_mode": STAGE_STRATEGY_BRIEF,
            "workflow_state": state,
            "pending_actions": [],
            "deliverables": _deliverables_from_state(state),
        }

    state["strategy"] = strategy
    state["stage"] = STAGE_STRATEGY_REVIEW
    state["channels"] = ["linkedin"]
    state["execution_plan"] = strategy.get("summary") or ""
    state["pending_actions"] = [ACTION_APPROVE_STRATEGY, ACTION_START_EXECUTION]
    if needs_clarification:
        reply = _strategy_chat_reply(
            "Montei um plano inicial com o que tenho. Revê no painel e diz-me se falta algo."
        )
    elif not reply or reply.startswith("{"):
        reply = _strategy_chat_reply("Defini a estratégia LinkedIn.")
    return {
        "reply": reply,
        "orchestration_mode": STAGE_STRATEGY_REVIEW,
        "workflow_state": state,
        "pending_actions": state["pending_actions"],
        "deliverables": _deliverables_from_state(state),
        "agents_involved": [],
    }


def _start_copy_from_strategy(
    *,
    state: Dict[str, Any],
    sanitized: Sequence[Dict[str, str]],
    language: str,
    reply_prefix: str = "",
) -> Dict[str, Any]:
    """Delega ao Copywriter o primeiro post com base na estratégia aprovada.

    Argumentos:
        state: Estado do workflow com estratégia aprovada.
        sanitized: Histórico da conversa.
        language: Idioma da copy.
        reply_prefix: Texto opcional a prefixar na resposta ao utilizador.

    Retorno:
        Payload com copy gerada e estado em ``copy_review``.

    Raises:
        RuntimeError: Se o Copywriter não estiver configurado.
        Exception: Falhas na geração de copy.
    """

    strategy = state.get("strategy") or {}
    strategy_brief = strategy_brief_for_execution(strategy)
    conversation = build_conversation_brief(sanitized)
    copy_brief = (
        f"{strategy_brief}\n\n"
        "Tarefa: produzir o primeiro post LinkedIn da semana, alinhado com o pilar "
        "de maior percentagem e com tom profissional para o ICP definido."
    )
    copy_result = _generate_campaign_copy(conversation, copy_brief, language)
    post = post_from_copywriter(copy_result, channel="linkedin")
    state["copy"] = copy_result
    state["post"] = post
    state["stage"] = STAGE_COPY_REVIEW
    state["pending_actions"] = [ACTION_APPROVE_COPY, ACTION_EDIT_COPY]
    prefix = f"{reply_prefix}\n\n" if reply_prefix else ""
    return {
        "reply": (
            f"{prefix}"
            "A equipa preparou a copy do primeiro post com base na estratégia aprovada. "
            "**Revê no painel** e clica em «Aprovar copy» quando estiveres satisfeito."
        ).strip(),
        "orchestration_mode": STAGE_COPY_REVIEW,
        "workflow_state": state,
        "pending_actions": state["pending_actions"],
        "deliverables": _deliverables_from_state(state),
        "agents_involved": ["Agente Copywriter"],
    }


def process_director_turn(
    *,
    messages: Sequence[Dict[str, str]],
    language: str,
    workflow_state: Optional[Dict[str, Any]],
    user_action: Optional[str],
    action_payload: Optional[Dict[str, Any]],
    openai_api_key: str,
    openai_model: str,
    agent_catalog: Sequence[str],
    routing_map: Dict[str, List[str]],
    action_plans: Dict[str, List[str]],
    linkedin_guidance: str,
    normalize_text: Callable[[str], str],
    resolve_linkedin: Callable[[str], Any],
    correct_linkedin_agent: Callable[[str, str], str],
    agent_page_url: Callable[[str], str],
) -> Dict[str, Any]:
    """Processa um turno do Diretor com fluxo de aprovações na mesma interface.

    Argumentos:
        messages: Histórico da chatroom.
        language: Idioma da resposta.
        workflow_state: Estado persistido no frontend entre turnos.
        user_action: Acção explícita (botões) ou None.
        action_payload: Dados extra (ex. texto editado, instruções de imagem).
        openai_api_key: Chave OpenAI.
        openai_model: Modelo LLM.
        agent_catalog: Lista de agentes permitidos.
        routing_map: Mapa de keywords do Diretor.
        action_plans: Planos por agente.
        linkedin_guidance: Regras LinkedIn.
        normalize_text: Função de normalização de texto.
        resolve_linkedin: Resolver intenção LinkedIn.
        correct_linkedin_agent: Correcção perfil vs ads.
        agent_page_url: URL da página de cada agente.

    Retorno:
        Payload API com `reply`, `workflow_state`, `deliverables`, `pending_actions`, etc.
    """

    state = normalize_workflow_state(workflow_state)
    payload = action_payload if isinstance(action_payload, dict) else {}
    client = OpenAI(api_key=openai_api_key)

    sanitized: List[Dict[str, str]] = []
    for message in messages:
        role = str(message.get("role", "")).strip()
        content = str(message.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            sanitized.append({"role": role, "content": content})

    last_user = next((m for m in reversed(sanitized) if m.get("role") == "user"), None)
    last_user_text = str(last_user.get("content", "")) if last_user else ""
    inferred = detect_action_from_text(last_user_text) if not user_action else None
    action = (user_action or inferred or "").strip().lower()

    base_response: Dict[str, Any] = {
        "orchestration_mode": state["stage"],
        "execution_plan": state.get("execution_plan", ""),
        "team_tasks": [],
        "agents_involved": [],
        "ready_to_route": False,
        "agent_name": None,
        "workflow_state": state,
        "deliverables": _deliverables_from_state(state),
        "pending_actions": state.get("pending_actions") or [],
    }

    # --- Estratégia LinkedIn ---
    if action == ACTION_APPROVE_STRATEGY and state["stage"] == STAGE_STRATEGY_REVIEW:
        state["stage"] = STAGE_STRATEGY_APPROVED
        state["pending_actions"] = [ACTION_START_EXECUTION]
        strategy = state.get("strategy") or {}
        base_response["reply"] = (
            "Estratégia aprovada. Quando quiseres, clica em «Iniciar execução» "
            "para a equipa produzir o primeiro post alinhado com o plano."
        )
        base_response["orchestration_mode"] = STAGE_STRATEGY_APPROVED
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state["pending_actions"]
        base_response["deliverables"] = _deliverables_from_state(state)
        base_response["execution_plan"] = strategy.get("summary") or state.get("execution_plan", "")
        return base_response

    if action == ACTION_START_EXECUTION and state["stage"] in {
        STAGE_STRATEGY_REVIEW,
        STAGE_STRATEGY_APPROVED,
    }:
        if state["stage"] == STAGE_STRATEGY_REVIEW:
            state["stage"] = STAGE_STRATEGY_APPROVED
        try:
            result = _start_copy_from_strategy(
                state=state,
                sanitized=sanitized,
                language=language,
                reply_prefix="Estratégia confirmada.",
            )
            base_response.update(result)
            base_response["team_tasks"] = [
                build_team_task_payload(
                    {
                        "agent_name": "Agente Copywriter",
                        "status": "completed",
                        "summary": (state.get("post") or {}).get("body", "")[:1500],
                        "error": None,
                    },
                    agent_page_url,
                )
            ]
            return base_response
        except Exception as exc:  # noqa: BLE001
            base_response["reply"] = f"Não consegui iniciar a execução agora: {exc!s}"
            base_response["orchestration_mode"] = STAGE_STRATEGY_APPROVED
            base_response["workflow_state"] = state
            return base_response

    if (
        state["stage"] in {STAGE_STRATEGY_BRIEF, STAGE_STRATEGY_REVIEW}
        and last_user_text
        and not user_action
    ):
        strategy_result = _generate_and_review_strategy(
            client=client,
            model=openai_model,
            messages=sanitized,
            language=language,
            state=state,
            previous_strategy=state.get("strategy"),
        )
        base_response.update(strategy_result)
        if state["stage"] == STAGE_STRATEGY_REVIEW:
            base_response["reply"] = (
                f"{strategy_result.get('reply', '')}\n\n"
                "(Refinei a estratégia com o teu feedback. Revê e aprova quando estiver pronta.)"
            ).strip()
        return base_response

    if state["stage"] == STAGE_STRATEGY_APPROVED and last_user_text and not user_action:
        normalized_approved = normalize_text(last_user_text)
        if _is_copy_or_design_request(normalized_approved) or "post" in normalized_approved:
            try:
                result = _start_copy_from_strategy(
                    state=state,
                    sanitized=sanitized,
                    language=language,
                )
                base_response.update(result)
                base_response["team_tasks"] = [
                    build_team_task_payload(
                        {
                            "agent_name": "Agente Copywriter",
                            "status": "completed",
                            "summary": (state.get("post") or {}).get("body", "")[:1500],
                            "error": None,
                        },
                        agent_page_url,
                    )
                ]
                return base_response
            except Exception as exc:  # noqa: BLE001
                base_response["reply"] = f"Não consegui gerar a copy: {exc!s}"
                return base_response
        base_response["reply"] = (
            "Estratégia aprovada. Clica em «Iniciar execução» para o primeiro post "
            "ou pede outro post alinhado com o plano."
        )
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state.get("pending_actions") or []
        return base_response

    if state["stage"] == STAGE_STRATEGY_REVIEW and user_action and action not in {
        ACTION_APPROVE_STRATEGY,
        ACTION_START_EXECUTION,
    }:
        base_response["reply"] = (
            "Revê a estratégia no painel. Usa «Aprovar estratégia» ou «Iniciar execução»."
        )
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state.get("pending_actions") or []
        return base_response

    # --- Acções explícitas do fluxo copy/imagem ---
    if action == ACTION_APPROVE_COPY and state["stage"] == STAGE_COPY_REVIEW:
        post = state.get("post") or {}
        if post:
            post["status"] = "approved"
            state["post"] = post
        state["stage"] = STAGE_IMAGE_CONFIRM
        state["pending_actions"] = [ACTION_GENERATE_IMAGE, ACTION_SKIP_IMAGE]
        base_response["reply"] = (
            "Copy aprovada. Queres que gere a imagem para este post? "
            "Clica em «Gerar imagem» ou escreve «gera imagem». "
            "Se não precisares de criativo visual, usa «Sem imagem»."
        )
        base_response["orchestration_mode"] = STAGE_IMAGE_CONFIRM
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state["pending_actions"]
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_EDIT_COPY and state["stage"] == STAGE_COPY_REVIEW:
        new_body = str(payload.get("body") or "").strip()
        post = dict(state.get("post") or {})
        if new_body:
            post["body"] = new_body
            state["post"] = post
        state["pending_actions"] = [ACTION_APPROVE_COPY, ACTION_EDIT_COPY]
        base_response["reply"] = "Atualizei o texto do post. Revê abaixo e clica em «Aprovar copy» quando estiver pronto."
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state["pending_actions"]
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_SKIP_IMAGE and state["stage"] == STAGE_IMAGE_CONFIRM:
        state["stage"] = STAGE_COMPLETED
        state["pending_actions"] = []
        base_response["reply"] = "Perfeito — pacote concluído só com a copy aprovada."
        base_response["orchestration_mode"] = STAGE_COMPLETED
        base_response["workflow_state"] = state
        return base_response

    if action in {ACTION_GENERATE_IMAGE, ACTION_REGENERATE_IMAGE} and state["stage"] in {
        STAGE_IMAGE_CONFIRM,
        STAGE_IMAGE_REVIEW,
    }:
        post = state.get("post") or {}
        if not str(post.get("body", "")).strip() or post.get("body") == "(sem texto)":
            base_response["reply"] = "Não há texto de post para gerar imagem. Aprova ou edita a copy primeiro."
            return base_response
        try:
            instr = str(payload.get("edit_instructions") or "").strip() or None
            image_result = _generate_post_image(post, edit_instructions=instr)
            state["image"] = image_result
            state["stage"] = STAGE_IMAGE_REVIEW
            state["pending_actions"] = [ACTION_APPROVE_IMAGE, ACTION_REGENERATE_IMAGE]
            base_response["reply"] = (
                "Imagem gerada. Revê a pré-visualização abaixo. "
                "Clica em «Aprovar imagem» ou «Regenerar imagem» com instruções."
            )
            base_response["team_tasks"] = [
                build_team_task_payload(
                    {
                        "agent_name": "Agente Designer",
                        "status": "completed",
                        "summary": f"Imagem: {image_result.get('image_url', '')}",
                        "error": None,
                    },
                    agent_page_url,
                )
            ]
            base_response["agents_involved"] = ["Agente Designer"]
        except Exception as exc:  # noqa: BLE001
            base_response["reply"] = f"Não consegui gerar a imagem: {exc!s}"
            state["pending_actions"] = [ACTION_GENERATE_IMAGE, ACTION_SKIP_IMAGE]
        base_response["orchestration_mode"] = state["stage"]
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state["pending_actions"]
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_APPROVE_IMAGE and state["stage"] == STAGE_IMAGE_REVIEW:
        state["stage"] = STAGE_COMPLETED
        state["pending_actions"] = []
        post = state.get("post") or {}
        if post:
            post["status"] = "ready"
            state["post"] = post
        base_response["reply"] = "Pacote concluído: copy e imagem aprovados. Podes reutilizar estes materiais na tua campanha."
        base_response["orchestration_mode"] = STAGE_COMPLETED
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        base_response["ready_to_route"] = False
        return base_response

    # Se já estamos numa etapa de revisão, não voltar a gerar copy sem pedido novo
    if state["stage"] in {STAGE_COPY_REVIEW, STAGE_IMAGE_CONFIRM, STAGE_IMAGE_REVIEW}:
        hint = {
            STAGE_COPY_REVIEW: "Estás a rever a copy. Usa «Aprovar copy» ou edita o texto no painel.",
            STAGE_IMAGE_CONFIRM: "Confirma se queres imagem: «Gerar imagem» ou «Sem imagem».",
            STAGE_IMAGE_REVIEW: "Revê a imagem: «Aprovar imagem» ou «Regenerar imagem».",
        }.get(state["stage"], "")
        base_response["reply"] = hint
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state.get("pending_actions") or []
        return base_response

    # --- Novo pedido / campanha ---
    normalized_last = normalize_text(last_user_text) if last_user_text else ""
    conversation_full = build_conversation_brief(sanitized)
    strategy_intent = is_linkedin_strategy_intent(
        f"{conversation_full}\n{last_user_text}",
        workflow_channels=state.get("channels"),
    )

    if strategy_intent or (
        state.get("strategy")
        and state["stage"] in {STAGE_IDLE, STAGE_COMPLETED, STAGE_STRATEGY_BRIEF}
        and "linkedin" in normalized_last
    ):
        strategy_result = _generate_and_review_strategy(
            client=client,
            model=openai_model,
            messages=sanitized,
            language=language,
            state=state,
            previous_strategy=state.get("strategy"),
        )
        base_response.update(strategy_result)
        return base_response

    if state["stage"] == STAGE_STRATEGY_APPROVED and _is_copy_or_design_request(
        normalized_last
    ):
        try:
            result = _start_copy_from_strategy(
                state=state,
                sanitized=sanitized,
                language=language,
            )
            base_response.update(result)
            base_response["team_tasks"] = [
                build_team_task_payload(
                    {
                        "agent_name": "Agente Copywriter",
                        "status": "completed",
                        "summary": (state.get("post") or {}).get("body", "")[:1500],
                        "error": None,
                    },
                    agent_page_url,
                )
            ]
            return base_response
        except Exception as exc:  # noqa: BLE001
            base_response["reply"] = f"Não consegui gerar a copy: {exc!s}"
            return base_response

    keyword_agents = infer_team_agents_from_keywords(
        normalized_last, routing_map, normalize_text, resolve_linkedin
    )
    if keyword_agents:
        keyword_agents = [correct_linkedin_agent(last_user_text, n) for n in keyword_agents]

    redirect_agent = None
    if not strategy_intent:
        redirect_agent = resolve_specialist_redirect(
            normalized_last,
            last_user_text,
            keyword_agents,
            resolve_linkedin,
            correct_linkedin_agent,
        )
    if redirect_agent in LINKEDIN_REDIRECT_AGENTS:
        return _build_linkedin_director_response(state, last_user_text)
    if redirect_agent:
        return _build_redirect_response(redirect_agent, agent_page_url)

    internal_keywords = [name for name in keyword_agents if name in DIRECTOR_INTERNAL_AGENTS]

    plan = plan_team_with_llm(
        client=client,
        model=openai_model,
        agent_catalog=DIRECTOR_INTERNAL_AGENTS,
        linkedin_guidance=linkedin_guidance,
        messages=sanitized,
        language=language,
        keyword_agents=internal_keywords,
    )

    reply_seed = str(plan.get("reply", "")).strip()
    execution_plan = str(plan.get("execution_plan", "")).strip()
    needs_clarification = bool(plan.get("needs_clarification", False))
    assignments = list(plan.get("team_assignments") or [])

    if needs_clarification or not assignments:
        state["stage"] = STAGE_PLANNING
        state["execution_plan"] = execution_plan
        base_response["reply"] = reply_seed or "Indica objetivo, público e tom para eu preparar copy e imagem."
        base_response["orchestration_mode"] = STAGE_PLANNING
        base_response["workflow_state"] = state
        return base_response

    conversation = build_conversation_brief(sanitized)
    copy_brief = execution_plan
    for item in assignments:
        if "Copywriter" in str(item.get("agent_name", "")):
            copy_brief = str(item.get("task_brief", "")).strip() or copy_brief
            break

    state["channels"] = _channels_from_assignments(assignments, conversation)
    state["execution_plan"] = execution_plan
    channel = state["channels"][0] if state["channels"] else "geral"

    try:
        copy_result = _generate_campaign_copy(conversation, copy_brief, language)
        post = post_from_copywriter(copy_result, channel=channel)
        state["copy"] = copy_result
        state["post"] = post
        state["stage"] = STAGE_COPY_REVIEW
        state["pending_actions"] = [ACTION_APPROVE_COPY, ACTION_EDIT_COPY]
        summary = _copy_summary_for_ui(copy_result, post)
        base_response["reply"] = (
            f"{reply_seed}\n\n"
            "Preparei a copy do post abaixo. **Revê no painel** e clica em "
            "«Aprovar copy» quando estiveres satisfeito — só depois pergunto "
            "se queres gerar a imagem."
        ).strip()
        base_response["team_tasks"] = [
            build_team_task_payload(
                {
                    "agent_name": "Agente Copywriter",
                    "status": "completed",
                    "summary": summary[:1500],
                    "error": None,
                },
                agent_page_url,
            )
        ]
        base_response["agents_involved"] = ["Agente Copywriter"]
        base_response["orchestration_mode"] = STAGE_COPY_REVIEW
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state["pending_actions"]
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response
    except Exception as exc:  # noqa: BLE001
        base_response["reply"] = (
            f"{reply_seed}\n\nNão consegui gerar a copy agora: {exc!s}"
        ).strip()
        base_response["orchestration_mode"] = STAGE_PLANNING
        return base_response
