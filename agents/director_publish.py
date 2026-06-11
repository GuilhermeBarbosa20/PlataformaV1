"""Publicação LinkedIn no fluxo do Diretor (Fase D).

Centraliza a actualização de estado após publicar ou saltar publicação,
para o workflow e a UI permanecerem consistentes. Reutiliza a API existente
``POST /agents/linkedin/publish-post`` — este módulo não duplica OAuth.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def attach_approved_image_to_post(
    post: Dict[str, Any],
    image: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Associa imagem aprovada ao post antes de publicar no LinkedIn.

    Argumentos:
        post: Objecto ``post`` do workflow do Diretor.
        image: Resultado do Designer com ``image_url`` (opcional).

    Retorno:
        Cópia do post com ``generated_image_url`` e ``image_status`` quando aplicável.
    """

    merged = dict(post or {})
    img = image if isinstance(image, dict) else {}
    url = str(img.get("image_url") or merged.get("generated_image_url") or "").strip()
    if url:
        merged["generated_image_url"] = url
        merged["image_status"] = "approved"
    return merged


def build_linkedin_publish_payload(post: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza o post do Diretor para o endpoint ``publish-post``.

    Argumentos:
        post: Post em memória (copy + metadados + imagem opcional).

    Retorno:
        Dicionário compatível com ``LinkedInPublishPostRequest.post``.
    """

    p = dict(post or {})
    return {
        "id": str(p.get("id") or ""),
        "title": str(p.get("title") or ""),
        "body": str(p.get("body") or ""),
        "hook": str(p.get("hook") or ""),
        "cta": str(p.get("cta") or ""),
        "content_type": str(p.get("content_type") or "texto"),
        "generated_image_url": p.get("generated_image_url"),
        "image_status": p.get("image_status"),
        "status": str(p.get("status") or "ready"),
    }


def mark_post_published(
    state: Dict[str, Any],
    *,
    post_id: str,
    linkedin_post_urn: str,
    published_with_image: bool,
) -> None:
    """Regista publicação bem-sucedida no post activo e no calendário.

    Argumentos:
        state: Estado mutável do workflow.
        post_id: Identificador do post publicado.
        linkedin_post_urn: URN devolvido pela API LinkedIn.
        published_with_image: Se a publicação incluiu imagem.
    """

    pid = str(post_id or "").strip()
    urn = str(linkedin_post_urn or "").strip()
    post = dict(state.get("post") or {})
    if pid and (not post.get("id") or str(post.get("id")) == pid):
        post["published_on_linkedin"] = True
        post["linkedin_post_urn"] = urn
        post["published_with_image"] = bool(published_with_image)
        post["status"] = "published"
        state["post"] = post

    calendar = state.get("linkedin_calendar") or []
    for entry in calendar:
        if str(entry.get("post_id")) != pid:
            continue
        inner = dict(entry.get("post") or {})
        inner["published_on_linkedin"] = True
        inner["linkedin_post_urn"] = urn
        inner["published_with_image"] = bool(published_with_image)
        inner["status"] = "published"
        entry["post"] = inner
        entry["status"] = "published"
        break
    state["linkedin_calendar"] = calendar


def sync_calendar_post_data(
    state: Dict[str, Any],
    post_id: str,
    post_data: Dict[str, Any],
    *,
    entry_status: Optional[str] = None,
) -> None:
    """Actualiza dados de um post no calendário editorial.

    Argumentos:
        state: Estado do workflow.
        post_id: ID do post no calendário.
        post_data: Objecto post actualizado.
        entry_status: Estado da entrada (``ready``, ``published``, etc.).
    """

    calendar = state.get("linkedin_calendar") or []
    for entry in calendar:
        if str(entry.get("post_id")) != str(post_id):
            continue
        entry["post"] = dict(post_data)
        if entry_status:
            entry["status"] = entry_status
        break
    state["linkedin_calendar"] = calendar
