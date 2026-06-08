"""Agente de Redes Sociais com análise por plataforma (Instagram, LinkedIn, etc.)."""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

METRIC_MISSING_DISPLAY_PT = "Sem dados públicos disponíveis."

# Regras de extensão para posts LinkedIn orgânicos (Diretor + página de perfil).
_LINKEDIN_POST_BODY_LENGTH_RULES = (
    "EXTENSÃO OBRIGATÓRIA no campo «body» (texto publicável completo):\n"
    "- Posts tipo texto/artigo/documento: MÍNIMO 280 palavras, ideal 350–550 palavras.\n"
    "- Estrutura: gancho forte (1–2 frases); 3–5 parágrafos com valor (história, dados ou exemplo); "
    "lista com 3–5 bullets quando fizer sentido; fecho com insight + CTA profissional.\n"
    "- Usa quebras de linha duplas (\\n\\n) entre blocos. O «hook» pode repetir a abertura do body.\n"
    "- NÃO entregues posts de 2–3 frases — são demasiado curtos para LinkedIn orgânico.\n"
    "- Polls: pergunta clara + contexto (80–120 palavras) + 3–4 opções. "
    "Vídeo: roteiro/gancho detalhado (200+ palavras)."
)

SUPPORTED_SOCIAL_PLATFORMS: Tuple[str, ...] = (
    "instagram",
    "linkedin",
    "facebook",
    "tiktok",
    "youtube",
)


def normalize_social_platform(platform: Optional[str]) -> str:
    """Normaliza o identificador da rede social para um valor suportado.

    Aceita texto livre (ex.: vindo de query string ou formulário), converte
    para minúsculas e compara com a lista interna de plataformas. Valores
    desconhecidos ou vazios caem no fallback ``instagram`` para manter
    compatibilidade com clientes antigos.

    Argumentos:
        platform: Nome da plataforma (ex.: ``linkedin``, ``Instagram``) ou
            ``None``.

    Retorno:
        Uma das cadeias em ``SUPPORTED_SOCIAL_PLATFORMS``, por defeito
        ``instagram``.
    """

    if not platform:
        return "instagram"
    p = str(platform).strip().lower()
    if p in SUPPORTED_SOCIAL_PLATFORMS:
        return p
    return "instagram"


def social_platform_label_pt(platform: str) -> str:
    """Devolve o nome legível em português da plataforma escolhida.

    Argumentos:
        platform: Identificador normalizado (ex.: ``linkedin``).

    Retorno:
        Etiqueta curta para UI ou metadados (ex.: ``LinkedIn``).
    """

    labels = {
        "instagram": "Instagram",
        "linkedin": "LinkedIn",
        "facebook": "Facebook",
        "tiktok": "TikTok",
        "youtube": "YouTube",
    }
    return labels.get(normalize_social_platform(platform), "Instagram")


def _compact_alnum(value: str) -> str:
    """Remove espaços e pontuação, mantendo apenas letras e dígitos em minúsculas.

    Argumentos:
        value: Texto original.

    Retorno:
        Cadeia compacta só com caracteres alfanuméricos em minúsculas.
    """

    return "".join(ch for ch in value.casefold() if ch.isalnum())


def is_placeholder_metric_display(value: Any) -> bool:
    """Indica se o valor de uma métrica deve ser tratado como «em falta» na UI.

    Usado para substituir respostas confusas do modelo (por exemplo o token
    ``lacunas_de_dados`` usado como valor de uma pill) e para decidir se o
    servidor pode preencher o campo com dados derivados do perfil.

    Argumentos:
        value: Valor cru associado a uma chave em ``metricas_universais`` ou
            ``metricas_instagram``.

    Retorno:
        ``True`` quando o valor está vazio, é claramente um placeholder ou
        corresponde à mensagem padrão de dado em falta; ``False`` caso contrário.
    """

    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    if text == METRIC_MISSING_DISPLAY_PT:
        return True
    compact = _compact_alnum(text)
    if compact in {"lacunasdedados", "lacunadedados"}:
        return True
    lowered = text.casefold()
    if lowered in {"n/a", "n/d", "null", "none", "unknown"}:
        return True
    if lowered in {"na", "nd"} and len(text) <= 4:
        return True
    if lowered in {
        "não disponível",
        "nao disponivel",
        "indisponível",
        "indisponivel",
        "not available",
        "unavailable",
        "sem dados",
        "sem dado",
        "sem informação",
        "sem informacao",
    }:
        return True
    if text in {"—", "-"}:
        return True
    return False


METRIC_UNAVAILABLE_PUBLIC_PT = "Dado não público no LinkedIn"


def linkedin_page_kind_from_url(profile_url: Optional[str]) -> str:
    """Classifica o URL LinkedIn para rótulos de métricas na interface.

    Páginas de empresa ou escola usam «Seguidores»; perfis pessoais usam
    «Ligações».

    Argumentos:
        profile_url: URL público normalizado (``/in/``, ``/company/``, ``/school/``).

    Retorno:
        ``organization`` para ``/company/`` e ``/school/``; ``personal`` para ``/in/``.
    """

    if not profile_url:
        return "personal"
    lower = str(profile_url).strip().lower()
    if "/company/" in lower or "/school/" in lower:
        return "organization"
    return "personal"


def _format_linkedin_metric_number(value: Any) -> Optional[str]:
    """Formata um número para exibição em métricas LinkedIn (pt-PT).

    Argumentos:
        value: Valor numérico ou texto convertível.

    Retorno:
        String com separador de milhares em ponto, ou ``None`` se inválido.
    """

    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num:  # NaN
        return None
    if abs(num - round(num)) < 0.01:
        return f"{int(round(num)):,}".replace(",", ".")
    text = f"{num:.2f}"
    return text.replace(".", ",")


def _set_linkedin_metric_if_missing(metrics: Dict[str, str], key: str, value: str) -> None:
    """Atribui uma métrica apenas se o campo estiver vazio ou for placeholder.

    Argumentos:
        metrics: Mapa de métricas a alterar in-place.
        key: Chave da métrica (ex.: ``ligacoes``).
        value: Valor legível para a UI.
    """

    if not value or not str(value).strip():
        return
    current = metrics.get(key)
    if current is None or is_placeholder_metric_display(current):
        metrics[key] = str(value).strip()


