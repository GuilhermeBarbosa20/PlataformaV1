"""Persistência dos perfis LinkedIn seguidos (engagement) na Supabase."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _profile_for_storage(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza um perfil seguido para gravar em JSON.

    Argumentos:
        raw: Entrada em memória no workflow do Diretor.

    Retorno:
        Dicionário serializável com ``id``, ``profile_url`` e ``display_name``.
    """

    url = str(raw.get("profile_url") or "").strip()
    if not url or "linkedin.com" not in url.casefold():
        return {}
    pid = str(raw.get("id") or "").strip()
    name = str(raw.get("display_name") or "").strip()
    out: Dict[str, Any] = {"profile_url": url}
    if pid:
        out["id"] = pid
    if name:
        out["display_name"] = name
    return out


def normalize_followed_profiles_for_storage(
    profiles: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Limpa a lista de perfis antes de upsert na base de dados.

    Argumentos:
        profiles: Lista ``followed_profiles`` do workflow.

    Retorno:
        Lista normalizada sem duplicados por URL (mantém a primeira ocorrência).
    """

    cleaned: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for row in profiles or []:
        if not isinstance(row, dict):
            continue
        item = _profile_for_storage(row)
        url = str(item.get("profile_url") or "").strip()
        if not url:
            continue
        key = url.rstrip("/").casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def fetch_user_linkedin_followed_profiles_from_database(
    access_token: str,
    supabase_url: str,
    anon_key: str,
) -> Optional[List[Dict[str, Any]]]:
    """Lê os perfis seguidos associados ao utilizador autenticado.

    Argumentos:
        access_token: JWT ``access_token`` da sessão Supabase.
        supabase_url: URL base do projecto.
        anon_key: Chave anon.

    Retorno:
        Lista de perfis ou ``None`` se a tabela não existir / sem dados.
    """

    token = str(access_token or "").strip()
    base = str(supabase_url or "").strip().rstrip("/")
    key = str(anon_key or "").strip()
    if not token or not base or not key:
        return None

    query = urllib.parse.urlencode({"select": "profiles", "limit": "1"})
    url = f"{base}/rest/v1/user_linkedin_followed_profiles?{query}"
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
    except urllib.error.HTTPError:
        return None
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return None

    if not isinstance(rows, list) or not rows:
        return []
    first = rows[0]
    if not isinstance(first, dict):
        return []
    profiles = first.get("profiles")
    if not isinstance(profiles, list):
        return []
    return normalize_followed_profiles_for_storage(
        [p for p in profiles if isinstance(p, dict)]
    )


def upsert_user_linkedin_followed_profiles_to_database(
    access_token: str,
    supabase_url: str,
    anon_key: str,
    user_id: str,
    profiles: List[Dict[str, Any]],
) -> bool:
    """Grava ou actualiza os perfis seguidos do utilizador.

    Argumentos:
        access_token: JWT da sessão Supabase.
        supabase_url: URL base do projecto.
        anon_key: Chave anon.
        user_id: UUID do utilizador.
        profiles: Lista de perfis a persistir.

    Retorno:
        ``True`` se o upsert foi aceite; ``False`` em caso de erro.
    """

    token = str(access_token or "").strip()
    base = str(supabase_url or "").strip().rstrip("/")
    key = str(anon_key or "").strip()
    uid = str(user_id or "").strip()
    if not token or not base or not key or not uid:
        return False

    cleaned = normalize_followed_profiles_for_storage(profiles)
    payload = {
        "user_id": uid,
        "profiles": cleaned,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/rest/v1/user_linkedin_followed_profiles",
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
