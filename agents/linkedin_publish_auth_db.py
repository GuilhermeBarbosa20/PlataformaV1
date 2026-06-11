"""Persistência da autorização OAuth LinkedIn para publicar posts (por utilizador)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


def _token_expires_at_iso(expires_in: Optional[int]) -> Optional[str]:
    """Calcula timestamp ISO de expiração a partir de ``expires_in`` em segundos.

    Argumentos:
        expires_in: Segundos até expirar devolvidos pelo LinkedIn.

    Retorno:
        String ISO UTC ou ``None`` se ``expires_in`` não for positivo.
    """

    if not expires_in or int(expires_in) <= 0:
        return None
    exp = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
    return exp.isoformat()


def fetch_user_linkedin_publish_oauth_from_database(
    access_token: str,
    supabase_url: str,
    anon_key: str,
) -> Optional[Dict[str, Any]]:
    """Lê a autorização de publicação LinkedIn do utilizador autenticado.

    Argumentos:
        access_token: JWT ``access_token`` da sessão Supabase.
        supabase_url: URL base do projecto Supabase.
        anon_key: Chave anon do Supabase.

    Retorno:
        Dicionário com ``linkedin_access_token``, ``linkedin_person_urn``,
        ``token_expires_at`` e ``authorized_at``, ou ``None`` se não existir
        ou estiver expirado.
    """

    token = str(access_token or "").strip()
    base = str(supabase_url or "").strip().rstrip("/")
    key = str(anon_key or "").strip()
    if not token or not base or not key:
        return None

    query = urllib.parse.urlencode(
        {
            "select": "linkedin_access_token,linkedin_refresh_token,linkedin_person_urn,token_expires_at,authorized_at",
            "limit": "1",
        }
    )
    url = f"{base}/rest/v1/user_linkedin_publish_oauth?{query}"
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
    row = rows[0]
    if not isinstance(row, dict):
        return None

    access = str(row.get("linkedin_access_token") or "").strip()
    if not access:
        return None

    expires_raw = row.get("token_expires_at")
    if expires_raw:
        try:
            exp = datetime.fromisoformat(str(expires_raw).replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                return None
        except ValueError:
            pass

    return {
        "linkedin_access_token": access,
        "linkedin_refresh_token": row.get("linkedin_refresh_token"),
        "linkedin_person_urn": row.get("linkedin_person_urn"),
        "token_expires_at": expires_raw,
        "authorized_at": row.get("authorized_at"),
    }


def upsert_user_linkedin_publish_oauth_to_database(
    access_token: str,
    supabase_url: str,
    anon_key: str,
    user_id: str,
    *,
    linkedin_access_token: str,
    linkedin_person_urn: Optional[str] = None,
    linkedin_refresh_token: Optional[str] = None,
    expires_in: Optional[int] = None,
) -> bool:
    """Grava ou actualiza a autorização de publicação LinkedIn do utilizador.

    Argumentos:
        access_token: JWT da sessão Supabase.
        supabase_url: URL base do projecto.
        anon_key: Chave anon.
        user_id: UUID do utilizador.
        linkedin_access_token: Token com permissão ``w_member_social``.
        linkedin_person_urn: URN do membro LinkedIn (opcional).
        linkedin_refresh_token: Refresh token OAuth (opcional).
        expires_in: Segundos até expirar (opcional).

    Retorno:
        ``True`` se o upsert foi aceite; ``False`` em caso de erro.
    """

    token = str(access_token or "").strip()
    base = str(supabase_url or "").strip().rstrip("/")
    key = str(anon_key or "").strip()
    uid = str(user_id or "").strip()
    publish_tok = str(linkedin_access_token or "").strip()
    if not token or not base or not key or not uid or not publish_tok:
        return False

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "user_id": uid,
        "linkedin_access_token": publish_tok,
        "linkedin_refresh_token": linkedin_refresh_token,
        "linkedin_person_urn": linkedin_person_urn,
        "token_expires_at": _token_expires_at_iso(expires_in),
        "authorized_at": now,
        "updated_at": now,
    }
    body = json.dumps(payload).encode("utf-8")
    upsert_url = f"{base}/rest/v1/user_linkedin_publish_oauth?on_conflict=user_id"
    req = urllib.request.Request(
        upsert_url,
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


def publish_oauth_status_for_client(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Expõe estado de autorização sem devolver o token ao frontend.

    Argumentos:
        row: Linha devolvida por ``fetch_user_linkedin_publish_oauth_from_database``.

    Retorno:
        ``{"authorized": bool, "expires_at": ..., "authorized_at": ...}``.
    """

    if not row:
        return {"authorized": False, "expires_at": None, "authorized_at": None}
    return {
        "authorized": True,
        "expires_at": row.get("token_expires_at"),
        "authorized_at": row.get("authorized_at"),
    }
