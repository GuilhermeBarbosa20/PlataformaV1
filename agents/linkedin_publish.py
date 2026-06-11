"""Publicação de posts no LinkedIn via API oficial (UGC Posts)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib import error, request

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_GENERATED_DIR = BASE_DIR / "static" / "generated"
LINKEDIN_API_BASE = "https://api.linkedin.com/v2"


def normalize_linkedin_person_urn(raw: str) -> Optional[str]:
    """Normaliza um ID ou URN LinkedIn para ``urn:li:person:...``.

    Argumentos:
        raw: ``sub`` do userinfo, ``id`` do ``/v2/me`` ou URN completo.

    Retorno:
        URN canónico ou ``None`` se vazio.
    """

    rid = str(raw or "").strip()
    if not rid:
        return None
    if rid.startswith("urn:li:person:"):
        return rid
    return f"urn:li:person:{rid}"


def get_linkedin_person_urn(access_token: str) -> Optional[str]:
    """Obtém o URN da pessoa autenticada (`urn:li:person:...`).

    Tenta ``/v2/userinfo`` (OpenID) e, se falhar, ``/v2/me`` com token
    ``w_member_social``.

    Argumentos:
        access_token: Token OAuth LinkedIn com permissão de publicação.

    Retorno:
        URN no formato ``urn:li:person:{id}`` ou ``None`` se a API falhar.
    """

    token = str(access_token or "").strip()
    if not token:
        return None

    data = _linkedin_get_json(f"{LINKEDIN_API_BASE}/userinfo", token)
    if isinstance(data, dict):
        sub = str(data.get("sub") or "").strip()
        urn = normalize_linkedin_person_urn(sub)
        if urn:
            return urn

    status, _, raw = _linkedin_request(f"{LINKEDIN_API_BASE}/me", token, method="GET")
    if status == 200:
        try:
            me = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            me = None
        if isinstance(me, dict) and me.get("id"):
            urn = normalize_linkedin_person_urn(str(me.get("id")))
            if urn:
                return urn

    return None


def format_linkedin_post_text(post: Dict[str, Any]) -> str:
    """Monta o texto final do post para publicar no LinkedIn.

    Argumentos:
        post: Objecto do post com ``title``, ``body``, ``hook``, ``cta``.

    Retorno:
        String pronta para o campo ``shareCommentary.text``.
    """

    body = str(post.get("body") or "").strip()
    title = str(post.get("title") or "").strip()
    hook = str(post.get("hook") or "").strip()
    cta = str(post.get("cta") or "").strip()
    parts: list[str] = []
    if hook and hook not in body:
        parts.append(hook)
    if title and title not in body and title != "Post LinkedIn":
        parts.append(title)
    if body:
        parts.append(body)
    if cta and cta not in body:
        parts.append(cta)
    text = "\n\n".join(p for p in parts if p).strip()
    return text or body or title or ""


def publish_to_linkedin(
    access_token: str,
    person_urn: str,
    text: str,
    *,
    image_url: Optional[str] = None,
    visibility: str = "PUBLIC",
) -> Dict[str, Any]:
    """Publica um post no LinkedIn (texto ou texto + imagem).

    Replica o fluxo da API UGC: registo de upload, PUT da imagem e criação
    do post com ``shareMediaCategory`` IMAGE ou NONE.

    Argumentos:
        access_token: Token OAuth LinkedIn com permissão de publicação.
        person_urn: URN do autor (``urn:li:person:...``).
        text: Legenda / corpo do post.
        image_url: URL absoluta, relativa ``/static/generated/...`` ou ``None``.
        visibility: ``PUBLIC`` ou ``CONNECTIONS``.

    Retorno:
        Dicionário com ``success`` (bool), ``linkedin_post_urn`` (opcional)
        e ``error`` (opcional).
    """

    token = str(access_token or "").strip()
    author = str(person_urn or "").strip()
    caption = str(text or "").strip()
    vis = visibility if visibility in ("PUBLIC", "CONNECTIONS") else "PUBLIC"

    if not token or not author:
        return {"success": False, "error": "Token ou URN do perfil LinkedIn em falta."}
    if not caption:
        return {"success": False, "error": "O post não tem texto para publicar."}

    if image_url:
        registration = _register_image_upload(token, author)
        if not registration:
            return {"success": False, "error": "Não foi possível registar o upload da imagem no LinkedIn."}
        upload_url, asset = registration
        if not _upload_image_bytes(token, upload_url, image_url):
            return {"success": False, "error": "Falha ao enviar a imagem para o LinkedIn."}
        return _create_image_post(token, author, caption, asset, vis)

    return _create_text_post(token, author, caption, vis)


def _linkedin_get_json(url: str, access_token: str) -> Optional[Dict[str, Any]]:
    """Executa GET JSON na API LinkedIn.

    Argumentos:
        url: Endpoint completo.
        access_token: Bearer token.

    Retorno:
        Dicionário parseado ou ``None`` em erro.
    """

    req = request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, dict) else None
    except (error.HTTPError, error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return None


def _linkedin_request(
    url: str,
    access_token: str,
    *,
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Dict[str, str], bytes]:
    """Executa pedido HTTP à API LinkedIn e devolve status, headers e corpo.

    Argumentos:
        url: URL do endpoint.
        access_token: Bearer token.
        method: Método HTTP (GET, POST, PUT).
        body: Corpo JSON opcional.
        extra_headers: Cabeçalhos adicionais.

    Retorno:
        Tuplo ``(status_code, headers_dict, body_bytes)``.
    """

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    if extra_headers:
        headers.update(extra_headers)
    data_bytes = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data_bytes = json.dumps(body).encode("utf-8")
    req = request.Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, hdrs, raw
    except error.HTTPError as exc:
        raw = exc.read() if exc.fp else b""
        hdrs = {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}
        return exc.code, hdrs, raw


def _register_image_upload(access_token: str, person_urn: str) -> Optional[Tuple[str, str]]:
    """Regista upload de imagem no LinkedIn.

    Argumentos:
        access_token: Bearer token.
        person_urn: URN do proprietário da imagem.

    Retorno:
        Tuplo ``(upload_url, asset_urn)`` ou ``None``.
    """

    payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": person_urn,
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }
            ],
        }
    }
    status, _, raw = _linkedin_request(
        f"{LINKEDIN_API_BASE}/assets?action=registerUpload",
        access_token,
        method="POST",
        body=payload,
    )
    if status not in (200, 201):
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return None
    value = data.get("value") if isinstance(data, dict) else None
    if not isinstance(value, dict):
        return None
    mechanism = value.get("uploadMechanism") or {}
    http_req = mechanism.get("com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest") or {}
    upload_url = http_req.get("uploadUrl")
    asset = value.get("asset")
    if upload_url and asset:
        return str(upload_url), str(asset)
    return None


def _load_image_bytes(image_url: str) -> Tuple[Optional[bytes], str]:
    """Carrega bytes da imagem a partir de URL local ou remota.

    Argumentos:
        image_url: Caminho relativo ``/static/generated/...`` ou URL http(s).

    Retorno:
        Tuplo ``(bytes, content_type)`` ou ``(None, "")`` se falhar.
    """

    url = str(image_url or "").strip()
    if not url:
        return None, ""

    local_match = re.match(r"^/static/generated/([^/?#]+)$", url)
    if local_match:
        path = STATIC_GENERATED_DIR / local_match.group(1)
        if path.is_file():
            ext = path.suffix.lower()
            ctype = "image/png" if ext == ".png" else "image/jpeg"
            return path.read_bytes(), ctype
        return None, ""

    if url.startswith("/"):
        path = BASE_DIR / url.lstrip("/")
        if path.is_file():
            ext = path.suffix.lower()
            ctype = "image/png" if ext == ".png" else "image/jpeg"
            return path.read_bytes(), ctype

    if url.startswith("http://") or url.startswith("https://"):
        req = request.Request(url, headers={"Accept": "image/*"}, method="GET")
        try:
            with request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                ctype = resp.headers.get("Content-Type") or "image/png"
                return data, ctype.split(";")[0].strip() or "image/png"
        except (error.HTTPError, error.URLError, TimeoutError, OSError):
            return None, ""

    return None, ""


def _upload_image_bytes(access_token: str, upload_url: str, image_url: str) -> bool:
    """Envia bytes da imagem para o URL de upload do LinkedIn.

    Argumentos:
        access_token: Bearer token.
        upload_url: URL temporário devolvido pelo registo.
        image_url: Origem da imagem (local ou remota).

    Retorno:
        ``True`` se o upload for aceite.
    """

    image_bytes, content_type = _load_image_bytes(image_url)
    if not image_bytes:
        return False
    req = request.Request(
        upload_url,
        data=image_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": content_type or "image/png",
        },
        method="PUT",
    )
    try:
        with request.urlopen(req, timeout=90) as resp:
            return resp.status in (200, 201)
    except error.HTTPError as exc:
        return exc.code in (200, 201)
    except (error.URLError, TimeoutError, OSError):
        return False


def _create_text_post(
    access_token: str,
    person_urn: str,
    text: str,
    visibility: str,
) -> Dict[str, Any]:
    """Cria post só com texto na API UGC do LinkedIn.

    Argumentos:
        access_token: Bearer token.
        person_urn: URN do autor.
        text: Legenda do post.
        visibility: Visibilidade da rede.

    Retorno:
        Resultado com ``success`` e opcionalmente ``linkedin_post_urn``.
    """

    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
    }
    return _post_ugc(access_token, payload)


def _create_image_post(
    access_token: str,
    person_urn: str,
    text: str,
    image_asset: str,
    visibility: str,
) -> Dict[str, Any]:
    """Cria post com imagem na API UGC do LinkedIn.

    Argumentos:
        access_token: Bearer token.
        person_urn: URN do autor.
        text: Legenda do post.
        image_asset: URN do asset devolvido no registo de upload.
        visibility: Visibilidade da rede.

    Retorno:
        Resultado com ``success`` e opcionalmente ``linkedin_post_urn``.
    """

    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "IMAGE",
                "media": [{"status": "READY", "media": image_asset}],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
    }
    return _post_ugc(access_token, payload)


def _post_ugc(access_token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Envia POST para ``/ugcPosts`` e interpreta a resposta.

    Argumentos:
        access_token: Bearer token.
        payload: Corpo JSON do post UGC.

    Retorno:
        Dicionário com resultado da publicação.
    """

    status, headers, raw = _linkedin_request(
        f"{LINKEDIN_API_BASE}/ugcPosts",
        access_token,
        method="POST",
        body=payload,
    )
    if status in (200, 201):
        post_urn = headers.get("x-restli-id") or headers.get("x-linkedIn-id")
        return {"success": True, "linkedin_post_urn": post_urn}
    err_text = raw.decode("utf-8", errors="replace")[:500]
    revoked = is_linkedin_token_revoked_error(status, err_text)
    if revoked:
        return {
            "success": False,
            "error": (
                "O token de publicação LinkedIn foi revogado ou expirou. "
                "Clica em «Reautorizar publicação LinkedIn» e aceita as permissões outra vez."
            ),
            "token_revoked": True,
        }
    hint = ""
    if status in (401, 403):
        hint = (
            " Verifica se autorizaste publicação com w_member_social "
            "(botão «Autorizar publicação LinkedIn», não só o login)."
        )
    return {
        "success": False,
        "error": f"LinkedIn API {status}: {err_text}{hint}",
        "token_revoked": False,
    }


