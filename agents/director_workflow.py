"""Fluxo operacional do Diretor: copy → aprovação → imagem → aprovação.

Toda a execução acontece na chatroom do Diretor (`/`), sem obrigar o utilizador
a mudar de página para aprovar copy ou gerar imagem.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence

from openai import OpenAI

from agents.copywriter import copywriter_agent
from agents.designer import designer_agent
from agents.director_team import (
    build_conversation_brief,
    build_team_task_payload,
    infer_team_agents_from_keywords,
    plan_team_with_llm,
)

STAGE_IDLE = "idle"
STAGE_PLANNING = "planning"
STAGE_COPY_REVIEW = "copy_review"
STAGE_IMAGE_CONFIRM = "image_confirm"
STAGE_IMAGE_REVIEW = "image_review"
STAGE_COMPLETED = "completed"

ACTION_APPROVE_COPY = "approve_copy"
ACTION_EDIT_COPY = "edit_copy"
ACTION_GENERATE_IMAGE = "generate_image"
ACTION_SKIP_IMAGE = "skip_image"
ACTION_APPROVE_IMAGE = "approve_image"
ACTION_REGENERATE_IMAGE = "regenerate_image"
ACTION_START_CAMPAIGN = "start_campaign"


def _new_workflow_state() -> Dict[str, Any]:
    """Inicializa estado vazio do fluxo do Diretor."""

    return {
        "stage": STAGE_IDLE,
        "execution_plan": "",
        "channels": [],
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
        STAGE_PLANNING,
        STAGE_COPY_REVIEW,
        STAGE_IMAGE_CONFIRM,
        STAGE_IMAGE_REVIEW,
        STAGE_COMPLETED,
    }:
        state["stage"] = stage
    state["execution_plan"] = str(raw.get("execution_plan", "")).strip()
    state["channels"] = raw.get("channels") if isinstance(raw.get("channels"), list) else []
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


def _channels_from_assignments(assignments: Sequence[Dict[str, str]]) -> List[str]:
    """Extrai canais a partir dos agentes mobilizados."""

    channels: List[str] = []
    for item in assignments:
        name = str(item.get("agent_name", ""))
        if "LinkedIn" in name and "linkedin" not in channels:
            channels.append("linkedin")
        if name in {"Agente Meta Ads", "Agente Redes sociais"} and "meta" not in channels:
            channels.append("meta")
    if not channels:
        channels.append("linkedin")
    return channels


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
        "deliverables": {
            "post": state.get("post"),
            "copy": state.get("copy"),
            "image": state.get("image"),
        },
        "pending_actions": state.get("pending_actions") or [],
    }

    # --- Acções explícitas do fluxo ---
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
        base_response["deliverables"] = {"post": state.get("post"), "copy": state.get("copy"), "image": None}
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
        base_response["deliverables"] = {"post": post, "copy": state.get("copy"), "image": None}
        return base_response

    if action == ACTION_SKIP_IMAGE and state["stage"] == STAGE_IMAGE_CONFIRM:
        state["stage"] = STAGE_COMPLETED
        state["pending_actions"] = []
        publish_hint = ""
        if "linkedin" in (state.get("channels") or []):
            publish_hint = (
                " Para publicar no LinkedIn com OAuth e calendário, abre o "
                "Agente LinkedIn (perfil) — o pacote de copy fica pronto aqui."
            )
        base_response["reply"] = f"Perfeito — ficamos só com a copy aprovada.{publish_hint}"
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
        base_response["deliverables"] = {
            "post": state.get("post"),
            "copy": state.get("copy"),
            "image": state.get("image"),
        }
        return base_response

    if action == ACTION_APPROVE_IMAGE and state["stage"] == STAGE_IMAGE_REVIEW:
        state["stage"] = STAGE_COMPLETED
        state["pending_actions"] = []
        post = state.get("post") or {}
        if post:
            post["status"] = "ready"
            state["post"] = post
        linkedin_url = agent_page_url("Agente LinkedIn (perfil)")
        base_response["reply"] = (
            "Pacote completo: copy e imagem aprovados. "
            f"Para publicar no LinkedIn (OAuth, calendário, aprovações finais na rede), "
            f"usa o agente dedicado: {linkedin_url}"
        )
        base_response["orchestration_mode"] = STAGE_COMPLETED
        base_response["workflow_state"] = state
        base_response["deliverables"] = {
            "post": state.get("post"),
            "copy": state.get("copy"),
            "image": state.get("image"),
        }
        base_response["agent_name"] = "Agente LinkedIn (perfil)"
        base_response["ready_to_route"] = True
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
    keyword_agents = infer_team_agents_from_keywords(
        normalized_last, routing_map, normalize_text, resolve_linkedin
    )
    if keyword_agents:
        keyword_agents = [correct_linkedin_agent(last_user_text, n) for n in keyword_agents]

    plan = plan_team_with_llm(
        client=client,
        model=openai_model,
        agent_catalog=agent_catalog,
        linkedin_guidance=linkedin_guidance,
        messages=sanitized,
        language=language,
        keyword_agents=keyword_agents,
    )

    reply_seed = str(plan.get("reply", "")).strip()
    execution_plan = str(plan.get("execution_plan", "")).strip()
    needs_clarification = bool(plan.get("needs_clarification", False))
    assignments = list(plan.get("team_assignments") or [])

    if needs_clarification or not assignments:
        state["stage"] = STAGE_PLANNING
        state["execution_plan"] = execution_plan
        base_response["reply"] = reply_seed or "Indica objetivo, canais (ex. LinkedIn + Meta) e público-alvo."
        base_response["orchestration_mode"] = STAGE_PLANNING
        base_response["workflow_state"] = state
        return base_response

    conversation = build_conversation_brief(sanitized)
    copy_brief = execution_plan
    for item in assignments:
        if "Copywriter" in str(item.get("agent_name", "")):
            copy_brief = str(item.get("task_brief", "")).strip() or copy_brief
            break

    state["channels"] = _channels_from_assignments(assignments)
    state["execution_plan"] = execution_plan
    channel = state["channels"][0] if state["channels"] else "linkedin"

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
        base_response["deliverables"] = {
            "post": post,
            "copy": copy_result,
            "image": None,
        }
        return base_response
    except Exception as exc:  # noqa: BLE001
        base_response["reply"] = (
            f"{reply_seed}\n\nNão consegui gerar a copy agora: {exc!s}"
        ).strip()
        base_response["orchestration_mode"] = STAGE_PLANNING
        return base_response
