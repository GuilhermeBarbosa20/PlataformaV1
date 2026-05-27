"""Visão Geral LinkedIn via harvestapi/linkedin-profile-scraper (campos Apify)."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from agents.social_media import is_placeholder_metric_display

# Ordem dos campos devolvidos por harvestapi/linkedin-profile-scraper.
HARVEST_LINKEDIN_PROFILE_FIELD_ORDER: Tuple[str, ...] = (
    "about",
    "causes",
    "certifications",
    "composeOptionType",
    "connectionsCount",
    "courses",
    "coverPicture",
    "creator",
    "currentPosition",
    "education",
    "emails",
    "experience",
    "featured",
    "firstName",
    "followerCount",
    "headline",
    "hiring",
    "honorsAndAwards",
    "id",
    "influencer",
    "languages",
    "lastName",
    "linkedinUrl",
    "location",
    "memorialized",
    "moreProfiles",
    "multiLocaleHeadline",
    "objectUrn",
    "openToWork",
    "organizations",
    "originalQuery",
    "patents",
    "photo",
    "premium",
    "primaryLocale",
    "profileLocales",
    "profilePicture",
    "profileTopEducation",
    "projects",
    "publicIdentifier",
    "publications",
    "receivedRecommendations",
    "registeredAt",
    "services",
    "skills",
    "topSkills",
    "verified",
    "volunteering",
)

HARVEST_LINKEDIN_PROFILE_LABELS_PT: Dict[str, str] = {
    "about": "About",
    "causes": "Causes",
    "certifications": "Certifications",
    "composeOptionType": "Compose Option Type",
    "connectionsCount": "Connections Count",
    "courses": "Courses",
    "coverPicture": "Cover Picture",
    "creator": "Creator",
    "currentPosition": "Current Position",
    "education": "Education",
    "emails": "Emails",
    "experience": "Experience",
    "featured": "Featured",
    "firstName": "First Name",
    "followerCount": "Follower Count",
    "headline": "Headline",
    "hiring": "Hiring",
    "honorsAndAwards": "Honors And Awards",
    "id": "ID",
    "influencer": "Influencer",
    "languages": "Languages",
    "lastName": "Last Name",
    "linkedinUrl": "Linkedin URL",
    "location": "Location",
    "memorialized": "Memorialized",
    "moreProfiles": "More Profiles",
    "multiLocaleHeadline": "Multi Locale Headline",
    "objectUrn": "Object Urn",
    "openToWork": "Open To Work",
    "organizations": "Organizations",
    "originalQuery": "Original Query",
    "patents": "Patents",
    "photo": "Photo",
    "premium": "Premium",
    "primaryLocale": "Primary Locale",
    "profileLocales": "Profile Locales",
    "profilePicture": "Profile Picture",
    "profileTopEducation": "Profile Top Education",
    "projects": "Projects",
    "publicIdentifier": "Public Identifier",
    "publications": "Publications",
    "receivedRecommendations": "Received Recommendations",
    "registeredAt": "Registered At",
    "services": "Services",
    "skills": "Skills",
    "topSkills": "Top Skills",
    "verified": "Verified",
    "volunteering": "Volunteering",
}

LINKEDIN_POST_DERIVED_METRIC_KEYS: frozenset[str] = frozenset(
    {
        "taxa_engagement_publicacoes",
        "publicacoes_no_periodo",
        "cadencia_dias_entre_posts",
        "publicacoes_analisadas",
        "reacoes_medias_por_publicacao",
        "comentarios_medios_por_publicacao",
        "cadencia_publicacao",
        "tipo_conteudo_mais_eficaz",
        "alcance_medio",
        "impressoes",
        "visualizacoes_perfil",
        "ligacoes",
        "seguidores",
    }
)


def _format_metric_number(value: Any) -> Optional[str]:
    """Formata número para cartões de métricas (pt-PT).

    Argumentos:
        value: Valor numérico ou texto convertível.

    Retorno:
        String com separador de milhares em ponto, ou ``None``.
    """

    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num:
        return None
    if abs(num - round(num)) < 0.01:
        return f"{int(round(num)):,}".replace(",", ".")
    return f"{num:.2f}".replace(".", ",")


def harvest_linkedin_profile_field_label_pt(field_key: str) -> str:
    """Devolve o rótulo legível de um campo harvestapi.

    Argumentos:
        field_key: Chave camelCase do JSON Apify.

    Retorno:
        Etiqueta para a UI.
    """

    key = str(field_key or "").strip()
    if key in HARVEST_LINKEDIN_PROFILE_LABELS_PT:
        return HARVEST_LINKEDIN_PROFILE_LABELS_PT[key]
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
    return spaced[:1].upper() + spaced[1:] if spaced else key


def _harvest_linkedin_location_text(location: Any) -> Optional[str]:
    """Extrai texto legível do campo ``location`` harvestapi."""

    if location is None:
        return None
    if isinstance(location, str):
        text = location.strip()
        return text or None
    if isinstance(location, dict):
        parsed = location.get("parsed")
        if isinstance(parsed, dict):
            text = str(parsed.get("text") or "").strip()
            if text:
                return text
        text = str(location.get("linkedinText") or location.get("text") or "").strip()
        return text or None
    return None


def _harvest_media_url(value: Any) -> Optional[str]:
    """Extrai URL de ``photo``, ``profilePicture`` ou ``coverPicture``."""

    if isinstance(value, str) and value.strip().startswith("http"):
        return value.strip()
    if isinstance(value, dict):
        direct = value.get("url")
        if isinstance(direct, str) and direct.strip().startswith("http"):
            return direct.strip()
        sizes = value.get("sizes")
        if isinstance(sizes, list):
            for item in sizes:
                if isinstance(item, dict):
                    u = item.get("url")
                    if isinstance(u, str) and u.strip().startswith("http"):
                        return u.strip()
    return None


def _harvest_list_item_title(item: Any) -> str:
    """Extrai título legível de um item de lista harvestapi (publicação, experiência, etc.)."""

    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return str(item).strip()
    for key in (
        "title",
        "name",
        "companyName",
        "schoolName",
        "position",
        "headline",
        "subtitle",
        "publisher",
    ):
        text = str(item.get(key) or "").strip()
        if text:
            return text
    return ""


def _harvest_summarize_list_items(items: List[Any], *, max_items: int = 3) -> str:
    """Resume lista harvestapi para um cartão."""

    if not items:
        return ""
    parts: List[str] = []
    for item in items[:max_items]:
        text = _harvest_list_item_title(item)
        if text:
            parts.append(text[:80])
    count = len(items)
    if not parts:
        return str(count)
    suffix = f" (+{count - max_items} mais)" if count > max_items else ""
    return f"{count} — " + "; ".join(parts) + suffix


def _format_harvest_profile_field_for_display(field_key: str, value: Any) -> Optional[str]:
    """Formata um campo harvestapi para exibição na Visão Geral."""

    if value is None:
        return None

    key = str(field_key or "").strip()

    if isinstance(value, bool):
        return "Sim" if value else "Não"

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        fmt = _format_metric_number(value)
        return fmt if fmt is not None else str(value)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if key == "about":
            return text[:1200] + ("…" if len(text) > 1200 else "")
        if key in {
            "photo",
            "profilePicture",
            "coverPicture",
            "logo",
            "backgroundCover",
        } and text.startswith("http"):
            return text[:500]
        if key == "description":
            return text[:1200] + ("…" if len(text) > 1200 else "")
        return text[:500] + ("…" if len(text) > 500 else "")

    if key == "location":
        return _harvest_linkedin_location_text(value)

    if key in {
        "photo",
        "profilePicture",
        "coverPicture",
        "logo",
        "backgroundCover",
    }:
        return _harvest_media_url(value)

    if key in {"logos", "backgroundCovers"} and isinstance(value, list):
        for item in value:
            url = _harvest_media_url(item)
            if url:
                return url
        return None

    if key == "certifications":
        return None

    if isinstance(value, list):
        if not value:
            return None
        if all(isinstance(x, str) for x in value):
            joined = ", ".join(str(x).strip() for x in value[:12] if str(x).strip())
            extra = len(value) - 12
            if extra > 0:
                joined += f" (+{extra} mais)"
            return joined[:600] if joined else str(len(value))
        if key == "emails":
            emails: List[str] = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    emails.append(item.strip())
                elif isinstance(item, dict):
                    em = str(item.get("email") or item.get("address") or "").strip()
                    if em:
                        emails.append(em)
            return ", ".join(emails[:5]) if emails else _harvest_summarize_list_items(value)
        if key == "currentPosition":
            companies: List[str] = []
            for item in value:
                if isinstance(item, dict):
                    c = str(item.get("companyName") or item.get("title") or "").strip()
                    if c:
                        companies.append(c)
            return "; ".join(companies[:5]) if companies else _harvest_summarize_list_items(value)
        if key in {"specialities", "industries", "locations"}:
            tags: List[str] = []
            for item in value[:24]:
                if isinstance(item, str) and item.strip():
                    tags.append(item.strip())
                elif isinstance(item, dict):
                    t = str(
                        item.get("name")
                        or item.get("title")
                        or item.get("linkedinText")
                        or item.get("text")
                        or ""
                    ).strip()
                    if t:
                        tags.append(t)
            if tags:
                return " · ".join(tags[:20]) + (f" (+{len(value) - 20} mais)" if len(value) > 20 else "")
        return _harvest_summarize_list_items(value)

    if isinstance(value, dict):
        if key == "phone":
            number = str(value.get("number") or value.get("phone") or "").strip()
            ext = str(value.get("extension") or "").strip()
            if number and ext:
                return f"{number} (ext. {ext})"
            return number or None
        if key == "foundedOn":
            if isinstance(value.get("year"), (int, float)):
                y = int(value["year"])
                m = value.get("month")
                d = value.get("day")
                if m and d:
                    return f"{d}/{m}/{y}"
                if m:
                    return f"{m}/{y}"
                return str(y)
        if key == "employeeCountRange":
            start = value.get("start")
            end = value.get("end")
            if start is not None and end is not None:
                return f"{start} – {end} colaboradores"
            if start is not None:
                return f"a partir de {start} colaboradores"
        if key == "multiLocaleHeadline":
            parts = []
            for loc, text in value.items():
                if text:
                    parts.append(f"{loc}: {str(text)[:80]}")
            return "; ".join(parts[:6]) if parts else json.dumps(value, ensure_ascii=False)[:400]
        if key == "primaryLocale":
            country = value.get("country")
            lang = value.get("language")
            bits = [str(x).strip() for x in (country, lang) if x]
            return " / ".join(bits) if bits else json.dumps(value, ensure_ascii=False)[:300]
        compact = json.dumps(value, ensure_ascii=False)
        return compact[:500] + ("…" if len(compact) > 500 else "")

    text = str(value).strip()
    return text[:500] if text else None


def _expand_certifications_into_metrics(
    record: Dict[str, Any],
    metrics: Dict[str, str],
) -> None:
    """Coloca cada certificação numa chave separada para a UI listar legivelmente.

    Argumentos:
        record: JSON bruto harvestapi.
        metrics: Mapa de métricas a alterar in-place.
    """

    certs = record.get("certifications")
    if not isinstance(certs, list) or not certs:
        return
    metrics.pop("certifications", None)
    for index, cert in enumerate(certs[:40], start=1):
        line: Optional[str] = None
        if isinstance(cert, dict):
            title = str(cert.get("title") or cert.get("name") or "").strip()
            if not title:
                title = f"Certificação {index}"
            issuer = str(cert.get("issuedBy") or cert.get("authority") or "").strip()
            when = str(cert.get("issuedAt") or cert.get("issuedOn") or "").strip()
            bits = [b for b in (title, issuer, when) if b]
            line = " — ".join(bits) if bits else title
        elif isinstance(cert, str) and cert.strip():
            line = cert.strip()
        if line:
            metrics[f"certification_{index}"] = line[:420]
    if len(certs) > 40:
        metrics["certifications_extra"] = f"+{len(certs) - 40} certificações adicionais"


def build_linkedin_overview_metrics_from_harvest_profile(
    record: Dict[str, Any],
    *,
    profile_url: Optional[str] = None,
) -> Dict[str, str]:
    """Constrói indicadores da Visão Geral a partir do harvestapi profile scraper.

    Argumentos:
        record: Primeiro item do dataset Apify.
        profile_url: URL analisado (reservado).

    Retorno:
        Mapa camelCase → valor legível para ``metricas_linkedin``.
    """

    if not isinstance(record, dict):
        return {}

    metrics: Dict[str, str] = {}
    seen: set[str] = set()

    for key in HARVEST_LINKEDIN_PROFILE_FIELD_ORDER:
        if key not in record:
            continue
        formatted = _format_harvest_profile_field_for_display(key, record[key])
        if formatted and str(formatted).strip():
            metrics[key] = str(formatted).strip()
            seen.add(key)

    for key, value in record.items():
        if key in seen or key.startswith("_"):
            continue
        if not isinstance(key, str) or not key.strip():
            continue
        formatted = _format_harvest_profile_field_for_display(key, value)
        if formatted and str(formatted).strip():
            metrics[key] = str(formatted).strip()

    _expand_certifications_into_metrics(record, metrics)

    return metrics


def merge_harvest_overview_into_linkedin_metrics(
    analysis: Dict[str, Any],
    harvest_record: Dict[str, Any],
    *,
    profile_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Funde campos harvestapi na resposta de análise LinkedIn.

    Argumentos:
        analysis: Resposta OpenAI já enriquecida com métricas de posts.
        harvest_record: JSON bruto do profile scraper.
        profile_url: URL do perfil.

    Retorno:
        Análise com ``metricas_linkedin`` = perfil Apify e posts em ``metricas_universais``.
    """

    if not isinstance(analysis, dict) or not isinstance(harvest_record, dict):
        return analysis

    harvest_metrics = build_linkedin_overview_metrics_from_harvest_profile(
        harvest_record, profile_url=profile_url
    )
    if not harvest_metrics:
        return analysis

    universal: Dict[str, str] = {}
    raw_universal = analysis.get("metricas_universais")
    if isinstance(raw_universal, dict):
        universal = {str(k): str(v) for k, v in raw_universal.items() if str(k).strip()}

    raw_specific = analysis.get("metricas_instagram")
    if isinstance(raw_specific, dict):
        for key, value in raw_specific.items():
            k = str(key).strip()
            if not k or is_placeholder_metric_display(value):
                continue
            if k in HARVEST_LINKEDIN_PROFILE_FIELD_ORDER or k in harvest_metrics:
                continue
            if k.startswith("certification_") or k == "certifications_extra":
                continue
            if k in LINKEDIN_POST_DERIVED_METRIC_KEYS:
                if k not in universal or is_placeholder_metric_display(universal.get(k)):
                    universal[k] = str(value).strip()

    analysis["metricas_linkedin"] = dict(harvest_metrics)
    analysis["metricas_instagram"] = dict(harvest_metrics)
    analysis["metricas_universais"] = universal
    analysis["overview_data_source"] = "harvestapi/linkedin-profile-scraper"
    analysis["harvest_profile_fields"] = list(harvest_metrics.keys())
    return analysis


def apply_linkedin_harvest_overview_to_analysis(
    analysis: Dict[str, Any],
    public_profile_data: Optional[Dict[str, Any]] = None,
    *,
    profile_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Aplica todos os campos harvestapi à Visão Geral (módulo só LinkedIn).

    Deve ser chamado **depois** de ``enrich_linkedin_analysis_metrics`` em ``app.py``.

    Argumentos:
        analysis: Resposta de análise LinkedIn.
        public_profile_data: Bundle com ``harvest_profile`` do Apify.
        profile_url: URL público analisado.

    Retorno:
        Análise com métricas de perfil harvestapi na Visão Geral.
    """

    if not isinstance(analysis, dict):
        return analysis

    profile = public_profile_data if isinstance(public_profile_data, dict) else {}
    harvest_raw = profile.get("harvest_profile")
    if not isinstance(harvest_raw, dict) or not harvest_raw:
        return analysis

    return merge_harvest_overview_into_linkedin_metrics(
        analysis,
        harvest_raw,
        profile_url=profile_url or profile.get("profile_url"),
    )
