"""Feed de publicações de perfis LinkedIn que o utilizador segue (Fase D).

Recolhe posts recentes via Apify (reutilizado da análise de perfil) e
mantém uma fila para o Diretor sugerir comentários com aprovação humana.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


def slug_from_linkedin_profile_url(profile_url: str) -> str:
    """Extrai identificador legível de um URL LinkedIn ``/in/`` ou ``/company/``.

    Argumentos:
        profile_url: URL do perfil.

    Retorno:
        Slug ou nome curto para exibir na UI.
    """

    raw = str(profile_url or "").strip().rstrip("/")
    if not raw:
        return "Perfil"
    path = urlparse(raw).path.strip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] in {"in", "company"}:
        return parts[1].replace("-", " ").title()
    if parts:
        return parts[-1].replace("-", " ").title()
    return "Perfil"


def normalize_followed_profile(profile_url: str, display_name: Optional[str] = None) -> Dict[str, str]:
    """Cria entrada de perfil seguido para o estado do Diretor.

    Argumentos:
        profile_url: URL LinkedIn do perfil que o utilizador segue.
        display_name: Nome opcional para a UI.

    Retorno:
        ``{id, profile_url, display_name}``.
    """

    url = str(profile_url or "").strip()
    name = str(display_name or "").strip() or slug_from_linkedin_profile_url(url)
    return {
        "id": uuid.uuid4().hex[:12],
        "profile_url": url,
        "display_name": name,
    }


def posts_from_apify_bundle(
    bundle: Dict[str, Any],
    *,
    profile_url: str,
    author_name: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Converte bundle Apify numa fila de posts para comentar.

    Argumentos:
        bundle: Resultado de ``_fetch_linkedin_public_profile_with_apify``.
        profile_url: URL do autor do post.
        author_name: Nome a mostrar na UI.
        limit: Máximo de posts recentes.

    Retorno:
        Lista de entradas ``followed_posts_queue`` com ``status=pending``.
    """

    if not isinstance(bundle, dict):
        return []

    author = str(author_name or slug_from_linkedin_profile_url(profile_url)).strip()
    posts_raw = bundle.get("recent_posts")
    if not isinstance(posts_raw, list):
        enrichment = bundle.get("apify_enrichment")
        if isinstance(enrichment, dict) and isinstance(enrichment.get("raw_posts"), list):
            posts_raw = enrichment.get("raw_posts")

    if not isinstance(posts_raw, list):
        return []

    out: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()
    for row in posts_raw[: max(limit, 1) * 3]:
        if not isinstance(row, dict):
            continue
        url = str(
            row.get("url")
            or row.get("postUrl")
            or row.get("linkedinUrl")
            or ""
        ).strip()
        text = str(
            row.get("caption")
            or row.get("text")
            or row.get("content")
            or row.get("headline")
            or ""
        ).strip()
        if not text and not url:
            continue
        dedupe_key = url or text[:120]
        if dedupe_key in seen_urls:
            continue
        seen_urls.add(dedupe_key)
        out.append(
            {
                "id": uuid.uuid4().hex[:12],
                "profile_url": profile_url,
                "author_name": author,
                "post_url": url,
                "snippet": text[:600],
                "published_label": str(
                    row.get("timestamp")
                    or row.get("postedAt")
                    or row.get("date")
                    or ""
                ).strip(),
                "status": "pending",
            }
        )
        if len(out) >= limit:
            break
    return out


def merge_profiles_from_posts(
    existing: List[Dict[str, Any]],
    posts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Adiciona perfis inferidos dos posts importados (ex.: feed da rede).

    Argumentos:
        existing: Lista ``followed_profiles`` actual.
        posts: Posts com ``profile_url`` e opcionalmente ``author_name``.

    Retorno:
        Lista de perfis sem duplicar URLs.
    """

    profiles = [dict(p) for p in existing if isinstance(p, dict)]
    known = {
        str(p.get("profile_url") or "").rstrip("/").casefold()
        for p in profiles
        if p.get("profile_url")
    }
    for post in posts:
        if not isinstance(post, dict):
            continue
        url = str(post.get("profile_url") or "").strip()
        if not url or "linkedin.com" not in url.casefold():
            continue
        key = url.rstrip("/").casefold()
        if key in known:
            continue
        name = str(post.get("author_name") or "").strip() or None
        profiles.append(normalize_followed_profile(url, name))
        known.add(key)
    return profiles


def merge_posts_into_queue(
    existing: List[Dict[str, Any]],
    new_posts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Funde posts novos na fila sem duplicar URLs.

    Argumentos:
        existing: Fila actual no workflow.
        new_posts: Posts recém-recolhidos.

    Retorno:
        Fila actualizada (máx. 30 entradas).
    """

    queue = [dict(e) for e in existing if isinstance(e, dict)]
    known = {
        str(e.get("post_url") or e.get("snippet", "")[:80])
        for e in queue
        if e.get("post_url") or e.get("snippet")
    }
    for post in new_posts:
        if not isinstance(post, dict):
            continue
        key = str(post.get("post_url") or post.get("snippet", "")[:80])
        if key and key not in known:
            queue.append(dict(post))
            known.add(key)
    return queue[:30]


def find_followed_post(queue: List[Dict[str, Any]], post_id: str) -> Optional[Dict[str, Any]]:
    """Localiza um post na fila pelo identificador.

    Argumentos:
        queue: ``followed_posts_queue``.
        post_id: ID da entrada.

    Retorno:
        Cópia do post ou ``None``.
    """

    pid = str(post_id or "").strip()
    if not pid:
        return None
    for entry in queue:
        if isinstance(entry, dict) and str(entry.get("id")) == pid:
            return dict(entry)
    return None


def update_followed_post_status(
    queue: List[Dict[str, Any]],
    post_id: str,
    status: str,
) -> List[Dict[str, Any]]:
    """Actualiza o estado de um post na fila (pending, approved, rejected, etc.).

    Argumentos:
        queue: Fila mutável (será copiada).
        post_id: ID do post.
        status: Novo estado.

    Retorno:
        Nova lista com o post actualizado.
    """

    pid = str(post_id or "").strip()
    updated: List[Dict[str, Any]] = []
    for entry in queue:
        if not isinstance(entry, dict):
            continue
        row = dict(entry)
        if str(row.get("id")) == pid:
            row["status"] = status
        updated.append(row)
    return updated


def next_pending_followed_post(queue: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Devolve o próximo post pendente de comentário na fila.

    Argumentos:
        queue: Fila de publicações de perfis seguidos.

    Retorno:
        Primeiro post com ``status=pending`` ou ``None``.
    """

    for entry in queue:
        if isinstance(entry, dict) and str(entry.get("status") or "pending") == "pending":
            return dict(entry)
    return None
