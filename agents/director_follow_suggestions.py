"""Sugestão de perfis LinkedIn para comentar, com base na estratégia/ICP.

O Diretor propõe líderes de opinião alinhados ao nicho; o utilizador confirma
antes de os adicionar à lista de perfis seguidos (recolha de posts via Apify).
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse

from openai import OpenAI

from agents.director_strategy import _parse_llm_json, strategy_brief_for_execution
from agents.social_media import canonicalize_linkedin_profile_url


def _slug_from_url_or_vanity(value: str) -> str:
    """Extrai slug ``/in/`` ou ``/company/`` de URL ou texto.

    Argumentos:
        value: URL LinkedIn ou slug isolado.

    Retorno:
        Slug normalizado ou string vazia.
    """

    raw = str(value or "").strip().rstrip("/")
    if not raw:
        return ""
    if "linkedin.com" in raw.casefold():
        path = urlparse(raw).path.strip("/")
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"in", "company"}:
            return parts[1].strip()
        return ""
    return re.sub(r"[^a-zA-Z0-9\-_]", "", raw.split("/")[-1]).strip()


def profile_url_from_suggestion(
    profile_url: str = "",
    linkedin_slug: str = "",
    profile_type: str = "person",
) -> str:
    """Constrói URL LinkedIn canónico a partir de URL ou slug.

    Argumentos:
        profile_url: URL completo, se já conhecido.
        linkedin_slug: Vanity slug (ex.: ``satyanadella``).
        profile_type: ``person`` → ``/in/``; ``company`` → ``/company/``.

    Retorno:
        URL canónico ou string vazia se inválido.
    """

    direct = str(profile_url or "").strip()
    if direct and "linkedin.com" in direct.casefold():
        canon = canonicalize_linkedin_profile_url(direct)
        if canon:
            return canon

    slug = _slug_from_url_or_vanity(linkedin_slug or direct)
    if not slug or len(slug) < 2:
        return ""

    kind = str(profile_type or "person").strip().casefold()
    segment = "company" if kind in {"company", "empresa", "organization"} else "in"
    built = f"https://www.linkedin.com/{segment}/{slug}/"
    return canonicalize_linkedin_profile_url(built) or built


def normalize_profile_suggestion(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normaliza uma sugestão devolvida pelo LLM.

    Argumentos:
        raw: Entrada bruta com ``display_name``, ``profile_url`` ou ``linkedin_slug``.

    Retorno:
        Sugestão normalizada com ``id``, ``status=pending`` ou ``None`` se inválida.
    """

    if not isinstance(raw, dict):
        return None

    name = str(
        raw.get("display_name")
        or raw.get("name")
        or raw.get("author_name")
        or ""
    ).strip()
    url = profile_url_from_suggestion(
        str(raw.get("profile_url") or raw.get("url") or ""),
        str(raw.get("linkedin_slug") or raw.get("slug") or raw.get("vanity") or ""),
        str(raw.get("profile_type") or raw.get("type") or "person"),
    )
    if not url:
        return None

    rationale = str(
        raw.get("rationale")
        or raw.get("reason")
        or raw.get("why")
        or ""
    ).strip()
    if not name:
        slug = _slug_from_url_or_vanity(url)
        name = slug.replace("-", " ").title() if slug else "Perfil LinkedIn"

    return {
        "id": str(raw.get("id") or uuid.uuid4().hex[:12]),
        "display_name": name,
        "profile_url": url,
        "rationale": rationale[:400],
        "profile_type": str(raw.get("profile_type") or "person"),
        "status": str(raw.get("status") or "pending"),
    }


