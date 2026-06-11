"""Tentativa de ler o feed da rede LinkedIn (publicações de ligações/seguidos).

A API oficial ``activityFeeds?q=networkShares`` só funciona para apps LinkedIn
aprovados com permissões alargadas — o login Supabase OIDC típico (openid,
profile, email, w_member_social) **não** inclui leitura do feed. Este módulo
tenta o endpoint e devolve erro claro quando a LinkedIn recusa.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, parse, request

LINKEDIN_API = "https://api.linkedin.com/v2"


def _get_json(url: str, access_token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """GET JSON na API LinkedIn com mensagem de erro legível.

    Argumentos:
        url: URL completa do endpoint.
        access_token: Bearer token (``provider_token`` da sessão).

    Retorno:
        Tuplo ``(dados, erro)`` — um dos dois é ``None``.
    """

    token = str(access_token or "").strip()
    if not token:
        return None, "Token LinkedIn em falta. Liga o LinkedIn no painel."

    req = request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return (data if isinstance(data, dict) else {}), None
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        if exc.code in (401, 403):
            return None, (
                "A LinkedIn não autoriza ler o teu feed com esta app "
                f"(HTTP {exc.code}). Usa «Adicionar perfil» com o URL de quem segues."
            )
        return None, f"LinkedIn API {exc.code}: {body or exc.reason}"
    except (error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        return None, str(exc)


def _extract_text_from_share(share: Dict[str, Any]) -> str:
    """Extrai texto legível de um objecto share/ugc da API LinkedIn."""

    if not isinstance(share, dict):
        return ""
    for key in ("text", "commentary", "message", "body"):
        val = share.get(key)
        if isinstance(val, dict):
            val = val.get("text")
        if isinstance(val, str) and val.strip():
            return val.strip()
    content = share.get("content")
    if isinstance(content, dict):
        title = content.get("title") or content.get("headline")
        if isinstance(title, str):
            return title.strip()
    return ""


def _parse_activity_feed_elements(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Converte resposta ``activityFeeds`` em entradas da fila do Diretor."""

    elements = payload.get("elements")
    if not isinstance(elements, list):
        return []

    posts: List[Dict[str, Any]] = []
    for item in elements:
        if not isinstance(item, dict):
            continue
        ref = item.get("reference")
        if isinstance(ref, dict):
            share = ref
        elif isinstance(ref, str):
            share = item
        else:
            share = item

        text = _extract_text_from_share(share if isinstance(share, dict) else {})
        url = ""
        if isinstance(share, dict):
            url = str(share.get("url") or share.get("permalink") or "").strip()

        owner = share.get("owner") if isinstance(share, dict) else None
        author_name = "Ligação LinkedIn"
        profile_url = ""
        if isinstance(owner, dict):
            author_name = str(
                owner.get("localizedFirstName") or owner.get("name") or author_name
            ).strip()
            last = str(owner.get("localizedLastName") or "").strip()
            if last:
                author_name = f"{author_name} {last}".strip()
            vanity = str(owner.get("vanityName") or owner.get("publicIdentifier") or "").strip()
            if vanity:
                profile_url = f"https://www.linkedin.com/in/{vanity}"

        if not text and not url:
            continue
        posts.append(
            {
                "id": uuid.uuid4().hex[:12],
                "profile_url": profile_url,
                "author_name": author_name,
                "post_url": url,
                "snippet": text[:600],
                "published_label": "Feed da rede",
                "status": "pending",
                "source": "linkedin_network_feed",
            }
        )
    return posts


def fetch_linkedin_network_feed_posts(
    provider_token: str,
    *,
    count: int = 15,
) -> Dict[str, Any]:
    """Tenta obter publicações do feed da rede (ligações) via API LinkedIn.

    Argumentos:
        provider_token: ``session.provider_token`` do login Supabase LinkedIn.
        count: Número máximo de entradas pedidas.

    Retorno:
        ``{success, posts, message, api_available}`` — ``success`` é ``False`` quando
        a app não tem permissão (caso habitual com OIDC standard).
    """

    n = max(1, min(30, int(count)))
    query = parse.urlencode({"q": "networkShares", "count": str(n)})
    url = f"{LINKEDIN_API}/activityFeeds?{query}"
    data, err = _get_json(url, provider_token)
    if err:
        return {
            "success": False,
            "posts": [],
            "message": err,
            "api_available": False,
        }
    posts = _parse_activity_feed_elements(data or {})
    if not posts:
        return {
            "success": False,
            "posts": [],
            "message": (
                "O feed veio vazio ou num formato não suportado. "
                "Adiciona manualmente o URL de perfis que segues."
            ),
            "api_available": True,
        }
    return {
        "success": True,
        "posts": posts,
        "message": f"Importámos {len(posts)} publicações do teu feed LinkedIn.",
        "api_available": True,
    }