def resolve_linkedin_publish_token_and_urn(
    *,
    client_token: str = "",
    client_person_urn: str = "",
    oauth_row: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Escolhe token e URN válidos para publicar (browser primeiro, depois BD).

    Argumentos:
        client_token: Token recente do ``sessionStorage`` (fluxo connect-publish).
        client_person_urn: URN guardado no browser após OAuth.
        oauth_row: Linha ``user_linkedin_publish_oauth`` da Supabase.

    Retorno:
        Tuplo ``(access_token, person_urn)`` — pode estar vazio se nada existir.
    """

    db_tok = ""
    db_urn = ""
    if isinstance(oauth_row, dict):
        db_tok = str(oauth_row.get("linkedin_access_token") or "").strip()
        db_urn = str(oauth_row.get("linkedin_person_urn") or "").strip()

    client_tok = str(client_token or "").strip()
    client_urn = str(client_person_urn or "").strip()

    for tok, urn_hint in ((client_tok, client_urn), (db_tok, db_urn)):
        if not tok:
            continue
        urn = urn_hint or (get_linkedin_person_urn(tok) or "")
        if urn:
            return tok, urn

    return client_tok or db_tok, client_urn or db_urn


def is_linkedin_token_revoked_error(status: int, body: str) -> bool:
    """Indica se a LinkedIn recusou o pedido por token revogado ou inválido.

    Argumentos:
        status: Código HTTP da API LinkedIn.
        body: Corpo da resposta (JSON ou texto).

    Retorno:
        ``True`` para ``REVOKED_ACCESS_TOKEN`` e erros equivalentes de auth.
    """

    if int(status) not in (401, 403):
        return False
    text = str(body or "").casefold()
    markers = (
        "revoked_access_token",
        '"code":"revoked_access_token"',
        "serviceerrorcode\":65601",
        "serviceerrorcode\":65600",
        "invalid access token",
        "expired access token",
    )
    return any(m in text for m in markers)
