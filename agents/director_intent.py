"""Interpretação de intenção do utilizador no Diretor via OpenAI.

O Diretor deixa de depender apenas de palavras-chave: o modelo lê o pedido
no contexto da conversa e da etapa actual do workflow antes de escolher o fluxo.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from openai import OpenAI

from agents.director_team import build_conversation_brief

VALID_DIRECTOR_INTENTS = frozenset(
    {
        "continue_current",
        "followed_profiles",
        "engagement_comment",
        "engagement_batch",
        "daily_digest",
        "linkedin_strategy",
        "linkedin_posts",
        "linkedin_optimization",
        "standalone_copy",
        "standalone_image",
        "general_plan",
        "clarify",
    }
)

_STAGE_LABELS_PT: Dict[str, str] = {
    "idle": "início",
    "planning": "planeamento",
    "strategy_brief": "brief estratégico LinkedIn (a recolher dados)",
    "strategy_review": "revisão de estratégia LinkedIn",
    "strategy_approved": "estratégia LinkedIn aprovada",
    "optimization_review": "revisão de optimização LinkedIn",
    "posts_review": "calendário de posts LinkedIn",
    "copy_review": "revisão de copy",
    "image_confirm": "confirmar se quer imagem",
    "image_review": "revisão de imagem",
    "publish_confirm": "confirmar publicação LinkedIn",
    "followed_feed": "perfis seguidos e comentários",
    "engagement_review": "aprovação de comentário",
    "completed": "concluído",
}


def _workflow_summary_for_intent(state: Dict[str, Any]) -> str:
    """Resume o estado do workflow para o classificador de intenção.

    Argumentos:
        state: Estado persistido do Diretor.

    Retorno:
        Texto curto com etapa e artefactos disponíveis.
    """

    stage = str(state.get("stage") or "idle")
    label = _STAGE_LABELS_PT.get(stage, stage)
    lines: List[str] = [f"Etapa actual: {label} ({stage})"]
    if state.get("strategy"):
        lines.append("Existe estratégia LinkedIn definida.")
    if state.get("linkedin_analysis"):
        lines.append("Perfil LinkedIn já analisado.")
    if state.get("linkedin_calendar"):
        n = len(state.get("linkedin_calendar") or [])
        if n:
            lines.append(f"Calendário com {n} posts.")
    if state.get("post"):
        lines.append("Há um post em revisão.")
    if state.get("image"):
        lines.append("Há uma imagem em revisão.")
    profiles = state.get("followed_profiles") or []
    if profiles:
        lines.append(f"{len(profiles)} perfil(is) na lista de seguidos.")
    queue = state.get("followed_posts_queue") or []
    pending = [p for p in queue if isinstance(p, dict) and (p.get("status") or "pending") == "pending"]
    if pending:
        lines.append(f"{len(pending)} publicação(ões) na fila para comentar.")
    if state.get("engagement_draft"):
        lines.append("Há um rascunho de comentário em revisão.")
    channels = state.get("channels") or []
    if channels:
        lines.append(f"Canais activos: {', '.join(str(c) for c in channels)}.")
    return "\n".join(lines)


def classify_director_intent(
    client: OpenAI,
    model: str,
    messages: Sequence[Dict[str, str]],
    state: Dict[str, Any],
    language: str,
) -> Dict[str, Any]:
    """Classifica o que o utilizador quer fazer neste turno (via OpenAI).

    Lê o histórico recente e o estado do workflow para decidir qual capacidade
    activar. Não assume LinkedIn por defeito — só quando o pedido ou o fluxo
    activo o justifica.

    Argumentos:
        client: Cliente OpenAI autenticado.
        model: Modelo (ex.: ``gpt-4o-mini``).
        messages: Histórico da conversa (``user``/``assistant``).
        state: Estado actual do workflow do Diretor.
        language: Idioma da resposta ao utilizador.

    Retorno:
        Dicionário com ``intent`` (um de ``VALID_DIRECTOR_INTENTS``),
        ``confidence`` (0–1), ``user_goal`` (resumo curto),
        ``auto_suggest_profiles`` (bool) e ``reply`` (mensagem opcional
        quando ``intent`` é ``clarify``).
    """

    conversation = build_conversation_brief(messages)
    context = _workflow_summary_for_intent(state)
    system_prompt = (
        "És o módulo de interpretação do Diretor de Marketing AI. "
        f"Responde em JSON. Idioma do utilizador: {language}.\n\n"
        "O utilizador fala SEMPRE com o Diretor; tu decides qual fluxo interno "
        "activar. NÃO assumes LinkedIn salvo se o utilizador o pedir ou já "
        "estiver numa etapa LinkedIn com estratégia/análise em curso.\n\n"
        "Intenções possíveis (campo intent):\n"
        "- continue_current: o utilizador continua a etapa actual (responde a "
        "perguntas do brief, ajusta copy/imagem em revisão, etc.).\n"
        "- followed_profiles: quer sugestões ou gestão de perfis/pessoas para "
        "seguir no LinkedIn (engagement, networking).\n"
        "- engagement_comment: quer comentar publicações de terceiros / posts "
        "de perfis que segue (um de cada vez).\n"
        "- engagement_batch: quer vários comentários de uma vez (ex.: 10 ou 15 "
        "sugestões para aprovar em lote).\n"
        "- daily_digest: quer briefing/análise do dia ou progresso diário.\n"
        "- linkedin_strategy: quer planear estratégia LinkedIn (objectivos, "
        "ICP, pilares, métricas).\n"
        "- linkedin_posts: quer gerar ou avançar posts/calendário a partir da "
        "estratégia aprovada.\n"
        "- linkedin_optimization: quer reanalisar métricas e optimizar a "
        "estratégia.\n"
        "- standalone_copy: quer texto/copy genérico SEM assumir LinkedIn.\n"
        "- standalone_image: quer imagem/criativo genérico SEM assumir LinkedIn.\n"
        "- general_plan: pedido de marketing genérico (site, campanha, etc.) "
        "que requer planeamento com a equipa.\n"
        "- clarify: falta informação essencial; reply com 1–2 perguntas curtas.\n\n"
        "Regras:\n"
        "1. Se a etapa é strategy_brief ou strategy_review e o utilizador "
        "fornece dados estratégicos, usa continue_current.\n"
        "2. Se a etapa é strategy_approved e pede pessoas/perfis para seguir, "
        "usa followed_profiles (auto_suggest_profiles=true).\n"
        "3. Sinónimos: «pessoas para seguir», «quem seguir», «perfis para "
        "seguir» → followed_profiles.\n"
        "4. confidence entre 0 e 1.\n"
        "5. auto_suggest_profiles: true quando devemos sugerir perfis por ICP.\n"
        "6. batch_count: número de comentários em lote (por defeito 10, máx. 15) "
        "quando intent=engagement_batch.\n\n"
        "JSON: "
        '{"intent":"<uma das intenções>","confidence":0.0,'
        '"user_goal":"<resumo em 1 frase>","auto_suggest_profiles":false,'
        '"batch_count":10,"reply":"<só se intent=clarify>"}'
    )
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Estado do workflow:\n{context}\n\n"
                    f"Conversa:\n{conversation or '(vazio)'}"
                ),
            },
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "intent": "general_plan",
            "confidence": 0.0,
            "user_goal": "",
            "auto_suggest_profiles": False,
            "reply": "",
        }

    intent = str(data.get("intent") or "general_plan").strip().lower()
    if intent not in VALID_DIRECTOR_INTENTS:
        intent = "general_plan"
    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    try:
        batch_count = int(data.get("batch_count") or 10)
    except (TypeError, ValueError):
        batch_count = 10
    batch_count = max(1, min(15, batch_count))

    return {
        "intent": intent,
        "confidence": confidence,
        "user_goal": str(data.get("user_goal") or "").strip(),
        "auto_suggest_profiles": bool(data.get("auto_suggest_profiles", False)),
        "batch_count": batch_count,
        "reply": str(data.get("reply") or "").strip(),
    }