def enrich_linkedin_analysis_metrics(
    analysis: Dict[str, Any],
    public_profile_data: Optional[Dict[str, Any]] = None,
    *,
    profile_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Preenche métricas LinkedIn em falta com dados derivados do Apify.

    Quando o modelo OpenAI não preenche ligações/seguidores, cadência ou
    intervalo entre posts, usa ``followers_count`` e ``apify_enrichment`` do
    payload público recolhido antes da análise.

    Argumentos:
        analysis: Resposta normalizada de ``analyze_instagram_data`` (LinkedIn).
        public_profile_data: Dados Apify / perfil público enviados ao modelo.
        profile_url: URL analisado (define ``linkedin_page_kind`` na resposta).

    Retorno:
        O mesmo dicionário ``analysis``, enriquecido e com ``metricas_linkedin``
        sincronizado; inclui ``linkedin_page_kind`` quando há ``profile_url``.
    """

    if not isinstance(analysis, dict):
        return analysis

    profile = public_profile_data if isinstance(public_profile_data, dict) else {}
    enrichment = profile.get("apify_enrichment")
    if not isinstance(enrichment, dict):
        enrichment = {}

    cadence = enrichment.get("posting_cadence")
    if not isinstance(cadence, dict):
        cadence = {}

    page_kind = linkedin_page_kind_from_url(profile_url or profile.get("profile_url"))
    analysis["linkedin_page_kind"] = page_kind

    specific: Dict[str, str] = {}
    raw_specific = analysis.get("metricas_instagram")
    if isinstance(raw_specific, dict):
        specific = {str(k): str(v) for k, v in raw_specific.items() if str(k).strip()}

    universal: Dict[str, str] = {}
    raw_universal = analysis.get("metricas_universais")
    if isinstance(raw_universal, dict):
        universal = {str(k): str(v) for k, v in raw_universal.items() if str(k).strip()}

    followers = profile.get("followers_count")
    followers_fmt = _format_linkedin_metric_number(followers)
    if followers_fmt:
        if page_kind == "organization":
            _set_linkedin_metric_if_missing(specific, "ligacoes", followers_fmt)
            _set_linkedin_metric_if_missing(specific, "seguidores", followers_fmt)
        else:
            _set_linkedin_metric_if_missing(specific, "ligacoes", followers_fmt)

    posts_n = profile.get("posts_count")
    if posts_n is None:
        recent = profile.get("recent_posts")
        if isinstance(recent, list):
            posts_n = len(recent)
    posts_fmt = _format_linkedin_metric_number(posts_n)
    if posts_fmt:
        _set_linkedin_metric_if_missing(specific, "publicacoes_analisadas", posts_fmt)
        _set_linkedin_metric_if_missing(universal, "publicacoes_no_periodo", posts_fmt)

    avg_reactions = enrichment.get("avg_reactions_per_post")
    avg_comments = enrichment.get("avg_comments_per_post")
    react_fmt = _format_linkedin_metric_number(avg_reactions)
    comm_fmt = _format_linkedin_metric_number(avg_comments)
    if react_fmt:
        _set_linkedin_metric_if_missing(specific, "reacoes_medias_por_publicacao", react_fmt)
    if comm_fmt:
        _set_linkedin_metric_if_missing(specific, "comentarios_medios_por_publicacao", comm_fmt)

    avg_days = cadence.get("avg_days_between_posts")
    try:
        avg_days_num = float(avg_days) if avg_days is not None else None
    except (TypeError, ValueError):
        avg_days_num = None

    if avg_days_num is not None and avg_days_num > 0:
        days_fmt = _format_linkedin_metric_number(avg_days_num)
        if days_fmt:
            cadence_text = f"≈{days_fmt} dias entre publicações"
            _set_linkedin_metric_if_missing(specific, "cadencia_publicacao", cadence_text)
            _set_linkedin_metric_if_missing(universal, "cadencia_dias_entre_posts", f"{days_fmt} dias")

    avg_er = enrichment.get("avg_engagement_pct")
    try:
        er_num = float(avg_er) if avg_er is not None else None
    except (TypeError, ValueError):
        er_num = None
    if er_num is not None and followers_fmt:
        er_display = f"{_format_linkedin_metric_number(er_num) or er_num}%"
        _set_linkedin_metric_if_missing(universal, "taxa_engagement_publicacoes", er_display)

    dist = enrichment.get("content_type_distribution") or enrichment.get("format_distribution")
    if isinstance(dist, dict) and dist:
        best_fmt = max(
            dist.keys(),
            key=lambda k: (dist.get(k) or {}).get("count", 0) if isinstance(dist.get(k), dict) else 0,
        )
        if best_fmt and is_placeholder_metric_display(specific.get("tipo_conteudo_mais_eficaz")):
            specific["tipo_conteudo_mais_eficaz"] = str(best_fmt)

    analysis["metricas_instagram"] = specific
    analysis["metricas_universais"] = universal
    analysis["metricas_linkedin"] = dict(specific)
    return analysis


def _lacunas_list_item_is_technical_token(text: str) -> bool:
    """Deteta quando a lista ``lacunas_de_dados`` contém só o nome do campo JSON.

    Argumentos:
        text: Uma entrada da lista ``lacunas_de_dados``.

    Retorno:
        ``True`` se o texto for essencialmente o token técnico mal usado.
    """

    compact = _compact_alnum(text)
    return compact in {"lacunasdedados", "lacunadedados"}


class SocialMediaAgent:
    """Analisa performance em redes sociais e gera recomendações acionáveis.

    O agente está preparado para **várias plataformas** (Instagram, LinkedIn,
    Facebook, TikTok, YouTube). A camada de análise separa métricas universais
    de métricas específicas da rede; o campo JSON ``metricas_instagram`` é o
    contentor histórico para «métricas específicas da plataforma escolhida»
    (o nome mantém-se por compatibilidade com APIs e UI existentes).

    Argumentos (atributos de instância):
        Nenhum obrigatório no construtor. A configuração vem de variáveis de
        ambiente (`OPENAI_API_KEY` e `OPENAI_MODEL`).

    Retorno:
        Os métodos públicos devolvem respostas de chat (string) ou dicionários
        estruturados, prontos para serialização JSON pela API.
    """

    def __init__(self) -> None:
        """Inicializa chave e modelo de IA para análises do agente.

        A função lê:
        - `OPENAI_API_KEY`: chave para autenticar pedidos ao modelo;
        - `OPENAI_MODEL`: modelo de chat a usar (fallback `gpt-4o-mini`).

        Argumentos:
            Nenhum.

        Retorno:
            Nenhum.
        """

        self._api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    def _refresh_from_env(self) -> None:
        """Atualiza configuração em runtime sem reiniciar o servidor.

        A função sincroniza novamente chave e modelo a partir das variáveis de
        ambiente atuais, permitindo alterar credenciais durante execução.

        Argumentos:
            Nenhum.

        Retorno:
            Nenhum.
        """

        self._api_key = os.getenv("OPENAI_API_KEY", "").strip() or self._api_key
        self._model = os.getenv("OPENAI_MODEL", self._model).strip()

    def is_configured(self) -> bool:
        """Valida se existe chave API configurada para análise automática.

        Argumentos:
            Nenhum.

        Retorno:
            `True` quando existe `OPENAI_API_KEY` não vazia; caso contrário `False`.
        """

        self._refresh_from_env()
        return bool(self._api_key)

    def generate_chat_reply(
        self,
        messages: List[Dict[str, str]],
        language: str = "pt-PT",
    ) -> str:
        """Gera resposta conversacional curta para recolher contexto de análise.

        A função processa o histórico da chatroom do agente e devolve a próxima
        resposta textual do assistente, focada em Instagram. O objetivo é
        pedir dados em falta de forma objetiva, sem teorias vagas, preparando a
        execução da análise estruturada final.

        Argumentos:
            messages: Histórico cronológico da conversa com objetos contendo
                `role` (`user` ou `assistant`) e `content`.
            language: Idioma/região da resposta (por defeito `pt-PT`).

        Retorno:
            String com a próxima resposta do agente na chatroom.

        Raises:
            RuntimeError: Quando a chave `OPENAI_API_KEY` não está configurada.
        """

        if not self.is_configured():
            raise RuntimeError(
                "OPENAI_API_KEY nao definida. Configura a variável para conversar com o Agente de Redes Sociais."
            )

        sanitized_messages: List[Dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "")).strip()
            content = str(message.get("content", "")).strip()
            if role not in {"user", "assistant"} or not content:
                continue
            sanitized_messages.append({"role": role, "content": content})

        client = OpenAI(api_key=self._api_key)
        system_prompt = (
            "És um Agente de Análise de Redes Sociais especializado em Instagram (MVP). "
            f"Responde sempre em {language}. "
            "Sê direto, prático e orientado a crescimento + engagement. "
            "Evita teoria e não assumes dados inexistentes. "
            "Faz no máximo 1 pergunta objetiva por resposta quando faltar contexto. "
            "Sempre que possível, pede números concretos: seguidores por período, "
            "engagement rate, métricas por formato (reels/carrossel/imagem), horários e hashtags."
        )
        response = client.chat.completions.create(
            model=self._model,
            temperature=0.35,
            messages=[{"role": "system", "content": system_prompt}, *sanitized_messages],
        )
        return (response.choices[0].message.content or "").strip()

    def analyze_instagram_data(
        self,
        messages: List[Dict[str, str]],
        instagram_data: Optional[Dict[str, Any]] = None,
        language: str = "pt-PT",
        platform: str = "instagram",
    ) -> Dict[str, Any]:
        """Produz análise estruturada de redes sociais com foco em ações prioritárias.

        A função combina histórico da conversa e dados estruturados fornecidos
        (quando existirem), executa uma interpretação analítica e devolve um
        objeto JSON com secções fixas de output: insights, problemas,
        oportunidades, ações, ideias de conteúdo e plano de crescimento.
        A resposta separa também métricas universais de métricas específicas da
        plataforma (por defeito Instagram; também suporta LinkedIn, etc.).

        Argumentos:
            messages: Histórico cronológico da chatroom com mensagens do
                utilizador e do agente.
            instagram_data: Dicionário opcional com métricas da plataforma
                (seguidores, engagement, posts, audiência, etc.).
            language: Idioma/região da análise final (por defeito `pt-PT`).
            platform: Identificador da rede (`instagram`, `linkedin`, etc.).

        Retorno:
            Dicionário com as chaves:
            - `principais_insights` (lista de strings)
            - `problemas_identificados` (lista de strings)
            - `oportunidades` (lista de strings)
            - `acoes_prioritarias` (lista de strings)
            - `ideias_conteudo` (lista de strings)
            - `plano_crescimento_curto_prazo` (lista de strings)
            - `metricas_universais` (objeto)
            - `metricas_instagram` (objeto)
            - `confianca_analise` (string curta)
            - `lacunas_de_dados` (lista de strings)

        Raises:
            RuntimeError: Quando não existe `OPENAI_API_KEY` para processar a análise.
        """

        if not self.is_configured():
            raise RuntimeError(
                "OPENAI_API_KEY nao definida. Configura a variável para gerar a análise de Instagram."
            )

        sanitized_messages: List[Dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "")).strip()
            content = str(message.get("content", "")).strip()
            if role not in {"user", "assistant"} or not content:
                continue
            sanitized_messages.append({"role": role, "content": content})

        pl = normalize_social_platform(platform)
        label = social_platform_label_pt(pl)
        profile_payload = instagram_data or {}
        compact_data = json.dumps(profile_payload, ensure_ascii=False, indent=2)

        if pl == "linkedin":
            platform_metrics_hint = (
                "métricas específicas de LinkedIn (ligações, publicações, reações, comentários, "
                "cadência, tipos de conteúdo: texto, artigo, documento, poll, vídeo — "
                "NÃO uses Reels, Stories, seguidores IG, guardados nem hashtags como métrica principal)"
            )
            platform_metrics_json = (
                "\"metricas_instagram\":{"
                "\"ligacoes\":\"...\","
                "\"publicacoes_analisadas\":\"...\","
                "\"reacoes_medias_por_publicacao\":\"...\","
                "\"comentarios_medios_por_publicacao\":\"...\","
                "\"cadencia_publicacao\":\"...\","
                "\"tipo_conteudo_mais_eficaz\":\"...\""
                "}"
            )
            linkedin_rules = (
                "7) Em `metricas_universais` usa apenas métricas de rede profissional: "
                "`taxa_engagement_publicacoes`, `publicacoes_no_periodo`, `cadencia_dias_entre_posts` — "
                "não uses crescimento_seguidores nem retencao_audiencia (são de Instagram).\n"
                "8) Em `ideias_conteudo`, cada item DEVE começar com o tipo entre parêntesis, "
                "ex.: «(Post texto) …», «(Artigo) …», «(Documento/PDF) …», «(Sondagem) …», «(Vídeo nativo) …».\n"
                "9) Em `acoes_prioritarias`, foca autoridade B2B, networking, thought leadership e CTAs profissionais.\n"
            )
        else:
            linkedin_rules = ""
            platform_metrics_hint = (
                f"métricas específicas de {label} (ex.: Reels, guardados, partilhas em Instagram)"
            )
            platform_metrics_json = (
                "\"metricas_instagram\":{"
                "\"reels_reach\":\"...\","
                "\"guardados\":\"...\","
                "\"partilhas\":\"...\""
                "}"
            )

        system_prompt = (
            f"És um Agente de Análise de Redes Sociais especializado em {label}. "
            "Objetivo: analisar performance e recomendar ações concretas com impacto em crescimento e engagement. "
            f"Responde sempre em {language}. "
            f"A plataforma em análise é **{label}** — ignora dados de outras redes. "
            "Não assumes dados inexistentes; quando faltar informação, explicita em `lacunas_de_dados`. "
            "Prioriza insight acionável, evita sugestões genéricas. "
            "Justifica cada conclusão com dados disponíveis (histórico e JSON). "
            f"Separa o que é universal do que é específico de {label} ({platform_metrics_hint}).\n\n"
            "Responde APENAS com JSON válido, sem markdown, com esta estrutura exata:\n"
            "{"
            "\"principais_insights\":[\"...\"],"
            "\"problemas_identificados\":[\"...\"],"
            "\"oportunidades\":[\"...\"],"
            "\"acoes_prioritarias\":[\"...\"],"
            "\"ideias_conteudo\":[\"...\"],"
            "\"plano_crescimento_curto_prazo\":[\"...\"],"
            "\"metricas_universais\":{"
            "\"engagement_rate\":\"...\","
            "\"crescimento_seguidores\":\"...\","
            "\"retencao_audiencia\":\"...\""
            "},"
            f"{platform_metrics_json},"
            "\"confianca_analise\":\"alta|media|baixa\","
            "\"lacunas_de_dados\":[\"...\"]"
            "}\n\n"
            "Regras obrigatórias:\n"
            "1) Incluir sempre as secções com conteúdo acionável.\n"
            "2) Referir possíveis causas para picos/quedas apenas quando suportado por dados.\n"
            "3) Recomendar frequência e horários de publicação apenas com base em padrões observáveis; "
            "se não houver padrão, indicar isso em `lacunas_de_dados`.\n"
            "4) Evitar texto vago como 'publicar melhor conteúdo'.\n"
            "5) Focar curto prazo (2 a 4 semanas) no plano de crescimento.\n"
            "6) Em `metricas_universais` e `metricas_instagram`, cada valor deve ser número+unidade ou frase curta "
            "baseada nos dados recebidos; nunca uses só «não disponível» nem repetas o nome interno do campo como valor.\n"
            f"{linkedin_rules}"
        )

        user_prompt = (
            f"Dados estruturados de {label} (podem estar incompletos):\n"
            f"{compact_data}\n\n"
            "Usa também o histórico de conversa para complementar contexto."
        )

        client = OpenAI(api_key=self._api_key)
        response = client.chat.completions.create(
            model=self._model,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                *sanitized_messages,
                {"role": "user", "content": user_prompt},
            ],
        )
        raw_content = (response.choices[0].message.content or "").strip()
        return self._attach_platform_meta(self._parse_analysis_json(raw_content), pl)

    def _parse_analysis_json(self, raw_content: str) -> Dict[str, Any]:
        """Normaliza e valida o JSON de análise devolvido pelo modelo.

        A função tenta interpretar a resposta textual do modelo como JSON,
        preenche campos obrigatórios em falta com valores default e garante que
        a API devolve sempre uma estrutura estável para o frontend.

        Argumentos:
            raw_content: Conteúdo bruto da resposta do modelo, esperado em JSON.

        Retorno:
            Dicionário com estrutura de análise normalizada.
        """

        defaults: Dict[str, Any] = {
            "principais_insights": [],
            "problemas_identificados": [],
            "oportunidades": [],
            "acoes_prioritarias": [],
            "ideias_conteudo": [],
            "plano_crescimento_curto_prazo": [],
            "metricas_universais": {},
            "metricas_instagram": {},
            "confianca_analise": "baixa",
            "lacunas_de_dados": ["Sem dados suficientes para análise robusta."],
        }

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            result = defaults.copy()
            result["lacunas_de_dados"] = [
                "O modelo devolveu resposta fora do formato esperado. Tenta novamente com dados mais estruturados."
            ]
            return result

        if not isinstance(parsed, dict):
            return defaults

        normalized = defaults.copy()
        for key in [
            "principais_insights",
            "problemas_identificados",
            "oportunidades",
            "acoes_prioritarias",
            "ideias_conteudo",
            "plano_crescimento_curto_prazo",
            "lacunas_de_dados",
        ]:
            normalized[key] = self._to_string_list(parsed.get(key))

        metricas_universais = parsed.get("metricas_universais")
        metricas_instagram = parsed.get("metricas_instagram")
        normalized["metricas_universais"] = self._stringify_metric_map(
            metricas_universais if isinstance(metricas_universais, dict) else {}
        )
        normalized["metricas_instagram"] = self._stringify_metric_map(
            metricas_instagram if isinstance(metricas_instagram, dict) else {}
        )

        normalized["lacunas_de_dados"] = self._sanitize_lacunas_list_items(normalized["lacunas_de_dados"])

        confidence = str(parsed.get("confianca_analise", "baixa")).strip().lower()
        normalized["confianca_analise"] = confidence if confidence in {"alta", "media", "baixa"} else "baixa"
        return normalized

    def _attach_platform_meta(self, result: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Acrescenta metadados de plataforma à resposta de análise para a UI.

        Argumentos:
            result: Dicionário normalizado da análise.
            platform: Identificador da rede (ex.: ``linkedin``).

        Retorno:
            O mesmo dicionário com ``plataforma`` e ``plataforma_label``.
        """

        pl = normalize_social_platform(platform)
        result["plataforma"] = pl
        result["plataforma_label"] = social_platform_label_pt(pl)
        if pl == "linkedin":
            metrics = result.get("metricas_instagram")
            if isinstance(metrics, dict):
                result["metricas_linkedin"] = dict(metrics)
        return result

    def _stringify_metric_map(self, raw: Dict[str, Any]) -> Dict[str, str]:
        """Converte um mapa de métricas em strings seguras para a UI.

        Garante chaves e valores em texto, substituindo tokens técnicos que o
        modelo por vezes cola como valor (ex.: nome do campo `lacunas_de_dados`)
        por uma mensagem legível em português.

        Argumentos:
            raw: Dicionário devolvido pelo modelo (valores arbitrários).

        Retorno:
            Dicionário `str -> str` pronto para `renderMetricPills` no frontend.
        """

        out: Dict[str, str] = {}
        if not isinstance(raw, dict):
            return out
        for key, value in raw.items():
            label = str(key).strip()
            if not label:
                continue
            out[label] = self._normalize_metric_cell(value)
        return out

    def _normalize_metric_cell(self, value: Any) -> str:
        """Normaliza uma célula de métrica para exibição ao utilizador.

        Trata listas/dicionários como falta de dado legível e converte tokens
        confusos da estrutura JSON em texto amigável.

        Argumentos:
            value: Valor bruto associado a uma chave de métricas.

        Retorno:
            String para mostrar na pill; nunca devolve o token técnico
            `lacunas_de_dados`.
        """

        if isinstance(value, (dict, list)):
            return METRIC_MISSING_DISPLAY_PT
        text = str(value).strip() if value is not None else ""
        if not text:
            return METRIC_MISSING_DISPLAY_PT
        if is_placeholder_metric_display(text):
            return METRIC_MISSING_DISPLAY_PT
        return text

    def _sanitize_lacunas_list_items(self, items: List[str]) -> List[str]:
        """Evita que a lista de lacunas mostre identificadores técnicos soltos.

        Argumentos:
            items: Lista já normalizada de lacunas de dados.

        Retorno:
            Lista com entradas ambíguas substituídas por texto claro.
        """

        cleaned: List[str] = []
        for item in items:
            s = str(item).strip()
            if not s:
                continue
            if _lacunas_list_item_is_technical_token(s):
                cleaned.append(
                    "Ausência de dados nesta dimensão (a análise não recebeu métricas suficientes)."
                )
                continue
            cleaned.append(s)
        return cleaned if cleaned else items

    def _to_string_list(self, value: Any) -> List[str]:
        """Converte qualquer valor numa lista limpa de strings não vazias.

        Argumentos:
            value: Valor potencialmente recebido do modelo (lista, string, etc.).

        Retorno:
            Lista de strings não vazias, adequada para serialização e consumo UI.
        """

        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value is None:
            return []
        text = str(value).strip()
        return [text] if text else []


    def generate_linkedin_posts_from_analysis(
        self,
        analysis: Dict[str, Any],
        *,
        public_profile_data: Optional[Dict[str, Any]] = None,
        profile_url: Optional[str] = None,
        count: int = 3,
        language: str = "pt-PT",
        strategy_brief: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Gera posts LinkedIn prontos a publicar com base na análise do perfil.

        Usa OpenAI para criar publicações alinhadas ao tom do perfil, insights da
        análise e tipos de conteúdo LinkedIn (texto, artigo, documento, poll, vídeo).

        Argumentos:
            analysis: Resultado da análise (insights, oportunidades, ideias, etc.).
            public_profile_data: Dados Apify/perfil recolhidos na análise.
            profile_url: URL público do perfil analisado.
            count: Número de posts a gerar (1–7).
            language: Idioma dos posts (por defeito ``pt-PT``).
            strategy_brief: Plano estratégico aprovado pelo Diretor (opcional).

        Retorno:
            Dicionário com chave ``posts`` (lista de objectos com ``id``, ``content_type``,
            ``title``, ``body``, ``hook``, ``cta``, ``angle``).

        Raises:
            RuntimeError: Sem ``OPENAI_API_KEY`` configurada.
        """

        if not self.is_configured():
            raise RuntimeError("OPENAI_API_KEY nao definida.")

        n = max(1, min(7, int(count)))
        compact_analysis = json.dumps(analysis or {}, ensure_ascii=False, indent=2)
        compact_profile = json.dumps(public_profile_data or {}, ensure_ascii=False, indent=2)
        url_hint = str(profile_url or "").strip()

        system_prompt = (
            "És um copywriter sénior especializado em LinkedIn B2B (português de Portugal). "
            f"Responde em {language}. "
            "Cria posts autênticos, específicos ao perfil analisado — sem clichés de Instagram. "
            "Cada post deve ter profundidade editorial: argumento desenvolvido, exemplos concretos "
            "e CTA profissional. Varia os formatos entre: texto, artigo, documento, poll, video. "
            f"{_LINKEDIN_POST_BODY_LENGTH_RULES} "
            "Responde APENAS com JSON válido:\n"
            '{"posts":[{"content_type":"texto|artigo|documento|poll|video",'
            '"title":"...",'
            '"body":"texto completo do post (com quebras de linha \\n)",'
            '"hook":"frase de abertura",'
            '"cta":"...",'
            '"angle":"porque encaixa neste perfil"}]}'
        )
        strategy_block = ""
        if strategy_brief and str(strategy_brief).strip():
            strategy_block = (
                f"\n\nESTRATÉGIA APROVADA (obrigatório seguir pilares, ICP e cadência):\n"
                f"{str(strategy_brief).strip()}\n"
            )
        user_prompt = (
            f"Cria exactamente {n} posts LinkedIn distintos para a semana.\n"
            f"Perfil / URL: {url_hint or 'n/d'}\n\n"
            f"Análise:\n{compact_analysis}\n\n"
            f"Dados do perfil:\n{compact_profile}"
            f"{strategy_block}\n"
            "Usa insights, oportunidades e ideias_conteudo da análise. "
            "Distribui os posts pelos pilares de conteúdo da estratégia. "
            "Prioriza posts longos e úteis (mínimo 280 palavras no body para texto/artigo/documento)."
        )

        client = OpenAI(api_key=self._api_key)
        response = client.chat.completions.create(
            model=self._model,
            temperature=0.55,
            max_tokens=min(16384, max(4096, 1800 * n)),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        return {"posts": self._parse_linkedin_posts_json(raw)}

    def regenerate_linkedin_post(
        self,
        analysis: Dict[str, Any],
        post: Dict[str, Any],
        *,
        public_profile_data: Optional[Dict[str, Any]] = None,
        profile_url: Optional[str] = None,
        edit_instructions: Optional[str] = None,
        language: str = "pt-PT",
    ) -> Dict[str, Any]:
        """Regera um único post LinkedIn (refazer ou após pedido de edição).

        Argumentos:
            analysis: Contexto da análise de perfil.
            post: Post actual (``content_type``, ``body``, etc.).
            public_profile_data: Dados do perfil (opcional).
            profile_url: URL do perfil.
            edit_instructions: Instruções do utilizador ao editar/refazer.
            language: Idioma do post.

        Retorno:
            Dicionário com chave ``post`` (objecto normalizado).

        Raises:
            RuntimeError: Sem ``OPENAI_API_KEY`` configurada.
        """

        if not self.is_configured():
            raise RuntimeError("OPENAI_API_KEY nao definida.")

        compact_analysis = json.dumps(analysis or {}, ensure_ascii=False, indent=2)
        compact_profile = json.dumps(public_profile_data or {}, ensure_ascii=False, indent=2)
        compact_post = json.dumps(post or {}, ensure_ascii=False, indent=2)
        instr = str(edit_instructions or "").strip() or "Melhora o post mantendo o mesmo tipo de conteúdo."

        system_prompt = (
            "És copywriter LinkedIn B2B. "
            f"Responde em {language}. "
            "Reescreve UM post com base no contexto, com mais profundidade e detalhe. "
            f"{_LINKEDIN_POST_BODY_LENGTH_RULES} "
            'Responde APENAS JSON: {"post":{"content_type":"...","title":"...","body":"...",'
            '"hook":"...","cta":"...","angle":"..."}}'
        )
        user_prompt = (
            f"Perfil: {profile_url or 'n/d'}\n"
            f"Instruções: {instr}\n\n"
            f"Post actual:\n{compact_post}\n\n"
            f"Análise:\n{compact_analysis}\n\n"
            f"Dados perfil:\n{compact_profile}\n\n"
            "Se o post actual for curto, expande-o até pelo menos 280 palavras no body."
        )

        client = OpenAI(api_key=self._api_key)
        response = client.chat.completions.create(
            model=self._model,
            temperature=0.6,
            max_tokens=6144,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"post": self._normalize_linkedin_post_item({})}
        item = parsed.get("post") if isinstance(parsed, dict) else {}
        normalized = self._normalize_linkedin_post_item(item if isinstance(item, dict) else {})
        normalized["id"] = str(post.get("id") or normalized.get("id") or uuid.uuid4().hex[:12])
        return {"post": normalized}

    def _parse_linkedin_posts_json(self, raw_content: str) -> List[Dict[str, Any]]:
        """Interpreta a resposta JSON do modelo com lista de posts LinkedIn.

        Argumentos:
            raw_content: JSON bruto do modelo.

        Retorno:
            Lista normalizada de posts (cada um com ``id`` único).
        """

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            return []
        rows = parsed.get("posts") if isinstance(parsed, dict) else parsed
        if not isinstance(rows, list):
            return []
        out: List[Dict[str, Any]] = []
        for row in rows[:7]:
            if isinstance(row, dict):
                out.append(self._normalize_linkedin_post_item(row))
        return out

    def _normalize_linkedin_post_item(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza um post LinkedIn para a UI (campos obrigatórios preenchidos).

        Argumentos:
            raw: Dicionário parcial devolvido pelo modelo.

        Retorno:
            Post com ``id``, ``content_type``, ``title``, ``body``, ``hook``, ``cta``, ``angle``.
        """

        allowed_types = {"texto", "artigo", "documento", "poll", "video", "imagem", "partilha"}
        ctype = str(raw.get("content_type") or "texto").strip().lower()
        if ctype not in allowed_types:
            ctype = "texto"
        body = str(raw.get("body") or raw.get("text") or "").strip()
        return {
            "id": str(raw.get("id") or uuid.uuid4().hex[:12]),
            "content_type": ctype,
            "title": str(raw.get("title") or "").strip() or "Post LinkedIn",
            "body": body or "(sem texto)",
            "hook": str(raw.get("hook") or "").strip(),
            "cta": str(raw.get("cta") or "").strip(),
            "angle": str(raw.get("angle") or "").strip(),
        }


def get_supabase_public_credentials() -> Tuple[str, str]:
    """Lê URL e chave ``anon`` públicas do projecto Supabase.

    Argumentos:
        Nenhum.

    Retorno:
        Tuplo ``(supabase_url, anon_key)`` (strings vazias se não configurado).
    """

    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip() or os.getenv("SUPABASE_URL", "").strip()
    anon = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "").strip() or os.getenv("SUPABASE_ANON_KEY", "").strip()
    return url, anon


_LINKEDIN_IN_URL_RE = re.compile(
    r"https?://(?:[a-z0-9-]+\.)?linkedin\.com/in/([a-zA-Z0-9\-_]+)",
    re.IGNORECASE,
)
_LINKEDIN_COMPANY_URL_RE = re.compile(
    r"https?://(?:[a-z0-9-]+\.)?linkedin\.com/company/([a-zA-Z0-9\-_]+)",
    re.IGNORECASE,
)
_LINKEDIN_SCHOOL_URL_RE = re.compile(
    r"https?://(?:[a-z0-9-]+\.)?linkedin\.com/school/([a-zA-Z0-9\-_]+)",
    re.IGNORECASE,
)

_LINKEDIN_ORG_PATH_MARKERS = ("/in/", "/company/", "/school/")


def _linkedin_company_url_from_string(value: str) -> Optional[str]:
    """Extrai URL público ``/company/...`` de uma string.

    Argumentos:
        value: Texto que pode conter ``linkedin.com/company/slug``.

    Retorno:
        URL normalizado ou ``None`` se não houver slug de empresa válido.
    """

    raw = str(value or "").strip()
    if not raw or "linkedin.com" not in raw.lower():
        return None
    match = _LINKEDIN_COMPANY_URL_RE.search(raw.split("#", 1)[0])
    if not match:
        return None
    slug = match.group(1).strip().strip("/")
    if not slug:
        return None
    return f"https://www.linkedin.com/company/{slug}"


def _linkedin_school_url_from_string(value: str) -> Optional[str]:
    """Extrai URL público ``/school/...`` de uma string (página de instituição).

    Argumentos:
        value: Texto que pode conter ``linkedin.com/school/slug``.

    Retorno:
        URL normalizado ou ``None`` se não houver slug válido.
    """

    raw = str(value or "").strip()
    if not raw or "linkedin.com" not in raw.lower():
        return None
    match = _LINKEDIN_SCHOOL_URL_RE.search(raw.split("#", 1)[0])
    if not match:
        return None
    slug = match.group(1).strip().strip("/")
    if not slug or not re.match(r"^[a-zA-Z0-9\-_]+$", slug):
        return None
    return f"https://www.linkedin.com/school/{slug}"


def canonicalize_linkedin_profile_url(raw: str) -> Optional[str]:
    """Converte texto livre num URL LinkedIn público ``/in/``, ``/company/`` ou ``/school/``.

    Tenta extrair o slug de URLs completos, caminhos parciais ou slugs soltos
    antes de falhar. Usado ao ler da BD, resolver sessão e validar pedidos de análise.

    Argumentos:
        raw: URL, caminho ou slug introduzido pelo utilizador ou guardado na BD.

    Retorno:
        URL ``https://www.linkedin.com/in/...``, ``/company/...``, ``/school/...``, ou ``None``.
    """

    s = str(raw or "").strip()
    if not s:
        return None
    for extractor in (
        _linkedin_profile_url_from_string,
        _linkedin_company_url_from_string,
        _linkedin_school_url_from_string,
    ):
        url = extractor(s)
        if url:
            return url
    if not s.lower().startswith("http") and "/" not in s and "linkedin.com" not in s.lower():
        slug = s.strip().strip("/")
        if slug and is_linkedin_public_vanity_slug(slug):
            return f"https://www.linkedin.com/in/{slug}"
    return None


def _linkedin_profile_url_from_string(value: str) -> Optional[str]:
    """Extrai URL público ``/in/...`` de uma string (URL completo ou caminho).

    Argumentos:
        value: Texto que pode conter ``linkedin.com/in/slug``.

    Retorno:
        URL normalizado ou ``None`` se o slug não for vanity público.
    """

    raw = str(value or "").strip()
    if not raw or "linkedin.com" not in raw.lower():
        return None
    match = _LINKEDIN_IN_URL_RE.search(raw.split("#", 1)[0])
    if not match:
        return None
    slug = match.group(1).strip().strip("/")
    if not is_linkedin_public_vanity_slug(slug):
        return None
    return f"https://www.linkedin.com/in/{slug}"


def _deep_scan_linkedin_profile_url(
    node: Any,
    *,
    depth: int = 0,
    max_depth: int = 8,
) -> Optional[str]:
    """Procura recursivamente um URL ``linkedin.com/in/...`` em metadados Supabase.

    Argumentos:
        node: Dicionário, lista ou valor escalar (``user``, ``user_metadata``, etc.).
        depth: Profundidade actual da recursão.
        max_depth: Limite para evitar ciclos ou árvores demasiado grandes.

    Retorno:
        Primeiro URL público válido encontrado, ou ``None``.
    """

    if depth > max_depth:
        return None
    if isinstance(node, str):
        return _linkedin_profile_url_from_string(node)
    if isinstance(node, dict):
        for key in (
            "picture",
            "avatar_url",
            "photo",
            "image",
            "profile_picture",
            "profilePicture",
            "profilePictureUrl",
            "profile_picture_url",
        ):
            val = node.get(key)
            if isinstance(val, str):
                url = _linkedin_profile_url_from_string(val)
                if url:
                    return url
        for val in node.values():
            url = _deep_scan_linkedin_profile_url(val, depth=depth + 1, max_depth=max_depth)
            if url:
                return url
        return None
    if isinstance(node, list):
        for item in node:
            url = _deep_scan_linkedin_profile_url(item, depth=depth + 1, max_depth=max_depth)
            if url:
                return url
    return None


def extract_linkedin_public_vanity_slug(profile_url: str) -> Optional[str]:
    """Extrai o slug público de um URL LinkedIn ``/in/``, ``/company/`` ou ``/school/``.

    Argumentos:
        profile_url: URL completo ou caminho com ``linkedin.com``.

    Retorno:
        Segmento após o marcador de caminho, ou ``None`` se não existir.
    """

    raw = str(profile_url or "").strip().split("#", 1)[0].rstrip("/")
    if not raw:
        return None
    lower = raw.lower()
    for marker in _LINKEDIN_ORG_PATH_MARKERS:
        idx = lower.find(marker)
        if idx >= 0:
            slug = raw[idx + len(marker) :].split("/", 1)[0].strip()
            return slug or None
    return None


def is_linkedin_public_vanity_slug(slug: str) -> bool:
    """Indica se o slug parece um nome público LinkedIn (não um ID interno).

    IDs internos (ex.: ``ACoAA...``, ``juGxdU4AEW``) costumam devolver 404 ou
  posts vazios no Apify.

    Argumentos:
        slug: Segmento do URL após ``/in/`` ou ``/company/``.

    Retorno:
        ``True`` quando o slug é plausível para scraping público; ``False`` caso contrário.
    """

    s = str(slug or "").strip().strip("/")
    if not s or " " in s or len(s) < 3 or len(s) > 100:
        return False
    if "linkedin.com" in s.lower():
        return False
    if s.upper().startswith("ACO") and len(s) > 20:
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    if not all(ch in allowed for ch in s):
        return False
    # Nomes públicos típicos: minúsculas, hífens ou uma palavra legível.
    if s.islower() or ("-" in s and s.lower() == s):
        return True
    has_upper = any(c.isupper() for c in s)
    has_lower = any(c.islower() for c in s)
    has_digit = any(c.isdigit() for c in s)
    if has_upper and has_lower and (has_digit or sum(1 for c in s if c.isupper()) >= 2):
        return False
    if has_digit and not s.islower():
        return False
    return "-" in s


def linkedin_slug_matches_internal_subject_id(slug: str, subject_id: str) -> bool:
    """Compara slug do URL com o ``sub`` OIDC (ID interno, não vanity).

    Argumentos:
        slug: Slug extraído do URL ``/in/...``.
        subject_id: Claim ``sub`` do utilizador LinkedIn.

    Retorno:
        ``True`` se forem o mesmo identificador (ignorando maiúsculas/minúsculas).
    """

    a = str(slug or "").strip().strip("/")
    b = str(subject_id or "").strip().strip("/")
    if not a or not b:
        return False
    return a.casefold() == b.casefold()


def _linkedin_slug_from_openid_sub(sub: str) -> Optional[str]:
    """Indica se ``sub`` do OIDC pode ser um vanity name (não ID interno LinkedIn).

    IDs internos (ex.: ``ACoAA...``, ``juGxdU4AEW``) não funcionam em ``/in/...`` público.

    Argumentos:
        sub: Claim ``sub`` do token/userinfo.

    Retorno:
        Slug para URL público ou ``None`` se for ID opaco ou inválido.
    """

    s = str(sub or "").strip().strip("/")
    if not is_linkedin_public_vanity_slug(s):
        return None
    return s


def _linkedin_url_from_oidc_claims(data: Dict[str, Any]) -> Optional[str]:
    """Extrai um URL público LinkedIn de claims OIDC / metadados.

    Argumentos:
        data: Dicionário (``userinfo``, ``user_metadata``, ``identity_data``, etc.).

    Retorno:
        URL ``https://www.linkedin.com/in/...`` ou ``None``.
    """

    if not isinstance(data, dict):
        return None
    for key in (
        "profile",
        "profile_url",
        "linkedin_url",
        "linkedin_profile_url",
        "website",
        "publicProfileUrl",
        "provider_url",
    ):
        val = data.get(key)
        if isinstance(val, str) and "linkedin.com" in val.lower():
            url = canonicalize_linkedin_profile_url(val)
            if url:
                return url
    sub_val = data.get("sub")
    if isinstance(sub_val, str):
        slug_from_sub = _linkedin_slug_from_openid_sub(sub_val)
        if slug_from_sub:
            return f"https://www.linkedin.com/in/{slug_from_sub}"
    for key in (
        "preferred_username",
        "nickname",
        "slug",
        "user_name",
        "vanityName",
        "vanity_name",
        "publicIdentifier",
    ):
        val = data.get(key)
        if not isinstance(val, str):
            continue
        v = val.strip().strip("/")
        if not v or " " in v or "linkedin.com" in v.lower():
            continue
        if is_linkedin_public_vanity_slug(v):
            return f"https://www.linkedin.com/in/{v}"
    return None


def extract_linkedin_profile_url_from_supabase_user(user: Dict[str, Any]) -> Optional[str]:
    """Obtém URL público LinkedIn a partir do utilizador Supabase (metadados OIDC).

    Percorre ``user_metadata``, ``app_metadata`` e ``identities[].identity_data``
  do fornecedor ``linkedin_oidc`` / ``linkedin``.

    Argumentos:
        user: Objecto ``GET /auth/v1/user`` (GoTrue).

    Retorno:
        URL ``https://www.linkedin.com/in/...`` ou ``None``.
    """

    if not isinstance(user, dict):
        return None
    for meta_key in ("user_metadata", "app_metadata", "raw_user_meta_data"):
        url = _linkedin_url_from_oidc_claims(user.get(meta_key) or {})
        if url:
            return url
    for ident in user.get("identities") or []:
        if not isinstance(ident, dict):
            continue
        prov = str(ident.get("provider", "")).lower()
        if prov not in ("linkedin_oidc", "linkedin"):
            continue
        id_data = ident.get("identity_data") or {}
        url = _linkedin_url_from_oidc_claims(id_data)
        if url:
            return url
        sub = id_data.get("sub") if isinstance(id_data, dict) else None
        if not sub and isinstance(ident.get("id"), str):
            sub = ident.get("id")
        slug = _linkedin_slug_from_openid_sub(str(sub or ""))
        if slug:
            return f"https://www.linkedin.com/in/{slug}"
    url = _deep_scan_linkedin_profile_url(user)
    if url:
        return url
    return None


def _decode_oidc_jwt_payload_unverified(id_token: str) -> Dict[str, Any]:
    """Descodifica o payload de um JWT OIDC (sem validar assinatura).

    Argumentos:
        id_token: JWT ``id_token`` devolvido pelo LinkedIn no exchange OAuth.

    Retorno:
        Claims JSON ou dicionário vazio se inválido.
    """

    import base64

    parts = str(id_token or "").strip().split(".")
    if len(parts) < 2:
        return {}
    segment = parts[1]
    pad = "=" * (-len(segment) % 4)
    try:
        raw = base64.urlsafe_b64decode(segment + pad)
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return {}


def _linkedin_vanity_slug_from_api_record(data: Dict[str, Any]) -> Optional[str]:
    """Extrai slug público de respostas ``/v2/me``, ``identityMe`` ou REST.

    Argumentos:
        data: Objecto JSON da API LinkedIn (pode incluir ``elements`` Rest.li).

    Retorno:
        Slug ``/in/...`` ou ``None``.
    """

    if not isinstance(data, dict):
        return None
    for key in ("vanityName", "publicIdentifier", "vanity_name"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            slug = val.strip().strip("/")
            if is_linkedin_public_vanity_slug(slug):
                return slug
    elements = data.get("elements")
    if isinstance(elements, list):
        for item in elements:
            if isinstance(item, dict):
                slug = _linkedin_vanity_slug_from_api_record(item)
                if slug:
                    return slug
    return None


def fetch_linkedin_profile_url_with_provider_token(
    provider_token: str,
    *,
    id_token: Optional[str] = None,
) -> Optional[str]:
    """Obtém o URL público do perfil via API LinkedIn (token OAuth da sessão).

    Ordem: claims do ``id_token``, ``/v2/userinfo``, ``/rest/identityMe``,
    ``/v2/me`` com ``vanityName``/``publicIdentifier`` (requer ``r_basicprofile``
    na app Developer além de ``openid profile email``).

    Argumentos:
        provider_token: Access token OAuth LinkedIn.
        id_token: JWT OIDC opcional do exchange (claims ``sub``, etc.).

    Retorno:
        URL ``https://www.linkedin.com/in/...`` ou ``None``.
    """

    import urllib.error
    import urllib.request

    token = str(provider_token or "").strip()
    if not token:
        return None

    jwt_claims = _decode_oidc_jwt_payload_unverified(str(id_token or ""))
    if jwt_claims:
        url = _linkedin_url_from_oidc_claims(jwt_claims)
        if url:
            return url

    def _get_json(url: str, extra: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if extra:
            headers.update(extra)
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data if isinstance(data, dict) else None
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
            return None

    userinfo = _get_json("https://api.linkedin.com/v2/userinfo")
    if userinfo:
        url = _linkedin_url_from_oidc_claims(userinfo)
        if url:
            return url
        scanned = _deep_scan_linkedin_profile_url(userinfo)
        if scanned:
            return scanned

    api_attempts: List[Tuple[str, Dict[str, str]]] = [
        (
            "https://api.linkedin.com/rest/identityMe",
            {
                "LinkedIn-Version": "202405",
                "X-Restli-Protocol-Version": "2.0.0",
            },
        ),
        (
            "https://api.linkedin.com/v2/me?projection=(id,vanityName,publicIdentifier,localizedFirstName,localizedLastName)",
            {"X-Restli-Protocol-Version": "2.0.0"},
        ),
        (
            "https://api.linkedin.com/v2/me?projection=(id,vanityName,publicIdentifier)",
            {"X-Restli-Protocol-Version": "2.0.0", "LinkedIn-Version": "202405"},
        ),
    ]
    for url_endpoint, headers in api_attempts:
        payload = _get_json(url_endpoint, headers)
        if not payload:
            continue
        slug = _linkedin_vanity_slug_from_api_record(payload)
        if slug:
            return f"https://www.linkedin.com/in/{slug}"
        url = _linkedin_url_from_oidc_claims(payload)
        if url:
            return url
    return None


def extract_linkedin_id_token_from_supabase_user(user: Dict[str, Any]) -> Optional[str]:
    """Extrai ``id_token`` OIDC LinkedIn guardado nos metadados Supabase, se existir.

    Argumentos:
        user: Objecto ``GET /auth/v1/user`` (GoTrue).

    Retorno:
        JWT ``id_token`` ou ``None``.
    """

    if not isinstance(user, dict):
        return None
    for meta_key in ("user_metadata", "app_metadata", "raw_user_meta_data"):
        block = user.get(meta_key)
        if isinstance(block, dict):
            for key in ("id_token", "provider_id_token"):
                val = block.get(key)
                if isinstance(val, str) and val.count(".") >= 2:
                    return val.strip()
    for ident in user.get("identities") or []:
        if not isinstance(ident, dict):
            continue
        prov = str(ident.get("provider", "")).lower()
        if prov not in ("linkedin_oidc", "linkedin"):
            continue
        id_data = ident.get("identity_data") or {}
        if isinstance(id_data, dict):
            for key in ("id_token", "provider_id_token"):
                val = id_data.get(key)
                if isinstance(val, str) and val.count(".") >= 2:
                    return val.strip()
    return None


def fetch_user_linkedin_profile_from_database(
    access_token: str,
    supabase_url: str,
    anon_key: str,
) -> Optional[str]:
    """Lê o URL LinkedIn associado ao login na tabela ``user_linkedin_profiles``.

    Usa o JWT do utilizador e RLS do Supabase (cada user só vê o seu registo).

    Argumentos:
        access_token: ``access_token`` da sessão Supabase.
        supabase_url: URL base do projecto Supabase.
        anon_key: Chave ``anon`` pública.

    Retorno:
        URL ``https://www.linkedin.com/in/...`` ou ``None`` se não existir / tabela em falta.
    """

    import urllib.error
    import urllib.parse
    import urllib.request

    token = str(access_token or "").strip()
    base = str(supabase_url or "").strip().rstrip("/")
    key = str(anon_key or "").strip()
    if not token or not base or not key:
        return None

    query = urllib.parse.urlencode({"select": "profile_url", "limit": "1"})
    url = f"{base}/rest/v1/user_linkedin_profiles?{query}"
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
    raw = first.get("profile_url")
    if not isinstance(raw, str):
        return None
    return canonicalize_linkedin_profile_url(raw)


def upsert_user_linkedin_profile_to_database(
    access_token: str,
    supabase_url: str,
    anon_key: str,
    user_id: str,
    profile_url: str,
    *,
    display_name: Optional[str] = None,
) -> bool:
    """Grava ou actualiza o URL LinkedIn do utilizador na base de dados Supabase.

    Argumentos:
        access_token: JWT da sessão Supabase (RLS ``authenticated``).
        supabase_url: URL base do projecto.
        anon_key: Chave ``anon``.
        user_id: UUID do utilizador (``auth.users.id``).
        profile_url: URL público normalizado do perfil LinkedIn.
        display_name: Nome opcional para exibição.

    Retorno:
        ``True`` se o upsert foi aceite; ``False`` em caso de erro ou tabela em falta.
    """

    import urllib.error
    import urllib.request
    from datetime import datetime, timezone

    token = str(access_token or "").strip()
    base = str(supabase_url or "").strip().rstrip("/")
    key = str(anon_key or "").strip()
    uid = str(user_id or "").strip()
    normalized = _linkedin_profile_url_from_string(str(profile_url or "").strip())
    if not token or not base or not key or not uid or not normalized:
        return False

    slug = normalized.rstrip("/").rsplit("/", 1)[-1][:120]
    payload = {
        "user_id": uid,
        "profile_url": normalized,
        "profile_slug": slug,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if display_name:
        payload["display_name"] = str(display_name).strip()[:200]

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/rest/v1/user_linkedin_profiles",
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
        with urllib.request.urlopen(req, timeout=20) as resp:
            return 200 <= int(getattr(resp, "status", 200) or 200) < 300
    except urllib.error.HTTPError:
        return False
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def resolve_linkedin_profile_url_for_session(
    user: Dict[str, Any],
    provider_token: Optional[str] = None,
    *,
    stored_profile_url: Optional[str] = None,
    database_profile_url: Optional[str] = None,
    id_token: Optional[str] = None,
) -> Optional[str]:
    """Resolve o URL público LinkedIn: BD, browser, API OAuth, metadados Supabase.

    Argumentos:
        user: Utilizador GoTrue (``GET /auth/v1/user``).
        provider_token: ``session.provider_token`` (opcional; muitas vezes só no login).
        stored_profile_url: URL previamente guardado no browser (``localStorage``).
        database_profile_url: URL lido de ``user_linkedin_profiles`` (Supabase).
        id_token: JWT OIDC LinkedIn (claims ``sub``, ``profile``, etc.).

    Retorno:
        URL normalizado ou ``None`` se não for possível inferir.
    """

    db_hint = str(database_profile_url or "").strip()
    if db_hint:
        url = _linkedin_profile_url_from_string(db_hint)
        if url:
            return url
    hint = str(stored_profile_url or "").strip()
    if hint:
        url = _linkedin_profile_url_from_string(hint)
        if url:
            return url
    oidc_token = str(id_token or "").strip() or extract_linkedin_id_token_from_supabase_user(user)
    if provider_token:
        url = fetch_linkedin_profile_url_with_provider_token(
            provider_token,
            id_token=oidc_token or None,
        )
        if url:
            return url
    if oidc_token:
        claims = _decode_oidc_jwt_payload_unverified(oidc_token)
        url = _linkedin_url_from_oidc_claims(claims)
        if url:
            return url
    return extract_linkedin_profile_url_from_supabase_user(user)


def fetch_supabase_auth_user(access_token: str, supabase_url: str, anon_key: str) -> Dict[str, Any]:
    """Obtém o utilizador autenticado via ``GET /auth/v1/user`` (GoTrue).

    Argumentos:
        access_token: JWT ``access_token`` da sessão Supabase.
        supabase_url: URL base do projecto Supabase.
        anon_key: Chave pública ``anon``.

    Retorno:
        Dicionário JSON do utilizador (``user_metadata``, ``identities``, etc.).

    Raises:
        urllib.error.HTTPError: Token inválido ou erro HTTP.
        urllib.error.URLError: Falha de rede.
    """

    import urllib.request

    base = supabase_url.rstrip("/")
    url = f"{base}/auth/v1/user"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": anon_key,
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


social_media_agent = SocialMediaAgent()
