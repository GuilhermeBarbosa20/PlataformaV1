"""OAuth LinkedIn com scope de publicação (w_member_social), separado do login Supabase OIDC."""

from __future__ import annotations

import json
import os
import secrets
import time
from typing import Any, Dict, Optional, Tuple
from urllib import error, parse, request

from agents.linkedin_publish import get_linkedin_person_urn

LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
DEFAULT_SCOPES = "openid profile email w_member_social"

# state -> {created_at, redirect_after}
_oauth_states: Dict[str, Dict[str, Any]] = {}
_STATE_TTL_SEC = 600


def linkedin_oauth_configured() -> bool:
    """Indica se CLIENT_ID e CLIENT_SECRET estão definidos no ambiente.

    Retorno:
        ``True`` quando ambas as variáveis existem.
    """

    return bool(_client_id() and _client_secret())


def _client_id() -> str:
    return str(os.getenv("LINKEDIN_CLIENT_ID") or "").strip()


def _client_secret() -> str:
    return str(os.getenv("LINKEDIN_CLIENT_SECRET") or "").strip()


def linkedin_publish_redirect_uri(base_url: str) -> str:
    """Constrói o redirect URI para o fluxo de publicação.

    Argumentos:
        base_url: Origem da app (ex.: ``http://127.0.0.1:8000``).

    Retorno:
        URL absoluta do callback de publicação.
    """

    env_uri = str(os.getenv("LINKEDIN_PUBLISH_REDIRECT_URI") or "").strip()
    if env_uri:
        return env_uri
    return f"{base_url.rstrip('/')}/agents/linkedin/connect-publish/callback"


def create_publish_authorization_url(*, base_url: str, return_path: str = "/agentes/linkedin-perfil") -> str:
    """Gera URL de autorização LinkedIn com scopes de publicação.

    Argumentos:
        base_url: Origem HTTP da aplicação.
        return_path: Caminho para redirecionar após sucesso.

    Retorno:
        URL completa para redireccionar o browser do utilizador.

    Raises:
        RuntimeError: Se as credenciais LinkedIn não estiverem configuradas.
    """

    client_id = _client_id()
    if not client_id or not _client_secret():
        raise RuntimeError("LINKEDIN_CLIENT_ID ou LINKEDIN_CLIENT_SECRET em falta no .env.")

    state = secrets.token_urlsafe(24)
    _oauth_states[state] = {
        "created_at": time.time(),
        "return_path": return_path,
    }
    _prune_states()

    scopes = str(os.getenv("LINKEDIN_SCOPES") or DEFAULT_SCOPES).strip()
    redirect_uri = linkedin_publish_redirect_uri(base_url)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": scopes,
    }
    return f"{LINKEDIN_AUTH_URL}?{parse.urlencode(params)}"


def exchange_code_for_publish_token(
    code: str,
    *,
    base_url: str,
) -> Dict[str, Any]:
    """Troca o authorization code por access token com permissão de publicação.

    Argumentos:
        code: Código devolvido pelo LinkedIn no callback.
        base_url: Origem da app (para o redirect_uri).

    Retorno:
        Dicionário com ``access_token``, ``expires_in``, ``person_urn``, ``scope``.

    Raises:
        RuntimeError: Em falha de troca de token ou credenciais em falta.
    """

    client_id = _client_id()
    client_secret = _client_secret()
    if not client_id or not client_secret:
        raise RuntimeError("Credenciais LinkedIn não configuradas.")

    redirect_uri = linkedin_publish_redirect_uri(base_url)
    body = parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")

    req = request.Request(
        LINKEDIN_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Troca de token LinkedIn falhou ({exc.code}): {err_body}") from exc
    except (error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Troca de token LinkedIn falhou: {exc!s}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Resposta de token LinkedIn inválida.")

    access_token = str(data.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("LinkedIn não devolveu access_token.")

    person_urn = get_linkedin_person_urn(access_token)
    return {
        "access_token": access_token,
        "expires_in": int(data.get("expires_in") or 5184000),
        "refresh_token": data.get("refresh_token"),
        "scope": data.get("scope"),
        "person_urn": person_urn,
    }


def pop_oauth_state(state: str) -> Optional[Dict[str, Any]]:
    """Valida e remove um state OAuth (protecção CSRF).

    Argumentos:
        state: Valor recebido no callback.

    Retorno:
        Metadados associados ao state ou ``None`` se inválido/expirado.
    """

    _prune_states()
    entry = _oauth_states.pop(str(state or "").strip(), None)
    if not entry:
        return None
    if time.time() - float(entry.get("created_at") or 0) > _STATE_TTL_SEC:
        return None
    return entry


def _prune_states() -> None:
    """Remove states OAuth expirados da memória."""

    now = time.time()
    expired = [k for k, v in _oauth_states.items() if now - float(v.get("created_at") or 0) > _STATE_TTL_SEC]
    for key in expired:
        _oauth_states.pop(key, None)
