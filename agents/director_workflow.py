"""Fluxo operacional do Diretor: estratégia → copy → imagem → aprovações.

Toda a execução acontece na chatroom do Diretor (`/`), sem obrigar o utilizador
a mudar de página. O utilizador fala só com o Diretor; este define estratégia
LinkedIn (objetivos SMART, ICP, pilares) e depois delega copy e design.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence

from openai import OpenAI

from agents.copywriter import copywriter_agent
from agents.designer import designer_agent
from agents.director_daily_digest import run_daily_digest, should_run_daily_digest
from agents.director_engagement import (
    DEFAULT_ENGAGEMENT_BATCH_SIZE,
    append_approved_engagement,
    generate_comment_for_followed_post,
    generate_comments_batch,
    pick_posts_for_engagement_batch,
)
from agents.director_follow_feed import (
    find_followed_post,
    merge_posts_into_queue,
    next_pending_followed_post,
    normalize_followed_profile,
    update_followed_post_status,
)
from agents.director_linkedin import (
    editor_post_from_linkedin,
    generate_director_linkedin_posts,
    profile_context_markdown,
    regenerate_director_linkedin_post,
)
from agents.director_publish import (
    attach_approved_image_to_post,
    mark_post_published,
    sync_calendar_post_data,
)
from agents.director_optimization import (
    apply_optimization_to_strategy,
    generate_optimization_report,
    optimization_has_content,
)
from agents.director_intent import classify_director_intent
from agents.director_strategy import (
    generate_linkedin_strategy,
    is_linkedin_strategy_intent,
    normalize_text as normalize_director_text,
    sanitize_strategy_chat_reply,
    strategy_brief_for_execution,
    strategy_has_core_content,
    text_mentions_linkedin,
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
STAGE_POSTS_REVIEW = "posts_review"
STAGE_OPTIMIZATION_REVIEW = "optimization_review"
STAGE_PLANNING = "planning"
STAGE_COPY_REVIEW = "copy_review"
STAGE_IMAGE_CONFIRM = "image_confirm"
STAGE_IMAGE_REVIEW = "image_review"
STAGE_PUBLISH_CONFIRM = "publish_confirm"
STAGE_ENGAGEMENT_REVIEW = "engagement_review"
STAGE_ENGAGEMENT_BATCH_REVIEW = "engagement_batch_review"
STAGE_DAILY_DIGEST_REVIEW = "daily_digest_review"
STAGE_FOLLOWED_FEED = "followed_feed"
STAGE_COMPLETED = "completed"

ACTION_APPROVE_STRATEGY = "approve_strategy"
ACTION_START_EXECUTION = "start_execution"
ACTION_ANALYZE_LINKEDIN = "analyze_linkedin_profile"
ACTION_SELECT_POST = "select_post"
ACTION_REGENERATE_LINKEDIN_POST = "regenerate_linkedin_post"
ACTION_REANALYZE_COMPLETE = "reanalyze_complete"
ACTION_APPROVE_OPTIMIZATION = "approve_optimization"
ACTION_DISMISS_OPTIMIZATION = "dismiss_optimization"
ACTION_APPROVE_COPY = "approve_copy"
ACTION_EDIT_COPY = "edit_copy"
ACTION_GENERATE_IMAGE = "generate_image"
ACTION_SKIP_IMAGE = "skip_image"
ACTION_APPROVE_IMAGE = "approve_image"
ACTION_REGENERATE_IMAGE = "regenerate_image"
ACTION_SKIP_PUBLISH = "skip_publish"
ACTION_MARK_PUBLISHED = "mark_published"
ACTION_ADD_FOLLOWED_PROFILE = "add_followed_profile"
ACTION_REMOVE_FOLLOWED_PROFILE = "remove_followed_profile"
ACTION_SUGGEST_FOLLOWED_PROFILES = "suggest_followed_profiles"
ACTION_ACCEPT_FOLLOWED_SUGGESTIONS = "accept_followed_suggestions"
ACTION_DISMISS_FOLLOWED_SUGGESTION = "dismiss_followed_suggestion"
ACTION_MERGE_FOLLOWED_POSTS = "merge_followed_posts"
ACTION_SELECT_FOLLOWED_POST = "select_followed_post"
ACTION_GENERATE_ENGAGEMENT = "generate_engagement"
ACTION_APPROVE_ENGAGEMENT = "approve_engagement"
ACTION_REJECT_ENGAGEMENT = "reject_engagement"
ACTION_REGENERATE_ENGAGEMENT = "regenerate_engagement"
ACTION_SKIP_ENGAGEMENT = "skip_engagement"
ACTION_GENERATE_ENGAGEMENT_BATCH = "generate_engagement_batch"
ACTION_APPROVE_ENGAGEMENT_BATCH = "approve_engagement_batch"
ACTION_DISMISS_ENGAGEMENT_BATCH = "dismiss_engagement_batch"
ACTION_RUN_DAILY_DIGEST = "run_daily_digest"
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
    "calendario",
    "oauth",
    "login",
    "ligar",
    "conectar",
    "metricas",
    "harvest",
    "linkedin.com",
)

_FOLLOWED_ENGAGEMENT_MARKERS = (
    "perfis para seguir",
    "perfil para seguir",
    "perfis a seguir",
    "pessoas para seguir",
    "pessoas a seguir",
    "pessoas que sigo",
    "sugestoes de pessoas",
    "sugestao de pessoas",
    "perfis que sigo",
    "quem seguir",
    "seguir perfis",
    "seguir pessoas",
    "comentar publicac",
    "comentar posts",
    "comentarios em public",
    "comentarios nas public",
    "comentarios nos posts",
    "comentar nas public",
    "engagement em public",
    "feed de perfis",
    "publicacoes de perfis",
    "publicacoes desses perfis",
    "importar feed",
    "sugerir perfis",
)

_LINKEDIN_WORKFLOW_STAGES = frozenset({
    STAGE_STRATEGY_BRIEF,
    STAGE_STRATEGY_REVIEW,
    STAGE_STRATEGY_APPROVED,
    STAGE_POSTS_REVIEW,
    STAGE_OPTIMIZATION_REVIEW,
    STAGE_PUBLISH_CONFIRM,
    STAGE_FOLLOWED_FEED,
    STAGE_ENGAGEMENT_REVIEW,
})

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
        "linkedin_analysis_baseline": None,
        "optimization_report": None,
        "linkedin_posts": [],
        "linkedin_calendar": [],
        "active_post_index": 0,
        "post": None,
        "copy": None,
        "image": None,
        "followed_profiles": [],
        "followed_profile_suggestions": [],
        "followed_posts_queue": [],
        "active_followed_post_id": "",
        "engagement_draft": None,
        "engagement_batch": [],
        "engagement_log": [],
        "daily_digest": None,
        "last_daily_digest_at": "",
        "pending_actions": [],
        "standalone_image": False,
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
        STAGE_POSTS_REVIEW,
        STAGE_OPTIMIZATION_REVIEW,
        STAGE_PLANNING,
        STAGE_COPY_REVIEW,
        STAGE_IMAGE_CONFIRM,
        STAGE_IMAGE_REVIEW,
        STAGE_PUBLISH_CONFIRM,
        STAGE_ENGAGEMENT_REVIEW,
        STAGE_ENGAGEMENT_BATCH_REVIEW,
        STAGE_DAILY_DIGEST_REVIEW,
        STAGE_FOLLOWED_FEED,
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
    if isinstance(raw.get("linkedin_analysis_baseline"), dict):
        state["linkedin_analysis_baseline"] = raw["linkedin_analysis_baseline"]
    if isinstance(raw.get("optimization_report"), dict):
        state["optimization_report"] = raw["optimization_report"]
    posts = raw.get("linkedin_posts")
    state["linkedin_posts"] = posts if isinstance(posts, list) else []
    calendar = raw.get("linkedin_calendar")
    state["linkedin_calendar"] = calendar if isinstance(calendar, list) else []
    try:
        state["active_post_index"] = int(raw.get("active_post_index") or 0)
    except (TypeError, ValueError):
        state["active_post_index"] = 0
    if isinstance(raw.get("post"), dict):
        state["post"] = raw["post"]
    if isinstance(raw.get("copy"), dict):
        state["copy"] = raw["copy"]
    if isinstance(raw.get("image"), dict):
        state["image"] = raw["image"]
    profiles = raw.get("followed_profiles")
    state["followed_profiles"] = profiles if isinstance(profiles, list) else []
    suggestions = raw.get("followed_profile_suggestions")
    state["followed_profile_suggestions"] = (
        suggestions if isinstance(suggestions, list) else []
    )
    queue = raw.get("followed_posts_queue")
    state["followed_posts_queue"] = queue if isinstance(queue, list) else []
    state["active_followed_post_id"] = str(raw.get("active_followed_post_id") or "").strip()
    if isinstance(raw.get("engagement_draft"), dict):
        state["engagement_draft"] = raw["engagement_draft"]
    batch = raw.get("engagement_batch")
    state["engagement_batch"] = batch if isinstance(batch, list) else []
    if isinstance(raw.get("daily_digest"), dict):
        state["daily_digest"] = raw["daily_digest"]
    state["last_daily_digest_at"] = str(raw.get("last_daily_digest_at") or "").strip()
    log = raw.get("engagement_log")
    state["engagement_log"] = log if isinstance(log, list) else []
    actions = raw.get("pending_actions")
    state["pending_actions"] = actions if isinstance(actions, list) else []
    state["standalone_image"] = bool(raw.get("standalone_image"))
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


def _channels_from_assignments(
    assignments: Sequence[Dict[str, str]],
    last_user_text: str,
) -> List[str]:
    """Infere canal alvo só a partir do pedido actual do utilizador.

    Argumentos:
        assignments: Tarefas planeadas (reservado para extensão futura).
        last_user_text: Última mensagem do utilizador (não o histórico completo).

    Retorno:
        Lista de canais (``geral`` quando não há rede explícita).
    """

    _ = assignments
    normalized = normalize_director_text(last_user_text) if last_user_text else ""
    channels: List[str] = []
    if text_mentions_linkedin(normalized):
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
        "publicacao",
        "publicação",
    )
    has_creative = any(marker in normalized for marker in creative_markers)
    if not has_creative:
        return False
    if text_mentions_linkedin(normalized) or any(m in normalized for m in _INSTAGRAM_MARKERS):
        has_platform_ops = any(marker in normalized for marker in _PLATFORM_OPERATION_MARKERS)
        return not has_platform_ops
    return True


def _in_linkedin_workflow(state: Dict[str, Any]) -> bool:
    """Indica se o utilizador está num fluxo LinkedIn activo (não só login ligado).

    Argumentos:
        state: Estado do workflow do Diretor.

    Retorno:
        ``True`` em etapas de estratégia, calendário ou publicação LinkedIn.
    """

    stage = str(state.get("stage") or STAGE_IDLE)
    if stage in _LINKEDIN_WORKFLOW_STAGES:
        return True
    channels = state.get("channels") if isinstance(state.get("channels"), list) else []
    if "linkedin" in [str(c).lower() for c in channels]:
        return bool(state.get("linkedin_calendar") or state.get("strategy"))
    return False


def _should_enter_linkedin_strategy(
    state: Dict[str, Any],
    last_user_text: str,
) -> bool:
    """Decide se o pedido deve entrar na estratégia LinkedIn.

    Argumentos:
        state: Estado actual do workflow.
        last_user_text: Última mensagem do utilizador.

    Retorno:
        ``True`` apenas com LinkedIn explícito ou continuação de brief/revisão.
    """

    stage = str(state.get("stage") or STAGE_IDLE)
    continuing = stage in {STAGE_STRATEGY_BRIEF, STAGE_STRATEGY_REVIEW}
    return is_linkedin_strategy_intent(
        last_user_text,
        workflow_channels=state.get("channels"),
        continue_linkedin_strategy=continuing,
    )


def _is_followed_engagement_intent(normalized: str) -> bool:
    """Deteta pedido de perfis a seguir ou comentários em publicações de terceiros.

    Argumentos:
        normalized: Última mensagem do utilizador normalizada.

    Retorno:
        ``True`` quando o utilizador quer o fluxo de engagement (Fase D).
    """

    if not normalized:
        return False
    if any(marker in normalized for marker in _FOLLOWED_ENGAGEMENT_MARKERS):
        return True
    if "seguir" in normalized and ("perfil" in normalized or "pessoa" in normalized):
        return True
    if "comentar" in normalized and ("public" in normalized or "post" in normalized):
        return True
    if "comentario" in normalized and (
        "public" in normalized or "post" in normalized or "perfil" in normalized
    ):
        return True
    return False


def _wants_auto_suggest_followed_profiles(normalized: str) -> bool:
    """Indica se o utilizador pede sugestões automáticas de perfis por ICP.

    Argumentos:
        normalized: Mensagem normalizada.

    Retorno:
        ``True`` para pedidos como «perfis para seguir» ou «sugerir perfis».
    """

    markers = (
        "sugerir",
        "sugest",
        "quero perfis",
        "quero pessoas",
        "perfis para",
        "pessoas para",
        "perfis a seguir",
        "pessoas a seguir",
        "quem seguir",
    )
    if any(marker in normalized for marker in markers):
        return True
    return "seguir" in normalized and ("perfil" in normalized or "pessoa" in normalized)


def _handle_followed_engagement_chat_intent(
    state: Dict[str, Any],
    normalized: str,
    client: OpenAI,
    model: str,
    language: str,
    *,
    auto_suggest: Optional[bool] = None,
) -> Dict[str, Any]:
    """Abre o fluxo de perfis seguidos e comentários conforme o pedido no chat.

    Argumentos:
        state: Estado mutável do workflow.
        normalized: Última mensagem do utilizador normalizada.
        client: Cliente OpenAI.
        model: Modelo LLM.
        language: Idioma das mensagens.

    Retorno:
        Payload com estágio ``followed_feed`` e painel activo.
    """

    state["stage"] = STAGE_FOLLOWED_FEED
    channels = list(state.get("channels") or [])
    if "linkedin" not in [str(c).lower() for c in channels]:
        channels.append("linkedin")
    state["channels"] = channels
    state["pending_actions"] = [
        ACTION_SUGGEST_FOLLOWED_PROFILES,
        ACTION_ADD_FOLLOWED_PROFILE,
        ACTION_MERGE_FOLLOWED_POSTS,
        ACTION_SELECT_FOLLOWED_POST,
        ACTION_GENERATE_ENGAGEMENT,
        ACTION_GENERATE_ENGAGEMENT_BATCH,
    ]

    wants_suggest = (
        auto_suggest
        if auto_suggest is not None
        else _wants_auto_suggest_followed_profiles(normalized)
    )
    strategy_ok = strategy_has_core_content(state.get("strategy") or {})

    if wants_suggest and strategy_ok and copywriter_agent.is_configured():
        from agents.director_follow_suggestions import (
            merge_suggestions_into_state,
            suggest_followed_profiles_from_strategy,
        )

        existing_profiles = state.get("followed_profiles") or []
        exclude = [str(p.get("profile_url") or "") for p in existing_profiles if isinstance(p, dict)]
        try:
            result = suggest_followed_profiles_from_strategy(
                client,
                model,
                state,
                language,
                count=5,
                exclude_urls=exclude,
            )
            if result.get("success"):
                new_suggestions = (
                    result.get("suggestions") if isinstance(result.get("suggestions"), list) else []
                )
                state["followed_profile_suggestions"] = merge_suggestions_into_state(
                    state.get("followed_profile_suggestions") or [],
                    new_suggestions,
                )
                reply = str(result.get("reply") or "").strip()
                if not reply:
                    reply = (
                        "Sugeri perfis alinhados com a tua estratégia/ICP no painel. "
                        "Confirma os que queres seguir; depois importa publicações e "
                        "escolhe uma para eu propor um comentário."
                    )
                return {
                    "reply": reply,
                    "orchestration_mode": STAGE_FOLLOWED_FEED,
                    "workflow_state": state,
                    "deliverables": _deliverables_from_state(state),
                    "pending_actions": state["pending_actions"],
                    "agents_involved": [],
                }
        except Exception:  # noqa: BLE001
            pass

    profiles = state.get("followed_profiles") or []
    queue = state.get("followed_posts_queue") or []
    pending_posts = [
        p for p in queue if isinstance(p, dict) and (p.get("status") or "pending") == "pending"
    ]

    if "comentar" in normalized or "comentario" in normalized:
        if pending_posts:
            reply = (
                "Tens publicações na fila. Escolhe uma no painel **Comentar publicações** "
                "e clica «Sugerir comentário» — ou diz qual perfil te interessa."
            )
        elif profiles:
            reply = (
                "Já tens perfis na lista. Clica **Actualizar publicações** no painel "
                "para recolher posts e depois escolhe um para comentar."
            )
        else:
            reply = (
                "Para comentar publicações de terceiros: adiciona perfis "
                "(sugestão por ICP ou URL manual), importa o feed e escolhe um post."
            )
    elif wants_suggest and not strategy_ok:
        reply = (
            "Para sugerir perfis por ICP preciso de uma estratégia com objetivos e ICP — "
            "ou cola URLs LinkedIn manualmente no painel «Comentar publicações de perfis que sigo»."
        )
    elif profiles or state.get("followed_profile_suggestions"):
        reply = (
            "Abri o painel de **perfis e comentários**. Confirma sugestões, actualiza "
            "publicações e escolhe um post para eu propor comentário."
        )
    else:
        reply = (
            "Vamos aos **perfis para seguir e comentários**. No painel abaixo usa "
            "«Sugerir perfis (ICP)», «+ URL manual» ou «Importar feed». Depois escolhes "
            "uma publicação para eu sugerir comentário."
        )

    return {
        "reply": reply,
        "orchestration_mode": STAGE_FOLLOWED_FEED,
        "workflow_state": state,
        "deliverables": _deliverables_from_state(state),
        "pending_actions": state["pending_actions"],
        "agents_involved": [],
    }


def _is_design_only_request(normalized: str) -> bool:
    """Deteta pedido de imagem/criativo genérico (sem canal LinkedIn/Instagram).

    Argumentos:
        normalized: Última mensagem normalizada.

    Retorno:
        ``True`` para pedidos como «criar uma imagem para uma publicação».
    """

    if text_mentions_linkedin(normalized):
        return False
    if any(m in normalized for m in _INSTAGRAM_MARKERS):
        return False
    image_markers = (
        "imagem",
        "criativo",
        "visual",
        "design",
        "ilustracao",
        "ilustração",
        "foto",
        "banner",
        "mockup",
    )
    return any(marker in normalized for marker in image_markers)


def _is_copy_only_request(normalized: str) -> bool:
    """Deteta pedido de copy/texto genérico (sem canal LinkedIn/Instagram).

    Argumentos:
        normalized: Última mensagem normalizada.

    Retorno:
        ``True`` para pedidos como «texto para uma publicação» sem rede explícita.
    """

    if text_mentions_linkedin(normalized):
        return False
    if any(m in normalized for m in _INSTAGRAM_MARKERS):
        return False
    if _is_design_only_request(normalized):
        return False
    copy_markers = (
        "copy",
        "texto",
        "legenda",
        "headline",
        "slogan",
        "publicacao",
        "publicação",
        "caption",
        "gancho",
        "cta",
    )
    return any(marker in normalized for marker in copy_markers)


def _handle_standalone_copy_request(
    state: Dict[str, Any],
    sanitized: Sequence[Dict[str, str]],
    language: str,
    *,
    agent_page_url: Callable[[str], str],
) -> Dict[str, Any]:
    """Gera copy via Copywriter sem assumir LinkedIn nem calendário.

    Argumentos:
        state: Estado mutável do workflow.
        sanitized: Histórico da conversa.
        language: Idioma da copy.
        agent_page_url: Resolver URL dos agentes para ``team_tasks``.

    Retorno:
        Payload parcial com copy em ``deliverables`` e estágio ``copy_review``.
    """

    conversation = build_conversation_brief(sanitized)
    try:
        copy_result = _generate_campaign_copy(
            conversation,
            "Gerar copy de marketing conforme o pedido do utilizador (canal genérico, sem LinkedIn).",
            language,
        )
        post = post_from_copywriter(copy_result, channel="geral")
        state["copy"] = copy_result
        state["post"] = post
        state["image"] = None
        state["standalone_image"] = False
        state["channels"] = ["geral"]
        state["stage"] = STAGE_COPY_REVIEW
        state["pending_actions"] = [ACTION_APPROVE_COPY, ACTION_EDIT_COPY]
        summary = _copy_summary_for_ui(copy_result, post)
        return {
            "reply": (
                "Tratei isto como copy geral — **não** assumi LinkedIn. "
                "Revê o texto no painel; aprova ou edita antes de pedires imagem."
            ),
            "orchestration_mode": STAGE_COPY_REVIEW,
            "workflow_state": state,
            "deliverables": _deliverables_from_state(state),
            "pending_actions": state["pending_actions"],
            "team_tasks": [
                build_team_task_payload(
                    {
                        "agent_name": "Agente Copywriter",
                        "status": "completed",
                        "summary": summary[:1500],
                        "error": None,
                    },
                    agent_page_url,
                )
            ],
            "agents_involved": ["Agente Copywriter"],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "reply": f"Não consegui gerar a copy agora: {exc!s}",
            "orchestration_mode": STAGE_PLANNING,
            "workflow_state": state,
            "deliverables": _deliverables_from_state(state),
            "pending_actions": [],
        }


def _handle_standalone_design_request(
    state: Dict[str, Any],
    sanitized: Sequence[Dict[str, str]],
    language: str,
    *,
    agent_page_url: Callable[[str], str],
) -> Dict[str, Any]:
    """Gera imagem via Designer sem assumir LinkedIn nem post de calendário.

    Argumentos:
        state: Estado mutável do workflow.
        sanitized: Histórico da conversa.
        language: Idioma (reservado para mensagens futuras).
        agent_page_url: Resolver URL dos agentes para ``team_tasks``.

    Retorno:
        Payload parcial com imagem em ``deliverables`` e estágio ``image_review``.
    """

    _ = language
    if not designer_agent.is_configured():
        return {
            "reply": (
                "Para gerar imagens aqui, configura NANO_BANANA ou OPENAI_IMAGE no servidor. "
                "O pedido não foi associado ao LinkedIn."
            ),
            "orchestration_mode": STAGE_PLANNING,
            "workflow_state": state,
            "deliverables": _deliverables_from_state(state),
            "pending_actions": [],
        }

    try:
        image_result = designer_agent.generate_image_from_chat(
            [dict(m) for m in sanitized if isinstance(m, dict)],
        )
        state["image"] = image_result
        state["post"] = None
        state["copy"] = None
        state["standalone_image"] = True
        state["channels"] = ["geral"]
        state["stage"] = STAGE_IMAGE_REVIEW
        state["pending_actions"] = [ACTION_APPROVE_IMAGE, ACTION_REGENERATE_IMAGE]
        return {
            "reply": (
                "Tratei isto como criativo visual geral — **não** assumi LinkedIn. "
                "Revê a imagem no painel; podes aprovar, regenerar ou pedir ajustes no chat."
            ),
            "orchestration_mode": STAGE_IMAGE_REVIEW,
            "workflow_state": state,
            "deliverables": _deliverables_from_state(state),
            "pending_actions": state["pending_actions"],
            "team_tasks": [
                build_team_task_payload(
                    {
                        "agent_name": "Agente Designer",
                        "status": "completed",
                        "summary": f"Imagem: {image_result.get('image_url', '')}",
                        "error": None,
                    },
                    agent_page_url,
                )
            ],
            "agents_involved": ["Agente Designer"],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "reply": f"Não consegui gerar a imagem agora: {exc!s}",
            "orchestration_mode": STAGE_PLANNING,
            "workflow_state": state,
            "deliverables": _deliverables_from_state(state),
            "pending_actions": [],
        }


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

    if text_mentions_linkedin(normalized) and any(
        marker in normalized for marker in _PLATFORM_OPERATION_MARKERS
    ):
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
    elif state.get("stage") == STAGE_PUBLISH_CONFIRM:
        reply = (
            "Estás na etapa de **publicação**. Usa os botões no painel: autoriza o LinkedIn, "
            "publica o post ou avança sem publicar."
        )
        state["pending_actions"] = [ACTION_SKIP_PUBLISH]
    elif state.get("stage") in {STAGE_ENGAGEMENT_REVIEW, STAGE_FOLLOWED_FEED}:
        reply = (
            "Gere comentários para **publicações de perfis que segues**. "
            "Adiciona perfis, actualiza o feed e escolhe uma publicação — "
            "aprovas ou reprovas o comentário antes de ir comentar no LinkedIn."
        )
        state["pending_actions"] = [
            ACTION_SELECT_FOLLOWED_POST,
            ACTION_GENERATE_ENGAGEMENT,
        ]
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
        "linkedin_posts": state.get("linkedin_posts") or [],
        "linkedin_calendar": state.get("linkedin_calendar") or [],
        "linkedin_analysis_baseline": state.get("linkedin_analysis_baseline"),
        "optimization_report": state.get("optimization_report"),
        "active_post_index": state.get("active_post_index", 0),
        "post": state.get("post"),
        "copy": state.get("copy"),
        "image": state.get("image"),
        "followed_profiles": state.get("followed_profiles") or [],
        "followed_profile_suggestions": state.get("followed_profile_suggestions") or [],
        "followed_posts_queue": state.get("followed_posts_queue") or [],
        "active_followed_post_id": state.get("active_followed_post_id") or "",
        "engagement_draft": state.get("engagement_draft"),
        "engagement_batch": state.get("engagement_batch") or [],
        "engagement_log": state.get("engagement_log") or [],
        "daily_digest": state.get("daily_digest"),
        "last_daily_digest_at": state.get("last_daily_digest_at") or "",
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


def _sync_calendar_entry(
    state: Dict[str, Any],
    post_id: str,
    post_data: Dict[str, Any],
    *,
    status: Optional[str] = None,
) -> None:
    """Actualiza um post no calendário editorial do Diretor."""

    calendar = state.get("linkedin_calendar") or []
    for entry in calendar:
        if str(entry.get("post_id")) == str(post_id):
            entry["post"] = post_data
            if status:
                entry["status"] = status
            break
    state["linkedin_calendar"] = calendar


def _package_post_ready(state: Dict[str, Any]) -> None:
    """Marca o post activo como pronto (copy + imagem aprovadas)."""

    post = dict(state.get("post") or {})
    image = state.get("image") if isinstance(state.get("image"), dict) else None
    post = attach_approved_image_to_post(post, image)
    post["status"] = "ready"
    state["post"] = post
    post_id = str(post.get("id") or "")
    if post_id:
        _sync_calendar_entry(state, post_id, post, status="ready")


def _enter_publish_confirm(state: Dict[str, Any]) -> str:
    """Prepara etapa de publicação LinkedIn no painel do Diretor.

    Argumentos:
        state: Estado mutável do workflow.

    Retorno:
        Mensagem ao utilizador.
    """

    state["image"] = None
    state["copy"] = None
    state["stage"] = STAGE_PUBLISH_CONFIRM
    state["pending_actions"] = [ACTION_SKIP_PUBLISH]
    has_image = bool((state.get("post") or {}).get("generated_image_url"))
    if has_image:
        return (
            "Pacote aprovado. Autoriza a publicação no LinkedIn (se ainda não fizeste) "
            "e clica em «Publicar» no painel — texto + imagem ou só texto. "
            "Também podes avançar sem publicar agora."
        )
    return (
        "Copy aprovada. Autoriza e publica no LinkedIn no painel, "
        "ou avança sem publicar para o próximo passo."
    )


def _start_comment_review_for_followed_post(
    *,
    client: OpenAI,
    model: str,
    state: Dict[str, Any],
    language: str,
    followed_post: Dict[str, Any],
) -> str:
    """Gera comentário para uma publicação de perfil seguido.

    Argumentos:
        client: Cliente OpenAI.
        model: Modelo LLM.
        state: Estado do workflow.
        language: Idioma.
        followed_post: Post da fila (autor, URL, texto).

    Retorno:
        Mensagem ao utilizador.
    """

    draft = generate_comment_for_followed_post(
        client, model, state, followed_post, language
    )
    state["engagement_draft"] = draft
    state["active_followed_post_id"] = str(followed_post.get("id") or "")
    queue = update_followed_post_status(
        state.get("followed_posts_queue") or [],
        str(followed_post.get("id") or ""),
        "draft",
    )
    state["followed_posts_queue"] = queue
    state["stage"] = STAGE_ENGAGEMENT_REVIEW
    state["pending_actions"] = [
        ACTION_APPROVE_ENGAGEMENT,
        ACTION_REJECT_ENGAGEMENT,
        ACTION_REGENERATE_ENGAGEMENT,
    ]
    author = str(followed_post.get("author_name") or "autor")
    return (
        f"Sugeri um comentário para a publicação de **{author}**. "
        "Revê no painel — aprova para copiar e ir comentar, ou reprova."
    )


def _start_engagement_batch_review(
    *,
    client: OpenAI,
    model: str,
    state: Dict[str, Any],
    language: str,
    count: int = DEFAULT_ENGAGEMENT_BATCH_SIZE,
) -> Dict[str, Any]:
    """Gera lote de comentários para várias publicações da fila.

    Argumentos:
        client: Cliente OpenAI.
        model: Modelo LLM.
        state: Estado mutável do workflow.
        language: Idioma.
        count: Número de publicações (máx. 15).

    Retorno:
        Payload parcial com ``engagement_batch`` e estágio ``engagement_batch_review``.
    """

    posts = pick_posts_for_engagement_batch(
        state.get("followed_posts_queue") or [],
        count=count,
    )
    if not posts:
        state["stage"] = STAGE_FOLLOWED_FEED
        state["pending_actions"] = [
            ACTION_SELECT_FOLLOWED_POST,
            ACTION_GENERATE_ENGAGEMENT,
            ACTION_GENERATE_ENGAGEMENT_BATCH,
        ]
        return {
            "reply": (
                "Não há publicações pendentes na fila. Adiciona perfis, importa o feed "
                "e clica em «Actualizar publicações»."
            ),
            "orchestration_mode": STAGE_FOLLOWED_FEED,
            "workflow_state": state,
            "pending_actions": state["pending_actions"],
        }

    drafts = generate_comments_batch(client, model, state, posts, language)
    state["engagement_batch"] = drafts
    state["engagement_draft"] = None
    state["stage"] = STAGE_ENGAGEMENT_BATCH_REVIEW
    state["pending_actions"] = [
        ACTION_APPROVE_ENGAGEMENT_BATCH,
        ACTION_DISMISS_ENGAGEMENT_BATCH,
    ]
    n = len(drafts)
    return {
        "reply": (
            f"Preparei **{n} comentários** para publicações diferentes. "
            "Marca os que queres aprovar no painel (podes editar o texto) e clica "
            "«Aprovar seleccionados» — depois copias e colas no LinkedIn."
        ),
        "orchestration_mode": STAGE_ENGAGEMENT_BATCH_REVIEW,
        "workflow_state": state,
        "pending_actions": state["pending_actions"],
    }


def _advance_calendar_or_complete(state: Dict[str, Any]) -> str:
    """Avança no calendário após publicar, saltar ou engagement concluído.

    Argumentos:
        state: Estado mutável do workflow.

    Retorno:
        Mensagem de progresso.
    """

    state["engagement_draft"] = None
    calendar = state.get("linkedin_calendar") or []
    if not calendar:
        state["stage"] = STAGE_COMPLETED
        state["pending_actions"] = []
        state["post"] = None
        return "Fluxo concluído."

    done_statuses = frozenset({"ready", "published"})
    done_count = sum(
        1 for e in calendar if isinstance(e, dict) and e.get("status") in done_statuses
    )
    published_count = sum(
        1 for e in calendar if isinstance(e, dict) and e.get("status") == "published"
    )
    total = len(calendar)

    pending = [
        e for e in calendar
        if isinstance(e, dict) and str(e.get("status") or "draft") == "draft"
    ]
    if not pending and done_count >= total:
        state["stage"] = STAGE_COMPLETED
        state["pending_actions"] = []
        state["post"] = None
        return (
            f"Semana concluída — {total} posts processados "
            f"({published_count} publicados no LinkedIn)."
        )

    state["stage"] = STAGE_POSTS_REVIEW
    state["pending_actions"] = [ACTION_SELECT_POST]
    state["post"] = None
    return (
        f"Progresso: {done_count}/{total} posts. "
        "Escolhe o próximo dia no calendário."
    )


def _advance_after_post_packaged(state: Dict[str, Any]) -> str:
    """Marca post pronto e abre etapa de publicação (Fase D)."""

    _package_post_ready(state)
    return _enter_publish_confirm(state)


def _select_calendar_post(state: Dict[str, Any], post_id: str) -> bool:
    """Carrega um post do calendário para revisão de copy/imagem.

    Argumentos:
        state: Estado do workflow.
        post_id: Identificador do post no calendário.

    Retorno:
        ``True`` se o post foi encontrado e carregado.
    """

    calendar = state.get("linkedin_calendar") or []
    for idx, entry in enumerate(calendar):
        if str(entry.get("post_id")) != str(post_id):
            continue
        raw = entry.get("post") if isinstance(entry.get("post"), dict) else {}
        state["post"] = editor_post_from_linkedin(raw)
        state["active_post_index"] = idx
        state["stage"] = STAGE_COPY_REVIEW
        state["pending_actions"] = [
            ACTION_APPROVE_COPY,
            ACTION_EDIT_COPY,
            ACTION_REGENERATE_LINKEDIN_POST,
        ]
        state["image"] = None
        state["copy"] = None
        return True
    return False


def _start_execution_from_strategy(
    *,
    state: Dict[str, Any],
    sanitized: Sequence[Dict[str, str]],
    language: str,
    reply_prefix: str = "",
) -> Dict[str, Any]:
    """Inicia execução: posts da semana (com análise) ou copy única (fallback).

    Argumentos:
        state: Estado com estratégia e opcionalmente análise LinkedIn.
        sanitized: Histórico da conversa.
        language: Idioma.
        reply_prefix: Texto introdutório opcional.

    Retorno:
        Payload com posts/calendário ou copy única.

    Raises:
        RuntimeError: Falha na geração.
    """

    strategy = state.get("strategy") or {}
    if state.get("linkedin_analysis") and strategy_has_core_content(strategy):
        posts, calendar = generate_director_linkedin_posts(state, language)
        state["linkedin_posts"] = posts
        state["linkedin_calendar"] = calendar
        if not calendar:
            raise RuntimeError("Não consegui gerar posts para a semana.")
        first = calendar[0]
        state["post"] = editor_post_from_linkedin(first.get("post") or {})
        state["active_post_index"] = 0
        state["stage"] = STAGE_COPY_REVIEW
        state["pending_actions"] = [
            ACTION_APPROVE_COPY,
            ACTION_EDIT_COPY,
            ACTION_REGENERATE_LINKEDIN_POST,
        ]
        state["image"] = None
        state["copy"] = None
        prefix = f"{reply_prefix}\n\n" if reply_prefix else ""
        count = len(calendar)
        return {
            "reply": (
                f"{prefix}"
                f"A equipa gerou **{count} posts** para a semana, alinhados com a tua estratégia. "
                "Revê o calendário abaixo e o primeiro post — aprova a copy e depois a imagem."
            ).strip(),
            "orchestration_mode": STAGE_COPY_REVIEW,
            "workflow_state": state,
            "pending_actions": state["pending_actions"],
            "deliverables": _deliverables_from_state(state),
            "agents_involved": ["Agente LinkedIn (perfil)", "Agente Copywriter"],
        }

    prefix_note = (
        "Nota: liga e analisa o perfil LinkedIn para gerar o calendário semanal completo. "
        "Por agora preparei só um post com base na estratégia.\n\n"
    )
    return _start_copy_from_strategy(
        state=state,
        sanitized=sanitized,
        language=language,
        reply_prefix=f"{reply_prefix}\n\n{prefix_note}".strip() if reply_prefix else prefix_note.strip(),
    )


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


def _classify_user_intent_with_fallback(
    client: OpenAI,
    model: str,
    sanitized: Sequence[Dict[str, str]],
    state: Dict[str, Any],
    language: str,
    last_user_text: str,
    normalize_text_fn: Callable[[str], str],
) -> Dict[str, Any]:
    """Classifica intenção com OpenAI e reforça com fallback por keywords.

    Argumentos:
        client: Cliente OpenAI.
        model: Modelo LLM.
        sanitized: Histórico da conversa.
        state: Estado do workflow.
        language: Idioma.
        last_user_text: Última mensagem do utilizador.
        normalize_text_fn: Função de normalização injectada pelo router.

    Retorno:
        Dicionário de classificação (``intent``, ``confidence``, etc.).
    """

    try:
        classification = classify_director_intent(
            client, model, sanitized, state, language
        )
    except Exception:  # noqa: BLE001
        classification = {
            "intent": "general_plan",
            "confidence": 0.0,
            "user_goal": "",
            "auto_suggest_profiles": False,
            "reply": "",
        }

    intent = str(classification.get("intent") or "general_plan")
    confidence = float(classification.get("confidence") or 0)
    normalized = normalize_text_fn(last_user_text)

    if confidence < 0.55 and intent in {"general_plan", "continue_current", "clarify"}:
        if _is_followed_engagement_intent(normalized):
            classification["intent"] = "followed_profiles"
            classification["confidence"] = 0.82
            classification["auto_suggest_profiles"] = _wants_auto_suggest_followed_profiles(
                normalized
            )
        elif _is_design_only_request(normalized) and not text_mentions_linkedin(normalized):
            classification["intent"] = "standalone_image"
            classification["confidence"] = 0.78
        elif _is_copy_only_request(normalized):
            classification["intent"] = "standalone_copy"
            classification["confidence"] = 0.78
        elif _should_enter_linkedin_strategy(state, last_user_text):
            classification["intent"] = "linkedin_strategy"
            classification["confidence"] = 0.75
        elif any(
            m in normalized
            for m in (
                "lote de coment",
                "varios coment",
                "vários coment",
                "10 coment",
                "15 coment",
                "comentarios em lote",
            )
        ):
            classification["intent"] = "engagement_batch"
            classification["confidence"] = 0.8
        elif any(m in normalized for m in ("briefing", "analise diaria", "análise diária", "resumo do dia")):
            classification["intent"] = "daily_digest"
            classification["confidence"] = 0.75

    return classification


def _apply_director_intent_classification(
    classification: Dict[str, Any],
    *,
    state: Dict[str, Any],
    sanitized: Sequence[Dict[str, str]],
    last_user_text: str,
    language: str,
    client: OpenAI,
    model: str,
    agent_page_url: Callable[[str], str],
    normalize_text_fn: Callable[[str], str],
    allow_continue: bool = True,
) -> Optional[Dict[str, Any]]:
    """Executa o fluxo correspondente à intenção classificada pelo LLM.

    Argumentos:
        classification: Resultado de ``_classify_user_intent_with_fallback``.
        state: Estado mutável do workflow.
        sanitized: Histórico da conversa.
        last_user_text: Última mensagem do utilizador.
        language: Idioma.
        client: Cliente OpenAI.
        model: Modelo LLM.
        agent_page_url: Resolver URLs dos agentes.
        normalize_text_fn: Normalização de texto.
        allow_continue: Se ``False``, ignora ``continue_current`` e ``general_plan``
            mas tenta rotear pedidos concretos (útil em ``strategy_approved``).

    Retorno:
        Payload parcial para ``base_response``, ou ``None`` para continuar o fluxo.
    """

    intent = str(classification.get("intent") or "general_plan")
    confidence = float(classification.get("confidence") or 0)
    min_confidence = 0.4

    if allow_continue and intent == "continue_current":
        return None
    if intent == "general_plan" and allow_continue:
        return None
    if confidence < min_confidence and intent != "clarify":
        return None

    normalized = normalize_text_fn(last_user_text)
    stage = str(state.get("stage") or STAGE_IDLE)

    if intent == "clarify":
        return {
            "reply": (
                classification.get("reply")
                or "Podes explicar um pouco melhor o que queres fazer?"
            ),
            "orchestration_mode": stage,
            "workflow_state": state,
            "deliverables": _deliverables_from_state(state),
            "pending_actions": state.get("pending_actions") or [],
            "agents_involved": [],
        }

    if intent == "daily_digest":
        try:
            return run_daily_digest(client, model, state, language)
        except Exception as exc:  # noqa: BLE001
            return {
                "reply": f"Não consegui gerar o briefing diário: {exc!s}",
                "orchestration_mode": str(state.get("stage") or STAGE_IDLE),
                "workflow_state": state,
            }

    if intent == "engagement_batch":
        count = int(classification.get("batch_count") or DEFAULT_ENGAGEMENT_BATCH_SIZE)
        return _start_engagement_batch_review(
            client=client,
            model=model,
            state=state,
            language=language,
            count=count,
        )

    if intent in {"followed_profiles", "engagement_comment"}:
        auto_flag = classification.get("auto_suggest_profiles")
        if intent == "engagement_comment" and not auto_flag:
            auto_flag = False
        elif intent == "followed_profiles" and auto_flag is None:
            auto_flag = True
        return _handle_followed_engagement_chat_intent(
            state,
            normalized,
            client,
            model,
            language,
            auto_suggest=auto_flag,
        )

    if intent == "standalone_image" and not text_mentions_linkedin(normalized):
        if stage in {
            STAGE_COPY_REVIEW,
            STAGE_IMAGE_REVIEW,
            STAGE_PUBLISH_CONFIRM,
            STAGE_ENGAGEMENT_REVIEW,
        }:
            return None
        return _handle_standalone_design_request(
            state, sanitized, language, agent_page_url=agent_page_url
        )

    if intent == "standalone_copy" and not text_mentions_linkedin(normalized):
        if stage in {STAGE_COPY_REVIEW, STAGE_PUBLISH_CONFIRM, STAGE_ENGAGEMENT_REVIEW}:
            return None
        return _handle_standalone_copy_request(
            state, sanitized, language, agent_page_url=agent_page_url
        )

    if intent == "linkedin_strategy":
        if stage in {STAGE_STRATEGY_BRIEF, STAGE_STRATEGY_REVIEW} and allow_continue:
            return None
        return _generate_and_review_strategy(
            client=client,
            model=model,
            messages=sanitized,
            language=language,
            state=state,
            previous_strategy=state.get("strategy"),
        )

    if intent == "linkedin_posts":
        if not state.get("strategy"):
            return {
                "reply": (
                    "Para gerar posts preciso primeiro de uma estratégia LinkedIn. "
                    "Descreve os teus objectivos e eu monto o plano."
                ),
                "orchestration_mode": stage,
                "workflow_state": state,
                "deliverables": _deliverables_from_state(state),
                "pending_actions": state.get("pending_actions") or [],
            }
        try:
            return _start_execution_from_strategy(
                state=state,
                sanitized=sanitized,
                language=language,
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "reply": f"Não consegui gerar os posts: {exc!s}",
                "orchestration_mode": stage,
                "workflow_state": state,
                "deliverables": _deliverables_from_state(state),
                "pending_actions": state.get("pending_actions") or [],
            }

    if intent == "linkedin_optimization":
        if not strategy_has_core_content(state.get("strategy") or {}):
            return {
                "reply": "Preciso de uma estratégia aprovada antes de optimizar.",
                "orchestration_mode": stage,
                "workflow_state": state,
                "deliverables": _deliverables_from_state(state),
            }
        if not isinstance(state.get("linkedin_analysis"), dict):
            return {
                "reply": "Analisa o perfil LinkedIn no painel antes de pedir optimização.",
                "orchestration_mode": stage,
                "workflow_state": state,
                "deliverables": _deliverables_from_state(state),
            }
        try:
            opt = generate_optimization_report(client, model, state, language)
            report = opt.get("report") if isinstance(opt.get("report"), dict) else {}
            state["optimization_report"] = report
            state["stage"] = STAGE_OPTIMIZATION_REVIEW
            state["pending_actions"] = [
                ACTION_APPROVE_OPTIMIZATION,
                ACTION_DISMISS_OPTIMIZATION,
            ]
            reply = str(opt.get("reply") or "").strip() or (
                "Comparei as métricas com a tua estratégia. Revê o relatório no painel."
            )
            return {
                "reply": reply,
                "orchestration_mode": STAGE_OPTIMIZATION_REVIEW,
                "workflow_state": state,
                "deliverables": _deliverables_from_state(state),
                "pending_actions": state["pending_actions"],
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "reply": f"Não consegui gerar optimização: {exc!s}",
                "orchestration_mode": stage,
                "workflow_state": state,
                "deliverables": _deliverables_from_state(state),
            }

    if not allow_continue and intent == "general_plan":
        goal = str(classification.get("user_goal") or "").strip()
        hint = f" Percebi: {goal}." if goal else ""
        return {
            "reply": (
                f"{hint} Podes pedir posts da estratégia, perfis para seguir, "
                "comentários, copy, imagem ou outra tarefa — diz o que preferes."
            ).strip(),
            "orchestration_mode": stage,
            "workflow_state": state,
            "deliverables": _deliverables_from_state(state),
            "pending_actions": state.get("pending_actions") or [],
        }

    return None


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

    intent_classification: Optional[Dict[str, Any]] = None
    if last_user_text and not user_action and not inferred:
        intent_classification = _classify_user_intent_with_fallback(
            client,
            openai_model,
            sanitized,
            state,
            language,
            last_user_text,
            normalize_text,
        )
        routed = _apply_director_intent_classification(
            intent_classification,
            state=state,
            sanitized=sanitized,
            last_user_text=last_user_text,
            language=language,
            client=client,
            model=openai_model,
            agent_page_url=agent_page_url,
            normalize_text_fn=normalize_text,
            allow_continue=True,
        )
        if routed is not None:
            base_response.update(routed)
            return base_response

    if action == ACTION_RUN_DAILY_DIGEST:
        try:
            digest_result = run_daily_digest(
                client, openai_model, state, language
            )
            base_response.update(digest_result)
            base_response["deliverables"] = _deliverables_from_state(state)
            return base_response
        except Exception as exc:  # noqa: BLE001
            base_response["reply"] = f"Não consegui gerar o briefing diário: {exc!s}"
            return base_response

    # --- Estratégia LinkedIn ---
    if action == ACTION_APPROVE_STRATEGY and state["stage"] == STAGE_STRATEGY_REVIEW:
        state["stage"] = STAGE_STRATEGY_APPROVED
        state["pending_actions"] = [ACTION_START_EXECUTION]
        baseline = state.get("linkedin_analysis")
        if isinstance(baseline, dict):
            state["linkedin_analysis_baseline"] = json.loads(
                json.dumps(baseline, ensure_ascii=False)
            )
        strategy = state.get("strategy") or {}
        base_response["reply"] = (
            "Estratégia aprovada. Clica em «Iniciar execução» para a equipa gerar "
            "os posts da semana (se o perfil estiver analisado) ou o primeiro post."
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
            result = _start_execution_from_strategy(
                state=state,
                sanitized=sanitized,
                language=language,
                reply_prefix="Estratégia confirmada.",
            )
            base_response.update(result)
            agents = result.get("agents_involved") or ["Agente Copywriter"]
            base_response["team_tasks"] = [
                build_team_task_payload(
                    {
                        "agent_name": agents[0],
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
        if intent_classification is None:
            intent_classification = _classify_user_intent_with_fallback(
                client,
                openai_model,
                sanitized,
                state,
                language,
                last_user_text,
                normalize_text,
            )
        routed = _apply_director_intent_classification(
            intent_classification,
            state=state,
            sanitized=sanitized,
            last_user_text=last_user_text,
            language=language,
            client=client,
            model=openai_model,
            agent_page_url=agent_page_url,
            normalize_text_fn=normalize_text,
            allow_continue=False,
        )
        if routed is not None:
            base_response.update(routed)
            return base_response
        normalized_approved = normalize_text(last_user_text)
        if _is_copy_or_design_request(normalized_approved) or (
            "post" in normalized_approved and "seguir" not in normalized_approved
        ):
            try:
                result = _start_execution_from_strategy(
                    state=state,
                    sanitized=sanitized,
                    language=language,
                )
                base_response.update(result)
                return base_response
            except Exception as exc:  # noqa: BLE001
                base_response["reply"] = f"Não consegui gerar os posts: {exc!s}"
                return base_response
        goal = str((intent_classification or {}).get("user_goal") or "").strip()
        hint = f" Percebi: {goal}." if goal else ""
        base_response["reply"] = (
            f"{hint} A estratégia está aprovada — podes pedir posts, perfis para seguir, "
            "comentários, copy ou imagem. Diz o que queres fazer agora."
        ).strip()
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

    # --- Ciclo análise → otimização (Fase C) ---
    if action == ACTION_REANALYZE_COMPLETE:
        if not strategy_has_core_content(state.get("strategy") or {}):
            base_response["reply"] = (
                "Preciso de uma estratégia aprovada antes de optimizar. "
                "Define objetivos e aprova o plano primeiro."
            )
            return base_response
        if not isinstance(state.get("linkedin_analysis"), dict):
            base_response["reply"] = "Analisa o perfil LinkedIn antes de pedir optimização."
            return base_response
        try:
            opt = generate_optimization_report(client, openai_model, state, language)
            report = opt.get("report") if isinstance(opt.get("report"), dict) else {}
            state["optimization_report"] = report
            state["stage"] = STAGE_OPTIMIZATION_REVIEW
            state["pending_actions"] = [
                ACTION_APPROVE_OPTIMIZATION,
                ACTION_DISMISS_OPTIMIZATION,
            ]
            reply = str(opt.get("reply") or "").strip()
            if not reply:
                reply = (
                    "Comparei as métricas com a tua estratégia. "
                    "Revê o relatório de optimização no painel."
                )
            base_response["reply"] = reply
            base_response["orchestration_mode"] = STAGE_OPTIMIZATION_REVIEW
            base_response["workflow_state"] = state
            base_response["pending_actions"] = state["pending_actions"]
            base_response["deliverables"] = _deliverables_from_state(state)
        except Exception as exc:  # noqa: BLE001
            base_response["reply"] = f"Não consegui gerar o relatório de optimização: {exc!s}"
        return base_response

    if action == ACTION_APPROVE_OPTIMIZATION and state["stage"] == STAGE_OPTIMIZATION_REVIEW:
        report = state.get("optimization_report") or {}
        if optimization_has_content(report):
            state["strategy"] = apply_optimization_to_strategy(
                state.get("strategy") or {},
                report,
                current_analysis=state.get("linkedin_analysis"),
            )
            state["execution_plan"] = state["strategy"].get("summary") or state.get("execution_plan", "")
        state["optimization_report"] = None
        state["stage"] = STAGE_STRATEGY_REVIEW
        state["pending_actions"] = [ACTION_APPROVE_STRATEGY, ACTION_START_EXECUTION]
        base_response["reply"] = (
            "Apliquei as optimizações à estratégia. Revê o plano actualizado no painel — "
            "aprova de novo ou inicia execução para gerar posts alinhados."
        )
        base_response["orchestration_mode"] = STAGE_STRATEGY_REVIEW
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state["pending_actions"]
        base_response["deliverables"] = _deliverables_from_state(state)
        base_response["execution_plan"] = state.get("execution_plan", "")
        return base_response

    if action == ACTION_DISMISS_OPTIMIZATION and state["stage"] == STAGE_OPTIMIZATION_REVIEW:
        state["optimization_report"] = None
        if state.get("linkedin_calendar"):
            state["stage"] = STAGE_POSTS_REVIEW
            state["pending_actions"] = [ACTION_SELECT_POST]
            msg = "Mantive a estratégia actual. Continua no calendário quando quiseres."
        elif strategy_has_core_content(state.get("strategy") or {}):
            state["stage"] = STAGE_STRATEGY_APPROVED
            state["pending_actions"] = [ACTION_START_EXECUTION]
            msg = "Mantive a estratégia actual. Podes iniciar execução ou reanalisar mais tarde."
        else:
            state["stage"] = STAGE_IDLE
            state["pending_actions"] = []
            msg = "Relatório dispensado."
        base_response["reply"] = msg
        base_response["orchestration_mode"] = state["stage"]
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state.get("pending_actions") or []
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if state["stage"] == STAGE_OPTIMIZATION_REVIEW and not user_action:
        base_response["reply"] = (
            "Revê o relatório de optimização no painel. "
            "Aplica os ajustes à estratégia ou mantém o plano actual."
        )
        base_response["orchestration_mode"] = STAGE_OPTIMIZATION_REVIEW
        base_response["workflow_state"] = state
        base_response["pending_actions"] = [
            ACTION_APPROVE_OPTIMIZATION,
            ACTION_DISMISS_OPTIMIZATION,
        ]
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    # --- Publicação e engagement LinkedIn (Fase D) ---
    if action == ACTION_MARK_PUBLISHED:
        post_id = str(payload.get("post_id") or (state.get("post") or {}).get("id") or "")
        urn = str(payload.get("linkedin_post_urn") or "").strip()
        with_image = bool(payload.get("published_with_image"))
        if post_id and urn:
            mark_post_published(
                state,
                post_id=post_id,
                linkedin_post_urn=urn,
                published_with_image=with_image,
            )
        msg = _advance_calendar_or_complete(state)
        base_response["reply"] = f"Publicado no LinkedIn. {msg}"
        base_response["orchestration_mode"] = state["stage"]
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state.get("pending_actions") or []
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_SKIP_PUBLISH and state["stage"] == STAGE_PUBLISH_CONFIRM:
        msg = _advance_calendar_or_complete(state)
        base_response["reply"] = msg
        base_response["orchestration_mode"] = state["stage"]
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state.get("pending_actions") or []
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    # --- Comentários em publicações de perfis seguidos ---
    if action == ACTION_ADD_FOLLOWED_PROFILE:
        url = str(payload.get("profile_url") or "").strip()
        name = str(payload.get("display_name") or "").strip() or None
        if not url or "linkedin.com" not in url.casefold():
            base_response["reply"] = "Indica um URL LinkedIn válido (ex.: https://linkedin.com/in/nome)."
            return base_response
        profiles = state.get("followed_profiles") or []
        if any(str(p.get("profile_url") or "").rstrip("/") == url.rstrip("/") for p in profiles if isinstance(p, dict)):
            base_response["reply"] = "Esse perfil já está na lista."
        else:
            profiles.append(normalize_followed_profile(url, name))
            state["followed_profiles"] = profiles
            state["stage"] = STAGE_FOLLOWED_FEED
            base_response["reply"] = (
                f"Perfil adicionado. Clica em «Actualizar publicações» para ver posts recentes "
                f"e escolhe um para eu sugerir um comentário."
            )
        base_response["orchestration_mode"] = state.get("stage") or STAGE_FOLLOWED_FEED
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_REMOVE_FOLLOWED_PROFILE:
        pid = str(payload.get("profile_id") or "").strip()
        profiles = [p for p in (state.get("followed_profiles") or []) if str(p.get("id")) != pid]
        state["followed_profiles"] = profiles
        base_response["reply"] = "Perfil removido da lista."
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_SUGGEST_FOLLOWED_PROFILES:
        from agents.director_follow_suggestions import (
            merge_suggestions_into_state,
            suggest_followed_profiles_from_strategy,
        )

        if not copywriter_agent.is_configured():
            base_response["reply"] = "OPENAI_API_KEY em falta — não consigo sugerir perfis."
            return base_response

        existing_profiles = state.get("followed_profiles") or []
        exclude = [str(p.get("profile_url") or "") for p in existing_profiles if isinstance(p, dict)]
        try:
            result = suggest_followed_profiles_from_strategy(
                client,
                openai_model,
                state,
                language,
                count=int(payload.get("count") or 5),
                exclude_urls=exclude,
            )
        except Exception as exc:
            base_response["reply"] = f"Não consegui sugerir perfis: {exc}"
            return base_response

        if not result.get("success"):
            base_response["reply"] = str(result.get("reply") or "Sem sugestões.")
            return base_response

        new_suggestions = result.get("suggestions") if isinstance(result.get("suggestions"), list) else []
        state["followed_profile_suggestions"] = merge_suggestions_into_state(
            state.get("followed_profile_suggestions") or [],
            new_suggestions,
        )
        state["stage"] = STAGE_FOLLOWED_FEED
        base_response["reply"] = str(result.get("reply") or "Sugestões prontas no painel.")
        base_response["orchestration_mode"] = STAGE_FOLLOWED_FEED
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_ACCEPT_FOLLOWED_SUGGESTIONS:
        from agents.director_follow_suggestions import accept_followed_suggestions

        ids = payload.get("suggestion_ids")
        id_list = ids if isinstance(ids, list) else []
        merged = accept_followed_suggestions(
            state.get("followed_profiles") or [],
            state.get("followed_profile_suggestions") or [],
            id_list,
            accept_all=bool(payload.get("accept_all")),
        )
        state["followed_profiles"] = merged.get("profiles") or []
        state["followed_profile_suggestions"] = merged.get("suggestions") or []
        state["stage"] = STAGE_FOLLOWED_FEED
        added = int(merged.get("added_count") or 0)
        if added:
            names = ", ".join(merged.get("added_names") or [])[:200]
            base_response["reply"] = (
                f"Adicionei {added} perfil(is): {names}. "
                "Clica em «Actualizar perfis guardados» para ver publicações."
            )
        else:
            base_response["reply"] = "Nenhum perfil novo foi adicionado."
        base_response["orchestration_mode"] = STAGE_FOLLOWED_FEED
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_DISMISS_FOLLOWED_SUGGESTION:
        sid = str(payload.get("suggestion_id") or "").strip()
        updated: List[Dict[str, Any]] = []
        for row in state.get("followed_profile_suggestions") or []:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            if str(item.get("id")) == sid:
                item["status"] = "dismissed"
            updated.append(item)
        state["followed_profile_suggestions"] = updated
        base_response["reply"] = "Sugestão removida."
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_MERGE_FOLLOWED_POSTS:
        from agents.director_follow_feed import merge_profiles_from_posts

        incoming = payload.get("posts")
        feed_message = str(payload.get("feed_message") or "").strip()
        if isinstance(incoming, list) and incoming:
            if payload.get("auto_add_profiles"):
                state["followed_profiles"] = merge_profiles_from_posts(
                    state.get("followed_profiles") or [],
                    incoming,
                )
            state["followed_posts_queue"] = merge_posts_into_queue(
                state.get("followed_posts_queue") or [],
                incoming,
            )
            state["stage"] = STAGE_FOLLOWED_FEED
            n = len(incoming)
            base_response["reply"] = feed_message or (
                f"Encontrei {n} publicação(ões) recentes. Escolhe uma no painel "
                "para eu sugerir um comentário."
            )
        else:
            base_response["reply"] = feed_message or "Não encontrei publicações novas nesses perfis."
        base_response["orchestration_mode"] = state.get("stage") or STAGE_FOLLOWED_FEED
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_SELECT_FOLLOWED_POST:
        post_id = str(payload.get("post_id") or "").strip()
        followed = find_followed_post(state.get("followed_posts_queue") or [], post_id)
        if not followed:
            base_response["reply"] = "Não encontrei essa publicação na fila."
            return base_response
        try:
            msg = _start_comment_review_for_followed_post(
                client=client,
                model=openai_model,
                state=state,
                language=language,
                followed_post=followed,
            )
            base_response["reply"] = msg
        except Exception as exc:  # noqa: BLE001
            base_response["reply"] = f"Não consegui gerar o comentário: {exc!s}"
        base_response["orchestration_mode"] = state["stage"]
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state.get("pending_actions") or []
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_GENERATE_ENGAGEMENT_BATCH:
        try:
            count = int(payload.get("count") or DEFAULT_ENGAGEMENT_BATCH_SIZE)
        except (TypeError, ValueError):
            count = DEFAULT_ENGAGEMENT_BATCH_SIZE
        batch_result = _start_engagement_batch_review(
            client=client,
            model=model,
            state=state,
            language=language,
            count=count,
        )
        base_response.update(batch_result)
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_APPROVE_ENGAGEMENT_BATCH and state["stage"] == STAGE_ENGAGEMENT_BATCH_REVIEW:
        approved_ids = payload.get("approved_ids")
        id_set = {str(i) for i in approved_ids} if isinstance(approved_ids, list) else set()
        items_payload = payload.get("items")
        edits: Dict[str, str] = {}
        if isinstance(items_payload, list):
            for row in items_payload:
                if isinstance(row, dict) and row.get("id"):
                    edits[str(row["id"])] = str(row.get("comment_body") or "").strip()

        batch = list(state.get("engagement_batch") or [])
        approved_count = 0
        for draft in batch:
            if not isinstance(draft, dict):
                continue
            did = str(draft.get("id") or "")
            selected = bool(draft.get("batch_selected", True))
            if id_set and did not in id_set:
                continue
            if not id_set and not selected:
                continue
            item = dict(draft)
            if did in edits and edits[did]:
                item["comment_body"] = edits[did]
            if not str(item.get("comment_body") or "").strip():
                continue
            append_approved_engagement(state, item)
            fpid = str(item.get("followed_post_id") or "")
            if fpid:
                state["followed_posts_queue"] = update_followed_post_status(
                    state.get("followed_posts_queue") or [],
                    fpid,
                    "approved",
                )
            approved_count += 1

        state["engagement_batch"] = []
        state["stage"] = STAGE_FOLLOWED_FEED
        state["pending_actions"] = [
            ACTION_SELECT_FOLLOWED_POST,
            ACTION_GENERATE_ENGAGEMENT,
            ACTION_GENERATE_ENGAGEMENT_BATCH,
        ]
        base_response["reply"] = (
            f"Aprovei **{approved_count}** comentário(s). Usa «Copiar aprovados» no painel "
            "ou o histórico no estado — cola cada um na publicação respectiva no LinkedIn."
        )
        base_response["orchestration_mode"] = STAGE_FOLLOWED_FEED
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        base_response["pending_actions"] = state["pending_actions"]
        return base_response

    if action == ACTION_DISMISS_ENGAGEMENT_BATCH:
        state["engagement_batch"] = []
        state["stage"] = STAGE_FOLLOWED_FEED
        state["pending_actions"] = [
            ACTION_SELECT_FOLLOWED_POST,
            ACTION_GENERATE_ENGAGEMENT,
            ACTION_GENERATE_ENGAGEMENT_BATCH,
        ]
        base_response["reply"] = "Lote de comentários descartado."
        base_response["orchestration_mode"] = STAGE_FOLLOWED_FEED
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_GENERATE_ENGAGEMENT:
        nxt = next_pending_followed_post(state.get("followed_posts_queue") or [])
        if not nxt:
            base_response["reply"] = (
                "Adiciona perfis que segues e clica em «Actualizar publicações» "
                "para eu sugerir comentários."
            )
            state["stage"] = STAGE_FOLLOWED_FEED
        else:
            try:
                msg = _start_comment_review_for_followed_post(
                    client=client,
                    model=openai_model,
                    state=state,
                    language=language,
                    followed_post=nxt,
                )
                base_response["reply"] = msg
            except Exception as exc:  # noqa: BLE001
                base_response["reply"] = f"Não consegui gerar o comentário: {exc!s}"
        base_response["orchestration_mode"] = state.get("stage") or STAGE_FOLLOWED_FEED
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state.get("pending_actions") or []
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_APPROVE_ENGAGEMENT and state["stage"] == STAGE_ENGAGEMENT_REVIEW:
        draft = dict(state.get("engagement_draft") or {})
        new_body = str(payload.get("comment_body") or "").strip()
        if new_body:
            draft["comment_body"] = new_body
        fpid = str(draft.get("followed_post_id") or state.get("active_followed_post_id") or "")
        if draft.get("comment_body"):
            append_approved_engagement(state, draft)
            if fpid:
                state["followed_posts_queue"] = update_followed_post_status(
                    state.get("followed_posts_queue") or [],
                    fpid,
                    "approved",
                )
        state["stage"] = STAGE_FOLLOWED_FEED
        state["pending_actions"] = [ACTION_SELECT_FOLLOWED_POST, ACTION_GENERATE_ENGAGEMENT]
        url = str(draft.get("target_url") or "").strip()
        link_hint = f" Abre a publicação: {url}" if url else ""
        base_response["reply"] = (
            f"Comentário aprovado — copia do painel e cola na publicação no LinkedIn.{link_hint}"
        )
        base_response["orchestration_mode"] = STAGE_FOLLOWED_FEED
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_REJECT_ENGAGEMENT and state["stage"] == STAGE_ENGAGEMENT_REVIEW:
        draft = state.get("engagement_draft") or {}
        fpid = str(draft.get("followed_post_id") or state.get("active_followed_post_id") or "")
        if fpid:
            state["followed_posts_queue"] = update_followed_post_status(
                state.get("followed_posts_queue") or [],
                fpid,
                "rejected",
            )
        state["engagement_draft"] = None
        state["stage"] = STAGE_FOLLOWED_FEED
        state["pending_actions"] = [ACTION_SELECT_FOLLOWED_POST, ACTION_GENERATE_ENGAGEMENT]
        base_response["reply"] = "Comentário reprovado. Escolhe outra publicação ou pede nova sugestão."
        base_response["orchestration_mode"] = STAGE_FOLLOWED_FEED
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_REGENERATE_ENGAGEMENT and state["stage"] == STAGE_ENGAGEMENT_REVIEW:
        instr = str(payload.get("edit_instructions") or "").strip() or None
        fpid = str(state.get("active_followed_post_id") or "")
        followed = find_followed_post(state.get("followed_posts_queue") or [], fpid)
        if not followed:
            base_response["reply"] = "Publicação em falta — escolhe outra na fila."
            return base_response
        try:
            draft = generate_comment_for_followed_post(
                client,
                openai_model,
                state,
                followed,
                language,
                edit_instructions=instr,
            )
            state["engagement_draft"] = draft
            base_response["reply"] = "Refiz o comentário para esta publicação. Revê abaixo."
        except Exception as exc:  # noqa: BLE001
            base_response["reply"] = f"Não consegui refazer o comentário: {exc!s}"
        base_response["orchestration_mode"] = STAGE_ENGAGEMENT_REVIEW
        base_response["workflow_state"] = state
        base_response["pending_actions"] = [
            ACTION_APPROVE_ENGAGEMENT,
            ACTION_REJECT_ENGAGEMENT,
            ACTION_REGENERATE_ENGAGEMENT,
        ]
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_SKIP_ENGAGEMENT and state["stage"] == STAGE_ENGAGEMENT_REVIEW:
        state["engagement_draft"] = None
        state["stage"] = STAGE_FOLLOWED_FEED
        state["pending_actions"] = [ACTION_SELECT_FOLLOWED_POST, ACTION_GENERATE_ENGAGEMENT]
        base_response["reply"] = "Volta ao feed de publicações quando quiseres."
        base_response["orchestration_mode"] = STAGE_FOLLOWED_FEED
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if state["stage"] == STAGE_PUBLISH_CONFIRM and not user_action:
        base_response["reply"] = (
            "Publica no LinkedIn no painel ou avança sem publicar."
        )
        base_response["orchestration_mode"] = STAGE_PUBLISH_CONFIRM
        base_response["workflow_state"] = state
        base_response["pending_actions"] = [ACTION_SKIP_PUBLISH]
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if state["stage"] == STAGE_ENGAGEMENT_BATCH_REVIEW and not user_action:
        n_batch = len(state.get("engagement_batch") or [])
        base_response["reply"] = (
            f"Revê o lote de **{n_batch} comentários** no painel — marca os que queres "
            "e clica em «Aprovar seleccionados»."
        )
        base_response["orchestration_mode"] = STAGE_ENGAGEMENT_BATCH_REVIEW
        base_response["workflow_state"] = state
        base_response["pending_actions"] = [
            ACTION_APPROVE_ENGAGEMENT_BATCH,
            ACTION_DISMISS_ENGAGEMENT_BATCH,
        ]
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if state["stage"] == STAGE_DAILY_DIGEST_REVIEW and not user_action:
        digest = state.get("daily_digest") or {}
        base_response["reply"] = str(digest.get("summary") or "Briefing do dia no painel.")
        base_response["orchestration_mode"] = STAGE_DAILY_DIGEST_REVIEW
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if state["stage"] == STAGE_ENGAGEMENT_REVIEW and not user_action:
        base_response["reply"] = (
            "Revê o comentário para a publicação que segues — aprova ou reprova."
        )
        base_response["orchestration_mode"] = STAGE_ENGAGEMENT_REVIEW
        base_response["workflow_state"] = state
        base_response["pending_actions"] = [
            ACTION_APPROVE_ENGAGEMENT,
            ACTION_REJECT_ENGAGEMENT,
            ACTION_REGENERATE_ENGAGEMENT,
        ]
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if state["stage"] == STAGE_FOLLOWED_FEED and not user_action:
        base_response["reply"] = (
            "Escolhe uma publicação de perfis que segues para eu sugerir um comentário."
        )
        base_response["orchestration_mode"] = STAGE_FOLLOWED_FEED
        base_response["workflow_state"] = state
        base_response["pending_actions"] = [
            ACTION_SELECT_FOLLOWED_POST,
            ACTION_GENERATE_ENGAGEMENT,
        ]
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    # --- Calendário / posts LinkedIn ---
    if action == ACTION_SELECT_POST:
        post_id = str(payload.get("post_id") or "").strip()
        if post_id and _select_calendar_post(state, post_id):
            entry = (state.get("linkedin_calendar") or [])[state.get("active_post_index", 0)]
            label = entry.get("scheduled_label") or entry.get("scheduled_date") or "post"
            base_response["reply"] = f"A rever o post de {label}. Edita, refaz ou aprova a copy."
            base_response["orchestration_mode"] = STAGE_COPY_REVIEW
            base_response["workflow_state"] = state
            base_response["pending_actions"] = state["pending_actions"]
            base_response["deliverables"] = _deliverables_from_state(state)
            return base_response
        base_response["reply"] = "Não encontrei esse post no calendário."
        return base_response

    if action == ACTION_REGENERATE_LINKEDIN_POST and state["stage"] == STAGE_COPY_REVIEW:
        post = dict(state.get("post") or {})
        instr = str(payload.get("edit_instructions") or "").strip() or None
        try:
            new_post = regenerate_director_linkedin_post(
                state, post, edit_instructions=instr, language=language
            )
            state["post"] = editor_post_from_linkedin(new_post)
            post_id = str(state["post"].get("id") or "")
            if post_id:
                _sync_calendar_entry(state, post_id, state["post"])
            base_response["reply"] = "Refiz o post com base na estratégia. Revê o texto abaixo."
        except Exception as exc:  # noqa: BLE001
            base_response["reply"] = f"Não consegui refazer o post: {exc!s}"
        base_response["orchestration_mode"] = STAGE_COPY_REVIEW
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state.get("pending_actions") or []
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if state["stage"] == STAGE_POSTS_REVIEW and not user_action:
        base_response["reply"] = (
            "Escolhe o próximo post no calendário abaixo para rever copy e imagem."
        )
        base_response["orchestration_mode"] = STAGE_POSTS_REVIEW
        base_response["workflow_state"] = state
        base_response["pending_actions"] = [ACTION_SELECT_POST]
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
            post_id = str(post.get("id") or "")
            if post_id:
                _sync_calendar_entry(state, post_id, post)
        state["pending_actions"] = [ACTION_APPROVE_COPY, ACTION_EDIT_COPY, ACTION_REGENERATE_LINKEDIN_POST]
        base_response["reply"] = "Atualizei o texto do post. Revê abaixo e clica em «Aprovar copy» quando estiver pronto."
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state["pending_actions"]
        base_response["deliverables"] = _deliverables_from_state(state)
        return base_response

    if action == ACTION_SKIP_IMAGE and state["stage"] == STAGE_IMAGE_CONFIRM:
        post = dict(state.get("post") or {})
        post["status"] = "ready"
        state["post"] = post
        if state.get("linkedin_calendar"):
            msg = _advance_after_post_packaged(state)
            base_response["reply"] = msg
            base_response["orchestration_mode"] = state["stage"]
        else:
            msg = _enter_publish_confirm(state)
            base_response["reply"] = msg
            base_response["orchestration_mode"] = STAGE_PUBLISH_CONFIRM
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        base_response["pending_actions"] = state.get("pending_actions") or []
        return base_response

    if action in {ACTION_GENERATE_IMAGE, ACTION_REGENERATE_IMAGE} and state["stage"] in {
        STAGE_IMAGE_CONFIRM,
        STAGE_IMAGE_REVIEW,
    }:
        if state.get("standalone_image"):
            try:
                instr = str(payload.get("edit_instructions") or "").strip() or None
                msgs = [dict(m) for m in sanitized if isinstance(m, dict)]
                if instr:
                    msgs.append({"role": "user", "content": f"Ajustes à imagem: {instr}"})
                image_result = designer_agent.generate_image_from_chat(msgs)
                state["image"] = image_result
                state["stage"] = STAGE_IMAGE_REVIEW
                state["pending_actions"] = [ACTION_APPROVE_IMAGE, ACTION_REGENERATE_IMAGE]
                base_response["reply"] = "Imagem actualizada. Revê no painel."
                base_response["orchestration_mode"] = STAGE_IMAGE_REVIEW
                base_response["workflow_state"] = state
                base_response["deliverables"] = _deliverables_from_state(state)
                base_response["pending_actions"] = state["pending_actions"]
                return base_response
            except Exception as exc:  # noqa: BLE001
                base_response["reply"] = f"Não consegui regenerar a imagem: {exc!s}"
                return base_response

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
        if state.get("standalone_image"):
            state["standalone_image"] = False
            state["stage"] = STAGE_COMPLETED
            state["pending_actions"] = []
            base_response["reply"] = (
                "Imagem aprovada. Se quiseres outra versão, descreve o que mudar no chat."
            )
            base_response["orchestration_mode"] = STAGE_COMPLETED
            base_response["workflow_state"] = state
            base_response["deliverables"] = _deliverables_from_state(state)
            return base_response

        _package_post_ready(state)
        if state.get("linkedin_calendar"):
            msg = _enter_publish_confirm(state)
            base_response["reply"] = msg
            base_response["orchestration_mode"] = state["stage"]
        else:
            msg = _enter_publish_confirm(state)
            base_response["reply"] = msg
            base_response["orchestration_mode"] = STAGE_PUBLISH_CONFIRM
        base_response["workflow_state"] = state
        base_response["deliverables"] = _deliverables_from_state(state)
        base_response["pending_actions"] = state.get("pending_actions") or []
        base_response["ready_to_route"] = False
        return base_response

    # Se já estamos numa etapa de revisão, não voltar a gerar copy sem pedido novo
    if state["stage"] in {
        STAGE_COPY_REVIEW,
        STAGE_IMAGE_CONFIRM,
        STAGE_IMAGE_REVIEW,
        STAGE_PUBLISH_CONFIRM,
        STAGE_ENGAGEMENT_REVIEW,
    }:
        hint = {
            STAGE_COPY_REVIEW: "Estás a rever a copy. Usa «Aprovar copy» ou edita o texto no painel.",
            STAGE_IMAGE_CONFIRM: "Confirma se queres imagem: «Gerar imagem» ou «Sem imagem».",
            STAGE_IMAGE_REVIEW: "Revê a imagem: «Aprovar imagem» ou «Regenerar imagem».",
            STAGE_PUBLISH_CONFIRM: "Autoriza e publica no LinkedIn, ou avança sem publicar.",
            STAGE_ENGAGEMENT_REVIEW: "Revê o comentário sugerido antes de publicar no LinkedIn.",
        }.get(state["stage"], "")
        base_response["reply"] = hint
        base_response["workflow_state"] = state
        base_response["pending_actions"] = state.get("pending_actions") or []
        return base_response

    # --- Novo pedido / campanha ---
    normalized_last = normalize_text(last_user_text) if last_user_text else ""

    if state["stage"] in {STAGE_IDLE, STAGE_PLANNING, STAGE_COMPLETED} and not _in_linkedin_workflow(
        state
    ):
        if not text_mentions_linkedin(normalized_last):
            state["channels"] = [c for c in (state.get("channels") or []) if str(c).lower() != "linkedin"]
            if not state["channels"]:
                state["channels"] = []

    _early_non_linkedin_stages = {
        STAGE_IDLE,
        STAGE_PLANNING,
        STAGE_COMPLETED,
        STAGE_STRATEGY_BRIEF,
        STAGE_STRATEGY_REVIEW,
    }
    _pivot_from_linkedin_brief = (
        state["stage"] in {STAGE_STRATEGY_BRIEF, STAGE_STRATEGY_REVIEW}
        and not text_mentions_linkedin(normalized_last)
    )
    if _pivot_from_linkedin_brief:
        state["strategy"] = None
        state["channels"] = ["geral"]

    if (
        _is_design_only_request(normalized_last)
        and not text_mentions_linkedin(normalized_last)
        and state["stage"] in _early_non_linkedin_stages
    ):
        design_result = _handle_standalone_design_request(
            state,
            sanitized,
            language,
            agent_page_url=agent_page_url,
        )
        base_response.update(design_result)
        return base_response

    if (
        _is_copy_only_request(normalized_last)
        and not text_mentions_linkedin(normalized_last)
        and state["stage"] in _early_non_linkedin_stages
    ):
        copy_result = _handle_standalone_copy_request(
            state,
            sanitized,
            language,
            agent_page_url=agent_page_url,
        )
        base_response.update(copy_result)
        return base_response

    strategy_intent = _should_enter_linkedin_strategy(state, last_user_text)

    if strategy_intent or (
        state.get("strategy")
        and state["stage"] in {STAGE_IDLE, STAGE_COMPLETED, STAGE_STRATEGY_BRIEF}
        and text_mentions_linkedin(normalized_last)
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
            result = _start_execution_from_strategy(
                state=state,
                sanitized=sanitized,
                language=language,
            )
            base_response.update(result)
            return base_response
        except Exception as exc:  # noqa: BLE001
            base_response["reply"] = f"Não consegui gerar os posts: {exc!s}"
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

    state["channels"] = _channels_from_assignments(assignments, last_user_text)
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
