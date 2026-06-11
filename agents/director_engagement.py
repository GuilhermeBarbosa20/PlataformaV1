"""Comentários em publicações de perfis que o utilizador segue (Fase D).

O Diretor sugere um comentário; o utilizador aprova ou reprova e depois
vai manualmente à publicação no LinkedIn para comentar (sem API de comentários).
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from openai import OpenAI

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

    system_prompt = (
        f"És o Diretor de Marketing AI — especialista em engagement LinkedIn B2B. "
        f"Responde em {language}. "
        "O utilizador vai comentar numa PUBLICAÇÃO DE OUTRA PESSOA (perfil que segue). "
        "Escreve UM comentário profissional, autêntico e útil — acrescenta valor real "
        "(insight, pergunta inteligente, experiência breve). "
        "Proibido: spam, pitch de vendas, «adorei o post», elogios vazios, hashtags em excesso. "
        "Comprimento: 2–5 frases, máximo ~80 palavras. "
        "Responde APENAS JSON: "
        '{"comment_body":"...","angle":"porque este comentário encaixa na estratégia do utilizador"}'
    )
    user_prompt = (
        f"Estratégia do utilizador:\n{brief or json.dumps(strategy, ensure_ascii=False)[:2000]}\n\n"
        f"PUBLICAÇÃO A COMENTAR (de {author}):\n"
        f"URL: {post_url or 'n/d'}\n"
        f"Texto da publicação:\n{snippet or '(sem texto recolhido — infere pelo contexto profissional)'}\n\n"
        "Gera um comentário que o utilizador possa publicar nesta publicação específica."
    )
    if instr:
        user_prompt += f"\nInstruções do utilizador: {instr}\n"

    response = client.chat.completions.create(
        model=model,
        temperature=0.55,
        max_tokens=1024,
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
