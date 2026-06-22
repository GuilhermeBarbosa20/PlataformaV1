"""Comentários em publicações de perfis que o utilizador segue (Fase D).

O Diretor sugere um comentário; o utilizador aprova ou reprova e depois
vai manualmente à publicação no LinkedIn para comentar (sem API de comentários).
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from openai import OpenAI

from agents.director_prompts import (
    analysis_context_snippet,
    director_voice_block,
    engagement_comment_rules_block,
    engagement_history_snippet,
    linkedin_organic_excellence_block,
)
from agents.director_strategy import _parse_llm_json, strategy_brief_for_execution


def generate_comment_for_followed_post(
    client: OpenAI,
    model: str,
    state: Dict[str, Any],
    followed_post: Dict[str, Any],
    language: str,
    *,
    edit_instructions: Optional[str] = None,
) -> Dict[str, Any]:
    """Gera rascunho de comentário para uma publicação de um perfil seguido.

    O comentário é para publicar na publicação de outra pessoa (ex.: um líder
    de opinião que segues) — nunca para os teus próprios posts.

    Argumentos:
        client: Cliente OpenAI.
        model: Modelo de chat.
        state: Estado do workflow (estratégia, ICP, análise).
        followed_post: Entrada da fila com ``author_name``, ``post_url``, ``snippet``.
        language: Idioma (ex.: ``pt-PT``).
        edit_instructions: Feedback para regenerar (opcional).

    Retorno:
        ``engagement_draft`` com ``followed_post_id``, texto do comentário e metadados.
    """

    strategy = state.get("strategy") if isinstance(state.get("strategy"), dict) else {}
    brief = strategy_brief_for_execution(strategy)
    author = str(followed_post.get("author_name") or "Autor").strip()
    snippet = str(followed_post.get("snippet") or "").strip()
    post_url = str(followed_post.get("post_url") or "").strip()
    instr = str(edit_instructions or "").strip()

    analysis_ctx = analysis_context_snippet(state.get("linkedin_analysis"))
    history_ctx = engagement_history_snippet(state)
    system_prompt = (
        f"{director_voice_block(language)}\n"
        f"{linkedin_organic_excellence_block()}\n"
        f"{engagement_comment_rules_block()}\n"
        "O utilizador vai comentar numa PUBLICAÇÃO DE OUTRA PESSOA (perfil que segue). "
        "Responde APENAS JSON: "
        '{"comment_body":"...","angle":"porque este comentário encaixa na estratégia do utilizador"}'
    )
    user_prompt = (
        f"Estratégia do utilizador:\n{brief or json.dumps(strategy, ensure_ascii=False)[:2000]}\n\n"
    )
    if analysis_ctx:
        user_prompt += f"Contexto do perfil do utilizador:\n{analysis_ctx}\n\n"
    if history_ctx:
        user_prompt += f"{history_ctx}\n\n"
    user_prompt += (
        f"PUBLICAÇÃO A COMENTAR (de {author}):\n"
        f"URL: {post_url or 'n/d'}\n"
        f"Texto da publicação:\n{snippet or '(sem texto recolhido — infere pelo contexto profissional)'}\n\n"
        "Gera um comentário específico para ESTA publicação — não genérico."
    )
    if instr:
        user_prompt += f"\nInstruções do utilizador: {instr}\n"

    response = client.chat.completions.create(
        model=model,
        temperature=0.62,
        max_tokens=1200,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    data = _parse_llm_json(raw)
    body = str((data or {}).get("comment_body") or "").strip()
    if not body:
        body = (
            f"Boa reflexão, {author}. O ponto sobre o impacto prático resonou comigo — "
            "na nossa experiência, medir isto de forma consistente é o que mais muda resultados. "
            "Como estão a abordar isso na vossa equipa?"
        )

    prev = state.get("engagement_draft") if isinstance(state.get("engagement_draft"), dict) else {}
    return {
        "id": str(prev.get("id") or uuid.uuid4().hex[:12]),
        "followed_post_id": str(followed_post.get("id") or ""),
        "target_label": f"Publicação de {author}",
        "target_url": post_url,
        "target_snippet": snippet[:400],
        "author_name": author,
        "comment_body": body,
        "angle": str((data or {}).get("angle") or "").strip(),
        "status": "draft",
    }


DEFAULT_ENGAGEMENT_BATCH_SIZE = 10


def pick_posts_for_engagement_batch(
    queue: List[Dict[str, Any]],
    *,
    count: int = DEFAULT_ENGAGEMENT_BATCH_SIZE,
) -> List[Dict[str, Any]]:
    """Selecciona publicações pendentes para um lote de comentários.

    Argumentos:
        queue: Fila ``followed_posts_queue``.
        count: Número máximo de posts (por defeito 10).

    Retorno:
        Lista de entradas com ``status=pending``, até ``count`` itens.
    """

    pending = [
        dict(p)
        for p in (queue or [])
        if isinstance(p, dict) and (p.get("status") or "pending") == "pending"
    ]
    return pending[: max(1, min(int(count or DEFAULT_ENGAGEMENT_BATCH_SIZE), 15))]


def generate_comments_batch(
    client: OpenAI,
    model: str,
    state: Dict[str, Any],
    posts: List[Dict[str, Any]],
    language: str,
) -> List[Dict[str, Any]]:
    """Gera vários rascunhos de comentário numa única chamada ao LLM.

    Argumentos:
        client: Cliente OpenAI.
        model: Modelo de chat.
        state: Estado do workflow (estratégia, ICP).
        posts: Publicações seleccionadas da fila.
        language: Idioma (ex.: ``pt-PT``).

    Retorno:
        Lista de rascunhos com ``followed_post_id``, ``comment_body``, metadados
        e ``batch_selected=true`` por defeito para aprovação em lote.
    """

    if not posts:
        return []

    strategy = state.get("strategy") if isinstance(state.get("strategy"), dict) else {}
    brief = strategy_brief_for_execution(strategy)
    lines: List[str] = []
    id_map: Dict[str, Dict[str, Any]] = {}
    for idx, post in enumerate(posts, start=1):
        pid = str(post.get("id") or "")
        if not pid:
            continue
        author = str(post.get("author_name") or "Autor").strip()
        snippet = str(post.get("snippet") or "").strip()[:400]
        id_map[pid] = post
        lines.append(
            f'{idx}. post_id="{pid}" | autor={author} | texto="{snippet.replace(chr(34), chr(39))}"'
        )

    if not lines:
        return []

    analysis_ctx = analysis_context_snippet(state.get("linkedin_analysis"))
    history_ctx = engagement_history_snippet(state)
    system_prompt = (
        f"{director_voice_block(language)}\n"
        f"{linkedin_organic_excellence_block()}\n"
        f"{engagement_comment_rules_block()}\n"
        "Para cada publicação listada, escreve UM comentário distinto dos outros. "
        "JSON: "
        '{"comments":[{"post_id":"...","comment_body":"...","angle":"..."}]}'
    )
    user_prompt = f"Estratégia do utilizador:\n{brief[:3500]}\n\n"
    if analysis_ctx:
        user_prompt += f"Contexto do perfil:\n{analysis_ctx}\n\n"
    if history_ctx:
        user_prompt += f"{history_ctx}\n\n"
    user_prompt += f"PUBLICAÇÕES ({len(lines)}):\n" + "\n".join(lines)
    response = client.chat.completions.create(
        model=model,
        temperature=0.65,
        max_tokens=6000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    data = _parse_llm_json(raw) or {}
    comments_raw = data.get("comments") if isinstance(data.get("comments"), list) else []

    drafts: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in comments_raw:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("post_id") or "").strip()
        if not pid or pid in seen_ids or pid not in id_map:
            continue
        post = id_map[pid]
        body = str(item.get("comment_body") or "").strip()
        if not body:
            continue
        seen_ids.add(pid)
        author = str(post.get("author_name") or "Autor").strip()
        drafts.append(
            {
                "id": uuid.uuid4().hex[:12],
                "followed_post_id": pid,
                "target_label": f"Publicação de {author}",
                "target_url": str(post.get("post_url") or "").strip(),
                "target_snippet": str(post.get("snippet") or "")[:400],
                "author_name": author,
                "comment_body": body,
                "angle": str(item.get("angle") or "").strip(),
                "status": "draft",
                "batch_selected": True,
            }
        )

    for post in posts:
        pid = str(post.get("id") or "")
        if pid in seen_ids or not pid:
            continue
        author = str(post.get("author_name") or "Autor").strip()
        drafts.append(
            {
                "id": uuid.uuid4().hex[:12],
                "followed_post_id": pid,
                "target_label": f"Publicação de {author}",
                "target_url": str(post.get("post_url") or "").strip(),
                "target_snippet": str(post.get("snippet") or "")[:400],
                "author_name": author,
                "comment_body": (
                    f"Excelente reflexão, {author}. O ponto que destacaste faz sentido "
                    "no contexto actual — como estão a medir o impacto disto na prática?"
                ),
                "angle": "fallback",
                "status": "draft",
                "batch_selected": True,
            }
        )
    return drafts


def append_approved_engagement(state: Dict[str, Any], draft: Dict[str, Any]) -> None:
    """Regista comentário aprovado no histórico do Diretor.

    Argumentos:
        state: Estado mutável do workflow.
        draft: Rascunho aprovado com ``comment_body`` e ``followed_post_id``.
    """

    if not isinstance(draft, dict):
        return
    approved = dict(draft)
    approved["status"] = "approved"
    log = state.get("engagement_log")
    if not isinstance(log, list):
        log = []
    log.append(approved)
    state["engagement_log"] = log[-30:]
    state["engagement_draft"] = None