def suggest_followed_profiles_from_strategy(
    client: OpenAI,
    model: str,
    state: Dict[str, Any],
    language: str,
    *,
    count: int = 5,
    exclude_urls: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Sugere perfis LinkedIn para comentar, alinhados à estratégia aprovada.

    Usa o ICP, pilares de conteúdo e objetivos SMART para propor líderes de
    opinião ou empresas relevantes no mesmo nicho. O utilizador deve confirmar
    cada sugestão — os URLs podem precisar de verificação manual no LinkedIn.

    Argumentos:
        client: Cliente OpenAI autenticado.
        model: Modelo de chat (ex.: ``gpt-4o-mini``).
        state: Estado do workflow com ``strategy`` e opcionalmente ``linkedin_analysis``.
        language: Idioma da resposta (ex.: ``pt-PT``).
        count: Número máximo de sugestões (1–8).
        exclude_urls: URLs já na lista de perfis seguidos (evitar duplicados).

    Retorno:
        ``{suggestions, reply, success}`` — ``suggestions`` é lista normalizada.
    """

    strategy = state.get("strategy") if isinstance(state.get("strategy"), dict) else {}
    brief = strategy_brief_for_execution(strategy)
    if not brief and not strategy.get("summary"):
        return {
            "success": False,
            "suggestions": [],
            "reply": (
                "Preciso de uma estratégia definida (ICP e objetivos) antes de sugerir perfis. "
                "Completa e aprova a estratégia no painel."
            ),
        }

    analysis = state.get("linkedin_analysis") if isinstance(state.get("linkedin_analysis"), dict) else {}
    industry = str(analysis.get("setor") or analysis.get("industry") or "").strip()
    own_url = str(state.get("linkedin_profile_url") or analysis.get("profile_url") or "").strip()

    excluded = {
        str(u).rstrip("/").casefold()
        for u in (exclude_urls or [])
        if str(u).strip()
    }
    if own_url:
        excluded.add(own_url.rstrip("/").casefold())

    n = max(1, min(8, int(count)))

    system_prompt = (
        f"És o Diretor de Marketing AI — especialista em LinkedIn B2B em {language}. "
        "Com base na estratégia do utilizador, sugere perfis LinkedIn onde comentar "
        "publicações de terceiros gera autoridade e networking no nicho certo. "
        "Prioriza: líderes de opinião, fundadores, CMOs, especialistas reconhecidos "
        "e (se relevante) páginas de empresa influentes no sector. "
        "Usa slugs LinkedIn reais e conhecidos — NÃO inventes URLs fictícios. "
        "Se não tiveres certeza do slug exacto, usa o slug mais provável do nome público "
        "e indica isso na rationale. "
        "Responde APENAS JSON: "
        '{"reply":"<1-2 frases ao utilizador>",'
        '"profiles":[{"display_name":"","linkedin_slug":"","profile_type":"person|company",'
        '"rationale":"<porque este perfil encaixa no ICP/estratégia>"}]}'
    )
    user_prompt = (
        f"Estratégia:\n{brief or json.dumps(strategy, ensure_ascii=False)[:3500]}\n\n"
        f"Sector inferido: {industry or 'n/d'}\n"
        f"Perfis a excluir (já na lista): {', '.join(sorted(excluded)) or 'nenhum'}\n\n"
        f"Sugere exactamente até {n} perfis distintos para o utilizador seguir e comentar."
    )

    response = client.chat.completions.create(
        model=model,
        temperature=0.45,
        max_tokens=2048,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    data = _parse_llm_json(raw)
    profiles_raw = data.get("profiles") if isinstance(data.get("profiles"), list) else []
    if not profiles_raw and isinstance(data.get("suggestions"), list):
        profiles_raw = data.get("suggestions")

    suggestions: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for row in profiles_raw:
        if not isinstance(row, dict):
            continue
        norm = normalize_profile_suggestion(row)
        if not norm:
            continue
        key = norm["profile_url"].rstrip("/").casefold()
        if key in excluded or key in seen:
            continue
        seen.add(key)
        suggestions.append(norm)
        if len(suggestions) >= n:
            break

    reply = str(data.get("reply") or "").strip()
    if not suggestions:
        return {
            "success": False,
            "suggestions": [],
            "reply": reply or "Não consegui gerar sugestões válidas. Tenta adicionar perfis manualmente.",
        }

    if not reply:
        reply = (
            f"Sugeri {len(suggestions)} perfil(is) alinhados com a tua estratégia. "
            "Confirma no painel e depois clica em «Actualizar perfis guardados»."
        )

    return {
        "success": True,
        "suggestions": suggestions,
        "reply": reply,
    }


def merge_suggestions_into_state(
    existing: List[Dict[str, Any]],
    new_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Funde novas sugestões na lista, substituindo pendentes antigas.

    Argumentos:
        existing: ``followed_profile_suggestions`` actual.
        new_items: Sugestões recém-geradas.

    Retorno:
        Lista actualizada (máx. 12 entradas, priorizando pendentes novas).
    """

    kept = [
        dict(s)
        for s in (existing or [])
        if isinstance(s, dict) and str(s.get("status") or "") == "accepted"
    ]
    pending_new = [dict(s) for s in new_items if isinstance(s, dict)]
    for item in pending_new:
        item["status"] = "pending"
    merged = pending_new + kept
    return merged[:12]


def accept_followed_suggestions(
    profiles: List[Dict[str, Any]],
    suggestions: List[Dict[str, Any]],
    suggestion_ids: Optional[Sequence[str]] = None,
    *,
    accept_all: bool = False,
) -> Dict[str, Any]:
    """Move sugestões aprovadas para a lista de perfis seguidos.

    Argumentos:
        profiles: Lista ``followed_profiles`` actual.
        suggestions: Lista ``followed_profile_suggestions``.
        suggestion_ids: IDs das sugestões a aceitar (ignorado se ``accept_all``).
        accept_all: Se ``True``, aceita todas com ``status=pending``.

    Retorno:
        ``{profiles, suggestions, added_count, added_names}``.
    """

    from agents.director_follow_feed import normalize_followed_profile

    ids_wanted = {str(i).strip() for i in (suggestion_ids or []) if str(i).strip()}
    want_all = bool(accept_all) or not ids_wanted

    known_urls = {
        str(p.get("profile_url") or "").rstrip("/").casefold()
        for p in profiles
        if isinstance(p, dict) and p.get("profile_url")
    }

    added_names: List[str] = []
    updated_profiles = [dict(p) for p in profiles if isinstance(p, dict)]
    updated_suggestions: List[Dict[str, Any]] = []

    for sug in suggestions:
        if not isinstance(sug, dict):
            continue
        row = dict(sug)
        sid = str(row.get("id") or "")
        is_pending = str(row.get("status") or "pending") == "pending"
        should_accept = is_pending and (want_all or sid in ids_wanted)
        if should_accept:
            url = str(row.get("profile_url") or "").strip()
            key = url.rstrip("/").casefold()
            if url and key not in known_urls:
                updated_profiles.append(
                    normalize_followed_profile(url, row.get("display_name"))
                )
                known_urls.add(key)
                added_names.append(str(row.get("display_name") or url))
            row["status"] = "accepted"
        updated_suggestions.append(row)

    return {
        "profiles": updated_profiles,
        "suggestions": updated_suggestions,
        "added_count": len(added_names),
        "added_names": added_names,
    }
