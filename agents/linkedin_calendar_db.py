"""Persistência dos posts do calendário LinkedIn na Supabase."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _calendar_post_for_storage(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza um post para gravar em JSON (sem campos temporários de UI).

    Argumentos:
        raw: Post em memória no frontend.

    Retorno:
        Dicionário serializável para ``jsonb``.
    """

    keys = (
        "id",
        "content_type",
        "title",
        "body",
        "hook",
        "cta",
        "angle",
        "status",
        "scheduled_date",
        "image_status",
        "generated_image_url",
        "generated_image_prompt",
        "published_on_linkedin",
        "linkedin_post_urn",
        "published_with_image",
    )
    out: Dict[str, Any] = {}
    for key in keys:
        if key in raw and raw[key] is not None:
            out[key] = raw[key]
    if not out.get("id"):
        return {}
    out.setdefault("status", "draft")
    return out


def normalize_calendar_posts_for_storage(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Limpa a lista de posts antes de upsert na base de dados.

    Argumentos:
        posts: Lista de posts do calendário.

    Retorno:
        Lista normalizada (sem entradas vazias).
    """

    cleaned: List[Dict[str, Any]] = []
    for row in posts or []:
        if not isinstance(row, dict):
            continue
        item = _calendar_post_for_storage(row)
        if item.get("id"):
            cleaned.append(item)
    return cleaned


def fetch_user_linkedin_calendar_posts_from_database(
    access_token: str,
    supabase_url: str,
    anon_key: str,
) -> Optional[Dict[str, Any]]:
    """Lê os posts do calendário associados ao utilizador autenticado.

    Argumentos:
        access_token: JWT ``access_token`` da sessão Supabase.
        supabase_url: URL base do projecto.
        anon_key: Chave anon.

    Retorno:
        ``{"week_start": "YYYY-MM-DD", "posts": [...]}`` ou ``None`` se não existir.
    """

    token = str(access_token or "").strip()
    base = str(supabase_url or "").strip().rstrip("/")
    key = str(anon_key or "").strip()
    if not token or not base or not key:
        return None

    query = urllib.parse.urlencode({"select": "week_start,posts", "limit": "1"})
    url = f"{base}/rest/v1/user_linkedin_calendar_posts?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": key,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 406):
            return None
        return None
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return None

    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    if not isinstance(first, dict):
        return None
    posts = first.get("posts")
    if not isinstance(posts, list):
        posts = []
    week_start = first.get("week_start")
    return {
        "week_start": str(week_start) if week_start else None,
        "posts": [p for p in posts if isinstance(p, dict)],
    }


def upsert_user_linkedin_calendar_posts_to_database(
    access_token: str,
    supabase_url: str,
    anon_key: str,
    user_id: str,
    posts: List[Dict[str, Any]],
    *,
    week_start: Optional[str] = None,
) -> bool:
    """Grava ou actualiza os posts do calendário semanal do utilizador.

    Argumentos:
        access_token: JWT da sessão Supabase.
        supabase_url: URL base do projecto.
        anon_key: Chave anon.
        user_id: UUID do utilizador.
        posts: Lista de posts a persistir.
        week_start: Data ISO do 1.º dia da semana planeado (opcional).

    Retorno:
        ``True`` se o upsert foi aceite; ``False`` em caso de erro.
    """

    token = str(access_token or "").strip()
    base = str(supabase_url or "").strip().rstrip("/")
    key = str(anon_key or "").strip()
    uid = str(user_id or "").strip()
    if not token or not base or not key or not uid:
        return False

    cleaned = normalize_calendar_posts_for_storage(posts)
    ws = str(week_start or "").strip()[:10] or datetime.now(timezone.utc).date().isoformat()
    payload = {
        "user_id": uid,
        "week_start": ws,
        "posts": cleaned,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/rest/v1/user_linkedin_calendar_posts",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": key,
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError:
        return False
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
