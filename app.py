from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
import unicodedata
from urllib import error, request
from urllib.parse import urlparse

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field
from dotenv import dotenv_values, load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

from agents.copywriter import copywriter_agent
from agents.designer import designer_agent
from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML
from agents.linkedin_oauth import (
    create_publish_authorization_url,
    exchange_code_for_publish_token,
    linkedin_oauth_configured,
    pop_oauth_state,
)
from agents.linkedin_calendar_db import (
    fetch_user_linkedin_calendar_posts_from_database,
    normalize_calendar_posts_for_storage,
    upsert_user_linkedin_calendar_posts_to_database,
)
from agents.linkedin_followed_profiles_db import (
    fetch_user_linkedin_followed_profiles_from_database,
    normalize_followed_profiles_for_storage,
    upsert_user_linkedin_followed_profiles_to_database,
)
from agents.linkedin_publish_auth_db import (
    clear_user_linkedin_publish_oauth_from_database,
    fetch_user_linkedin_publish_oauth_from_database,
    publish_oauth_status_for_client,
    upsert_user_linkedin_publish_oauth_to_database,
)
from agents.linkedin_harvest_profile import apply_linkedin_harvest_overview_to_analysis
from agents.linkedin_publish import (
    format_linkedin_post_text,
    get_linkedin_person_urn,
    publish_to_linkedin,
    resolve_linkedin_publish_token_and_urn,
)
from agents.director_workflow import process_director_turn
from agents.social_media import (
    canonicalize_linkedin_profile_url,
    _linkedin_slug_from_openid_sub,
    extract_linkedin_public_vanity_slug,
    extract_linkedin_profile_url_from_supabase_user,
    fetch_linkedin_profile_url_with_provider_token,
    fetch_supabase_auth_user,
    fetch_user_linkedin_profile_from_database,
    get_supabase_public_credentials,
    is_linkedin_public_vanity_slug,
    linkedin_slug_matches_internal_subject_id,
    enrich_linkedin_analysis_metrics,
    linkedin_page_kind_from_url,
    normalize_social_platform,
    resolve_linkedin_profile_url_for_session,
    social_media_agent,
    social_platform_label_pt,
    upsert_user_linkedin_profile_to_database,
)


STATIC_DIR = BASE_DIR / "static"
COPYWRITER_PHOTO_PATH = Path(
    r"C:\Users\Gui\.cursor\projects\c-Users-Gui-Desktop-Cursor-Teste-PlataformaV1\assets\c__Users_Gui_AppData_Roaming_Cursor_User_workspaceStorage_5cf04d98823b3ed471fa9fcf2f9a8995_images_image-086e2d41-4ac7-4b47-94ee-d5b6a9591ec8.png"
)
DESIGNER_PHOTO_PATH = Path(
    r"C:\Users\Gui\.cursor\projects\c-Users-Gui-Desktop-Cursor-Teste-PlataformaV1\assets\c__Users_Gui_AppData_Roaming_Cursor_User_workspaceStorage_5cf04d98823b3ed471fa9fcf2f9a8995_images_image-60079ec3-45f1-4734-bbfb-0c9b44f7606c.png"
)
INSTAGRAM_OAUTH_AUTHORIZE_URL = "https://www.facebook.com/v25.0/dialog/oauth"
INSTAGRAM_GRAPH_API_BASE_URL = "https://graph.facebook.com/v25.0"
DATA_DIR = BASE_DIR / "data"
SOCIAL_SNAPSHOTS_FILE = DATA_DIR / "social_media_snapshots.json"

app = FastAPI(
    title="Diretor de Marketing AI",
    description="Diretor de Marketing orquestra a equipa de agentes numa única conversa.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Armazenamento em memória para MVP local (single-user).
_instagram_auth_state: Dict[str, str] = {
    "access_token": "",
    "ig_user_id": "",
    "username": "",
    "last_error": "",
}


def _get_env_setting(key: str, default: str = "") -> str:
    """Lê configuração do ambiente com fallback explícito para `.env`.

    A função prioriza variáveis de ambiente já carregadas, mas também consulta
    diretamente o ficheiro `.env` do projeto para reduzir problemas de reload
    quando o servidor não atualiza o processo imediatamente.

    Argumentos:
        key: Nome da variável de ambiente a ler.
        default: Valor devolvido quando a chave não existe.

    Retorno:
        String com valor da configuração sem espaços laterais.
    """

    dotenv_path = BASE_DIR / ".env"
    if dotenv_path.exists():
        dotenv_data = dotenv_values(dotenv_path)
        file_value = dotenv_data.get(key)
        if file_value is not None and str(file_value).strip():
            return str(file_value).strip()
    env_value = os.getenv(key)
    if env_value is not None and str(env_value).strip():
        return str(env_value).strip()
    return default.strip()

AGENT_SLUGS: Dict[str, str] = {
    "Agente Copywriter": "copywriter",
    "Agente Designer": "designer",
    "Agente Redes sociais": "redes-sociais",
    "Agente LinkedIn (perfil)": "linkedin-perfil",
    "Agente Meta Ads": "meta-ads",
    "Agente Linkedin Ads": "linkedin-ads",
    "Agente Google Ads": "google-ads",
    "Agente Web Developer": "web-developer",
    "Agente Seo": "seo",
    "Agente GEO": "geo",
    "Agente Analista de Score": "analista-score",
}

SLUG_TO_AGENT: Dict[str, str] = {slug: name for name, slug in AGENT_SLUGS.items()}


@dataclass
class AgentResult:
    """Representa o resultado produzido por um agente especializado.

    A classe serve para unificar o formato de resposta de todos os agentes
    especializados, garantindo que o backend devolve sempre os mesmos campos
    ao frontend e a outros consumidores da API.

    Argumentos:
        agent_name: Nome humano do agente que respondeu ao pedido.
        action_plan: Lista de passos recomendados para executar o pedido.
        justification: Explicação resumida do motivo para este plano.
    """

    agent_name: str
    action_plan: List[str]
    justification: str


def _agent_page_url(agent_name: str) -> str:
    """Constrói a URL da página de conversa para um agente específico.

    A função recebe o nome canónico do agente devolvido pelo Diretor e converte
    esse nome para o slug definido em `AGENT_SLUGS`, garantindo que a interface
    consegue sempre abrir a página correta de continuidade da conversa.

    Argumentos:
        agent_name: Nome completo do agente (ex.: `Agente Copywriter`).

    Retorno:
        String com URL relativa da página do agente (ex.: `/agentes/copywriter`).
        Se o agente não estiver no mapa, devolve `/` como fallback seguro.
    """

    slug = AGENT_SLUGS.get(agent_name)
    if not slug:
        return "/"
    return f"/agentes/{slug}"


class ChatRequest(BaseModel):
    """Corpo do pedido enviado pelo utilizador no chat.

    Esta estrutura valida e documenta o input recebido via API. O campo
    principal é a instrução em linguagem natural que o Diretor de Marketing
    vai analisar para decidir o encaminhamento.

    Argumentos:
        user_input: Texto livre introduzido pelo utilizador com objetivo,
            contexto, restrições e pedidos de marketing.

    Retorno:
        Instância validada de ChatRequest usada no endpoint `/chat`.
    """

    user_input: str = Field(..., min_length=3, description="Instrução do utilizador.")


class DirectorChatMessage(BaseModel):
    """Mensagem individual da chatroom do Diretor de Marketing.

    Esta estrutura representa cada turno de conversa entre o utilizador e o
    Diretor. O histórico completo destas mensagens é enviado ao LLM para que a
    próxima resposta seja contextual, educada e coerente com o que já foi dito.

    Argumentos:
        role: Papel da mensagem no histórico (`user` ou `assistant`).
        content: Texto da mensagem em linguagem natural.

    Retorno:
        Instância validada para compor o histórico da chatroom do Diretor.
    """

    role: Literal["user", "assistant"] = Field(..., description="Autor da mensagem.")
    content: str = Field(..., min_length=1, description="Conteúdo textual da mensagem.")


class DirectorChatTurnRequest(BaseModel):
    """Pedido para gerar a próxima resposta do Diretor na chatroom.

    Inclui estado do fluxo operacional (copy → aprovar → imagem → aprovar) para
    que tudo corra na interface do Diretor sem mudar de página.

    Argumentos:
        messages: Histórico cronológico da conversa na chatroom do Diretor.
        language: Idioma preferido da resposta (por defeito `pt-PT`).
        workflow_state: Estado persistido entre turnos (stage, post, imagem).
        user_action: Acção de botão (`approve_copy`, `generate_image`, etc.).
        action_payload: Dados extra (corpo editado, instruções de imagem).

    Retorno:
        Instância validada para o endpoint `POST /director/chat-reply`.
    """

    messages: List[DirectorChatMessage] = Field(
        ..., min_length=1, description="Histórico de mensagens da chatroom do Diretor."
    )
    language: str = Field("pt-PT", min_length=2, description="Idioma da resposta do Diretor.")
    workflow_state: Optional[Dict[str, Any]] = Field(
        None, description="Estado do fluxo copy/imagem na interface do Diretor."
    )
    user_action: Optional[str] = Field(
        None, description="Acção explícita: approve_copy, generate_image, approve_image, etc."
    )
    action_payload: Optional[Dict[str, Any]] = Field(
        None, description="Payload opcional para edit_copy ou regenerar imagem."
    )


class CopywriterRequest(BaseModel):
    """Pedido ao Agente Copywriter para gerar textos via OpenAI.

    O utilizador descreve objetivos, público, tom, canal, restrições e
    estratégia de copy; o agente devolve headlines, texto principal e CTAs em
    JSON estruturado.

    Argumentos:
        brief: Contexto livre do produto/oferta/campanha.
        objective: Objetivo principal da peça (vendas, leads, cliques, etc.).
        cta: Call-to-action desejado.
        funnel_stage: Etapa do funil (Topo, Meio, Fundo).
        persona: Persona/público-alvo.
        knowledge_level: Nível de conhecimento do público.
        pains: Dores principais do público.
        desires: Desejos/motivações do público.
        min_words: Número mínimo de palavras.
        max_words: Número máximo de palavras.
        output_format: Formato da peça (parágrafo, bullet points, carrossel...).
        language: Idioma/variante da copy (por defeito `pt-PT`).
        copy_type: Tipo de copy (persuasiva, informativa, storytelling...).
        tone: Tom de voz.
        formality_level: Nível de formalidade.
        brand_personality: Personalidade da marca.
        reference_brands: Marcas de referência para estilo.
        channel: Canal de distribuição.
        asset_type: Tipo de peça (post, anúncio, email, headline...).
        brand_positioning: Posicionamento da marca.
        avoid_words: Palavras a evitar.
        required_terms: Keywords/termos obrigatórios.
        legal_limits: Limitações legais/compliance.
        avoid_exaggeration: Evitar promessas exageradas.
        framework: Framework de copy (AIDA, PAS, BAB...).
        main_angle: Ângulo principal (dor, benefício, urgência...).
        include_social_proof: Incluir prova social.
        variations: Número de variações.
        creativity_level: Nível de criatividade.
        include_emojis: Incluir emojis.
        include_hashtags: Incluir hashtags.
        expected_output_example: Exemplo de output esperado.

    Retorno:
        Instância validada usada no endpoint `POST /agents/copywriter/generate`.
    """

    brief: str = Field(..., min_length=10, description="Brief para gerar copy.")
    objective: Optional[str] = Field(None, description="Objetivo principal.")
    cta: Optional[str] = Field(None, description="Call-to-action desejado.")
    funnel_stage: Optional[str] = Field(None, description="Etapa do funil.")
    persona: Optional[str] = Field(None, description="Persona/público-alvo.")
    knowledge_level: Optional[str] = Field(None, description="Nível de conhecimento do público.")
    pains: Optional[str] = Field(None, description="Dores principais do público.")
    desires: Optional[str] = Field(None, description="Desejos e motivações do público.")
    min_words: Optional[int] = Field(None, ge=1, description="Número mínimo de palavras.")
    max_words: Optional[int] = Field(None, ge=1, description="Número máximo de palavras.")
    output_format: Optional[str] = Field(None, description="Formato da peça.")
    language: str = Field("pt-PT", min_length=2, description="Idioma da copy.")
    copy_type: Optional[str] = Field(None, description="Tipo de copy.")
    tone: Optional[str] = Field(None, description="Tom de voz desejado.")
    formality_level: Optional[str] = Field(None, description="Nível de formalidade.")
    brand_personality: Optional[str] = Field(None, description="Personalidade da marca.")
    reference_brands: Optional[str] = Field(None, description="Marcas de referência.")
    channel: Optional[str] = Field(None, description="Canal de distribuição.")
    asset_type: Optional[str] = Field(None, description="Tipo de peça.")
    brand_positioning: Optional[str] = Field(None, description="Posicionamento da marca.")
    avoid_words: Optional[str] = Field(None, description="Palavras a evitar.")
    required_terms: Optional[str] = Field(None, description="Termos obrigatórios/keywords.")
    legal_limits: Optional[str] = Field(None, description="Limitações legais e compliance.")
    avoid_exaggeration: Optional[bool] = Field(None, description="Evitar promessas exageradas.")
    framework: Optional[str] = Field(None, description="Framework de copy.")
    main_angle: Optional[str] = Field(None, description="Ângulo principal da mensagem.")
    include_social_proof: Optional[bool] = Field(None, description="Incluir prova social.")
    variations: int = Field(3, ge=1, le=10, description="Número de variações de copy.")
    creativity_level: Optional[str] = Field(None, description="Nível de criatividade.")
    include_emojis: Optional[bool] = Field(None, description="Incluir emojis.")
    include_hashtags: Optional[bool] = Field(None, description="Incluir hashtags.")
    expected_output_example: Optional[str] = Field(None, description="Exemplo de output esperado.")


class CopywriterChatMessage(BaseModel):
    """Mensagem individual da chatroom do Agente Copywriter.

    Esta estrutura representa cada entrada da conversa entre utilizador e
    agente, preservando o papel de quem escreveu e o conteúdo textual. O
    histórico completo destas mensagens é usado para construir o brief final
    enviado ao motor de geração de copy.

    Argumentos:
        role: Papel da mensagem na conversa. Aceita `user` para utilizador e
            `assistant` para respostas intermédias do agente.
        content: Texto da mensagem em linguagem natural.

    Retorno:
        Instância validada de uma linha da conversa da chatroom.
    """

    role: Literal["user", "assistant"] = Field(..., description="Autor da mensagem.")
    content: str = Field(..., min_length=1, description="Conteúdo textual da mensagem.")


class CopywriterChatRequest(BaseModel):
    """Pedido de geração de copy a partir de histórico de chatroom.

    O payload inclui a lista de mensagens trocadas na sala de conversa do
    Copywriter. O backend converte esse histórico num brief estruturado para
    garantir que a geração final respeita contexto, dores, oferta e objetivos
    discutidos no chat.

    Argumentos:
        messages: Histórico da conversa, em ordem cronológica.
        language: Idioma final da copy (por defeito `pt-PT`).
        tone: Tom de voz pretendido para a peça gerada.
        variations: Número de variações de copy pedidas ao gerador.

    Retorno:
        Instância validada para o endpoint `POST /agents/copywriter/chat-generate`.
    """

    messages: List[CopywriterChatMessage] = Field(
        ..., min_length=1, description="Mensagens da conversa da chatroom."
    )
    language: str = Field("pt-PT", min_length=2, description="Idioma da copy final.")
    tone: Optional[str] = Field(None, description="Tom de voz desejado.")
    variations: int = Field(3, ge=1, le=10, description="Número de variações finais.")


class CopywriterChatTurnRequest(BaseModel):
    """Pedido de próxima resposta do agente na chatroom do Copywriter.

    Este modelo representa uma iteração conversacional (um turno). O frontend
    envia o histórico atual, e o backend chama o LLM para produzir a próxima
    resposta do agente de forma autónoma e contextual.

    Argumentos:
        messages: Histórico cronológico de mensagens da chatroom.
        language: Idioma da resposta do agente (por defeito `pt-PT`).
        tone: Tom de voz preferido para o modo conversacional.

    Retorno:
        Instância validada para o endpoint `POST /agents/copywriter/chat-reply`.
    """

    messages: List[CopywriterChatMessage] = Field(
        ..., min_length=1, description="Histórico de mensagens da chatroom."
    )
    language: str = Field("pt-PT", min_length=2, description="Idioma da resposta do agente.")
    tone: Optional[str] = Field(None, description="Tom preferido para a resposta.")


class DesignerChatMessage(BaseModel):
    """Mensagem individual da chatroom do Agente Designer.

    Esta estrutura representa cada mensagem no histórico da conversa do agente,
    preservando quem escreveu e o conteúdo textual para manter contexto visual.

    Argumentos:
        role: Papel da mensagem (`user` ou `assistant`).
        content: Conteúdo textual introduzido na chatroom.

    Retorno:
        Instância validada para compor o histórico do Designer.
    """

    role: Literal["user", "assistant"] = Field(..., description="Autor da mensagem.")
    content: str = Field(..., min_length=1, description="Conteúdo textual da mensagem.")


class DesignerChatTurnRequest(BaseModel):
    """Pedido da próxima resposta do agente na chatroom do Designer.

    O frontend envia o histórico e o backend devolve a resposta seguinte do
    Agente Designer para continuar a recolher contexto visual antes da geração.

    Argumentos:
        messages: Histórico cronológico da conversa.
        language: Idioma preferido da resposta textual.
        style: Estilo visual desejado (ex.: minimalista, 3D, realista).
        reference_image_urls: Lista opcional com URLs de imagens de referência.

    Retorno:
        Instância validada para `POST /agents/designer/chat-reply`.
    """

    messages: List[DesignerChatMessage] = Field(
        ..., min_length=1, description="Histórico de mensagens da chatroom."
    )
    language: str = Field("pt-PT", min_length=2, description="Idioma da resposta do agente.")
    style: Optional[str] = Field(None, description="Estilo visual desejado.")
    reference_image_urls: List[str] = Field(
        default_factory=list,
        description="URLs de imagens de referência anexadas pelo utilizador.",
    )


class DesignerImageGenerateRequest(BaseModel):
    """Pedido para gerar imagem com Nano Banana a partir da chatroom.

    O pedido inclui o histórico conversacional do Designer e parâmetros visuais
    finais para o endpoint de geração de imagem.

    Argumentos:
        messages: Histórico da chatroom usado para construir o prompt final.
        size: Dimensão da imagem (ex.: `1024x1024`).
        style: Estilo visual opcional.
        reference_image_urls: Lista opcional de URLs de imagens para guiar edição/geração.

    Retorno:
        Instância validada para `POST /agents/designer/chat-generate-image`.
    """

    messages: List[DesignerChatMessage] = Field(
        ..., min_length=1, description="Histórico de mensagens da chatroom."
    )
    size: str = Field("1024x1024", min_length=3, description="Tamanho final da imagem.")
    style: Optional[str] = Field(None, description="Estilo visual opcional.")
    reference_image_urls: List[str] = Field(
        default_factory=list,
        description="URLs de imagens de referência anexadas pelo utilizador.",
    )


SocialMediaPlatform = Literal["instagram", "linkedin", "facebook", "tiktok", "youtube"]


class SocialMediaChatMessage(BaseModel):
    """Mensagem individual da chatroom do Agente de Redes Sociais.

    Esta estrutura guarda cada turno da conversa para que o agente tenha
    contexto ao responder perguntas e ao gerar a análise final da rede escolhida.

    Argumentos:
        role: Papel da mensagem (`user` ou `assistant`).
        content: Texto da mensagem em linguagem natural.

    Retorno:
        Instância validada para compor o histórico da chatroom.
    """

    role: Literal["user", "assistant"] = Field(..., description="Autor da mensagem.")
    content: str = Field(..., min_length=1, description="Conteúdo textual da mensagem.")


class SocialMediaChatTurnRequest(BaseModel):
    """Pedido da próxima resposta conversacional do agente de Redes Sociais.

    O frontend envia o histórico atual da conversa para o backend, que devolve
    uma resposta curta e contextual do agente, focada em recolher dados úteis
    para a análise da plataforma indicada.

    Argumentos:
        messages: Histórico cronológico da chatroom.
        language: Idioma da resposta do agente (por defeito `pt-PT`).
        platform: Rede social em foco (instagram, linkedin, facebook, tiktok, youtube).

    Retorno:
        Instância validada para `POST /agents/social-media/chat-reply`.
    """

    messages: List[SocialMediaChatMessage] = Field(
        ..., min_length=1, description="Histórico de mensagens da chatroom."
    )
    language: str = Field("pt-PT", min_length=2, description="Idioma da resposta do agente.")
    platform: SocialMediaPlatform = Field(
        "instagram",
        description="Plataforma alvo da conversa (por defeito Instagram).",
    )


class SocialMediaAnalysisRequest(BaseModel):
    """Pedido da análise estruturada a partir da chatroom.

    A função de análise recebe o histórico textual e, opcionalmente, um bloco
    JSON com métricas da rede escolhida. O agente cruza ambos para gerar
    insights e plano de crescimento de curto prazo.

    Argumentos:
        messages: Histórico cronológico da chatroom.
        instagram_data: Dados estruturados opcionais (nome histórico; serve para qualquer rede).
        language: Idioma da resposta analítica final.
        platform: Rede social em análise.

    Retorno:
        Instância validada para `POST /agents/social-media/chat-analyze`.
    """

    messages: List[SocialMediaChatMessage] = Field(
        ..., min_length=1, description="Histórico de mensagens da chatroom."
    )
    instagram_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Bloco JSON opcional com métricas da plataforma escolhida.",
    )
    language: str = Field("pt-PT", min_length=2, description="Idioma da análise final.")
    platform: SocialMediaPlatform = Field(
        "instagram",
        description="Plataforma alvo da análise.",
    )


class SocialMediaProfileAnalysisRequest(BaseModel):
    """Pedido de análise a partir de identificador público de perfil.

    Para **Instagram**, o backend pode recolher dados públicos e enriquecer
    com Apify. Para **LinkedIn**, com ``APIFY_API_TOKEN`` e actor configurado,
    tenta-se recolha via Apify;     com ``supabase_access_token`` (e opcionalmente ``linkedin_provider_token``),
    o URL do perfil autenticado é resolvido via API LinkedIn e/ou metadados
    Supabase (OAuth LinkedIn OIDC), depois analisado com Apify.

    Argumentos:
        profile_input: URL, @username ou identificador; pode ficar vazio em
            LinkedIn se enviares ``supabase_access_token`` válido.
        messages: Histórico opcional da conversa para adicionar contexto.
        language: Idioma da análise final (por defeito `pt-PT`).
        platform: Rede social em análise.
        supabase_access_token: JWT ``access_token`` da sessão Supabase no
            browser (opcional) para analisar o perfil LinkedIn sem colar URL.

    Retorno:
        Instância validada para `POST /agents/social-media/profile-analyze`.
    """

    profile_input: str = Field(
        "",
        max_length=4000,
        description="Username, URL ou identificador do perfil (vazio com token Supabase só em LinkedIn).",
    )
    messages: List[SocialMediaChatMessage] = Field(
        default_factory=list,
        description="Histórico opcional de mensagens para contexto adicional.",
    )
    language: str = Field("pt-PT", min_length=2, description="Idioma da análise final.")
    platform: SocialMediaPlatform = Field(
        "instagram",
        description="Plataforma alvo (recolha automática completa só em Instagram).",
    )
    supabase_access_token: Optional[str] = Field(
        None,
        description="Access token JWT Supabase Auth (opcional) para resolver perfil LinkedIn da sessão.",
    )
    linkedin_provider_token: Optional[str] = Field(
        None,
        description=(
            "Token OAuth do LinkedIn (provider_token da sessão Supabase) para obter "
            "o URL do perfil via API oficial antes do scrape Apify."
        ),
    )
    stored_linkedin_profile_url: Optional[str] = Field(
        None,
        max_length=4000,
        description="URL público guardado no browser (localStorage) de análises anteriores.",
    )
    linkedin_id_token: Optional[str] = Field(
        None,
        description="JWT OIDC LinkedIn (id_token) capturado no login, para resolver vanity name.",
    )
    link_as_own_profile: bool = Field(
        False,
        description="Se True, grava o URL analisado em user_linkedin_profiles (perfil do login).",
    )


class LinkedInResolveProfileRequest(BaseModel):
    """Pedido para resolver o URL público LinkedIn a partir da sessão Supabase.

    Argumentos:
        supabase_access_token: JWT da sessão (obrigatório).
        linkedin_provider_token: Token OAuth LinkedIn (``session.provider_token``).
    """

    supabase_access_token: str = Field(..., min_length=20)
    linkedin_provider_token: Optional[str] = Field(None)
    stored_linkedin_profile_url: Optional[str] = Field(None, max_length=4000)
    linkedin_id_token: Optional[str] = Field(None)


class LinkedInStoredProfileRequest(BaseModel):
    """Ler ou gravar o URL LinkedIn do utilizador na base de dados Supabase.

    Argumentos:
        supabase_access_token: JWT da sessão (obrigatório).
        profile_url: Se enviado, faz upsert; se omitido, devolve o URL guardado.
        display_name: Nome opcional para a linha na BD.
    """

    supabase_access_token: str = Field(..., min_length=20)
    profile_url: Optional[str] = Field(None, max_length=4000)
    display_name: Optional[str] = Field(None, max_length=200)


class LinkedInCalendarPostsLoadRequest(BaseModel):
    """Pedido para carregar posts do calendário semanal guardados na BD.

    Argumentos:
        supabase_access_token: JWT da sessão Supabase (obrigatório).
    """

    supabase_access_token: str = Field(..., min_length=20)


class LinkedInCalendarPostsSaveRequest(BaseModel):
    """Pedido para gravar posts do calendário semanal na BD.

    Argumentos:
        supabase_access_token: JWT da sessão.
        posts: Lista de posts do calendário (estado actual).
        week_start: Data ISO do primeiro dia da semana (opcional).
    """

    supabase_access_token: str = Field(..., min_length=20)
    posts: List[Dict[str, Any]] = Field(default_factory=list)
    week_start: Optional[str] = Field(None, max_length=10)


class LinkedInFollowedProfilesLoadRequest(BaseModel):
    """Pedido para carregar perfis LinkedIn seguidos guardados na BD.

    Argumentos:
        supabase_access_token: JWT da sessão Supabase (obrigatório).
    """

    supabase_access_token: str = Field(..., min_length=20)


class LinkedInFollowedProfilesSaveRequest(BaseModel):
    """Pedido para gravar perfis LinkedIn seguidos na BD.

    Argumentos:
        supabase_access_token: JWT da sessão.
        profiles: Lista de perfis (``id``, ``profile_url``, ``display_name``).
    """

    supabase_access_token: str = Field(..., min_length=20)
    profiles: List[Dict[str, Any]] = Field(default_factory=list)


class LinkedInGeneratePostsRequest(BaseModel):
    """Pedido para gerar posts LinkedIn a partir de uma análise de perfil.

    Argumentos:
        analysis: Resultado JSON da análise (tab Visão Geral / Ações).
        public_profile_data: Dados Apify do perfil (opcional).
        profile_url: URL do perfil analisado.
        count: Quantidade de posts (1–7).
        language: Idioma dos textos.
    """

    analysis: Dict[str, Any] = Field(default_factory=dict)
    public_profile_data: Optional[Dict[str, Any]] = Field(None)
    profile_url: Optional[str] = Field(None, max_length=4000)
    count: int = Field(3, ge=1, le=7)
    language: str = Field("pt-PT", min_length=2)


class LinkedInRegeneratePostRequest(BaseModel):
    """Pedido para refazer um post LinkedIn com contexto da análise.

    Argumentos:
        analysis: Análise de perfil (contexto).
        post: Post actual a substituir.
        public_profile_data: Dados do perfil.
        profile_url: URL do perfil.
        edit_instructions: Instruções do utilizador (editar/refazer).
        language: Idioma.
    """

    analysis: Dict[str, Any] = Field(default_factory=dict)
    post: Dict[str, Any] = Field(default_factory=dict)
    public_profile_data: Optional[Dict[str, Any]] = Field(None)
    profile_url: Optional[str] = Field(None, max_length=4000)
    edit_instructions: Optional[str] = Field(None, max_length=4000)
    language: str = Field("pt-PT", min_length=2)


class LinkedInGeneratePostImageRequest(BaseModel):
    """Pedido para gerar imagem ilustrativa de um post LinkedIn aprovado.

    Argumentos:
        post: Objecto do post (``body``, ``title``, ``hook``, ``content_type``, etc.).
        size: Dimensão pedida ao motor de imagem (ex.: ``1024x1024``).
        edit_instructions: Instruções opcionais ao refazer a imagem.
    """

    post: Dict[str, Any] = Field(default_factory=dict)
    size: str = Field("1024x1024", min_length=3, max_length=32)
    edit_instructions: Optional[str] = Field(None, max_length=4000)


class LinkedInFollowedProfilePostsRequest(BaseModel):
    """Pedido para recolher publicações recentes de um perfil LinkedIn seguido.

    Argumentos:
        profile_url: URL ``linkedin.com/in/...`` ou ``/company/...``.

    Retorno:
        Usado pelo endpoint ``POST /agents/linkedin/followed-profile-posts``.
    """

    profile_url: str = Field(..., min_length=12, description="URL do perfil LinkedIn seguido.")


class LinkedInNetworkFeedRequest(BaseModel):
    """Pedido para tentar importar o feed da rede LinkedIn (ligações).

    Argumentos:
        linkedin_provider_token: ``session.provider_token`` do login Supabase.

    Retorno:
        Usado pelo endpoint ``POST /agents/linkedin/network-feed``.
    """

    linkedin_provider_token: str = Field(..., min_length=20)


class LinkedInPublishPostRequest(BaseModel):
    """Pedido para publicar um post gerado no LinkedIn (conta autenticada).

    Argumentos:
        supabase_access_token: JWT da sessão Supabase (validação).
        linkedin_provider_token: Token OAuth LinkedIn (``provider_token``).
        linkedin_id_token: JWT OIDC opcional.
        post: Post com texto e opcionalmente ``generated_image_url``.
        include_image: Se ``True``, publica texto + imagem (quando existir).
        visibility: ``PUBLIC`` ou ``CONNECTIONS``.
    """

    supabase_access_token: str = Field(..., min_length=20)
    linkedin_provider_token: Optional[str] = Field(None)
    linkedin_publish_access_token: Optional[str] = Field(
        None,
        description="Token OAuth com w_member_social (fluxo connect-publish), não o OIDC Supabase.",
    )
    linkedin_person_urn: Optional[str] = Field(
        None,
        description="URN do membro LinkedIn (sessionStorage após connect-publish).",
    )
    linkedin_id_token: Optional[str] = Field(None)
    post: Dict[str, Any] = Field(default_factory=dict)
    include_image: bool = False
    visibility: str = Field("PUBLIC", min_length=3, max_length=20)


class LinkedInPublishAuthStoreRequest(BaseModel):
    """Pedido para guardar autorização OAuth de publicação LinkedIn na Supabase.

    Argumentos:
        supabase_access_token: JWT da sessão Supabase do utilizador.
        linkedin_publish_access_token: Access token com ``w_member_social``.
        linkedin_person_urn: URN do membro LinkedIn (opcional).
        expires_in: Segundos até expirar (opcional).

    Retorno:
        Usado em ``POST /agents/linkedin/publish-auth/store`` (sem corpo de resposta complexo).
    """

    supabase_access_token: str = Field(..., min_length=20)
    linkedin_publish_access_token: str = Field(..., min_length=20)
    linkedin_person_urn: Optional[str] = None
    expires_in: Optional[int] = Field(None, ge=60)


class LinkedInPublishAuthStatusRequest(BaseModel):
    """Pedido para verificar se o utilizador já autorizou publicação no LinkedIn.

    Argumentos:
        supabase_access_token: JWT da sessão Supabase.

    Retorno:
        Usado em ``POST /agents/linkedin/publish-auth/status``.
    """

    supabase_access_token: str = Field(..., min_length=20)


class SocialMediaUnifiedAnalysisRequest(BaseModel):
    """Pedido unificado para análise com perfil e métricas (MVP: Instagram).

    Este modelo simplifica o frontend para um único botão de análise. O
    utilizador pode enviar username/link, métricas manuais e séries mensais
    num único payload. O backend agrega os dados e chama o agente.

    Argumentos:
        profile_input: Username ou link de perfil (Instagram quando platform=instagram).
        instagram_data: Métricas estruturadas adicionais preenchidas no formulário.
        language: Idioma da análise final (por defeito `pt-PT`).
        platform: Rede social; fluxo Apify + comparativos temporais só em Instagram.

    Retorno:
        Instância validada para `POST /agents/social-media/analyze`.
    """

    profile_input: Optional[str] = Field(
        None,
        description="Username ou URL de perfil para recolha automática (Instagram).",
    )
    instagram_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Métricas manuais estruturadas para reforçar a análise.",
    )
    language: str = Field("pt-PT", min_length=2, description="Idioma da análise final.")
    platform: SocialMediaPlatform = Field(
        "instagram",
        description="Plataforma; análise unificada com Apify só para instagram.",
    )


class MarketingDirector:
    """Gestor de equipa de marketing que orquestra vários agentes numa conversa.

    O Diretor de Marketing é o front office: o utilizador fala apenas com ele.
    Internamente, planeia tarefas, delega aos especialistas (Copywriter, Designer,
    LinkedIn, Meta/redes, etc.) e agrega os resultados numa resposta unificada.
    """

    def __init__(self) -> None:
        """Inicializa o roteamento por palavras-chave para cada especialidade.

        Define um dicionário de agentes com palavras-chave associadas que
        permitem inferir rapidamente a área de marketing pretendida, e planos de
        ação por agente. A ordem de inserção no dicionário desempata empates na
        pontuação (ganha o primeiro agente listado com a pontuação máxima).

        Argumentos:
            Nenhum.

        Retorno:
            Nenhum.
        """

        self.routing_map: Dict[str, List[str]] = {
            "Agente LinkedIn (perfil)": [
                "linkedin supabase",
                "oauth linkedin",
                "login linkedin",
                "perfil linkedin",
                "perfis linkedin",
                "analise linkedin",
                "analisar perfil linkedin",
                "analisar perfis linkedin",
                "analise de perfil linkedin",
                "auditoria linkedin",
                "auditar perfil linkedin",
                "visao geral linkedin",
                "indicadores linkedin",
                "metricas linkedin",
                "publicacoes linkedin",
                "posts linkedin",
                "calendario linkedin",
                "empresa linkedin",
                "pagina empresa linkedin",
                "company linkedin",
                "linkedin.com/in/",
                "linkedin.com/company/",
                "ssi linkedin",
                "seguidores linkedin",
                "harvest linkedin",
                "scraper linkedin",
                "linkedin oidc",
                "sign in linkedin",
                "conectar linkedin",
                "ligar linkedin",
            ],
            "Agente Meta Ads": [
                "meta ads",
                "facebook ads",
                "anuncios facebook",
                "instagram ads",
                "anuncios instagram",
                "business manager",
                "campanha meta",
            ],
            "Agente Linkedin Ads": [
                "linkedin ads",
                "anuncios linkedin",
                "anuncio linkedin",
                "linkedin sponsorizado",
                "sponsored linkedin",
                "campanha linkedin",
                "campanhas linkedin",
                "lead gen linkedin",
                "linkedin b2b ads",
            ],
            "Agente Google Ads": [
                "google ads",
                "adwords",
                "performance max",
                "pmax",
                "pesquisa paga",
                "search ads",
                "youtube ads",
            ],
            "Agente GEO": [
                "geo",
                "generative engine",
                "visibilidade em ia",
                "chatgpt",
                "perplexity",
                "ai overview",
                "citacao em ia",
            ],
            "Agente Seo": [
                "seo",
                "palavra-chave",
                "palavras-chave",
                "keyword",
                "serp",
                "backlink",
                "organico",
                "trafego organico",
            ],
            "Agente Web Developer": [
                "web developer",
                "desenvolvimento web",
                "programador",
                "landing page tecnica",
                "wordpress",
                "frontend",
                "backend",
                "integracao api",
                "bug site",
                "performance web",
            ],
            "Agente Designer": [
                "designer",
                "imagem",
                "imagens",
                "image",
                "visual",
                "criativo visual",
                "arte",
                "ilustracao",
                "mockup",
                "design grafico",
                "figma",
                "criativo",
                "banner",
                "thumbnail",
                "identidade visual",
                "brand book",
                "layout",
            ],
            "Agente Redes sociais": [
                "redes sociais",
                "social media",
                "instagram",
                "reels",
                "tiktok",
                "stories",
                "calendario editorial",
                "community management",
            ],
            "Agente Copywriter": [
                "copywriter",
                "copy",
                "texto publicitario",
                "headline",
                "roteiro",
                "storytelling",
                "newsletter",
                "email marketing texto",
            ],
            "Agente Analista de Score": [
                "score",
                "scorecard",
                "pontuacao",
                "metricas",
                "kpi",
                "analytics",
                "dashboard",
                "relatorio",
                "benchmark",
            ],
        }
        self._agent_catalog = list(self.routing_map.keys())
        self._action_plans: Dict[str, List[str]] = {
            "Agente Copywriter": [
                "Alinhar proposta de valor, tom de voz e público-alvo num brief único.",
                "Produzir 3 variantes de copy (curta, média e longa) com CTAs distintos.",
                "Validar clareza e consistência com checklist de leitura e mensagem única.",
            ],
            "Agente Designer": [
                "Traduzir o brief em moodboard, grid e hierarquia visual.",
                "Entregar peças nos formatos pedidos (feed, stories, display, etc.).",
                "Preparar ficheiros finais e notas de handoff para implementação.",
            ],
            "Agente Redes sociais": [
                "Definir pilares de conteúdo e cadência por canal.",
                "Montar calendário editorial com formatos (Reels, carrossel, texto).",
                "Estabelecer rotina de resposta à comunidade e relatório semanal.",
            ],
            "Agente LinkedIn (perfil)": [
                "Configurar Supabase (LinkedIn OIDC) e redirect URLs permitidos.",
                "Iniciar sessão OAuth e confirmar estado da sessão no browser.",
                "Analisar URL pública do perfil e consolidar recomendações de IA.",
            ],
            "Agente Meta Ads": [
                "Definir objetivo de campanha, orçamento e estrutura de conjuntos.",
                "Configurar públicos, exclusões e eventos de conversão.",
                "Testar criativos e mensagens com plano de iteração quinzenal.",
            ],
            "Agente Linkedin Ads": [
                "Escolher formato (single image, documento, mensagem) e objetivo B2B.",
                "Segmentar por cargo, empresa, intenção e remarketing.",
                "Ajustar oferta e landing para lead quality e custo por lead.",
            ],
            "Agente Google Ads": [
                "Estruturar contas: campanhas, grupos de anúncios e palavras negativas.",
                "Alinhar pesquisa, Performance Max e remarketing ao funil.",
                "Monitorizar qualidade, CPA e volume com relatórios semanais.",
            ],
            "Agente Web Developer": [
                "Especificar stack, integrações e requisitos de performance (Core Web Vitals).",
                "Implementar landing ou alterações com ambiente de staging e revisão.",
                "Garantir tracking, formulários e eventos para marketing medir conversões.",
            ],
            "Agente Seo": [
                "Mapear intenção de pesquisa e clusters de conteúdo.",
                "Otimizar on-page (títulos, estrutura, schema quando aplicável).",
                "Planear autoridade técnica e links internos/externos.",
            ],
            "Agente GEO": [
                "Identificar perguntas e tópicos onde a marca deve ser citada por IAs.",
                "Estruturar conteúdo com fontes, dados e formato fácil de citar.",
                "Medir presença em motores generativos e ajustar páginas piloto.",
            ],
            "Agente Analista de Score": [
                "Definir fórmula de score, pesos e fontes de dados.",
                "Construir dashboard ou folha de cálculo com atualização acordada.",
                "Documentar interpretação do score e ações quando cair ou subir.",
            ],
        }
        self._ai_api_url = os.getenv("DIRECTOR_AI_API_URL", "").strip()
        self._ai_model = os.getenv("DIRECTOR_AI_MODEL", "gpt-4o-mini").strip()
        self._ai_api_key = os.getenv("DIRECTOR_AI_API_KEY", "").strip()
        self._openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self._allow_compatible_api = (
            os.getenv("DIRECTOR_ALLOW_COMPATIBLE_API", "false").strip().lower()
            in {"1", "true", "yes", "on"}
        )

    def route(self, user_input: str) -> AgentResult:
        """Seleciona e executa o agente posterior mais adequado ao pedido.

        A função analisa o texto do utilizador, calcula uma pontuação por agente
        com base em ocorrências de palavras-chave e, por fim, devolve o plano de
        ação do agente especializado vencedor.

        Argumentos:
            user_input: Texto em linguagem natural enviado pelo utilizador.

        Retorno:
            AgentResult com o nome do agente escolhido, plano de ação e
            justificação do encaminhamento.
        """

        ai_decision = self._route_with_ai(user_input)
        if ai_decision:
            selected_agent, rationale = ai_decision
            selected_agent = self._correct_agent_for_linkedin_intent(user_input, selected_agent)
            return self._build_agent_result(selected_agent, user_input, score=10, rationale=rationale)

        normalized = self._normalize_text(user_input)
        selected_agent, score = self._select_agent(normalized)
        if score == 0:
            selected_agent = "Agente Copywriter"
        return self._build_agent_result(selected_agent, user_input, score=score)

    def _normalize_text(self, text: str) -> str:
        """Normaliza texto para melhorar robustez do roteamento por fallback.

        A função transforma o texto em minúsculas, remove acentos e comprime
        espaços, para que termos como "anúncios", "anuncios" e "ANUNCIOS"
        sejam tratados da mesma forma durante a comparação com palavras-chave.

        Argumentos:
            text: Texto original do utilizador ou palavras-chave do sistema.

        Retorno:
            String normalizada, sem acentos e com espaços limpos, pronta para
            ser usada em operações de correspondência textual.
        """

        lowered = text.lower()
        no_accents = "".join(
            char for char in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(char)
        )
        return " ".join(no_accents.split())

    def _route_with_ai(self, user_input: str) -> Optional[Tuple[str, str]]:
        """Tenta roteamento autónomo com OpenAI como fonte principal.

        Esta função envia o pedido do utilizador para um modelo de linguagem e
        pede uma resposta estritamente em JSON, contendo o agente escolhido e a
        justificação. A decisão é validada contra o catálogo oficial de agentes
        para impedir nomes inválidos e manter consistência no sistema.

        Argumentos:
            user_input: Texto livre do utilizador com o pedido de marketing.

        Retorno:
            Tuplo `(agent_name, rationale)` quando a IA responde de forma válida;
            `None` quando o serviço não está disponível, devolve formato inválido
            ou escolhe um agente fora da lista permitida.
        """

        # Atualiza configuração em runtime para refletir alterações no ambiente.
        self._openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self._ai_api_url = os.getenv("DIRECTOR_AI_API_URL", "").strip()
        self._ai_model = os.getenv("DIRECTOR_AI_MODEL", "gpt-4o-mini").strip()
        self._ai_api_key = os.getenv("DIRECTOR_AI_API_KEY", "").strip()

        self._allow_compatible_api = (
            os.getenv("DIRECTOR_ALLOW_COMPATIBLE_API", "false").strip().lower()
            in {"1", "true", "yes", "on"}
        )

        # 1) OpenAI oficial é a fonte principal sempre que OPENAI_API_KEY existir.
        if self._openai_api_key:
            return self._route_with_openai(user_input)

        # 2) Endpoint compatível só é usado por opt-in explícito.
        if self._allow_compatible_api and self._ai_api_url:
            return self._route_with_compatible_api(user_input)

        return None

    def _route_with_openai(self, user_input: str) -> Optional[Tuple[str, str]]:
        """Encaminha com OpenAI oficial usando `OPENAI_API_KEY`.

        A função usa o SDK oficial para pedir ao modelo uma decisão em JSON com
        `agent_name` e `rationale`, valida o agente devolvido e retorna o
        encaminhamento apenas quando a decisão é segura e consistente.

        Argumentos:
            user_input: Pedido original do utilizador em linguagem natural.

        Retorno:
            Tuplo `(agent_name, rationale)` quando a resposta é válida;
            `None` quando há falha de API, parsing inválido ou agente não
            autorizado.
        """

        try:
            client = OpenAI(api_key=self._openai_api_key)
            response = client.chat.completions.create(
                model=self._ai_model,
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self._build_router_system_prompt()},
                    {"role": "user", "content": user_input},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            decision = json.loads(content)
            selected_agent = decision["agent_name"]
            rationale = decision.get("rationale", "Decisão tomada pela IA.")
        except Exception:  # noqa: BLE001 - fallback silencioso para regras locais
            return None

        if selected_agent not in self._agent_catalog:
            return None
        selected_agent = self._correct_agent_for_linkedin_intent(user_input, selected_agent)
        return selected_agent, str(rationale)

    def _linkedin_routing_guidance(self) -> str:
        """Texto de regras para desambiguar pedidos LinkedIn nos prompts do Diretor.

        Centraliza instruções sobre quando encaminhar para análise de perfil
        orgânico (`Agente LinkedIn (perfil)`) versus campanhas pagas
        (`Agente Linkedin Ads`) ou gestão de outras redes (`Agente Redes sociais`).

        Argumentos:
            Nenhum.

        Retorno:
            Bloco de texto em português para injetar em prompts de sistema.
        """

        return (
            "REGRAS LINKEDIN (obrigatório): "
            "Usa «Agente LinkedIn (perfil)» quando o pedido for analisar/auditar perfil pessoal "
            "ou página de empresa no LinkedIn, métricas orgânicas (seguidores, SSI, publicações), "
            "login OAuth Supabase, URL linkedin.com/in/ ou linkedin.com/company/, calendário de posts "
            "LinkedIn ou recomendações de IA sobre presença no perfil. "
            "Usa «Agente Linkedin Ads» apenas para campanhas pagas, sponsored content, lead gen B2B "
            "ou orçamento de anúncios no LinkedIn — não para análise de perfil orgânico. "
            "Usa «Agente Redes sociais» para Instagram, TikTok, Reels, stories e calendário editorial "
            "fora do LinkedIn; não uses para análise de perfil LinkedIn."
        )

    def _is_linkedin_ads_intent(self, normalized: str) -> bool:
        """Deteta pedidos de publicidade paga no LinkedIn.

        Argumentos:
            normalized: Texto do utilizador já normalizado (sem acentos, minúsculas).

        Retorno:
            `True` quando o pedido aponta para campanhas/ads LinkedIn, não perfil orgânico.
        """

        ads_markers = (
            "linkedin ads",
            "anuncios linkedin",
            "anuncio linkedin",
            "campanha linkedin",
            "campanhas linkedin",
            "sponsorizado",
            "sponsored linkedin",
            "lead gen linkedin",
            "linkedin b2b ads",
            "orcamento linkedin",
            "cpc linkedin",
            "cpl linkedin",
        )
        return any(marker in normalized for marker in ads_markers)

    def _is_linkedin_profile_intent(self, normalized: str) -> bool:
        """Deteta pedidos de análise, auditoria ou gestão de perfil LinkedIn orgânico.

        Argumentos:
            normalized: Texto do utilizador já normalizado.

        Retorno:
            `True` quando o pedido é sobre perfil, métricas orgânicas ou OAuth LinkedIn.
        """

        if self._is_linkedin_ads_intent(normalized):
            return False
        profile_markers = (
            "perfil linkedin",
            "perfis linkedin",
            "linkedin perfil",
            "analise linkedin",
            "analisar perfil",
            "analise de perfil",
            "auditoria linkedin",
            "auditar perfil",
            "visao geral linkedin",
            "indicadores linkedin",
            "metricas linkedin",
            "publicacoes linkedin",
            "posts linkedin",
            "calendario linkedin",
            "empresa linkedin",
            "pagina empresa linkedin",
            "company linkedin",
            "ssi linkedin",
            "seguidores linkedin",
            "oauth linkedin",
            "login linkedin",
            "linkedin supabase",
            "linkedin oidc",
            "sign in linkedin",
            "conectar linkedin",
            "ligar linkedin",
            "linkedin.com/in/",
            "linkedin.com/company/",
        )
        if any(marker in normalized for marker in profile_markers):
            return True
        if "linkedin" in normalized and any(
            word in normalized
            for word in (
                "perfil",
                "perfis",
                "analis",
                "auditor",
                "metric",
                "indicad",
                "seguidor",
                "publicac",
                "post",
                "calend",
                "ssi",
                "empresa",
                "company",
                "oauth",
                "login",
                "supabase",
            )
        ):
            return True
        return False

    def _resolve_linkedin_routing(self, normalized: str) -> Optional[Tuple[str, int]]:
        """Desambigua pedidos LinkedIn antes do scoring genérico por keywords.

        Argumentos:
            normalized: Texto do utilizador normalizado.

        Retorno:
            Tuplo `(agent_name, score)` quando a intenção LinkedIn é clara;
            `None` quando não há sinal suficiente de perfil ou ads LinkedIn.
        """

        if self._is_linkedin_ads_intent(normalized):
            return "Agente Linkedin Ads", 5
        if self._is_linkedin_profile_intent(normalized):
            return "Agente LinkedIn (perfil)", 5
        return None

    def _correct_agent_for_linkedin_intent(self, user_input: str, selected_agent: str) -> str:
        """Corrige escolhas da IA que confundem perfil LinkedIn com ads ou redes sociais.

        Argumentos:
            user_input: Pedido original do utilizador.
            selected_agent: Agente devolvido pelo roteador (IA ou keywords).

        Retorno:
            Nome do agente corrigido quando o pedido é claramente de perfil LinkedIn.
        """

        normalized = self._normalize_text(user_input)
        if not self._is_linkedin_profile_intent(normalized):
            return selected_agent
        if self._is_linkedin_ads_intent(normalized):
            return selected_agent
        wrong_agents = {
            "Agente Linkedin Ads",
            "Agente Redes sociais",
            "Agente Copywriter",
            "Agente Analista de Score",
        }
        if selected_agent in wrong_agents:
            return "Agente LinkedIn (perfil)"
        return selected_agent

    def generate_chat_reply(
        self,
        messages: List[Dict[str, str]],
        language: str = "pt-PT",
        workflow_state: Optional[Dict[str, Any]] = None,
        user_action: Optional[str] = None,
        action_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, object]:
        """Orquestra copy, aprovações e imagem na chatroom do Diretor.

        Argumentos:
            messages: Histórico da conversa.
            language: Idioma da resposta.
            workflow_state: Estado do fluxo no frontend.
            user_action: Acção de botão (approve_copy, generate_image, …).
            action_payload: Dados de edição ou regeneração.

        Retorno:
            Payload com `reply`, `workflow_state`, `deliverables`, etc.

        Raises:
            RuntimeError: Se `OPENAI_API_KEY` não estiver configurada.
        """

        return self.orchestrate_chat(
            messages=messages,
            language=language,
            workflow_state=workflow_state,
            user_action=user_action,
            action_payload=action_payload,
        )

    def orchestrate_chat(
        self,
        messages: List[Dict[str, str]],
        language: str = "pt-PT",
        workflow_state: Optional[Dict[str, Any]] = None,
        user_action: Optional[str] = None,
        action_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, object]:
        """Coordena copy, aprovações e imagem na interface do Diretor.

        Argumentos:
            messages: Histórico da chatroom do Diretor.
            language: Idioma preferido do utilizador.
            workflow_state: Estado do fluxo (frontend).
            user_action: Acção de botão ou inferida do texto.
            action_payload: Dados de edição ou regeneração de imagem.

        Retorno:
            Payload com `reply`, `workflow_state`, `deliverables`, `pending_actions`.

        Raises:
            RuntimeError: Quando falta `OPENAI_API_KEY`.
        """

        self._openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not self._openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY nao configurada no servidor. Define a variavel de ambiente para usar a chatroom do Diretor."
            )

        model = (
            os.getenv("DIRECTOR_AI_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
            or "gpt-4o-mini"
        )
        return process_director_turn(
            messages=messages,
            language=language,
            workflow_state=workflow_state,
            user_action=user_action,
            action_payload=action_payload,
            openai_api_key=self._openai_api_key,
            openai_model=model,
            agent_catalog=self._agent_catalog,
            routing_map=self.routing_map,
            action_plans=self._action_plans,
            linkedin_guidance=self._linkedin_routing_guidance(),
            normalize_text=self._normalize_text,
            resolve_linkedin=self._resolve_linkedin_routing,
            correct_linkedin_agent=self._correct_agent_for_linkedin_intent,
            agent_page_url=_agent_page_url,
        )

    def _reply_looks_like_executable_marketing_copy(self, reply: str) -> bool:
        """Deteta se o Diretor devolveu texto executável em vez de triagem.

        O Diretor não deve produzir posts, hashtags ou blocos longos de copy.
        Esta função usa heurísticas simples para detetar quando o modelo falhou
        essa regra e é preciso corrigir o encaminhamento.

        Argumentos:
            reply: Texto devolvido pelo modelo no campo `reply` do JSON.

        Retorno:
            `True` quando a resposta parece copy/marketing pronto a publicar;
            `False` caso contrário.
        """

        if not reply:
            return False
        if "#" in reply:
            return True
        if len(reply) > 380:
            return True
        if reply.count("\n") >= 5 and len(reply) > 180:
            return True
        lowered = reply.lower()
        markers = (
            "cta",
            "call to action",
            "headline",
            "hashtag",
            "descobre",
            "não percas",
            "clique aqui",
            "clica aqui",
        )
        return any(marker in lowered for marker in markers)

    def _infer_route_from_last_user_message(
        self, sanitized_messages: List[Dict[str, str]]
    ) -> Optional[Dict[str, object]]:
        """Infere encaminhamento imediato a partir da última mensagem do utilizador.

        Quando o pedido é inequívoco (ex.: texto para publicação), o Diretor não
        deve pedir briefing de copy aqui: deve encaminhar logo para o agente
        certo. Usa primeiro o mapa de keywords do Diretor; se não houver match
        mas o pedido for claramente de escrita, sugere o Agente Copywriter.

        Argumentos:
            sanitized_messages: Histórico da chatroom já filtrado por role/conteúdo.

        Retorno:
            Dicionário com `reply`, `ready_to_route` e `agent_name` quando a
            intenção for clara; `None` quando deve prevalecer a resposta do LLM.
        """

        last_user = next((m for m in reversed(sanitized_messages) if m.get("role") == "user"), None)
        if not last_user:
            return None
        raw = str(last_user.get("content", "")).strip()
        if len(raw) > 500:
            return None

        normalized = self._normalize_text(raw)
        linkedin_route = self._resolve_linkedin_routing(normalized)
        if linkedin_route is not None:
            linkedin_agent, _ = linkedin_route
            return {
                "reply": (
                    f"Para análise e gestão de perfil LinkedIn, o especialista certo é o {linkedin_agent}. "
                    "Clica em «Encaminhar para o agente» para continuares na página dedicada."
                ),
                "ready_to_route": True,
                "agent_name": linkedin_agent,
            }

        keyword_agent, score = self._select_agent(normalized)
        if score >= 1:
            return {
                "reply": (
                    f"Para este pedido, o especialista mais adequado é o {keyword_agent}. "
                    "Clica em «Encaminhar para o agente» para continuares com ele."
                ),
                "ready_to_route": True,
                "agent_name": keyword_agent,
            }

        # Uma só palavra (ex.: "texto") = pedido de copy; encaminhar já, sem perguntas ao LLM.
        copy_single_words = frozenset(
            {
                "texto",
                "copy",
                "legenda",
                "roteiro",
                "headline",
                "headlines",
                "slogan",
                "publicacao",
                "newsletter",
                "caption",
                "post",
                "anuncio",
            }
        )
        tokens = [t for t in normalized.split() if t]
        if len(tokens) == 1 and tokens[0] in copy_single_words:
            return {
                "reply": (
                    "Para criar ou melhorar esse conteúdo escrito, o passo seguinte é o Agente Copywriter. "
                    "Clica em «Encaminhar para o agente» para continuares na página dele."
                ),
                "ready_to_route": True,
                "agent_name": "Agente Copywriter",
            }

        copy_markers = (
            "texto para",
            "texto pra",
            "quero texto",
            "quero um texto",
            "preciso de texto",
            "preciso texto",
            "legenda para",
            "legenda do",
            "copy para",
            "roteiro para",
            "texto para uma publicacao",
            "texto para uma publicação",
            "texto para publicacao",
            "texto para publicação",
            "para uma publicacao",
            "para uma publicação",
            "texto de publicacao",
            "texto de publicação",
        )
        if any(marker in normalized for marker in copy_markers):
            return {
                "reply": (
                    "Para escrever o texto da publicação, encaminho-te para o Agente Copywriter — "
                    "lá afinas tema, público e tom na chatroom dele. Clica em «Encaminhar para o agente»."
                ),
                "ready_to_route": True,
                "agent_name": "Agente Copywriter",
            }

        if "texto" in normalized and (
            "publicacao" in normalized
            or "public" in normalized
            or "post" in normalized
            or "legenda" in normalized
        ):
            return {
                "reply": (
                    "Isto é trabalho do Agente Copywriter. Clica em «Encaminhar para o agente» "
                    "para ele gerar o texto na página dedicada."
                ),
                "ready_to_route": True,
                "agent_name": "Agente Copywriter",
            }

        return None

    def _coerce_director_chat_decision(
        self,
        reply: str,
        ready_to_route: bool,
        agent_name: Optional[str],
        sanitized_messages: List[Dict[str, str]],
    ) -> Dict[str, object]:
        """Garante que o Diretor não executa trabalho dos agentes nem fica sem encaminhamento válido.

        Se o modelo tiver escrito copy longa ou com hashtags, força encaminhamento
        para o Agente Copywriter com uma resposta curta de triagem. Se já estiver
        `ready_to_route` mas o `reply` violar o limite de tamanho, substitui por
        uma mensagem de encaminhamento neutra.

        Argumentos:
            reply: Texto atual do campo `reply`.
            ready_to_route: Estado de encaminhamento devolvido pelo modelo.
            agent_name: Agente escolhido pelo modelo, se existir.
            sanitized_messages: Histórico da conversa para inferência de intenção.

        Retorno:
            Dicionário com `reply`, `ready_to_route` e `agent_name` corrigidos.
        """

        copywriter = "Agente Copywriter"

        if self._reply_looks_like_executable_marketing_copy(reply):
            return {
                "reply": (
                    "Aqui no Diretor não escrevo o texto final do post — isso fica a cargo do "
                    f"{copywriter}. Clica em «Encaminhar para o agente» para continuar lá com o mesmo pedido."
                ),
                "ready_to_route": True,
                "agent_name": copywriter,
            }

        if ready_to_route and agent_name and len(reply) > 450:
            return {
                "reply": (
                    f"Recomendo o {agent_name} para executar este pedido. "
                    "Clica em «Encaminhar para o agente» para abrir a página desse especialista."
                ),
                "ready_to_route": True,
                "agent_name": agent_name,
            }

        return {
            "reply": reply,
            "ready_to_route": ready_to_route,
            "agent_name": agent_name,
        }

    def _route_with_compatible_api(self, user_input: str) -> Optional[Tuple[str, str]]:
        """Encaminha com endpoint compatível OpenAI definido por URL.

        Esta função usa HTTP direto para compatibilidade com serviços locais
        (por exemplo Ollama) e espera resposta JSON equivalente ao formato
        `chat.completions`.

        Argumentos:
            user_input: Pedido original do utilizador em linguagem natural.

        Retorno:
            Tuplo `(agent_name, rationale)` quando a resposta é válida;
            `None` quando o endpoint falha, responde fora do formato ou devolve
            agente não permitido.
        """

        payload = {
            "model": self._ai_model,
            "messages": [
                {"role": "system", "content": self._build_router_system_prompt()},
                {"role": "user", "content": user_input},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if self._ai_api_key:
            headers["Authorization"] = f"Bearer {self._ai_api_key}"

        http_request = request.Request(
            self._ai_api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=10) as response:
                body = response.read().decode("utf-8")
        except (error.URLError, error.HTTPError, TimeoutError, OSError):
            return None

        try:
            outer = json.loads(body)
            content = outer["choices"][0]["message"]["content"]
            decision = json.loads(content)
            selected_agent = decision["agent_name"]
            rationale = decision.get("rationale", "Decisão tomada pela IA.")
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return None

        if selected_agent not in self._agent_catalog:
            return None
        selected_agent = self._correct_agent_for_linkedin_intent(user_input, selected_agent)
        return selected_agent, str(rationale)

    def _build_router_system_prompt(self) -> str:
        """Constrói o prompt de sistema para o roteador autónomo de IA.

        O prompt define as regras do “Diretor de Marketing”, lista os agentes
        autorizados e obriga a IA a responder em JSON válido com os campos
        `agent_name` e `rationale`, sem texto adicional fora do objeto.

        Argumentos:
            Nenhum.

        Retorno:
            String com instruções completas para guiar a decisão de roteamento.
        """

        allowed_agents = ", ".join(self._agent_catalog)
        return (
            "És um Diretor de Marketing AI que escolhe exatamente um agente especializado. "
            f"Agentes permitidos: {allowed_agents}. "
            f"{self._linkedin_routing_guidance()} "
            "Responde apenas com JSON válido no formato: "
            '{"agent_name":"<um dos agentes permitidos>","rationale":"<explicação curta>"}'
        )

    def _select_agent(self, normalized_input: str) -> Tuple[str, int]:
        """Calcula qual o agente com maior correspondência textual.

        A função percorre todas as especialidades definidas no mapa de
        roteamento e soma ocorrências de palavras-chave para encontrar o melhor
        encaminhamento automático.

        Argumentos:
            normalized_input: Input do utilizador em minúsculas para facilitar
                comparações.

        Retorno:
            Tuplo `(nome_do_agente, pontuacao)` com o agente escolhido e o nível
            de confiança simples baseado na contagem de palavras-chave.
        """

        linkedin_route = self._resolve_linkedin_routing(normalized_input)
        if linkedin_route is not None:
            return linkedin_route

        first_agent = next(iter(self.routing_map))
        best_agent = first_agent
        best_score = -1
        for agent, keywords in self.routing_map.items():
            score = sum(1 for keyword in keywords if self._normalize_text(keyword) in normalized_input)
            if score > best_score:
                best_agent = agent
                best_score = score
        return best_agent, max(best_score, 0)

    def _build_agent_result(
        self, agent_name: str, user_input: str, score: int, rationale: Optional[str] = None
    ) -> AgentResult:
        """Monta a resposta final do agente escolhido com plano e justificação.

        Combina o nome canónico do agente com o respetivo plano de ação
        pré-definido e uma justificação que inclui a confiança do roteamento e
        o pedido original para auditoria.

        Argumentos:
            agent_name: Nome exato do agente conforme `self.routing_map`.
            user_input: Instrução original do utilizador.
            score: Pontuação de confiança do `_select_agent` (número de hits).
            rationale: Justificação opcional vinda do roteamento por IA.

        Retorno:
            AgentResult pronto para serialização na API `/chat`.
        """

        plan = self._action_plans[agent_name]
        if rationale:
            justification = (
                f"Encaminhado autonomamente para {agent_name} pelo Diretor AI. "
                f"Motivo: {rationale}. Pedido: {user_input}"
            )
            return AgentResult(
                agent_name=agent_name,
                action_plan=list(plan),
                justification=justification,
            )

        if score == 0 and agent_name == "Agente Copywriter":
            justification = (
                "Sem palavras-chave especificas detetadas: encaminhamento por defeito "
                f"para {agent_name} como especialista em mensagem. Pedido: {user_input}"
            )
        else:
            justification = (
                f"Encaminhado para {agent_name} com base na analise do pedido "
                f"(confianca: {score}). Pedido: {user_input}"
            )
        return AgentResult(
            agent_name=agent_name,
            action_plan=list(plan),
            justification=justification,
        )


director = MarketingDirector()


@app.head("/")
def home_head() -> HTMLResponse:
    """Responde ao health check HEAD do Render (evita 405 na raiz)."""

    return HTMLResponse(content="", status_code=200)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    """Renderiza interface web simples para conversar por instrução.

    A função devolve uma página HTML com identidade visual profissional,
    avatar do Diretor servido em `/static/diretor-avatar.png`, campo de texto
    e botão “Enviar”, permitindo ao utilizador interagir com o colaborador
    virtual sem precisar de ferramentas externas. Inclui login LinkedIn
    (Supabase OIDC) e análise de perfil no próprio painel do Diretor.

    Argumentos:
        Nenhum.

    Retorno:
        String HTML completa da interface de chat.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    html = """
    <!doctype html>
    <html lang="pt">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Diretor de Marketing AI</title>
        <style>
          :root {
            --bg: #0f1419;
            --surface: #1a2332;
            --surface-elevated: #222d3f;
            --border: rgba(255, 255, 255, 0.08);
            --text: #f0f4f8;
            --text-muted: #94a3b8;
            --user: #2563eb;
            --assistant: #0f766e;
          }
          * { box-sizing: border-box; }
          body {
            margin: 0;
            min-height: 100vh;
            font-family: "Segoe UI", system-ui, sans-serif;
            background: radial-gradient(ellipse 120% 80% at 50% -20%, #1e3a5f 0%, var(--bg) 55%);
            color: var(--text);
            padding: 24px 16px 40px;
          }
          .shell { max-width: 980px; margin: 0 auto; }
          .panel {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 18px;
            box-shadow: 0 20px 40px -24px rgba(0, 0, 0, 0.55);
          }
          .top { display: flex; gap: 14px; align-items: center; margin-bottom: 10px; }
          .avatar {
            width: 72px;
            height: 72px;
            border-radius: 50%;
            overflow: hidden;
            border: 2px solid rgba(255, 255, 255, 0.14);
            background: #fff;
          }
          .avatar img { width: 100%; height: 100%; object-fit: cover; }
          .title { margin: 0; font-size: 1.45rem; }
          .subtitle { margin: 4px 0 0; color: var(--text-muted); font-size: 0.92rem; }
          .chat-log {
            margin-top: 14px;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: #152034;
            padding: 14px;
            min-height: 330px;
            max-height: 450px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 10px;
          }
          .msg {
            max-width: 84%;
            padding: 10px 12px;
            border-radius: 10px;
            line-height: 1.45;
            font-size: 0.94rem;
            white-space: pre-wrap;
          }
          .msg.user { align-self: flex-end; background: var(--user); }
          .msg.assistant { align-self: flex-start; background: var(--assistant); }
          .msg.typing {
            align-self: flex-start;
            background: var(--assistant);
            display: inline-flex;
            align-items: center;
            gap: 5px;
            min-width: 54px;
          }
          .typing-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.92);
            animation: typingBounce 1.1s infinite ease-in-out;
          }
          .typing-dot:nth-child(2) { animation-delay: 0.15s; }
          .typing-dot:nth-child(3) { animation-delay: 0.3s; }
          @keyframes typingBounce {
            0%, 80%, 100% { transform: translateY(0); opacity: 0.55; }
            40% { transform: translateY(-4px); opacity: 1; }
          }
          .controls {
            margin-top: 12px;
            display: grid;
            grid-template-columns: 1fr 120px;
            gap: 10px;
          }
          textarea, input {
            width: 100%;
            border: 1px solid var(--border);
            border-radius: 10px;
            background: var(--surface-elevated);
            color: var(--text);
            padding: 11px 12px;
            font-family: inherit;
            box-sizing: border-box;
          }
          textarea { min-height: 58px; resize: vertical; }
          .actions { margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap; }
          button {
            border: none;
            border-radius: 9px;
            padding: 10px 14px;
            color: #fff;
            font-weight: 600;
            cursor: pointer;
          }
          .send-btn { background: linear-gradient(180deg, #3b82f6, #2563eb); }
          .reset-btn { background: linear-gradient(180deg, #64748b, #475569); }
          .hint { margin-top: 8px; color: var(--text-muted); font-size: 0.82rem; }
          .result {
            margin-top: 14px;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: var(--surface-elevated);
            padding: 14px;
          }
          .result h3 { margin: 0 0 10px; color: #93c5fd; }
          .result p { margin: 0 0 10px; color: #cbd5e1; }
          .result ol { margin: 0; padding-left: 1.2rem; }
          .result a { color: #93c5fd; text-decoration: none; font-weight: 600; }
          .team-panel { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; }
          .team-card {
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 12px;
            background: #111b2e;
          }
          .team-card h4 { margin: 0 0 6px; font-size: 0.92rem; color: #93c5fd; }
          .team-card .status {
            display: inline-block;
            font-size: 0.72rem;
            padding: 2px 8px;
            border-radius: 999px;
            margin-bottom: 8px;
            background: rgba(16, 185, 129, 0.2);
            color: #6ee7b7;
          }
          .team-card .status.error { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
          .team-card .status.skipped { background: rgba(148, 163, 184, 0.2); color: #cbd5e1; }
          .team-card pre {
            margin: 0 0 8px;
            white-space: pre-wrap;
            font-family: inherit;
            font-size: 0.85rem;
            color: #cbd5e1;
            line-height: 1.4;
          }
          .team-card a {
            color: #93c5fd;
            font-size: 0.82rem;
            font-weight: 600;
            text-decoration: none;
          }
          .plan-line { color: #a5b4fc; font-size: 0.88rem; margin: 0 0 10px; }
          .forward-btn {
            margin-top: 8px;
            display: inline-block;
            padding: 8px 12px;
            border-radius: 8px;
            border: none;
            font-weight: 600;
            font-size: 0.82rem;
            cursor: pointer;
            color: #fff;
            background: linear-gradient(180deg, #10b981, #059669);
            text-decoration: none;
          }
          .forward-btn:hover { filter: brightness(1.06); }
          .workflow-panel { margin-top: 12px; display: flex; flex-direction: column; gap: 12px; }
          .workflow-post {
            width: 100%;
            min-height: 140px;
            border: 1px solid var(--border);
            border-radius: 10px;
            background: #0f172a;
            color: var(--text);
            padding: 10px;
            font-family: inherit;
            font-size: 0.9rem;
            line-height: 1.45;
            resize: vertical;
          }
          .workflow-image {
            max-width: 100%;
            border-radius: 10px;
            border: 1px solid var(--border);
            margin-top: 8px;
          }
          .workflow-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
          .wf-btn {
            border: none;
            border-radius: 8px;
            padding: 9px 12px;
            font-weight: 600;
            font-size: 0.82rem;
            cursor: pointer;
            color: #fff;
          }
          .wf-btn-approve { background: linear-gradient(180deg, #10b981, #059669); }
          .wf-btn-strategy { background: linear-gradient(180deg, #0ea5e9, #0369a1); }
          .wf-btn-image { background: linear-gradient(180deg, #8b5cf6, #6d28d9); }
          .wf-btn-secondary { background: linear-gradient(180deg, #64748b, #475569); }
          .strategy-panel {
            margin-top: 12px;
            padding: 14px;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: rgba(15, 23, 42, 0.6);
          }
          .strategy-panel h4 { margin: 0 0 10px; color: #e2e8f0; font-size: 0.95rem; }
          .strategy-section { margin-bottom: 14px; }
          .strategy-section h5 {
            margin: 0 0 6px;
            color: #93c5fd;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
          }
          .strategy-list { margin: 0; padding-left: 18px; color: #cbd5e1; font-size: 0.86rem; line-height: 1.45; }
          .pillar-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
            font-size: 0.84rem;
            color: #e2e8f0;
          }
          .pillar-bar-wrap {
            flex: 1;
            height: 8px;
            background: #1e293b;
            border-radius: 999px;
            overflow: hidden;
          }
          .pillar-bar {
            height: 100%;
            background: linear-gradient(90deg, #0ea5e9, #6366f1);
            border-radius: 999px;
          }
          .pillar-pct { min-width: 38px; text-align: right; color: #94a3b8; font-size: 0.8rem; }
          .linkedin-auth-bar {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            margin: 12px 0 4px;
            padding: 12px 14px;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: rgba(15, 23, 42, 0.55);
          }
          .director-linkedin-hidden { display: none !important; }
          .linkedin-auth-status { display: flex; align-items: center; gap: 8px; font-size: 0.86rem; color: #cbd5e1; }
          .auth-dot {
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: #64748b;
          }
          .auth-dot.connected { background: #10b981; box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.25); }
          .linkedin-auth-actions { display: flex; flex-wrap: wrap; gap: 8px; }
          .li-btn {
            border: none;
            border-radius: 8px;
            padding: 8px 12px;
            font-weight: 600;
            font-size: 0.8rem;
            cursor: pointer;
            color: #fff;
          }
          .li-btn:disabled { opacity: 0.45; cursor: not-allowed; }
          .li-btn-login { background: linear-gradient(180deg, #0a66c2, #004182); }
          .li-btn-analyze { background: linear-gradient(180deg, #10b981, #059669); }
          .li-btn-logout { background: linear-gradient(180deg, #64748b, #475569); }
          .li-btn-optimize { background: linear-gradient(180deg, #a855f7, #7c3aed); }
          .linkedin-profile-hint { margin: 0 0 8px; font-size: 0.8rem; color: #94a3b8; min-height: 1.2em; }
          .optimization-panel {
            margin-top: 12px;
            padding: 14px;
            border: 1px solid rgba(168, 85, 247, 0.35);
            border-radius: 12px;
            background: rgba(49, 46, 129, 0.25);
          }
          .optimization-panel h4 { margin: 0 0 8px; color: #e9d5ff; }
          .opt-status-badge {
            display: inline-block;
            font-size: 0.72rem;
            padding: 4px 10px;
            border-radius: 999px;
            margin-bottom: 10px;
            background: rgba(148, 163, 184, 0.25);
            color: #e2e8f0;
          }
          .opt-status-badge.on_track { background: rgba(16, 185, 129, 0.25); color: #6ee7b7; }
          .opt-status-badge.ahead { background: rgba(14, 165, 233, 0.25); color: #7dd3fc; }
          .opt-status-badge.behind, .opt-status-badge.critical { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
          .opt-table { width: 100%; font-size: 0.82rem; border-collapse: collapse; margin: 10px 0; }
          .opt-table th, .opt-table td { text-align: left; padding: 6px 4px; border-bottom: 1px solid rgba(255,255,255,0.06); color: #cbd5e1; }
          .opt-table th { color: #94a3b8; font-weight: 600; }
          .opt-priority-alta { color: #fca5a5; }
          .opt-priority-media { color: #fcd34d; }
          .calendar-panel {
            margin-top: 12px;
            padding: 14px;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: rgba(30, 41, 59, 0.55);
          }
          .calendar-panel h4 { margin: 0 0 10px; color: #e2e8f0; }
          .cal-row {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 10px;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.06);
          }
          .cal-row:last-child { border-bottom: none; }
          .cal-row.is-ready { opacity: 0.72; }
          .cal-row.is-active { background: rgba(14, 165, 233, 0.08); border-radius: 8px; padding: 10px; }
          .cal-meta { font-size: 0.82rem; color: #94a3b8; }
          .cal-title { font-size: 0.9rem; color: #e2e8f0; font-weight: 600; margin-top: 4px; }
          .cal-status {
            font-size: 0.72rem;
            padding: 3px 8px;
            border-radius: 999px;
            background: rgba(148, 163, 184, 0.2);
            color: #cbd5e1;
            white-space: nowrap;
          }
          .cal-status.ready { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
          .cal-status.published { background: rgba(14, 165, 233, 0.25); color: #7dd3fc; }
          .publish-panel {
            margin-top: 12px;
            padding: 14px;
            border: 1px solid rgba(14, 165, 233, 0.35);
            border-radius: 12px;
            background: rgba(15, 23, 42, 0.65);
          }
          .publish-panel h4 { margin: 0 0 8px; color: #7dd3fc; }
          .publish-auth-ok { font-size: 0.78rem; color: #6ee7b7; }
          .engagement-panel {
            margin-top: 12px;
            padding: 14px;
            border: 1px solid rgba(251, 191, 36, 0.35);
            border-radius: 12px;
            background: rgba(69, 26, 3, 0.2);
          }
          .engagement-panel h4 { margin: 0 0 8px; color: #fcd34d; }
          .engagement-comment {
            width: 100%;
            min-height: 100px;
            margin: 8px 0;
            padding: 10px;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: rgba(15, 23, 42, 0.8);
            color: #e2e8f0;
            font-family: inherit;
            font-size: 0.88rem;
            resize: vertical;
          }
          .profile-panel {
            margin-top: 12px;
            padding: 12px 14px;
            border: 1px solid var(--border);
            border-radius: 10px;
            background: rgba(16, 185, 129, 0.08);
          }
          .profile-panel h5 { margin: 0 0 6px; color: #6ee7b7; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; }
          .director-collapse {
            margin-top: 12px;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: rgba(15, 23, 42, 0.6);
            overflow: hidden;
          }
          .director-collapse-summary {
            margin: 0;
            padding: 12px 14px;
            cursor: pointer;
            list-style: none;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            font-size: 0.95rem;
            font-weight: 600;
            color: #e2e8f0;
            user-select: none;
          }
          .director-collapse-summary::-webkit-details-marker { display: none; }
          .director-collapse-summary::after {
            content: "▾";
            font-size: 0.95rem;
            color: #94a3b8;
            transition: transform 0.2s ease;
            flex-shrink: 0;
          }
          .director-collapse:not([open]) .director-collapse-summary::after {
            transform: rotate(-90deg);
          }
          .director-collapse-body {
            padding: 0 14px 14px;
            border-top: 1px solid rgba(255, 255, 255, 0.06);
          }
          .director-collapse--profile {
            background: rgba(16, 185, 129, 0.08);
            border-color: rgba(16, 185, 129, 0.25);
          }
          .director-collapse--profile .director-collapse-summary {
            color: #6ee7b7;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
          }
          .director-collapse--strategy .director-collapse-summary { color: #e2e8f0; }
          .director-collapse--calendar .director-collapse-summary { color: #e2e8f0; }
          .director-collapse--optimization {
            background: rgba(88, 28, 135, 0.15);
            border-color: rgba(168, 85, 247, 0.35);
          }
          .director-collapse--optimization .director-collapse-summary { color: #e9d5ff; }
          .director-collapse--publish {
            border-color: rgba(14, 165, 233, 0.35);
            background: rgba(15, 23, 42, 0.65);
          }
          .director-collapse--publish .director-collapse-summary { color: #7dd3fc; }
          .director-collapse--followed {
            border-color: rgba(251, 191, 36, 0.35);
            background: rgba(69, 26, 3, 0.15);
          }
          .director-collapse--followed .director-collapse-summary { color: #fcd34d; }
          .director-collapse--engagement {
            border-color: rgba(251, 191, 36, 0.35);
            background: rgba(69, 26, 3, 0.2);
          }
          .director-collapse--engagement .director-collapse-summary { color: #fcd34d; }
          .director-collapse--digest {
            border-top-color: rgba(56, 189, 248, 0.45);
          }
          .director-collapse--digest .director-collapse-summary { color: #7dd3fc; }
          .digest-worked { color: #6ee7b7; }
          .digest-under { color: #fca5a5; }
          .digest-post-row {
            margin: 6px 0;
            padding: 8px 10px;
            border-radius: 8px;
            background: rgba(15, 23, 42, 0.45);
            font-size: 0.82rem;
          }
          .digest-post-row strong { color: #e2e8f0; }
          .timing-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.8rem;
            margin-top: 6px;
          }
          .timing-table th, .timing-table td {
            padding: 6px 8px;
            text-align: left;
            border-bottom: 1px solid rgba(148, 163, 184, 0.2);
          }
          .timing-table th { color: #94a3b8; font-weight: 600; }
          .timing-table tr:first-child td { color: #6ee7b7; font-weight: 600; }
          .stage-hint {
            margin: 0 0 12px;
            color: #94a3b8;
            font-size: 0.86rem;
            line-height: 1.4;
          }
          .post-meta {
            margin: 0 0 8px;
            color: #93c5fd;
            font-size: 0.82rem;
            line-height: 1.35;
          }
          footer { margin-top: 18px; text-align: center; color: #64748b; font-size: 0.75rem; }
          @media (max-width: 700px) { .controls { grid-template-columns: 1fr; } .msg { max-width: 94%; } }
        </style>
      </head>
      <body>
        <div class="shell">
          <section class="panel">
            <div class="top">
              <div class="avatar">
                <img src="/static/diretor-avatar.png" alt="Avatar do Diretor de Marketing" />
              </div>
              <div>
                <h1 class="title">Diretor de Marketing · Chatroom</h1>
                <p class="subtitle">Falas só comigo — eu coordeno copy, design e canais conforme o que pedires.</p>
              </div>
            </div>

            <div id="linkedinAuthBar" class="linkedin-auth-bar director-linkedin-hidden">
              <div class="linkedin-auth-status">
                <span id="linkedinAuthDot" class="auth-dot"></span>
                <span id="linkedinAuthLabel">LinkedIn: não ligado</span>
              </div>
              <div class="linkedin-auth-actions">
                <button type="button" class="li-btn li-btn-login" id="btnDirectorLinkedinLogin" onclick="startDirectorLinkedinLogin()">Ligar LinkedIn</button>
                <button type="button" class="li-btn li-btn-analyze" id="btnDirectorAnalyze" onclick="runDirectorLinkedinAnalysis()" disabled>Analisar perfil</button>
                <button type="button" class="li-btn li-btn-optimize" id="btnDirectorOptimize" onclick="runDirectorReanalyzeAndOptimize()" disabled style="display:none">Reanalisar e otimizar</button>
                <button type="button" class="li-btn li-btn-logout" id="btnDirectorLinkedinLogout" onclick="endDirectorLinkedinSession()" style="display:none">Terminar sessão</button>
              </div>
            </div>
            <p id="linkedinProfileHint" class="linkedin-profile-hint director-linkedin-hidden"></p>

            <div id="chatLog" class="chat-log"></div>
            <div class="controls">
              <textarea id="chatInput" placeholder="Escreve o que pretendes fazer no marketing do teu negócio..."></textarea>
              <input id="languageInput" value="pt-PT" placeholder="Idioma" />
            </div>
            <div class="actions">
              <button type="button" class="send-btn" onclick="sendMessage()">Enviar</button>
              <button type="button" class="reset-btn" onclick="resetChat()">Limpar conversa</button>
            </div>
            <p class="hint">Descreve o que queres (copy, imagem, campanha, site, LinkedIn…). Eu trato com a equipa e trago o resultado.</p>
            <div id="result" class="result"></div>
          </section>
          <footer>PlataformaV1 · Diretor de Marketing AI</footer>
        </div>
        <script>
          const SUPABASE_PUBLIC_URL = ___SUPABASE_URL_JSON___;
          const SUPABASE_ANON_KEY = ___SUPABASE_ANON_JSON___;
          const DIRECTOR_LINKEDIN_PROFILE_KEY = "plataforma_director_linkedin_profile_url";

          const chatLog = document.getElementById("chatLog");
          const chatInput = document.getElementById("chatInput");
          const languageInput = document.getElementById("languageInput");
          const result = document.getElementById("result");
          const messages = [];
          let workflowState = null;
          let directorSupabaseClient = null;
          let directorLinkedinSession = null;
          const WORKFLOW_STORAGE_KEY = "plataforma_director_workflow";
          const DIRECTOR_WELCOME = (
            "Olá! Sou o teu Diretor de Marketing. Diz-me o que queres fazer — "
            + "copy, imagem, campanha, site ou outro canal — e eu coordeno a equipa por ti."
          );

          function setDirectorLinkedinBarVisible(visible) {
            const bar = document.getElementById("linkedinAuthBar");
            const hint = document.getElementById("linkedinProfileHint");
            if (bar) bar.classList.toggle("director-linkedin-hidden", !visible);
            if (hint) hint.classList.toggle("director-linkedin-hidden", !visible);
          }

          function normalizePersistedWorkflowState(ws) {
            if (!ws || typeof ws !== "object") return null;
            const stage = String(ws.stage || "idle");
            if (stage === "strategy_brief" && !ws.strategy) {
              ws.stage = "idle";
              if (Array.isArray(ws.channels)) {
                ws.channels = ws.channels.filter((c) => String(c).toLowerCase() !== "linkedin");
              }
            }
            return ws;
          }

          function shouldRestoreDirectorPanel(ws) {
            if (!ws || typeof ws !== "object") return false;
            const stage = String(ws.stage || "idle");
            const hasDeliverable = Boolean(
              ws.strategy
              || ws.post
              || (ws.image && ws.image.image_url)
              || (Array.isArray(ws.linkedin_calendar) && ws.linkedin_calendar.length)
              || ws.linkedin_analysis
              || ws.optimization_report
              || (Array.isArray(ws.followed_profiles) && ws.followed_profiles.length)
              || (Array.isArray(ws.followed_posts_queue) && ws.followed_posts_queue.length)
              || ws.engagement_draft
            );
            if (stage === "idle" || stage === "planning") {
              return Boolean(ws.post || (ws.image && ws.image.image_url) || ws.execution_plan);
            }
            if (stage === "strategy_brief" && !ws.strategy) return false;
            if (stage === "followed_feed" || stage === "engagement_review" || stage === "engagement_batch_review") return true;
            if (stage === "daily_digest_review") return true;
            return hasDeliverable;
          }

          function showSavedSessionHint(ws) {
            if (!shouldRestoreDirectorPanel(ws)) return;
            const stage = String((ws && ws.stage) || "idle");
            const hints = {
              copy_review: "continua o post",
              optimization_review: "mostra a análise de optimização",
              posts_review: "mostra o calendário",
              strategy_review: "mostra a estratégia",
            };
            const example = hints[stage] || "continua onde parei";
            result.innerHTML = (
              "<p class=\"hint\">Tens uma sessão guardada neste browser. "
              + "O painel só aparece quando pedires no chat — por exemplo: «"
              + escapeHtml(example) + "».</p>"
            );
          }

          function loadWorkflowState() {
            try {
              const raw = localStorage.getItem(WORKFLOW_STORAGE_KEY);
              if (!raw) return;
              workflowState = normalizePersistedWorkflowState(JSON.parse(raw));
            } catch (e) {}
          }

          function saveWorkflowState() {
            try {
              if (workflowState) {
                localStorage.setItem(WORKFLOW_STORAGE_KEY, JSON.stringify(workflowState));
              } else {
                localStorage.removeItem(WORKFLOW_STORAGE_KEY);
              }
            } catch (e) {}
          }

          function addMessage(role, content) {
            messages.push({ role, content });
            const bubble = document.createElement("div");
            bubble.className = `msg ${role}`;
            bubble.textContent = content;
            chatLog.appendChild(bubble);
            chatLog.scrollTop = chatLog.scrollHeight;
          }

          function showTypingIndicator() {
            const bubble = document.createElement("div");
            bubble.className = "msg assistant typing";
            bubble.id = "typingIndicator";
            bubble.innerHTML = `
              <span class="typing-dot"></span>
              <span class="typing-dot"></span>
              <span class="typing-dot"></span>
            `;
            chatLog.appendChild(bubble);
            chatLog.scrollTop = chatLog.scrollHeight;
          }

          function hideTypingIndicator() {
            const el = document.getElementById("typingIndicator");
            if (el) {
              el.remove();
            }
          }

          function escapeHtml(text) {
            return String(text)
              .replace(/&/g, "&amp;")
              .replace(/</g, "&lt;")
              .replace(/>/g, "&gt;")
              .replace(/"/g, "&quot;");
          }

          function sanitizeChatReply(text) {
            const t = String(text || "").trim();
            if (!t) return "Percebi.";
            if (t.startsWith("{") && t.includes('"strategy"')) {
              try {
                const parsed = JSON.parse(t);
                if (parsed && typeof parsed.reply === "string" && parsed.reply.trim()) {
                  return parsed.reply.trim();
                }
              } catch (e) {}
              return "Plano pronto. Revê os detalhes no painel abaixo.";
            }
            if (t.startsWith("{") && t.length > 120) {
              return "Plano pronto. Revê os detalhes no painel abaixo.";
            }
            return t;
          }

          function mergeFollowedProfilesByUrl(localList, remoteList) {
            const byUrl = new Map();
            const add = (p) => {
              if (!p || typeof p !== "object") return;
              const url = String(p.profile_url || "").trim();
              if (!url) return;
              const key = url.replace(/\/+$/, "").toLowerCase();
              if (!byUrl.has(key)) byUrl.set(key, { ...p, profile_url: url });
            };
            (remoteList || []).forEach(add);
            (localList || []).forEach(add);
            return Array.from(byUrl.values());
          }

          async function loadFollowedProfilesFromDatabase() {
            if (!directorLinkedinSession || !directorLinkedinSession.access_token) return;
            try {
              const resp = await fetch("/agents/linkedin/followed-profiles/load", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  supabase_access_token: directorLinkedinSession.access_token,
                }),
              });
              const data = await resp.json();
              if (!resp.ok || !Array.isArray(data.profiles)) return;
              if (!workflowState) workflowState = {};
              const local = workflowState.followed_profiles || [];
              const merged = mergeFollowedProfilesByUrl(local, data.profiles);
              if (merged.length || data.found) {
                workflowState.followed_profiles = merged;
                saveWorkflowState();
                renderDirectorPanel({
                  orchestration_mode: workflowState.stage || "idle",
                  deliverables: { followed_profiles: merged },
                  workflow_state: workflowState,
                });
              }
            } catch (e) {
              console.warn("loadFollowedProfilesFromDatabase:", e);
            }
          }

          async function saveFollowedProfilesToDatabase() {
            if (!directorLinkedinSession || !directorLinkedinSession.access_token) return;
            const profiles = (workflowState && workflowState.followed_profiles) || [];
            try {
              await fetch("/agents/linkedin/followed-profiles/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  supabase_access_token: directorLinkedinSession.access_token,
                  profiles,
                }),
              });
            } catch (e) {
              console.warn("saveFollowedProfilesToDatabase:", e);
            }
          }

          async function applyDirectorResponse(data) {
            if (data.workflow_state) {
              workflowState = data.workflow_state;
              saveWorkflowState();
              void saveFollowedProfilesToDatabase();
            }
            addMessage("assistant", sanitizeChatReply(data.reply));
            renderDirectorPanel(data);
            await refreshDirectorLinkedinAuth();
          }

          async function callDirector(payload) {
            result.innerHTML = "<p>A processar…</p>";
            showTypingIndicator();
            try {
              const response = await fetch("/director/chat-reply", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
              });
              const data = await response.json();
              hideTypingIndicator();
              if (!response.ok) {
                const detailText = data.detail || JSON.stringify(data);
                addMessage("assistant", "Não consegui responder agora. Verifica a API key e tenta novamente.");
                result.innerHTML = `<p><strong>Erro:</strong> ${detailText}</p>`;
                return;
              }
              applyDirectorResponse(data);
            } catch (err) {
              hideTypingIndicator();
              const errorMessage = err instanceof Error ? err.message : String(err);
              addMessage("assistant", "Não consegui responder agora. Verifica a ligação e tenta novamente.");
              result.innerHTML = `<p><strong>Erro:</strong> ${errorMessage}</p>`;
            }
          }

          async function getDirectorSupabaseClient() {
            if (!SUPABASE_PUBLIC_URL || !SUPABASE_ANON_KEY) return null;
            if (directorSupabaseClient) return directorSupabaseClient;
            const { createClient } = await import("https://esm.sh/@supabase/supabase-js@2");
            directorSupabaseClient = createClient(SUPABASE_PUBLIC_URL, SUPABASE_ANON_KEY, {
              auth: { detectSessionInUrl: true, persistSession: true, autoRefreshToken: true },
            });
            return directorSupabaseClient;
          }

          async function initDirectorSupabaseFromUrl() {
            const sb = await getDirectorSupabaseClient();
            if (!sb) return null;
            const params = new URLSearchParams(window.location.search || "");
            const code = params.get("code");
            try {
              if (code) await sb.auth.exchangeCodeForSession(code);
              else if (window.location.hash && window.location.hash.includes("access_token")) {
                await sb.auth.getSession();
              }
            } catch (e) {
              console.warn("Director Supabase init:", e);
            }
            if (code || (window.location.hash && window.location.hash.includes("access_token"))) {
              window.history.replaceState({}, "", window.location.pathname);
            }
            return sb;
          }

          async function refreshDirectorLinkedinAuth() {
            const dot = document.getElementById("linkedinAuthDot");
            const label = document.getElementById("linkedinAuthLabel");
            const loginBtn = document.getElementById("btnDirectorLinkedinLogin");
            const analyzeBtn = document.getElementById("btnDirectorAnalyze");
            const optimizeBtn = document.getElementById("btnDirectorOptimize");
            const logoutBtn = document.getElementById("btnDirectorLinkedinLogout");
            const hint = document.getElementById("linkedinProfileHint");
            const sb = await getDirectorSupabaseClient();
            if (!sb) {
              if (label) label.textContent = "LinkedIn: Supabase não configurado no servidor";
              return;
            }
            const { data } = await sb.auth.getSession();
            directorLinkedinSession = data.session || null;
            const connected = Boolean(directorLinkedinSession && directorLinkedinSession.access_token);
            if (!workflowState) workflowState = {};
            workflowState.linkedin_connected = connected;
            if (dot) dot.classList.toggle("connected", connected);
            if (label) label.textContent = connected ? "LinkedIn: ligado" : "LinkedIn: não ligado";
            if (loginBtn) loginBtn.style.display = connected ? "none" : "";
            if (logoutBtn) logoutBtn.style.display = connected ? "" : "none";
            if (analyzeBtn) analyzeBtn.disabled = !connected;
            const hasStrategy = workflowState && workflowState.strategy && (
              (workflowState.strategy.smart_objectives && workflowState.strategy.smart_objectives.length)
              || (workflowState.strategy.content_pillars && workflowState.strategy.content_pillars.length)
              || workflowState.strategy.summary
            );
            if (optimizeBtn) {
              optimizeBtn.style.display = connected && hasStrategy ? "" : "none";
              optimizeBtn.disabled = !connected || !hasStrategy;
            }
            if (connected) {
              const stored = localStorage.getItem(DIRECTOR_LINKEDIN_PROFILE_KEY) || "";
              if (stored) workflowState.linkedin_profile_url = stored;
              if (hint) hint.textContent = stored ? `Perfil guardado: ${stored}` : "Ligado — clica em «Analisar perfil» para métricas reais.";
              if (directorLinkedinSession) {
                void syncDirectorPublishAuthFromServer(directorLinkedinSession).then((ok) => {
                  directorPublishAuthorizedServer = ok || !!getDirectorPublishToken();
                });
                void loadFollowedProfilesFromDatabase();
              }
            } else if (hint) {
              hint.textContent = "";
            }
            saveWorkflowState();
          }

          async function startDirectorLinkedinLogin() {
            const sb = await getDirectorSupabaseClient();
            if (!sb) {
              alert("Supabase não configurado no servidor (.env).");
              return;
            }
            const redirectTo = window.location.origin + window.location.pathname;
            const { error } = await sb.auth.signInWithOAuth({
              provider: "linkedin_oidc",
              options: { redirectTo },
            });
            if (error) alert("Erro no login LinkedIn: " + error.message);
          }

          async function endDirectorLinkedinSession() {
            const sb = await getDirectorSupabaseClient();
            if (sb) await sb.auth.signOut();
            directorLinkedinSession = null;
            if (workflowState) {
              workflowState.linkedin_connected = false;
              workflowState.linkedin_analysis = null;
            }
            await refreshDirectorLinkedinAuth();
            saveWorkflowState();
            renderDirectorPanel({
              orchestration_mode: (workflowState && workflowState.stage) || "idle",
              deliverables: { strategy: workflowState && workflowState.strategy, linkedin_analysis: null },
              workflow_state: workflowState,
            });
          }

          function appendDirectorLinkedinSessionFields(payload) {
            if (!payload || !directorLinkedinSession) return payload;
            payload.supabase_access_token = directorLinkedinSession.access_token;
            if (directorLinkedinSession.provider_token) {
              payload.linkedin_provider_token = directorLinkedinSession.provider_token;
            }
            const idTok = directorLinkedinSession.provider_id_token
              || (directorLinkedinSession.user && directorLinkedinSession.user.id_token);
            if (idTok) payload.linkedin_id_token = idTok;
            const stored = localStorage.getItem(DIRECTOR_LINKEDIN_PROFILE_KEY) || "";
            if (stored) payload.stored_linkedin_profile_url = stored;
            return payload;
          }

          function buildDirectorLinkedinSlim(data) {
            const profile = data.public_profile_data || {};
            const enrichment = profile.apify_enrichment || {};
            return {
              profile_url: data.profile_url,
              linkedin_own_profile: true,
              linkedin_page_kind: data.linkedin_page_kind,
              metricas_linkedin: data.metricas_linkedin || data.metricas_instagram || {},
              metricas_universais: data.metricas_universais || {},
              principais_insights: (data.principais_insights || []).slice(0, 6),
              problemas_identificados: (data.problemas_identificados || []).slice(0, 5),
              oportunidades: (data.oportunidades || []).slice(0, 6),
              acoes_prioritarias: (data.acoes_prioritarias || []).slice(0, 5),
              ideias_conteudo: (data.ideias_conteudo || []).slice(0, 8),
              plano_crescimento_curto_prazo: (data.plano_crescimento_curto_prazo || []).slice(0, 6),
              posting_cadence: enrichment.posting_cadence || {},
              content_type_distribution: enrichment.content_type_distribution || enrichment.format_distribution || {},
              public_profile_data: {
                profile_url: profile.profile_url || data.profile_url,
                headline: profile.headline || enrichment.headline,
                summary: profile.summary || enrichment.summary,
                apify_enrichment: {
                  content_type_distribution: enrichment.content_type_distribution || enrichment.format_distribution,
                  posting_cadence: enrichment.posting_cadence,
                  top_posts: (enrichment.top_posts || []).slice(0, 8),
                },
              },
              recent_posts: (profile.recent_posts || enrichment.recent_posts || []).slice(0, 15),
            };
          }

          async function fetchDirectorLinkedinAnalysis() {
            const payload = appendDirectorLinkedinSessionFields({
              profile_input: "",
              messages: [],
              language: languageInput.value.trim() || "pt-PT",
              platform: "linkedin",
              link_as_own_profile: true,
            });
            const response = await fetch("/agents/social-media/profile-analyze", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok) {
              const detail = data.detail || JSON.stringify(data);
              throw new Error(detail);
            }
            return data;
          }

          async function runDirectorLinkedinAnalysis() {
            if (!directorLinkedinSession) {
              alert("Liga o LinkedIn primeiro.");
              return;
            }
            const hint = document.getElementById("linkedinProfileHint");
            if (hint) hint.textContent = "A analisar perfil LinkedIn (Apify + IA)…";
            try {
              const data = await fetchDirectorLinkedinAnalysis();
              if (!workflowState) workflowState = {};
              workflowState.linkedin_connected = true;
              workflowState.linkedin_profile_url = data.profile_url || "";
              if (data.profile_url) {
                localStorage.setItem(DIRECTOR_LINKEDIN_PROFILE_KEY, data.profile_url);
              }
              const slim = buildDirectorLinkedinSlim(data);
              workflowState.linkedin_analysis = slim;
              workflowState.channels = ["linkedin"];
              saveWorkflowState();
              await refreshDirectorLinkedinAuth();
              if (hint) hint.textContent = data.profile_url
                ? `Perfil analisado: ${data.profile_url}`
                : "Perfil analisado.";
              addMessage("assistant", "Perfil LinkedIn analisado. Agora diz-me os teus objetivos — eu monto a estratégia para atingires o que definires.");
              renderDirectorPanel({
                orchestration_mode: workflowState.stage || "idle",
                execution_plan: workflowState.execution_plan || "",
                deliverables: {
                  strategy: workflowState.strategy,
                  linkedin_analysis: slim,
                  linkedin_connected: true,
                  linkedin_profile_url: workflowState.linkedin_profile_url,
                },
                workflow_state: workflowState,
              });
            } catch (err) {
              if (hint) hint.textContent = "";
              const msg = err instanceof Error ? err.message : String(err);
              addMessage("assistant", "Não consegui analisar o perfil. " + msg);
            }
          }

          async function runDirectorReanalyzeAndOptimize() {
            if (!directorLinkedinSession) {
              alert("Liga o LinkedIn primeiro.");
              return;
            }
            if (!workflowState || !workflowState.strategy) {
              alert("Define e aprova uma estratégia antes de optimizar.");
              return;
            }
            const hint = document.getElementById("linkedinProfileHint");
            if (hint) hint.textContent = "A reanalisar perfil e comparar com a estratégia…";
            const previousBaseline = workflowState.linkedin_analysis_baseline
              || workflowState.linkedin_analysis;
            if (workflowState.linkedin_analysis && !workflowState.linkedin_analysis_baseline) {
              workflowState.linkedin_analysis_baseline = JSON.parse(
                JSON.stringify(workflowState.linkedin_analysis)
              );
            }
            try {
              const data = await fetchDirectorLinkedinAnalysis();
              const slim = buildDirectorLinkedinSlim(data);
              if (!workflowState) workflowState = {};
              workflowState.linkedin_analysis = slim;
              if (previousBaseline && !workflowState.linkedin_analysis_baseline) {
                workflowState.linkedin_analysis_baseline = previousBaseline;
              }
              workflowState.linkedin_profile_url = data.profile_url || workflowState.linkedin_profile_url || "";
              saveWorkflowState();
              if (hint) hint.textContent = "A gerar relatório de optimização…";
              await directorAction("reanalyze_complete", {}, "Reanalisei o perfil LinkedIn.");
              if (hint) hint.textContent = workflowState.linkedin_profile_url
                ? `Reanálise: ${workflowState.linkedin_profile_url}`
                : "Reanálise concluída.";
              await refreshDirectorLinkedinAuth();
            } catch (err) {
              if (hint) hint.textContent = "";
              const msg = err instanceof Error ? err.message : String(err);
              addMessage("assistant", "Falha na reanálise. " + msg);
            }
          }

          window.startDirectorLinkedinLogin = startDirectorLinkedinLogin;
          window.endDirectorLinkedinSession = endDirectorLinkedinSession;
          window.runDirectorLinkedinAnalysis = runDirectorLinkedinAnalysis;
          window.runDirectorReanalyzeAndOptimize = runDirectorReanalyzeAndOptimize;

          let directorPublishAuthorizedServer = false;

          function getDirectorPublishToken() {
            try {
              const tok = sessionStorage.getItem("plataforma_linkedin_publish_token");
              const exp = parseInt(sessionStorage.getItem("plataforma_linkedin_publish_expires_at") || "0", 10);
              if (!tok) return null;
              if (exp && Date.now() > exp) {
                sessionStorage.removeItem("plataforma_linkedin_publish_token");
                sessionStorage.removeItem("plataforma_linkedin_publish_person_urn");
                return null;
              }
              return tok;
            } catch (e) {
              return null;
            }
          }

          function hasDirectorPublishAuth() {
            return directorPublishAuthorizedServer || !!getDirectorPublishToken();
          }

          async function ensureDirectorLinkedinSessionFresh() {
            const sb = await getDirectorSupabaseClient();
            if (!sb) return directorLinkedinSession;
            try {
              const { data: refreshed } = await sb.auth.refreshSession();
              if (refreshed && refreshed.session) {
                directorLinkedinSession = refreshed.session;
                return refreshed.session;
              }
            } catch (e) {}
            const { data } = await sb.auth.getSession();
            directorLinkedinSession = (data && data.session) || directorLinkedinSession;
            return directorLinkedinSession;
          }

          function getDirectorPublishPersonUrn() {
            try {
              return sessionStorage.getItem("plataforma_linkedin_publish_person_urn") || "";
            } catch (e) {
              return "";
            }
          }

          function clearDirectorPublishLocalAuth() {
            try {
              sessionStorage.removeItem("plataforma_linkedin_publish_token");
              sessionStorage.removeItem("plataforma_linkedin_publish_person_urn");
              sessionStorage.removeItem("plataforma_linkedin_publish_expires_at");
            } catch (e) {}
            directorPublishAuthorizedServer = false;
          }

          async function clearDirectorPublishAuth() {
            clearDirectorPublishLocalAuth();
            if (directorLinkedinSession && directorLinkedinSession.access_token) {
              try {
                await fetch("/agents/linkedin/publish-auth/clear", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    supabase_access_token: directorLinkedinSession.access_token,
                  }),
                });
              } catch (e) {}
            }
          }

          function parseApiErrorDetail(data) {
            const d = data && data.detail;
            if (!d) return { message: "Falha no pedido.", needReauth: false };
            if (typeof d === "string") {
              return {
                message: d,
                needReauth: /revogad|reautoriz|w_member_social|autoriza/i.test(d),
              };
            }
            if (typeof d === "object") {
              return {
                message: String(d.message || d.msg || "Falha no pedido."),
                needReauth: Boolean(d.need_reauth),
              };
            }
            return { message: String(d), needReauth: false };
          }

          async function syncDirectorPublishAuthFromServer(session) {
            if (!session || !session.access_token) return false;
            try {
              const resp = await fetch("/agents/linkedin/publish-auth/status", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ supabase_access_token: session.access_token }),
              });
              const data = await resp.json().catch(() => ({}));
              if (resp.ok && data.authorized) {
                directorPublishAuthorizedServer = true;
                return true;
              }
            } catch (e) {}
            directorPublishAuthorizedServer = false;
            return false;
          }

          async function persistDirectorPublishAuthToServer(session) {
            if (!session || !session.access_token) return false;
            const publishTok = getDirectorPublishToken();
            if (!publishTok) return false;
            let personUrn = "";
            try {
              personUrn = sessionStorage.getItem("plataforma_linkedin_publish_person_urn") || "";
            } catch (e) {}
            const exp = parseInt(sessionStorage.getItem("plataforma_linkedin_publish_expires_at") || "0", 10);
            const expiresIn = exp > Date.now() ? Math.floor((exp - Date.now()) / 1000) : 3600;
            try {
              const resp = await fetch("/agents/linkedin/publish-auth/store", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  supabase_access_token: session.access_token,
                  linkedin_publish_access_token: publishTok,
                  linkedin_person_urn: personUrn || null,
                  expires_in: expiresIn,
                }),
              });
              if (resp.ok) {
                directorPublishAuthorizedServer = true;
                return true;
              }
            } catch (e) {}
            return false;
          }

          async function connectDirectorLinkedinPublish(forceReauth) {
            if (!directorLinkedinSession) {
              alert("Liga o LinkedIn primeiro (botão acima).");
              return;
            }
            const mustReauth = forceReauth === true;
            if (!mustReauth) {
              const ok = directorPublishAuthorizedServer
                || !!getDirectorPublishToken()
                || (await syncDirectorPublishAuthFromServer(directorLinkedinSession));
              if (ok) {
                alert("Publicação já autorizada. Se falhar ao publicar, usa «Reautorizar publicação».");
                return;
              }
            } else {
              await clearDirectorPublishAuth();
            }
            const returnPath = window.location.pathname || "/";
            window.location.href =
              "/agents/linkedin/connect-publish?return_path=" + encodeURIComponent(returnPath);
          }

          function buildDirectorPublishPostPayload(post, includeImage) {
            return {
              id: post.id,
              title: post.title,
              body: post.body,
              hook: post.hook,
              cta: post.cta,
              content_type: post.content_type,
              generated_image_url: includeImage ? (post.generated_image_url || null) : null,
              image_status: post.image_status || null,
              status: post.status || "ready",
            };
          }

          async function directorPublishCurrentPost(includeImage) {
            if (!workflowState || !workflowState.post) {
              alert("Não há post para publicar.");
              return;
            }
            const post = workflowState.post;
            if (includeImage && !post.generated_image_url) {
              alert("Este post não tem imagem aprovada.");
              return;
            }
            await ensureDirectorLinkedinSessionFresh();
            if (!directorLinkedinSession || !directorLinkedinSession.access_token) {
              alert("Liga o LinkedIn primeiro.");
              return;
            }
            let publishTok = getDirectorPublishToken();
            if (!publishTok && !directorPublishAuthorizedServer) {
              await syncDirectorPublishAuthFromServer(directorLinkedinSession);
            }
            publishTok = getDirectorPublishToken();
            if (!publishTok && !directorPublishAuthorizedServer) {
              alert("Clica primeiro em «Autorizar publicação LinkedIn».");
              return;
            }
            if (publishTok) {
              await persistDirectorPublishAuthToServer(directorLinkedinSession);
            }
            const personUrn = getDirectorPublishPersonUrn();
            const modeLabel = includeImage ? "texto + imagem" : "só texto";
            if (!confirm(`Publicar no LinkedIn (${modeLabel})?\n\nSerá usada a tua conta ligada.`)) return;
            const payload = {
              supabase_access_token: directorLinkedinSession.access_token,
              linkedin_publish_access_token: publishTok || undefined,
              linkedin_person_urn: personUrn || undefined,
              include_image: !!includeImage,
              post: buildDirectorPublishPostPayload(post, includeImage),
              visibility: "PUBLIC",
            };
            try {
              const resp = await fetch("/agents/linkedin/publish-post", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
              });
              const data = await resp.json().catch(() => ({}));
              if (!resp.ok) {
                const parsed = parseApiErrorDetail(data);
                if (parsed.needReauth) {
                  await clearDirectorPublishAuth();
                  if (workflowState) {
                    renderDirectorPanel({
                      orchestration_mode: workflowState.stage || "publish_confirm",
                      workflow_state: workflowState,
                      deliverables: {
                        strategy: workflowState.strategy,
                        linkedin_calendar: workflowState.linkedin_calendar,
                        post: workflowState.post,
                        image: workflowState.image,
                      },
                    });
                  }
                }
                throw new Error(parsed.message);
              }
              await directorAction("mark_published", {
                post_id: post.id,
                linkedin_post_urn: data.linkedin_post_urn || "",
                published_with_image: !!data.published_with_image,
              }, "Publiquei no LinkedIn.");
            } catch (err) {
              const msg = err instanceof Error ? err.message : String(err);
              const extra = /revogad|reautoriz/i.test(msg)
                ? " Clica em «Reautorizar publicação LinkedIn» no painel."
                : "";
              addMessage("assistant", "Não consegui publicar: " + msg + extra);
            }
          }

          async function processDirectorPublishOAuthReturn() {
            const q = new URLSearchParams(window.location.search || "");
            if (q.get("publish_connected") !== "1" && q.get("publish_error") !== "1") return;
            if (q.get("publish_error") === "1") {
              addMessage("assistant", "A autorização de publicação LinkedIn falhou. Tenta outra vez.");
            }
            if (q.get("publish_connected") === "1") {
              if (!directorLinkedinSession) {
                await refreshDirectorLinkedinAuth();
              }
              if (directorLinkedinSession) {
                const stored = await persistDirectorPublishAuthToServer(directorLinkedinSession);
                directorPublishAuthorizedServer = stored || !!getDirectorPublishToken();
                addMessage(
                  "assistant",
                  stored
                    ? "Publicação no LinkedIn autorizada e guardada. Já podes publicar o post no painel."
                    : "Token de publicação recebido, mas não foi guardado no servidor. Tenta «Autorizar publicação LinkedIn» outra vez ou confirma a migration 004 no Supabase."
                );
              } else {
                addMessage("assistant", "Publicação autorizada no browser, mas a sessão LinkedIn não está activa. Liga o LinkedIn e autoriza outra vez.");
              }
            }
            q.delete("publish_connected");
            q.delete("publish_error");
            const qs = q.toString();
            window.history.replaceState({}, "", window.location.pathname + (qs ? "?" + qs : ""));
          }

          function buildPayload(extra = {}) {
            if (!workflowState) workflowState = {};
            workflowState.linkedin_connected = Boolean(
              directorLinkedinSession && directorLinkedinSession.access_token
            );
            return {
              messages,
              language: languageInput.value.trim() || "pt-PT",
              workflow_state: workflowState,
              ...extra
            };
          }

          async function directorAction(action, actionPayload = {}, userLabel = "") {
            if (userLabel) {
              addMessage("user", userLabel);
            }
            await callDirector(buildPayload({
              user_action: action,
              action_payload: actionPayload
            }));
          }

          const DIRECTOR_PANEL_COLLAPSE_KEY = "plataforma_director_panel_collapsed";

          function getDirectorPanelCollapsedMap() {
            try {
              const raw = localStorage.getItem(DIRECTOR_PANEL_COLLAPSE_KEY);
              return raw ? JSON.parse(raw) : {};
            } catch (e) {
              return {};
            }
          }

          function saveDirectorPanelCollapsed(panelId, collapsed) {
            try {
              const map = getDirectorPanelCollapsedMap();
              map[panelId] = collapsed;
              localStorage.setItem(DIRECTOR_PANEL_COLLAPSE_KEY, JSON.stringify(map));
            } catch (e) {}
          }

          function wrapDirectorCollapsiblePanel(panelId, title, bodyHtml, defaultOpen, variantClass) {
            const map = getDirectorPanelCollapsedMap();
            let open = defaultOpen;
            if (Object.prototype.hasOwnProperty.call(map, panelId)) {
              open = map[panelId] !== true;
            }
            const openAttr = open ? " open" : "";
            const variant = variantClass ? ` ${variantClass}` : "";
            return `<details class="director-collapse${variant}" data-panel-id="${escapeHtml(panelId)}"${openAttr}>
              <summary class="director-collapse-summary">${escapeHtml(title)}</summary>
              <div class="director-collapse-body">${bodyHtml}</div>
            </details>`;
          }

          function attachDirectorPanelCollapseListeners(root) {
            const container = root || result;
            if (!container) return;
            container.querySelectorAll("details.director-collapse[data-panel-id]").forEach((el) => {
              if (el.dataset.collapseBound === "1") return;
              el.dataset.collapseBound = "1";
              el.addEventListener("toggle", () => {
                const id = el.getAttribute("data-panel-id");
                if (id) saveDirectorPanelCollapsed(id, !el.open);
              });
            });
          }

          function renderStrategyPanel(strategy, mode) {
            if (!strategy) return "";
            const icp = strategy.icp || {};
            const hasContent = strategy.summary
              || (strategy.smart_objectives && strategy.smart_objectives.length)
              || (strategy.content_pillars && strategy.content_pillars.length)
              || icp.persona_label
              || icp.description;
            if (!hasContent) return "";
            const objectives = strategy.smart_objectives || [];
            const pillars = strategy.content_pillars || [];
            const cadence = strategy.cadence || {};
            const scenarios = strategy.scenarios || [];
            const tactics = strategy.organic_tactics || [];
            const formats = strategy.formats_mix || {};

            const objHtml = objectives.length
              ? `<ul class="strategy-list">${objectives.map((o) =>
                  `<li><strong>${escapeHtml(o.metric || "")}</strong>: ${escapeHtml(String(o.current_value ?? "—"))} → ${escapeHtml(String(o.target_value ?? "—"))} até ${escapeHtml(o.deadline || "—")}</li>`
                ).join("")}</ul>`
              : "";

            const pillarHtml = pillars.length
              ? pillars.map((p) => {
                  const pct = Number(p.weekly_percentage) || 0;
                  return `<div class="pillar-row">
                    <span>${escapeHtml(p.theme || "")}</span>
                    <div class="pillar-bar-wrap"><div class="pillar-bar" style="width:${pct}%"></div></div>
                    <span class="pillar-pct">${pct}%</span>
                  </div>`;
                }).join("")
              : "";

            const scenarioHtml = scenarios.length
              ? `<ul class="strategy-list">${scenarios.map((s) => {
                  const gain = s.weekly_follower_gain != null ? ` (+${s.weekly_follower_gain}/sem)` : "";
                  return `<li><strong>${escapeHtml(s.name || "")}</strong>${escapeHtml(gain)}: ${escapeHtml(s.description || "")}</li>`;
                }).join("")}</ul>`
              : "";

            const formatHtml = Object.keys(formats).length
              ? `<p class="post-meta">${Object.entries(formats).map(([k, v]) => `${escapeHtml(k)} ${escapeHtml(String(v))}%`).join(" · ")}</p>`
              : "";

            const cadenceDays = (cadence.best_days || []).join(", ");
            const cadenceTimes = (cadence.best_times || []).join(", ");
            const cadenceHtml = cadence.posts_per_week
              ? `<p class="post-meta">${cadence.posts_per_week} posts/semana${cadenceDays ? ` · ${escapeHtml(cadenceDays)}` : ""}${cadenceTimes ? ` · ${escapeHtml(cadenceTimes)}` : ""}</p>`
              : "";

            const tacticsHtml = tactics.length
              ? `<ul class="strategy-list">${tactics.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}</ul>`
              : "";

            let actionsHtml = "";
            if (mode === "strategy_review") {
              actionsHtml = `
                <div class="workflow-actions">
                  <button type="button" class="wf-btn wf-btn-approve" onclick="approveStrategy()">Aprovar estratégia</button>
                  <button type="button" class="wf-btn wf-btn-strategy" onclick="startExecution()">Iniciar execução</button>
                </div>`;
            } else if (mode === "strategy_approved") {
              actionsHtml = `
                <div class="workflow-actions">
                  <button type="button" class="wf-btn wf-btn-strategy" onclick="startExecution()">Iniciar execução</button>
                </div>`;
            }

            const body = `
                ${strategy.summary ? `<p class="post-meta">${escapeHtml(strategy.summary)}</p>` : ""}
                <div class="strategy-section">
                  <h5>ICP — público-alvo</h5>
                  <p class="post-meta">${escapeHtml(icp.persona_label || "")}${icp.description ? " — " + escapeHtml(icp.description) : ""}</p>
                </div>
                ${objectives.length ? `<div class="strategy-section"><h5>Objetivos SMART</h5>${objHtml}</div>` : ""}
                ${pillars.length ? `<div class="strategy-section"><h5>Pilares de conteúdo (% semanal)</h5>${pillarHtml}</div>` : ""}
                ${cadenceHtml ? `<div class="strategy-section"><h5>Cadência</h5>${cadenceHtml}</div>` : ""}
                ${formatHtml ? `<div class="strategy-section"><h5>Mix de formatos</h5>${formatHtml}</div>` : ""}
                ${scenarios.length ? `<div class="strategy-section"><h5>Cenários</h5>${scenarioHtml}</div>` : ""}
                ${tacticsHtml ? `<div class="strategy-section"><h5>Táticas orgânicas</h5>${tacticsHtml}</div>` : ""}
                ${actionsHtml}`;
            const defaultOpen = ["strategy_brief", "strategy_review"].includes(mode);
            return wrapDirectorCollapsiblePanel(
              "strategy",
              "Estratégia LinkedIn",
              body,
              defaultOpen,
              "director-collapse--strategy"
            );
          }

          function renderCalendarPanel(calendar, activePostId, mode) {
            if (!calendar || !calendar.length) return "";
            const rows = calendar.map((entry) => {
              const post = entry.post || {};
              const status = entry.status || "draft";
              const isActive = activePostId && String(entry.post_id) === String(activePostId);
              const cls = `cal-row${status === "ready" ? " is-ready" : ""}${status === "published" ? " is-ready" : ""}${isActive ? " is-active" : ""}`;
              const statusLabel = status === "published" ? "Publicado" : status === "ready" ? "Pronto" : "Rascunho";
              const statusClass = status === "published" ? "published" : status === "ready" ? "ready" : "";
              const pillar = entry.pillar_theme ? ` · ${entry.pillar_theme}` : "";
              return `<div class="${cls}">
                <div>
                  <div class="cal-meta">${escapeHtml(entry.scheduled_label || entry.scheduled_date || "")}${escapeHtml(pillar)}</div>
                  <div class="cal-title">${escapeHtml(post.title || "Post LinkedIn")}</div>
                </div>
                <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
                  <span class="cal-status ${statusClass}">${escapeHtml(statusLabel)}</span>
                  ${status === "draft" ? `<button type="button" class="wf-btn wf-btn-strategy" style="padding:6px 10px;font-size:0.75rem" onclick='selectCalendarPost(${JSON.stringify(String(entry.post_id || ""))})'>Rever</button>` : ""}
                </div>
              </div>`;
            }).join("");
            const defaultOpen = ["posts_review", "copy_review", "image_confirm", "image_review", "publish_confirm"].includes(mode);
            return wrapDirectorCollapsiblePanel(
              "calendar",
              "Calendário da semana",
              rows,
              defaultOpen,
              "director-collapse--calendar"
            );
          }

          const OPT_STATUS_LABEL = {
            on_track: "No caminho",
            behind: "Atrasado",
            ahead: "À frente",
            critical: "Crítico",
            insufficient_data: "Dados insuficientes",
          };

          function renderOptimizationPanel(report, mode) {
            if (!report || (!report.headline && !report.insights && !report.objective_progress)) return "";
            const status = report.overall_status || "insufficient_data";
            const statusLabel = OPT_STATUS_LABEL[status] || status;
            const exec = report.execution_summary || {};
            const execHtml = exec.posts_total
              ? `<p class="post-meta">Calendário: ${exec.posts_ready || 0}/${exec.posts_total} posts prontos (${exec.completion_pct || 0}%)</p>`
              : "";
            const objectives = report.objective_progress || [];
            const objRows = objectives.map((o) => {
              const st = OPT_STATUS_LABEL[o.status] || o.status || "";
              return `<tr>
                <td>${escapeHtml(o.metric || "")}</td>
                <td>${escapeHtml(String(o.baseline || "—"))}</td>
                <td>${escapeHtml(String(o.current || "—"))}</td>
                <td>${escapeHtml(String(o.target || "—"))}</td>
                <td>${escapeHtml(st)}</td>
              </tr>`;
            }).join("");
            const objTable = objRows
              ? `<table class="opt-table"><thead><tr><th>Métrica</th><th>Antes</th><th>Agora</th><th>Meta</th><th>Estado</th></tr></thead><tbody>${objRows}</tbody></table>`
              : "";
            const deltas = (report.metric_deltas || []).slice(0, 6).map((d) =>
              `<li>${escapeHtml(d.metric || "")}: ${escapeHtml(String(d.before))} → ${escapeHtml(String(d.after))}</li>`
            ).join("");
            const deltaHtml = deltas ? `<ul class="strategy-list">${deltas}</ul>` : "";
            const insights = (report.insights || []).map((i) => `<li>${escapeHtml(i)}</li>`).join("");
            const insightsHtml = insights ? `<div class="strategy-section"><h5>Insights</h5><ul class="strategy-list">${insights}</ul></div>` : "";
            const workedSection = renderDigestListItems(report.worked_well, "digest-worked");
            const workedBlock = workedSection
              ? `<div class="strategy-section"><h5>O que funcionou</h5>${workedSection}</div>` : "";
            const underSection = renderDigestListItems(report.underperformed, "digest-under");
            const underBlock = underSection
              ? `<div class="strategy-section"><h5>O que ficou aquém</h5>${underSection}</div>` : "";
            const postPerfBlock = renderPostInsightsBlock(report.post_insights);
            const formatLines = (report.format_insights || []).map((f) => `<li>${escapeHtml(f)}</li>`).join("");
            const formatBlock = formatLines
              ? `<div class="strategy-section"><h5>Performance por formato</h5><ul class="strategy-list">${formatLines}</ul></div>` : "";
            const timingBlock = renderTimingAnalysisBlock(
              report.timing_analysis
              || (report.post_performance && report.post_performance.timing_analysis)
            );
            const timingLines = (!timingBlock && (report.timing_insights || []).length)
              ? (report.timing_insights || []).map((t) => `<li>${escapeHtml(t)}</li>`).join("")
              : "";
            const timingBlockOrList = timingBlock || (timingLines
              ? `<div class="strategy-section"><h5>Horário / cadência</h5><ul class="strategy-list">${timingLines}</ul></div>`
              : "");
            const nextAdj = report.next_posts_adjustment
              ? `<div class="strategy-section"><h5>Ajuste aos próximos posts</h5><p class="post-meta">${escapeHtml(report.next_posts_adjustment)}</p></div>`
              : "";
            const recs = (report.recommendations || []).map((r) => {
              const pri = String(r.priority || "").toLowerCase();
              const cls = pri === "alta" ? "opt-priority-alta" : pri === "media" ? "opt-priority-media" : "";
              return `<li class="${cls}"><strong>${escapeHtml(r.area || "")}</strong>: ${escapeHtml(r.action || "")}</li>`;
            }).join("");
            const recHtml = recs ? `<div class="strategy-section"><h5>Recomendações</h5><ul class="strategy-list">${recs}</ul></div>` : "";
            const adj = report.strategy_adjustments || {};
            const adjSummary = adj.summary
              ? `<div class="strategy-section"><h5>Ajustes propostos à estratégia</h5><p class="post-meta">${escapeHtml(adj.summary)}</p></div>`
              : "";
            let actionsHtml = "";
            if (mode === "optimization_review") {
              actionsHtml = `
                <div class="workflow-actions">
                  <button type="button" class="wf-btn wf-btn-approve" onclick="approveOptimization()">Aplicar optimizações</button>
                  <button type="button" class="wf-btn wf-btn-secondary" onclick="dismissOptimization()">Manter estratégia actual</button>
                </div>`;
            }
            const body = `
                <span class="opt-status-badge ${escapeHtml(status)}">${escapeHtml(statusLabel)}</span>
                ${execHtml}
                ${objTable}
                ${deltaHtml ? `<div class="strategy-section"><h5>Variação de métricas</h5>${deltaHtml}</div>` : ""}
                ${workedBlock}
                ${underBlock}
                ${postPerfBlock}
                ${formatBlock}
                ${timingBlockOrList}
                ${nextAdj}
                ${insightsHtml}
                ${recHtml}
                ${adjSummary}
                ${actionsHtml}`;
            return wrapDirectorCollapsiblePanel(
              "optimization",
              report.headline || "Optimização LinkedIn",
              body,
              mode === "optimization_review",
              "director-collapse--optimization"
            );
          }

          function renderPublishPanel(post, mode) {
            if (!post) return "";
            if (post.published_on_linkedin) {
              const body = `
                  <p class="post-meta">${post.published_with_image ? "Com imagem" : "Só texto"}</p>
                  ${post.linkedin_post_urn ? `<p class="post-meta">ID: ${escapeHtml(String(post.linkedin_post_urn))}</p>` : ""}`;
              return wrapDirectorCollapsiblePanel(
                "publish_done",
                "Publicado no LinkedIn",
                body,
                false,
                "director-collapse--publish"
              );
            }
            if (mode !== "publish_confirm") return "";
            const hasImg = !!(post.generated_image_url);
            const authHtml = hasDirectorPublishAuth()
              ? `<span class="publish-auth-ok">Publicação autorizada</span>
                 <button type="button" class="wf-btn wf-btn-secondary" style="padding:6px 10px;font-size:0.75rem"
                   onclick="connectDirectorLinkedinPublish(true)">Reautorizar publicação</button>`
              : `<button type="button" class="wf-btn wf-btn-strategy" onclick="connectDirectorLinkedinPublish(false)">Autorizar publicação LinkedIn</button>`;
            const imgBtn = hasImg
              ? `<button type="button" class="wf-btn wf-btn-approve" onclick="directorPublishCurrentPost(true)">Publicar texto + imagem</button>`
              : "";
            const body = `
                <p class="post-meta">O login acima analisa o perfil; autoriza aqui para publicar posts (permissão w_member_social).</p>
                <div class="workflow-actions" style="flex-wrap:wrap;align-items:center;gap:8px">
                  ${authHtml}
                  <button type="button" class="wf-btn wf-btn-approve" onclick="directorPublishCurrentPost(false)">Publicar só texto</button>
                  ${imgBtn}
                  <button type="button" class="wf-btn wf-btn-secondary" onclick="skipPublish()">Avançar sem publicar</button>
                </div>`;
            return wrapDirectorCollapsiblePanel(
              "publish",
              "Publicar no LinkedIn",
              body,
              true,
              "director-collapse--publish"
            );
          }

          function isDirectorLinkedinContext(mode, workflowState, deliverables) {
            const linkedinModes = new Set([
              "strategy_brief", "strategy_review", "strategy_approved",
              "optimization_review", "daily_digest_review", "posts_review", "publish_confirm",
              "followed_feed", "engagement_review", "engagement_batch_review"
            ]);
            if (linkedinModes.has(mode)) return true;
            const ws = workflowState || {};
            const channels = (ws.channels || []).map((c) => String(c).toLowerCase());
            if (channels.includes("linkedin")) return true;
            const d = deliverables || {};
            if (d.strategy) return true;
            if (Array.isArray(d.linkedin_calendar) && d.linkedin_calendar.length) return true;
            if (Array.isArray(ws.linkedin_calendar) && ws.linkedin_calendar.length) return true;
            if (Array.isArray(d.followed_profiles) && d.followed_profiles.length) return true;
            if (Array.isArray(d.followed_posts_queue) && d.followed_posts_queue.length) return true;
            return false;
          }

          function renderFollowedFeedPanel(profiles, queue, suggestions, mode, linkedinContext) {
            if (!linkedinContext) return "";
            const profs = Array.isArray(profiles) ? profiles : [];
            const posts = Array.isArray(queue) ? queue : [];
            const sugs = (Array.isArray(suggestions) ? suggestions : [])
              .filter((s) => (s.status || "pending") === "pending");
            if (!profs.length && !posts.length && !sugs.length && mode !== "followed_feed" && mode !== "engagement_review") {
              return "";
            }
            const sugRows = sugs.map((s) => `
              <div class="cal-row" style="margin-bottom:6px">
                <div>
                  <div class="cal-meta">${escapeHtml(s.display_name || "")}</div>
                  <div class="cal-title" style="font-size:0.8rem">${escapeHtml(s.rationale || "")}</div>
                  <a href="${escapeHtml(s.profile_url || "#")}" target="_blank" rel="noopener" style="font-size:0.75rem;color:#93c5fd">Ver perfil</a>
                </div>
                <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
                  <button type="button" class="wf-btn wf-btn-approve" style="padding:4px 8px;font-size:0.7rem"
                    onclick='acceptFollowedSuggestion(${JSON.stringify(String(s.id || ""))})'>Adicionar</button>
                  <button type="button" class="wf-btn wf-btn-secondary" style="padding:4px 8px;font-size:0.7rem"
                    onclick='dismissFollowedSuggestion(${JSON.stringify(String(s.id || ""))})'>Ignorar</button>
                </div>
              </div>`).join("");
            const profRows = profs.map((p) => `
              <li>${escapeHtml(p.display_name || p.profile_url || "")}
                <button type="button" class="wf-btn wf-btn-secondary" style="padding:2px 8px;font-size:0.7rem;margin-left:6px"
                  onclick='removeFollowedProfile(${JSON.stringify(String(p.id || ""))})'>Remover</button>
              </li>`).join("");
            const statusLabel = { pending: "Pendente", draft: "Em revisão", approved: "Aprovado", rejected: "Reprovado" };
            const postRows = posts.map((entry) => {
              const st = entry.status || "pending";
              const cls = st === "pending" ? "" : " is-ready";
              const snippet = String(entry.snippet || "").slice(0, 120);
              return `<div class="cal-row${cls}">
                <div>
                  <div class="cal-meta">${escapeHtml(entry.author_name || "")}</div>
                  <div class="cal-title">${escapeHtml(snippet || "Publicação")}${snippet.length >= 120 ? "…" : ""}</div>
                </div>
                <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
                  <span class="cal-status">${escapeHtml(statusLabel[st] || st)}</span>
                  ${st === "pending" ? `<button type="button" class="wf-btn wf-btn-strategy" style="padding:6px 10px;font-size:0.75rem"
                    onclick='selectFollowedPost(${JSON.stringify(String(entry.id || ""))})'>Sugerir comentário</button>` : ""}
                  ${entry.post_url ? `<a href="${escapeHtml(entry.post_url)}" target="_blank" rel="noopener" style="font-size:0.75rem;color:#93c5fd">Abrir</a>` : ""}
                </div>
              </div>`;
            }).join("");
            const body = `
                <p class="post-meta">Sugiro perfis com base na tua estratégia/ICP — confirmas antes de adicionar. Depois recolho posts públicos (Apify) e proponho comentários para aprovares.</p>
                <div class="workflow-actions" style="margin-bottom:10px;flex-wrap:wrap">
                  <button type="button" class="wf-btn wf-btn-strategy" onclick="suggestFollowedProfiles()">Sugerir perfis (ICP)</button>
                  <button type="button" class="wf-btn wf-btn-secondary" onclick="syncLinkedInNetworkFeed()">Importar feed</button>
                  <button type="button" class="wf-btn wf-btn-strategy" onclick="promptAddFollowedProfile()">+ URL manual</button>
                  <button type="button" class="wf-btn wf-btn-secondary" onclick="refreshFollowedPosts()">Actualizar publicações</button>
                  <button type="button" class="wf-btn wf-btn-approve" onclick="generateEngagementBatch()">Gerar lote (10 comentários)</button>
                </div>
                ${sugRows ? `<div style="margin-bottom:10px"><h5 style="margin:0 0 6px;font-size:0.85rem">Sugestões (confirma)</h5>${sugRows}
                  <button type="button" class="wf-btn wf-btn-approve" style="margin-top:6px;padding:6px 10px;font-size:0.75rem" onclick="acceptAllFollowedSuggestions()">Adicionar todas</button></div>` : ""}
                ${profRows ? `<ul class="strategy-list">${profRows}</ul>` : `<p class="post-meta">Ainda não adicionaste perfis.</p>`}
                ${postRows ? `<div style="margin-top:10px">${postRows}</div>` : ""}`;
            const defaultOpen = mode === "followed_feed" || mode === "engagement_review";
            return wrapDirectorCollapsiblePanel(
              "followed_feed",
              "Comentar publicações de perfis que sigo",
              body,
              defaultOpen,
              "director-collapse--followed"
            );
          }

          function renderDigestListItems(items, cssClass) {
            const list = (items || []).filter(Boolean);
            if (!list.length) return "";
            const body = list.map((i) => `<li>${escapeHtml(String(i))}</li>`).join("");
            return `<div class="${cssClass}"><ul class="strategy-list">${body}</ul></div>`;
          }

          function renderTimingAnalysisBlock(timing) {
            if (!timing || typeof timing !== "object") return "";
            const days = Array.isArray(timing.best_weekdays) ? timing.best_weekdays : [];
            const hours = Array.isArray(timing.best_hours) ? timing.best_hours : [];
            if (!days.length && !hours.length) return "";
            const tz = timing.timezone === "Europe/Lisbon" ? " (hora de Lisboa)" : "";
            let html = "";
            if (days.length) {
              const dayRows = days.map((d, i) => `<tr>
                <td>${i === 0 ? "★ " : ""}${escapeHtml(d.day || d.day_short || "")}</td>
                <td>${escapeHtml(String(d.avg_score != null ? d.avg_score : "—"))}</td>
                <td>${escapeHtml(String(d.post_count || 0))} posts</td>
              </tr>`).join("");
              html += `<div class="strategy-section"><h5>Melhores dias da semana${tz}</h5>
                <table class="timing-table"><thead><tr><th>Dia</th><th>Score médio</th><th>Amostra</th></tr></thead>
                <tbody>${dayRows}</tbody></table></div>`;
            }
            if (hours.length) {
              const hourRows = hours.map((h, i) => `<tr>
                <td>${i === 0 ? "★ " : ""}${escapeHtml(h.hour_label || h.hour_range || "")}</td>
                <td>${escapeHtml(String(h.avg_score != null ? h.avg_score : "—"))}</td>
                <td>${escapeHtml(String(h.post_count || 0))} posts</td>
              </tr>`).join("");
              html += `<div class="strategy-section"><h5>Melhores horários${tz}</h5>
                <table class="timing-table"><thead><tr><th>Hora</th><th>Score médio</th><th>Amostra</th></tr></thead>
                <tbody>${hourRows}</tbody></table></div>`;
            }
            const insights = (timing.timing_insights || []).map((t) => `<li>${escapeHtml(t)}</li>`).join("");
            if (insights) {
              html += `<ul class="strategy-list" style="margin-top:8px">${insights}</ul>`;
            }
            return html;
          }

          function renderPostInsightsBlock(insights) {
            const rows = (insights || []).filter((p) => p && typeof p === "object");
            if (!rows.length) return "";
            const html = rows.map((p) => {
              const verdict = String(p.verdict || p.bucket || "").toLowerCase();
              const cls = verdict.includes("fraco") || verdict === "weak" ? "digest-under" : "digest-worked";
              const preview = p.post_preview || p.preview || "";
              const reason = p.likely_reason || "";
              const when = (p.posted_weekday || p.posted_hour)
                ? `<span class="post-meta">${escapeHtml([p.posted_weekday, p.posted_hour].filter(Boolean).join(" · "))}</span><br>`
                : "";
              return `<div class="digest-post-row ${cls}">
                <strong>${escapeHtml(String(p.format || "post"))}</strong>
                — ${escapeHtml(String(preview).slice(0, 120))}
                <br>${when}
                ${reason ? `<span class="post-meta">${escapeHtml(reason)}</span>` : ""}
              </div>`;
            }).join("");
            return `<div class="strategy-section"><h5>Por publicação</h5>${html}</div>`;
          }

          function renderDailyDigestPanel(digest, mode) {
            if (!digest || (!digest.headline && !digest.summary)) return "";
            const workedHtml = renderDigestListItems(digest.worked_well, "digest-worked");
            const workedSection = workedHtml
              ? `<div class="strategy-section"><h5>O que funcionou</h5>${workedHtml}</div>` : "";
            const underHtml = renderDigestListItems(digest.underperformed, "digest-under");
            const underSection = underHtml
              ? `<div class="strategy-section"><h5>O que ficou aquém</h5>${underHtml}</div>` : "";
            const formatLines = (digest.format_insights || []).map((f) => `<li>${escapeHtml(f)}</li>`).join("");
            const formatSection = formatLines
              ? `<div class="strategy-section"><h5>Formatos</h5><ul class="strategy-list">${formatLines}</ul></div>` : "";
            const timingBlock = renderTimingAnalysisBlock(
              digest.timing_analysis || (digest.post_performance && digest.post_performance.timing_analysis)
            );
            const timingLines = (!timingBlock && (digest.timing_insights || []).length)
              ? (digest.timing_insights || []).map((t) => `<li>${escapeHtml(t)}</li>`).join("")
              : "";
            const timingSection = timingBlock || (timingLines
              ? `<div class="strategy-section"><h5>Horário / cadência</h5><ul class="strategy-list">${timingLines}</ul></div>`
              : "");
            const postInsights = renderPostInsightsBlock(digest.post_insights);
            const priorities = (digest.priorities || []).map((p) => `<li>${escapeHtml(p)}</li>`).join("");
            const prioHtml = priorities ? `<div class="strategy-section"><h5>Prioridades hoje</h5><ul class="strategy-list">${priorities}</ul></div>` : "";
            const focus = digest.focus_today
              ? `<p class="post-meta"><strong>Foco de hoje:</strong> ${escapeHtml(digest.focus_today)}</p>`
              : "";
            const adjust = digest.next_posts_adjustment
              ? `<p class="post-meta"><strong>Próximos posts:</strong> ${escapeHtml(digest.next_posts_adjustment)}</p>`
              : "";
            const body = `
                <p class="post-meta">${escapeHtml(digest.summary || "")}</p>
                ${workedSection}
                ${underSection}
                ${postInsights}
                ${formatSection}
                ${timingSection}
                ${focus}
                ${adjust}
                ${prioHtml}`;
            return wrapDirectorCollapsiblePanel(
              "daily_digest",
              digest.headline || "Análise de ontem",
              body,
              mode === "daily_digest_review",
              "director-collapse--digest"
            );
          }

          function renderEngagementBatchPanel(batch, mode) {
            const items = Array.isArray(batch) ? batch : [];
            if (!items.length) {
              if (mode !== "engagement_batch_review") return "";
              return `<div class="engagement-panel"><p class="post-meta">A gerar lote de comentários…</p></div>`;
            }
            const rows = items.map((item) => {
              const id = String(item.id || "");
              const checked = item.batch_selected !== false ? "checked" : "";
              const url = item.target_url
                ? `<a href="${escapeHtml(item.target_url)}" target="_blank" rel="noopener" style="font-size:0.75rem;color:#93c5fd">Abrir publicação</a>`
                : "";
              return `<div class="cal-row" data-batch-comment-id="${escapeHtml(id)}" style="align-items:flex-start;margin-bottom:10px">
                <div style="flex:1">
                  <label style="display:flex;gap:8px;align-items:flex-start;cursor:pointer">
                    <input type="checkbox" class="batch-select" ${checked} style="margin-top:4px" />
                    <div>
                      <div class="cal-meta">${escapeHtml(item.target_label || item.author_name || "")}</div>
                      ${item.target_snippet ? `<p class="post-meta" style="font-style:italic">«${escapeHtml(String(item.target_snippet).slice(0, 160))}»</p>` : ""}
                      <textarea class="engagement-comment batch-comment-body" style="margin-top:6px;min-height:72px">${escapeHtml(item.comment_body || "")}</textarea>
                      ${url}
                    </div>
                  </label>
                </div>
              </div>`;
            }).join("");
            const actions = mode === "engagement_batch_review" ? `
              <div class="workflow-actions">
                <button type="button" class="wf-btn wf-btn-approve" onclick="approveEngagementBatch()">Aprovar seleccionados</button>
                <button type="button" class="wf-btn wf-btn-secondary" onclick="copyApprovedBatchToClipboard()">Copiar seleccionados</button>
                <button type="button" class="wf-btn wf-btn-secondary" onclick="dismissEngagementBatch()">Descartar lote</button>
              </div>` : "";
            const body = `
                <p class="post-meta">Marca os comentários que queres usar, edita se precisares, e aprova em lote.</p>
                ${rows}
                ${actions}`;
            return wrapDirectorCollapsiblePanel(
              "engagement_batch",
              `Lote de comentários (${items.length})`,
              body,
              mode === "engagement_batch_review",
              "director-collapse--batch"
            );
          }

          function renderEngagementPanel(draft, mode) {
            if (!draft || !draft.comment_body) {
              if (mode !== "engagement_review") return "";
              return `<div class="engagement-panel"><p class="post-meta">A gerar comentário para a publicação…</p></div>`;
            }
            const openPost = draft.target_url
              ? `<a class="wf-btn wf-btn-approve" style="display:inline-block;text-decoration:none;margin-bottom:8px"
                  href="${escapeHtml(draft.target_url)}" target="_blank" rel="noopener">Abrir publicação no LinkedIn</a>`
              : "";
            const actions = mode === "engagement_review" ? `
              <div class="workflow-actions">
                <button type="button" class="wf-btn wf-btn-approve" onclick="approveEngagement()">Aprovar comentário</button>
                <button type="button" class="wf-btn wf-btn-secondary" onclick="rejectEngagement()">Reprovar</button>
                <button type="button" class="wf-btn wf-btn-secondary" onclick="copyEngagementToClipboard()">Copiar texto</button>
                <button type="button" class="wf-btn wf-btn-image" onclick="regenerateEngagement()">Refazer</button>
              </div>` : "";
            const body = `
                <p class="post-meta">${escapeHtml(draft.target_label || "")}</p>
                ${draft.target_snippet ? `<p class="post-meta" style="font-style:italic">«${escapeHtml(String(draft.target_snippet).slice(0, 200))}»</p>` : ""}
                ${openPost}
                ${draft.angle ? `<p class="post-meta">${escapeHtml(draft.angle)}</p>` : ""}
                <textarea id="directorEngagementBody" class="engagement-comment">${escapeHtml(draft.comment_body || "")}</textarea>
                <p class="post-meta">Depois de aprovar: copia o texto, abre a publicação e cola o comentário.</p>
                ${actions}`;
            return wrapDirectorCollapsiblePanel(
              "engagement",
              "Comentário para publicação de terceiro",
              body,
              mode === "engagement_review",
              "director-collapse--engagement"
            );
          }

          function renderProfilePanel(snapshot) {
            if (!snapshot || !snapshot.profile_url) return "";
            const metrics = snapshot.metricas_linkedin || {};
            const metricLines = Object.entries(metrics).slice(0, 6)
              .map(([k, v]) => `<li>${escapeHtml(k)}: ${escapeHtml(String(v))}</li>`).join("");
            const insights = (snapshot.principais_insights || []).slice(0, 3)
              .map((i) => `<li>${escapeHtml(i)}</li>`).join("");
            const body = `
                <p class="post-meta">${escapeHtml(snapshot.profile_url)}</p>
                ${metricLines ? `<ul class="strategy-list">${metricLines}</ul>` : ""}
                ${insights ? `<ul class="strategy-list">${insights}</ul>` : ""}`;
            return wrapDirectorCollapsiblePanel(
              "profile",
              "Perfil LinkedIn analisado",
              body,
              false,
              "director-collapse--profile"
            );
          }

          function renderDirectorPanel(data) {
            const mode = data.orchestration_mode || "planning";
            const ws = data.workflow_state || workflowState;
            const plan = data.execution_plan
              ? `<p class="plan-line"><strong>Plano:</strong> ${escapeHtml(data.execution_plan)}</p>`
              : "";
            const deliverables = data.deliverables || {};
            const strategy = deliverables.strategy || (workflowState && workflowState.strategy) || null;
            const linkedinAnalysis = deliverables.linkedin_analysis
              || (workflowState && workflowState.linkedin_analysis) || null;
            const calendar = deliverables.linkedin_calendar
              || (workflowState && workflowState.linkedin_calendar) || [];
            const post = deliverables.post || (workflowState && workflowState.post) || null;
            const image = deliverables.image || (workflowState && workflowState.image) || null;
            const optimizationReport = deliverables.optimization_report
              || (workflowState && workflowState.optimization_report) || null;
            const engagementDraft = deliverables.engagement_draft
              || (workflowState && workflowState.engagement_draft) || null;
            const engagementBatch = deliverables.engagement_batch
              || (workflowState && workflowState.engagement_batch) || [];
            const dailyDigest = deliverables.daily_digest
              || (workflowState && workflowState.daily_digest) || null;
            const followedProfiles = deliverables.followed_profiles
              || (workflowState && workflowState.followed_profiles) || [];
            const followedSuggestions = deliverables.followed_profile_suggestions
              || (workflowState && workflowState.followed_profile_suggestions) || [];
            const followedPostsQueue = deliverables.followed_posts_queue
              || (workflowState && workflowState.followed_posts_queue) || [];
            const activePostId = post && post.id ? post.id : null;
            const stageLabel = {
              strategy_brief: "Brief estratégico",
              strategy_review: "Revisão de estratégia",
              strategy_approved: "Estratégia aprovada",
              optimization_review: "Análise de ontem e optimização",
              posts_review: "Calendário de posts",
              planning: "Planeamento",
              copy_review: "Revisão de copy",
              image_confirm: "Confirmar imagem",
              image_review: "Revisão de imagem",
              publish_confirm: "Publicar no LinkedIn",
              engagement_review: "Comentário (aprovação)",
              engagement_batch_review: "Lote de comentários",
              daily_digest_review: "Análise de ontem",
              followed_feed: "Publicações de perfis seguidos",
              completed: "Concluído",
              redirect: "Encaminhamento",
              idle: "Início"
            }[mode] || mode;
            const stageHint = {
              strategy_brief: "Ainda faltam dados. Completa objetivos SMART, ICP e métricas no chat.",
              strategy_review: "Plano estratégico abaixo. Aprova ou pede ajustes antes dos posts.",
              strategy_approved: "Estratégia fechada. Inicia a execução ou reanalisa para optimizar.",
              optimization_review: "Compara o que funcionou vs o que ficou aquém. Aplica ou ignora os ajustes.",
              posts_review: "Escolhe o próximo post no calendário para rever copy e imagem.",
              planning: "Indica objetivo, público e tom. LinkedIn só entra se o pedires explicitamente.",
              copy_review: calendar.length
                ? "Revisa o post do dia: copy → imagem → próximo no calendário."
                : "Passo 1 de 2: revê o texto, edita se precisares e clica em «Aprovar copy».",
              image_confirm: "Passo 2 de 2: copy aprovada. Queres o criativo visual?",
              image_review: "Revê a imagem. Aprova ou regenera com novas instruções.",
              publish_confirm: "Autoriza a publicação OAuth e publica o post, ou avança sem publicar.",
              engagement_review: "Comentário para uma publicação de alguém que segues — aprova ou reprova.",
              engagement_batch_review: "Revê o lote de comentários — marca, edita e aprova os que quiseres.",
              daily_digest_review: "O que funcionou ontem, o que ficou aquém e o foco de hoje.",
              followed_feed: "Escolhe uma publicação para eu sugerir um comentário.",
              completed: "Semana ou post concluídos. Podes comentar em perfis que segues ou reanalisar.",
              redirect: "Este pedido é do agente especializado — continua na página dele.",
              idle: "Descreve o que queres (copy, imagem, campanha). Menciona LinkedIn só se for para essa rede."
            }[mode] || "";

            const linkedinContext = isDirectorLinkedinContext(mode, ws, deliverables);
            setDirectorLinkedinBarVisible(linkedinContext);
            let workflowHtml = (linkedinContext ? renderProfilePanel(linkedinAnalysis) : "")
              + (linkedinContext ? renderStrategyPanel(strategy, mode) : "")
              + (mode === "daily_digest_review" ? renderDailyDigestPanel(dailyDigest, mode) : "")
              + (linkedinContext ? renderOptimizationPanel(optimizationReport, mode) : "")
              + (linkedinContext ? renderCalendarPanel(calendar, activePostId, mode) : "")
              + (linkedinContext ? renderPublishPanel(post, mode) : "")
              + renderFollowedFeedPanel(followedProfiles, followedPostsQueue, followedSuggestions, mode, linkedinContext)
              + renderEngagementBatchPanel(engagementBatch, mode)
              + (linkedinContext ? renderEngagementPanel(engagementDraft, mode) : "");
            if (post && post.body && mode !== "engagement_review") {
              const readonly = mode !== "copy_review";
              const metaParts = [];
              if (post.title) metaParts.push(`Título: ${post.title}`);
              if (post.hook) metaParts.push(`Gancho: ${post.hook}`);
              if (post.cta) metaParts.push(`CTA: ${post.cta}`);
              const metaHtml = metaParts.length
                ? `<p class="post-meta">${metaParts.map(escapeHtml).join(" · ")}</p>`
                : "";
              workflowHtml += `
                <div class="workflow-panel">
                  <h4>Post (${escapeHtml(post.channel || "linkedin")})</h4>
                  ${metaHtml}
                  <textarea id="workflowPostBody" class="workflow-post" ${readonly ? "readonly" : ""}>${escapeHtml(post.body || "")}</textarea>
              `;
              if (mode === "copy_review") {
                workflowHtml += `
                  <div class="workflow-actions">
                    <button type="button" class="wf-btn wf-btn-approve" onclick="approveCopy()">Aprovar copy</button>
                    <button type="button" class="wf-btn wf-btn-secondary" onclick="saveCopyEdit()">Guardar edição</button>
                    ${calendar.length ? `<button type="button" class="wf-btn wf-btn-image" onclick="regenerateLinkedinPost()">Refazer post</button>` : ""}
                  </div>
                `;
              }
              if (mode === "image_confirm") {
                workflowHtml += `
                  <div class="workflow-actions">
                    <button type="button" class="wf-btn wf-btn-image" onclick="generateImage()">Gerar imagem</button>
                    <button type="button" class="wf-btn wf-btn-secondary" onclick="skipImage()">Sem imagem</button>
                  </div>
                `;
              }
              workflowHtml += `</div>`;
            }
            if (image && image.image_url) {
              workflowHtml += `
                <div class="workflow-panel">
                  <h4>Imagem gerada</h4>
                  <img class="workflow-image" src="${escapeHtml(image.image_url)}" alt="Imagem do post" />
              `;
              if (mode === "image_review") {
                workflowHtml += `
                  <div class="workflow-actions">
                    <button type="button" class="wf-btn wf-btn-approve" onclick="approveImage()">Aprovar imagem</button>
                    <button type="button" class="wf-btn wf-btn-image" onclick="regenerateImage()">Regenerar imagem</button>
                  </div>
                `;
              }
              workflowHtml += `</div>`;
            }

            let redirectHtml = "";
            if (data.ready_to_route && data.agent_url && data.agent_name) {
              const agentLabel = escapeHtml(data.agent_name);
              redirectHtml = `
                <div class="workflow-actions" style="margin-top:12px">
                  <a class="forward-btn" href="${escapeHtml(data.agent_url)}">Ir para ${agentLabel}</a>
                </div>
              `;
            }

            const hasWorkflowContent = Boolean(
              (plan && plan.trim())
              || workflowHtml.trim()
              || redirectHtml.trim()
            );
            const showPanel = hasWorkflowContent
              || mode === "followed_feed"
              || mode === "engagement_review"
              || mode === "engagement_batch_review"
              || mode === "daily_digest_review"
              || (mode !== "idle" && mode !== "planning" && mode !== "strategy_brief");
            if (!showPanel) {
              result.innerHTML = "";
              if (!linkedinContext) setDirectorLinkedinBarVisible(false);
              return;
            }

            result.innerHTML = `
              <h3>Painel do Diretor</h3>
              ${plan}
              <p><strong>Etapa:</strong> ${escapeHtml(stageLabel)}</p>
              ${stageHint ? `<p class="stage-hint">${escapeHtml(stageHint)}</p>` : ""}
              ${redirectHtml}
              ${workflowHtml}
            `;
            attachDirectorPanelCollapseListeners(result);
          }

          window.approveStrategy = () => directorAction("approve_strategy", {}, "Aprovo a estratégia.");
          window.startExecution = () => directorAction("start_execution", {}, "Iniciar execução.");
          window.approveCopy = () => directorAction("approve_copy", {}, "Aprovo a copy.");
          window.saveCopyEdit = () => {
            const el = document.getElementById("workflowPostBody");
            const body = el ? el.value.trim() : "";
            directorAction("edit_copy", { body }, "Editei a copy.");
          };
          window.generateImage = () => directorAction("generate_image", {}, "Gera a imagem.");
          window.skipImage = () => directorAction("skip_image", {}, "Sem imagem.");
          window.approveImage = () => directorAction("approve_image", {}, "Aprovo a imagem.");
          window.regenerateImage = () => {
            const instr = window.prompt("Instruções para a nova imagem (opcional):") || "";
            directorAction("regenerate_image", { edit_instructions: instr }, "Regenerar imagem.");
          };
          window.selectCalendarPost = (postId) => directorAction(
            "select_post",
            { post_id: postId },
            "Quero rever este post do calendário."
          );
          window.regenerateLinkedinPost = () => {
            const instr = window.prompt("O que queres mudar neste post? (opcional)") || "";
            directorAction("regenerate_linkedin_post", { edit_instructions: instr }, "Refazer post LinkedIn.");
          };
          window.approveOptimization = () => directorAction(
            "approve_optimization",
            {},
            "Aplico as optimizações à estratégia."
          );
          window.dismissOptimization = () => directorAction(
            "dismiss_optimization",
            {},
            "Manter a estratégia actual."
          );
          window.connectDirectorLinkedinPublish = connectDirectorLinkedinPublish;
          window.clearDirectorPublishAuth = clearDirectorPublishAuth;
          window.directorPublishCurrentPost = directorPublishCurrentPost;
          window.skipPublish = () => directorAction("skip_publish", {}, "Avançar sem publicar agora.");
          window.rejectEngagement = () => directorAction("reject_engagement", {}, "Reprovo este comentário.");
          window.selectFollowedPost = (postId) => directorAction(
            "select_followed_post",
            { post_id: postId },
            "Quero um comentário para esta publicação."
          );
          window.promptAddFollowedProfile = () => {
            const url = window.prompt("URL do perfil LinkedIn que segues (ex.: https://linkedin.com/in/nome):") || "";
            if (!url.trim()) return;
            const name = window.prompt("Nome para mostrar (opcional):") || "";
            directorAction("add_followed_profile", {
              profile_url: url.trim(),
              display_name: name.trim() || undefined,
            }, "Adicionar perfil seguido.");
          };
          window.removeFollowedProfile = (profileId) => directorAction(
            "remove_followed_profile",
            { profile_id: profileId },
            "Remover perfil da lista."
          );
          window.suggestFollowedProfiles = () => directorAction(
            "suggest_followed_profiles",
            { count: 5 },
            "Sugerir perfis LinkedIn alinhados com a minha estratégia e ICP."
          );
          window.acceptFollowedSuggestion = (suggestionId) => directorAction(
            "accept_followed_suggestions",
            { suggestion_ids: [suggestionId] },
            "Adicionar este perfil sugerido."
          );
          window.acceptAllFollowedSuggestions = () => directorAction(
            "accept_followed_suggestions",
            { accept_all: true },
            "Adicionar todas as sugestões de perfis."
          );
          window.dismissFollowedSuggestion = (suggestionId) => directorAction(
            "dismiss_followed_suggestion",
            { suggestion_id: suggestionId },
            "Ignorar sugestão de perfil."
          );
          async function syncLinkedInNetworkFeed() {
            if (!directorLinkedinSession || !directorLinkedinSession.provider_token) {
              alert("Liga o LinkedIn primeiro (login no painel) para tentar importar o feed.");
              return;
            }
            const hint = document.getElementById("linkedinProfileHint");
            if (hint) hint.textContent = "A tentar importar o teu feed LinkedIn…";
            try {
              const resp = await fetch("/agents/linkedin/network-feed", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  linkedin_provider_token: directorLinkedinSession.provider_token,
                }),
              });
              const data = await resp.json();
              if (hint) hint.textContent = "";
              if (resp.ok && data.success && Array.isArray(data.posts) && data.posts.length) {
                await directorAction("merge_followed_posts", {
                  posts: data.posts,
                  auto_add_profiles: true,
                  feed_message: data.message || "Feed importado.",
                }, "Importar publicações do feed LinkedIn.");
                return;
              }
              const msg = (data && data.message) || "A LinkedIn não autorizou ler o feed desta app.";
              alert(msg + "\\n\\nAdiciona manualmente o URL de perfis que segues (botão «+ Adicionar perfil»).");
            } catch (e) {
              if (hint) hint.textContent = "";
              alert("Não foi possível importar o feed. Adiciona perfis manualmente.");
            }
          }
          window.syncLinkedInNetworkFeed = syncLinkedInNetworkFeed;
          async function refreshFollowedPosts() {
            if (!workflowState) workflowState = {};
            const profiles = workflowState.followed_profiles || [];
            if (!profiles.length) {
              alert("Adiciona pelo menos um perfil LinkedIn ou tenta «Importar do meu feed».");
              return;
            }
            const hint = document.getElementById("linkedinProfileHint");
            if (hint) hint.textContent = "A recolher publicações dos perfis guardados…";
            const collected = [];
            for (const prof of profiles) {
              const url = prof.profile_url;
              if (!url) continue;
              try {
                const resp = await fetch("/agents/linkedin/followed-profile-posts", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ profile_url: url }),
                });
                const data = await resp.json();
                if (resp.ok && Array.isArray(data.posts)) {
                  collected.push(...data.posts);
                }
              } catch (e) {}
            }
            if (hint) hint.textContent = "";
            await directorAction("merge_followed_posts", { posts: collected }, "Actualizei as publicações dos perfis guardados.");
          }
          window.refreshFollowedPosts = refreshFollowedPosts;
          window.approveEngagement = () => {
            const el = document.getElementById("directorEngagementBody");
            const comment_body = el ? el.value.trim() : "";
            directorAction("approve_engagement", { comment_body }, "Aprovo o comentário sugerido.");
          };
          window.regenerateEngagement = () => {
            const instr = window.prompt("O que queres mudar no comentário? (opcional)") || "";
            directorAction("regenerate_engagement", { edit_instructions: instr }, "Refazer comentário.");
          };
          window.loadFollowedProfilesFromDatabase = loadFollowedProfilesFromDatabase;
          window.generateEngagementBatch = () => directorAction(
            "generate_engagement_batch",
            { count: 10 },
            "Gera um lote de 10 comentários para publicações na fila."
          );
          window.approveEngagementBatch = () => {
            const cards = document.querySelectorAll("[data-batch-comment-id]");
            const approved_ids = [];
            const items = [];
            cards.forEach((card) => {
              const id = card.getAttribute("data-batch-comment-id");
              const cb = card.querySelector(".batch-select");
              const ta = card.querySelector("textarea");
              if (!id || !cb || !cb.checked) return;
              approved_ids.push(id);
              items.push({ id, comment_body: ta ? ta.value.trim() : "" });
            });
            if (!approved_ids.length) {
              alert("Selecciona pelo menos um comentário.");
              return;
            }
            directorAction(
              "approve_engagement_batch",
              { approved_ids, items },
              "Aprovo os comentários seleccionados do lote."
            );
          };
          window.dismissEngagementBatch = () => directorAction(
            "dismiss_engagement_batch",
            {},
            "Descartar o lote de comentários."
          );
          window.copyApprovedBatchToClipboard = async () => {
            const cards = document.querySelectorAll("[data-batch-comment-id]");
            const parts = [];
            cards.forEach((card) => {
              const cb = card.querySelector(".batch-select");
              const ta = card.querySelector("textarea");
              if (!cb || !cb.checked || !ta) return;
              const label = card.querySelector(".cal-meta");
              const text = ta.value.trim();
              if (!text) return;
              parts.push(`--- ${label ? label.textContent : "Comentário"} ---\\n${text}`);
            });
            if (!parts.length) {
              alert("Selecciona comentários para copiar.");
              return;
            }
            try {
              await navigator.clipboard.writeText(parts.join("\\n\\n"));
              alert("Comentários copiados — cola cada um na publicação respectiva no LinkedIn.");
            } catch (e) {
              alert("Não foi possível copiar automaticamente.");
            }
          };

          window.copyEngagementToClipboard = async () => {
            const el = document.getElementById("directorEngagementBody");
            const text = el ? el.value.trim() : "";
            if (!text) return;
            try {
              await navigator.clipboard.writeText(text);
              alert("Comentário copiado — cola no LinkedIn.");
            } catch (e) {
              alert("Não foi possível copiar automaticamente. Selecciona e copia o texto.");
            }
          };

          async function sendMessage() {
            const content = chatInput.value.trim();
            if (!content) return;
            addMessage("user", content);
            chatInput.value = "";
            await callDirector(buildPayload());
          }

          function resetChat() {
            messages.length = 0;
            workflowState = null;
            saveWorkflowState();
            chatLog.innerHTML = "";
            result.innerHTML = "";
            setDirectorLinkedinBarVisible(false);
            addMessage("assistant", DIRECTOR_WELCOME);
          }

          loadWorkflowState();
          setDirectorLinkedinBarVisible(false);
          addMessage("assistant", DIRECTOR_WELCOME);
          showSavedSessionHint(workflowState);
          (async function bootstrapDirectorPage() {
            await initDirectorSupabaseFromUrl();
            await refreshDirectorLinkedinAuth();
            await processDirectorPublishOAuthReturn();
          })();
          chatInput.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              sendMessage();
            }
          });
        </script>
      </body>
    </html>
    """
    return (
        html.replace("___SUPABASE_URL_JSON___", json.dumps(sup_url))
        .replace("___SUPABASE_ANON_JSON___", json.dumps(sup_anon))
    )


@app.post("/chat")
def chat(payload: ChatRequest) -> Dict[str, object]:
    """Processa pedido único e orquestra a equipa de marketing do Diretor.

    Recebe uma instrução, mobiliza os agentes relevantes internamente e
    devolve resposta agregada com tarefas por especialista.

    Argumentos:
        payload: Objeto validado contendo o texto do utilizador.

    Retorno:
        Dicionário com `reply`, `orchestration_mode`, `execution_plan`,
        `team_tasks`, `agents_involved` e campos legados de roteamento.
    """

    try:
        decision = director.orchestrate_chat(
            messages=[{"role": "user", "content": payload.user_input}],
            language="pt-PT",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Falha ao orquestrar equipa: {exc!s}") from exc

    agents = decision.get("agents_involved") or []
    agent_name = decision.get("agent_name") or (agents[0] if len(agents) == 1 else None)
    return {
        "reply": decision.get("reply"),
        "orchestration_mode": decision.get("orchestration_mode"),
        "execution_plan": decision.get("execution_plan"),
        "team_tasks": decision.get("team_tasks", []),
        "agents_involved": agents,
        "agent_name": agent_name,
        "action_plan": [t.get("summary", "")[:200] for t in decision.get("team_tasks", []) if t.get("summary")],
        "justification": decision.get("execution_plan") or "",
        "agent_url": _agent_page_url(str(agent_name)) if agent_name else None,
        "ready_to_route": decision.get("ready_to_route", False),
    }


@app.post("/internal/cron/director-daily-digest")
def cron_director_daily_digest(request: Request) -> Dict[str, object]:
    """Endpoint para o cron Render (lembrete de digest diário).

    O digest completo corre na primeira visita do utilizador ao Diretor
    (estado no browser). Este endpoint valida o ``CRON_SECRET`` e regista
    a execução agendada.

    Argumentos:
        request: Pedido HTTP com cabeçalho ``Authorization: Bearer <CRON_SECRET>``.

    Retorno:
        Estado ``ok`` e nota sobre o fluxo client-side.

    Raises:
        HTTPException: 503 se ``CRON_SECRET`` não estiver configurado; 403 se inválido.
    """

    secret = os.getenv("CRON_SECRET", "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="CRON_SECRET não configurado no servidor.",
        )
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {secret}":
        raise HTTPException(status_code=403, detail="Não autorizado.")
    return {
        "ok": True,
        "message": (
            "Cron diário activo. O briefing corre quando o utilizador abre o Diretor "
            "(uma vez por dia, se houver estratégia aprovada)."
        ),
    }


@app.post("/director/chat-reply")
def director_chat_reply(payload: DirectorChatTurnRequest) -> Dict[str, object]:
    """Gera resposta do Diretor orquestrando a equipa na mesma conversa.

    O endpoint recebe o histórico, planeia tarefas para um ou vários agentes,
    executa-os internamente quando possível e devolve uma resposta agregada.

    Argumentos:
        payload: Histórico validado da chatroom e idioma pretendido.

    Retorno:
        Dicionário com `reply`, `orchestration_mode`, `execution_plan`,
        `team_tasks`, `agents_involved` e campos legados de encaminhamento.

    Raises:
        HTTPException: 503 quando a chave OpenAI não está configurada;
            502 quando a orquestração falha.
    """

    try:
        history = [{"role": item.role, "content": item.content} for item in payload.messages]
        decision = director.generate_chat_reply(
            messages=history,
            language=payload.language,
            workflow_state=payload.workflow_state,
            user_action=payload.user_action,
            action_payload=payload.action_payload,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — expor mensagem genérica ao cliente
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao contactar OpenAI: {exc!s}",
        ) from exc

    agents = decision.get("agents_involved") or []
    agent_name = decision.get("agent_name") or (agents[0] if len(agents) == 1 else None)
    agent_url = _agent_page_url(str(agent_name)) if agent_name else None
    return {
        "reply": str(decision.get("reply") or "Percebi. Explica-me um pouco mais para eu orientar-te melhor."),
        "orchestration_mode": decision.get("orchestration_mode", "planning"),
        "execution_plan": decision.get("execution_plan", ""),
        "team_tasks": decision.get("team_tasks", []),
        "agents_involved": agents,
        "ready_to_route": bool(decision.get("ready_to_route", False)),
        "agent_name": agent_name,
        "agent_url": agent_url,
        "workflow_state": decision.get("workflow_state"),
        "deliverables": decision.get("deliverables"),
        "pending_actions": decision.get("pending_actions", []),
    }


@app.post("/agents/copywriter/generate")
def copywriter_generate(payload: CopywriterRequest) -> Dict[str, object]:
    """Gera copy de marketing com o Agente Copywriter (OpenAI).

    Valida o brief, verifica se existe `OPENAI_API_KEY` e devolve headlines,
    texto principal e CTAs estruturados.

    Argumentos:
        payload: Brief obrigatório e opcionalmente tom e idioma.

    Retorno:
        Dicionário com `headlines`, `primary_text`, `ctas` e `notes` (opcional).

    Raises:
        HTTPException: 503 se a API key não estiver configurada; 502 se a
            geração falhar no cliente OpenAI.
    """

    if payload.min_words and payload.max_words and payload.min_words > payload.max_words:
        raise HTTPException(
            status_code=422,
            detail="`min_words` não pode ser maior do que `max_words`.",
        )

    if not copywriter_agent.is_configured():
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY nao configurada no servidor. Define a variavel de ambiente e reinicia o uvicorn.",
        )
    try:
        structured_brief = _build_copywriter_brief(payload)
        return copywriter_agent.generate_marketing_copy(
            brief=structured_brief,
            tone=payload.tone,
            language=payload.language,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — expor mensagem genérica ao cliente
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao contactar OpenAI: {exc!s}",
        ) from exc


@app.post("/agents/copywriter/chat-generate")
def copywriter_chat_generate(payload: CopywriterChatRequest) -> Dict[str, object]:
    """Gera copy final com base no histórico da chatroom do Copywriter.

    O endpoint recebe as mensagens acumuladas da conversa, transforma-as num
    brief único e executa a geração com OpenAI. O objetivo é que a resposta
    final reflita exatamente o contexto construído na chatroom antes do clique
    em "Gerar copy final".

    Argumentos:
        payload: Histórico validado da conversa e parâmetros finais de geração.

    Retorno:
        Dicionário com `main_text_variations`, `headlines`, `ctas`,
        `improvement_suggestions`, `primary_text` e `notes`.

    Raises:
        HTTPException: 422 quando não há conteúdo útil no histórico;
            503 quando a API key não está configurada; 502 quando a OpenAI falha.
    """

    if not copywriter_agent.is_configured():
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY nao configurada no servidor. Define a variavel de ambiente e reinicia o uvicorn.",
        )

    chat_brief = _build_copywriter_chat_brief(payload)
    if len(chat_brief.strip()) < 20:
        raise HTTPException(
            status_code=422,
            detail="A conversa ainda não tem conteúdo suficiente para gerar a copy.",
        )

    try:
        response = copywriter_agent.generate_marketing_copy(
            brief=chat_brief,
            tone=payload.tone,
            language=payload.language,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — expor mensagem genérica ao cliente
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao contactar OpenAI: {exc!s}",
        ) from exc

    response["conversation_turns"] = len(payload.messages)
    response["source"] = "copywriter-chatroom"
    return response


@app.post("/agents/copywriter/chat-reply")
def copywriter_chat_reply(payload: CopywriterChatTurnRequest) -> Dict[str, str]:
    """Gera a próxima resposta autónoma do Agente Copywriter na chatroom.

    O endpoint usa o histórico completo de mensagens para pedir ao LLM uma
    resposta contextual, coerente com a pergunta mais recente do utilizador e
    com os objetivos já discutidos. Isto substitui a lógica de perguntas fixas
    por conversação dinâmica conduzida pelo modelo.

    Argumentos:
        payload: Histórico da chatroom e preferências de idioma/tom.

    Retorno:
        Dicionário com a chave `reply`, contendo a resposta textual do agente.

    Raises:
        HTTPException: 503 quando a chave OpenAI não está configurada;
            502 quando a geração da resposta falha no cliente OpenAI.
    """

    if not copywriter_agent.is_configured():
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY nao configurada no servidor. Define a variavel de ambiente e reinicia o uvicorn.",
        )

    try:
        history = [{"role": item.role, "content": item.content} for item in payload.messages]
        reply = copywriter_agent.generate_chat_reply(
            messages=history,
            tone=payload.tone,
            language=payload.language,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — expor mensagem genérica ao cliente
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao contactar OpenAI: {exc!s}",
        ) from exc

    return {"reply": reply or "Percebi. Podes dar-me mais contexto para eu refinar a resposta?"}


@app.post("/agents/social-media/chat-reply")
def social_media_chat_reply(payload: SocialMediaChatTurnRequest) -> Dict[str, str]:
    """Gera a próxima resposta do Agente de Redes Sociais na chatroom.

    Este endpoint mantém a conversa focada em Instagram e recolhe dados úteis
    para análise acionável de crescimento e engagement.

    Argumentos:
        payload: Histórico da conversa e idioma preferido.

    Retorno:
        Dicionário com a chave `reply` para o próximo turno da chatroom.

    Raises:
        HTTPException: 503 quando a chave OpenAI não está configurada;
            502 quando a geração da resposta falha no cliente OpenAI.
    """

    if not social_media_agent.is_configured():
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY nao configurada no servidor. Define a variavel de ambiente e reinicia o uvicorn.",
        )

    try:
        history = [{"role": item.role, "content": item.content} for item in payload.messages]
        reply = social_media_agent.generate_chat_reply(
            messages=history,
            language=payload.language,
            platform=payload.platform,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao contactar OpenAI: {exc!s}",
        ) from exc

    return {
        "reply": reply
        or "Percebi. Partilha dados concretos de seguidores, engagement e formatos para eu avançar com precisão."
    }


@app.post("/agents/social-media/chat-analyze")
def social_media_chat_analyze(payload: SocialMediaAnalysisRequest) -> Dict[str, Any]:
    """Gera análise estruturada de Instagram com secções orientadas à execução.

    O endpoint cruza a conversa da chatroom com os dados estruturados enviados
    e devolve um output padronizado para tomada de decisão no MVP.

    Argumentos:
        payload: Histórico da conversa, dados estruturados e idioma.

    Retorno:
        Dicionário com insights, problemas, oportunidades, ações prioritárias,
        ideias de conteúdo e plano de crescimento de curto prazo.

    Raises:
        HTTPException: 503 quando a chave OpenAI não está configurada;
            502 quando a análise falha no cliente OpenAI.
    """

    if not social_media_agent.is_configured():
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY nao configurada no servidor. Define a variavel de ambiente e reinicia o uvicorn.",
        )

    try:
        history = [{"role": item.role, "content": item.content} for item in payload.messages]
        response = social_media_agent.analyze_instagram_data(
            messages=history,
            instagram_data=payload.instagram_data,
            language=payload.language,
            platform=payload.platform,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao processar análise de Instagram: {exc!s}",
        ) from exc

    response["source"] = "social-media-chatroom"
    response["conversation_turns"] = len(payload.messages)
    return response


@app.post("/agents/linkedin/resolve-profile-url")
def linkedin_resolve_profile_url(payload: LinkedInResolveProfileRequest) -> Dict[str, Any]:
    """Resolve o URL público LinkedIn do utilizador autenticado (para preencher a UI).

    Argumentos:
        payload: Tokens da sessão Supabase e opcionalmente ``provider_token`` LinkedIn.

    Retorno:
        ``{"profile_url": "https://www.linkedin.com/in/..."}``.

    Raises:
        HTTPException: 401 sessão inválida; 422 URL não encontrado.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    if not sup_url or not sup_anon:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_URL / SUPABASE_ANON_KEY não configurados no servidor.",
        )
    access_tok = payload.supabase_access_token.strip()
    try:
        user = fetch_supabase_auth_user(access_tok, sup_url, sup_anon)
    except error.HTTPError as exc:
        raise HTTPException(status_code=401, detail="Sessão Supabase inválida ou expirada.") from exc
    except (error.URLError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao validar sessão: {exc!s}") from exc

    provider_tok = (payload.linkedin_provider_token or "").strip() or None
    stored_url = (payload.stored_linkedin_profile_url or "").strip() or None
    id_tok = (payload.linkedin_id_token or "").strip() or None
    db_url = _linkedin_profile_url_from_database(access_tok)
    profile_url = _resolve_authenticated_linkedin_profile_url(
        user,
        provider_tok,
        stored_profile_url=stored_url,
        database_profile_url=db_url,
        id_token=id_tok,
    )
    if not profile_url:
        raise HTTPException(
            status_code=422,
            detail=(
                "Não foi possível obter o URL do perfil a partir da sessão. "
                "Cola o URL público do LinkedIn na caixa (ex.: https://www.linkedin.com/in/o-teu-nome/) "
                "— na primeira vez é necessário; depois fica guardado na base de dados."
            ),
        )
    try:
        _assert_linkedin_profile_url_usable(profile_url, user)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    saved_db = False
    if profile_url != db_url:
        saved_db = _save_linkedin_profile_to_database(access_tok, user, profile_url)
    return {
        "profile_url": profile_url,
        "ok": True,
        "from_database": bool(db_url and profile_url == db_url),
        "saved_to_database": saved_db,
    }


@app.post("/agents/linkedin/stored-profile")
def linkedin_stored_profile(payload: LinkedInStoredProfileRequest) -> Dict[str, Any]:
    """Lê ou grava o URL LinkedIn do utilizador na base de dados Supabase.

    Sem ``profile_url`` no body: devolve o URL associado ao login.
    Com ``profile_url``: faz upsert (útil na 1.ª configuração manual).

    Argumentos:
        payload: Token de sessão e opcionalmente URL a guardar.

    Retorno:
        ``profile_url``, ``from_database``, ``saved_to_database``.

    Raises:
        HTTPException: 401 sessão inválida; 404 sem registo (só em leitura).
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    if not sup_url or not sup_anon:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_URL / SUPABASE_ANON_KEY não configurados no servidor.",
        )
    access_tok = payload.supabase_access_token.strip()
    try:
        user = fetch_supabase_auth_user(access_tok, sup_url, sup_anon)
    except error.HTTPError as exc:
        raise HTTPException(status_code=401, detail="Sessão Supabase inválida ou expirada.") from exc
    except (error.URLError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao validar sessão: {exc!s}") from exc

    to_save = (payload.profile_url or "").strip()
    if to_save:
        try:
            normalized = _normalize_linkedin_public_profile_input(to_save)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        _assert_linkedin_profile_url_usable(normalized, user)
        saved = _save_linkedin_profile_to_database(
            access_tok,
            user,
            normalized,
            display_name=payload.display_name,
        )
        if not saved:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Não foi possível guardar o perfil na base de dados. "
                    "Executa migrations/001_user_linkedin_profiles.sql no Supabase."
                ),
            )
        return {"profile_url": normalized, "from_database": False, "saved_to_database": True, "ok": True}

    db_url = _linkedin_profile_url_from_database(access_tok)
    if not db_url:
        raise HTTPException(
            status_code=404,
            detail="Ainda não há perfil LinkedIn associado a esta conta. Cola o URL e guarda na primeira análise.",
        )
    return {"profile_url": db_url, "from_database": True, "saved_to_database": False, "ok": True}


def _linkedin_calendar_posts_from_database(access_token: str) -> Optional[Dict[str, Any]]:
    """Lê posts do calendário LinkedIn na Supabase para a sessão actual.

    Argumentos:
        access_token: JWT ``access_token`` Supabase.

    Retorno:
        Dict com ``week_start`` e ``posts``, ou ``None``.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    if not access_token or not sup_url or not sup_anon:
        return None
    try:
        return fetch_user_linkedin_calendar_posts_from_database(access_token, sup_url, sup_anon)
    except (error.HTTPError, error.URLError, OSError, json.JSONDecodeError, TypeError):
        return None


def _save_linkedin_calendar_posts_to_database(
    access_token: str,
    user: Dict[str, Any],
    posts: List[Dict[str, Any]],
    *,
    week_start: Optional[str] = None,
) -> bool:
    """Persiste posts do calendário semanal na Supabase.

    Argumentos:
        access_token: JWT da sessão.
        user: Utilizador GoTrue.
        posts: Lista de posts.
        week_start: Primeiro dia da semana (ISO).

    Retorno:
        ``True`` se gravado com sucesso.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    uid = str((user or {}).get("id") or "").strip()
    if not access_token or not sup_url or not sup_anon or not uid:
        return False
    cleaned = normalize_calendar_posts_for_storage(posts)
    try:
        return upsert_user_linkedin_calendar_posts_to_database(
            access_token,
            sup_url,
            sup_anon,
            uid,
            cleaned,
            week_start=week_start,
        )
    except (error.HTTPError, error.URLError, OSError, TypeError):
        return False


@app.post("/agents/linkedin/calendar-posts/load")
def linkedin_calendar_posts_load(payload: LinkedInCalendarPostsLoadRequest) -> Dict[str, Any]:
    """Carrega posts do calendário semanal guardados para o utilizador autenticado.

    Argumentos:
        payload: Token de sessão Supabase.

    Retorno:
        ``posts``, ``week_start``, ``found``, ``count``.

    Raises:
        HTTPException: 401 sessão inválida.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    if not sup_url or not sup_anon:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_URL / SUPABASE_ANON_KEY não configurados no servidor.",
        )
    access_tok = payload.supabase_access_token.strip()
    try:
        fetch_supabase_auth_user(access_tok, sup_url, sup_anon)
    except error.HTTPError as exc:
        raise HTTPException(status_code=401, detail="Sessão Supabase inválida ou expirada.") from exc
    except (error.URLError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao validar sessão: {exc!s}") from exc

    row = _linkedin_calendar_posts_from_database(access_tok)
    if not row:
        return {"found": False, "posts": [], "week_start": None, "count": 0}
    posts = row.get("posts") if isinstance(row.get("posts"), list) else []
    return {
        "found": len(posts) > 0,
        "posts": posts,
        "week_start": row.get("week_start"),
        "count": len(posts),
    }


@app.post("/agents/linkedin/calendar-posts/save")
def linkedin_calendar_posts_save(payload: LinkedInCalendarPostsSaveRequest) -> Dict[str, Any]:
    """Grava posts do calendário semanal na base de dados Supabase.

    Argumentos:
        payload: Token, lista de posts e opcionalmente ``week_start``.

    Retorno:
        ``ok``, ``saved_to_database``, ``count``.

    Raises:
        HTTPException: 401 sessão inválida; 502 falha ao gravar.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    if not sup_url or not sup_anon:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_URL / SUPABASE_ANON_KEY não configurados no servidor.",
        )
    access_tok = payload.supabase_access_token.strip()
    try:
        user = fetch_supabase_auth_user(access_tok, sup_url, sup_anon)
    except error.HTTPError as exc:
        raise HTTPException(status_code=401, detail="Sessão Supabase inválida ou expirada.") from exc
    except (error.URLError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao validar sessão: {exc!s}") from exc

    posts = payload.posts if isinstance(payload.posts, list) else []
    saved = _save_linkedin_calendar_posts_to_database(
        access_tok,
        user,
        posts,
        week_start=payload.week_start,
    )
    if not saved:
        raise HTTPException(
            status_code=502,
            detail=(
                "Não foi possível guardar o calendário na base de dados. "
                "Executa migrations/003_user_linkedin_calendar_posts.sql no Supabase."
            ),
        )
    cleaned = normalize_calendar_posts_for_storage(posts)
    return {"ok": True, "saved_to_database": True, "count": len(cleaned)}


def _linkedin_followed_profiles_from_database(access_token: str) -> Optional[List[Dict[str, Any]]]:
    """Lê perfis seguidos da BD para o token Supabase dado."""

    sup_url, sup_anon = get_supabase_public_credentials()
    if not sup_url or not sup_anon:
        return None
    try:
        return fetch_user_linkedin_followed_profiles_from_database(access_token, sup_url, sup_anon)
    except (error.HTTPError, error.URLError, OSError, TypeError):
        return None


def _save_linkedin_followed_profiles_to_database(
    access_token: str,
    user: Dict[str, Any],
    profiles: List[Dict[str, Any]],
) -> bool:
    """Grava perfis seguidos na Supabase."""

    sup_url, sup_anon = get_supabase_public_credentials()
    if not sup_url or not sup_anon:
        return False
    uid = str(user.get("id") or "").strip()
    if not uid:
        return False
    cleaned = normalize_followed_profiles_for_storage(profiles)
    try:
        return upsert_user_linkedin_followed_profiles_to_database(
            access_token,
            sup_url,
            sup_anon,
            uid,
            cleaned,
        )
    except (error.HTTPError, error.URLError, OSError, TypeError):
        return False


@app.post("/agents/linkedin/followed-profiles/load")
def linkedin_followed_profiles_load(payload: LinkedInFollowedProfilesLoadRequest) -> Dict[str, Any]:
    """Carrega perfis LinkedIn seguidos guardados para o utilizador autenticado.

    Argumentos:
        payload: Token de sessão Supabase.

    Retorno:
        ``profiles``, ``found``, ``count``.

    Raises:
        HTTPException: 401 sessão inválida.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    if not sup_url or not sup_anon:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_URL / SUPABASE_ANON_KEY não configurados no servidor.",
        )
    access_tok = payload.supabase_access_token.strip()
    try:
        fetch_supabase_auth_user(access_tok, sup_url, sup_anon)
    except error.HTTPError as exc:
        raise HTTPException(status_code=401, detail="Sessão Supabase inválida ou expirada.") from exc
    except (error.URLError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao validar sessão: {exc!s}") from exc

    profiles = _linkedin_followed_profiles_from_database(access_tok)
    if profiles is None:
        return {"found": False, "profiles": [], "count": 0}
    return {
        "found": len(profiles) > 0,
        "profiles": profiles,
        "count": len(profiles),
    }


@app.post("/agents/linkedin/followed-profiles/save")
def linkedin_followed_profiles_save(payload: LinkedInFollowedProfilesSaveRequest) -> Dict[str, Any]:
    """Grava perfis LinkedIn seguidos na base de dados Supabase.

    Argumentos:
        payload: Token e lista de perfis.

    Retorno:
        ``ok``, ``saved_to_database``, ``count``.

    Raises:
        HTTPException: 401 sessão inválida; 502 falha ao gravar.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    if not sup_url or not sup_anon:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_URL / SUPABASE_ANON_KEY não configurados no servidor.",
        )
    access_tok = payload.supabase_access_token.strip()
    try:
        user = fetch_supabase_auth_user(access_tok, sup_url, sup_anon)
    except error.HTTPError as exc:
        raise HTTPException(status_code=401, detail="Sessão Supabase inválida ou expirada.") from exc
    except (error.URLError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao validar sessão: {exc!s}") from exc

    profiles = payload.profiles if isinstance(payload.profiles, list) else []
    saved = _save_linkedin_followed_profiles_to_database(access_tok, user, profiles)
    if not saved:
        raise HTTPException(
            status_code=502,
            detail=(
                "Não foi possível guardar os perfis na base de dados. "
                "Executa migrations/006_user_linkedin_followed_profiles.sql no Supabase."
            ),
        )
    cleaned = normalize_followed_profiles_for_storage(profiles)
    return {"ok": True, "saved_to_database": True, "count": len(cleaned)}


def _slim_linkedin_profile_for_post_generation(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Remove dados Apify pesados antes de enviar análise/perfil ao modelo de posts."""

    if not isinstance(profile, dict):
        return {}
    slim = dict(profile)
    slim.pop("harvest_profile", None)
    enrichment = slim.get("apify_enrichment")
    if isinstance(enrichment, dict):
        slim["apify_enrichment"] = {
            k: v
            for k, v in enrichment.items()
            if k not in {"raw_posts", "posts_raw"}
        }
    recent = slim.get("recent_posts")
    if isinstance(recent, list) and len(recent) > 8:
        slim["recent_posts"] = recent[:8]
    return slim


def _slim_linkedin_analysis_for_post_generation(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Reduz o JSON da análise para geração de posts (menos tokens/latência)."""

    if not isinstance(analysis, dict):
        return {}
    keep_keys = (
        "linkedin_own_profile",
        "profile_url",
        "profile_username",
        "principais_insights",
        "problemas_identificados",
        "oportunidades",
        "acoes_prioritarias",
        "ideias_conteudo",
        "plano_crescimento_curto_prazo",
        "confianca_analise",
        "lacunas_de_dados",
        "public_profile_data",
    )
    slim = {key: analysis[key] for key in keep_keys if key in analysis}
    ppd = slim.get("public_profile_data")
    if isinstance(ppd, dict):
        slim["public_profile_data"] = _slim_linkedin_profile_for_post_generation(ppd)
    return slim

@app.post("/agents/linkedin/followed-profile-posts")
def linkedin_followed_profile_posts(payload: LinkedInFollowedProfilePostsRequest) -> Dict[str, Any]:
    """Recolhe publicações recentes de um perfil que o utilizador segue.

    Usado pelo Diretor para sugerir comentários em publicações de terceiros
    (não nas publicações do próprio utilizador).

    Argumentos:
        payload: URL do perfil LinkedIn.

    Retorno:
        ``{"profile_url", "display_name", "posts": [...]}`` para a fila do Diretor.

    Raises:
        HTTPException: 422 URL inválido; 503 sem Apify; 502 falha na recolha.
    """

    from agents.director_follow_feed import posts_from_apify_bundle, slug_from_linkedin_profile_url

    raw_url = str(payload.profile_url or "").strip()
    profile_url = canonicalize_linkedin_profile_url(raw_url) if raw_url else ""
    if not profile_url or "linkedin.com" not in profile_url.casefold():
        raise HTTPException(status_code=422, detail="URL LinkedIn inválido.")

    apify_token = os.getenv("APIFY_API_TOKEN", "").strip()
    if not apify_token:
        raise HTTPException(
            status_code=503,
            detail="APIFY_API_TOKEN em falta — necessário para recolher publicações de perfis seguidos.",
        )
    try:
        bundle = _fetch_linkedin_public_profile_with_apify(profile_url)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    display_name = slug_from_linkedin_profile_url(profile_url)
    posts = posts_from_apify_bundle(
        bundle,
        profile_url=profile_url,
        author_name=display_name,
        limit=5,
    )
    return {
        "profile_url": profile_url,
        "display_name": display_name,
        "posts": posts,
        "count": len(posts),
    }


@app.post("/agents/linkedin/network-feed")
def linkedin_network_feed(payload: LinkedInNetworkFeedRequest) -> Dict[str, Any]:
    """Tenta importar publicações do feed da rede LinkedIn (quem segues/ligações).

    A API oficial só funciona se a app LinkedIn tiver permissões alargadas;
    com login OIDC standard costuma falhar — nesse caso usa perfis manuais + Apify.

    Argumentos:
        payload: ``provider_token`` da sessão Supabase.

    Retorno:
        ``{success, posts, message, api_available, count}``.
    """

    from agents.linkedin_network_feed import fetch_linkedin_network_feed_posts

    result = fetch_linkedin_network_feed_posts(payload.linkedin_provider_token)
    posts = result.get("posts") if isinstance(result.get("posts"), list) else []
    return {
        "success": bool(result.get("success")),
        "posts": posts,
        "message": str(result.get("message") or ""),
        "api_available": bool(result.get("api_available")),
        "count": len(posts),
    }


@app.post("/agents/linkedin/generate-posts")
def linkedin_generate_posts(payload: LinkedInGeneratePostsRequest) -> Dict[str, Any]:
    """Gera posts LinkedIn prontos a publicar com base na análise do perfil.

    Argumentos:
        payload: Análise, dados do perfil e número de posts desejados.

    Retorno:
        ``{"posts": [...], "count": N}``.

    Raises:
        HTTPException: 503 sem OpenAI; 502 em falha do modelo.
    """

    if not social_media_agent.is_configured():
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY nao configurada no servidor.")
    analysis = _slim_linkedin_analysis_for_post_generation(
        payload.analysis if isinstance(payload.analysis, dict) else {}
    )
    if not analysis.get("linkedin_own_profile"):
        raise HTTPException(
            status_code=403,
            detail="Gerar posts só está disponível na Auto-análise do teu perfil LinkedIn.",
        )
    profile_data = _slim_linkedin_profile_for_post_generation(payload.public_profile_data)
    try:
        result = social_media_agent.generate_linkedin_posts_from_analysis(
            analysis,
            public_profile_data=profile_data,
            profile_url=payload.profile_url,
            count=payload.count,
            language=payload.language,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Falha ao gerar posts: {exc!s}") from exc
    posts = result.get("posts") if isinstance(result, dict) else []
    return {"posts": posts if isinstance(posts, list) else [], "count": len(posts)}


@app.post("/agents/linkedin/regenerate-post")
def linkedin_regenerate_post(payload: LinkedInRegeneratePostRequest) -> Dict[str, Any]:
    """Regera um post LinkedIn (botão Refazer ou após edição).

    Argumentos:
        payload: Post actual, análise e instruções opcionais do utilizador.

    Retorno:
        ``{"post": {...}}``.

    Raises:
        HTTPException: 503 sem OpenAI; 502 em falha do modelo.
    """

    if not social_media_agent.is_configured():
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY nao configurada no servidor.")
    analysis = payload.analysis if isinstance(payload.analysis, dict) else {}
    if not analysis.get("linkedin_own_profile"):
        raise HTTPException(
            status_code=403,
            detail="Refazer posts só está disponível na Auto-análise do teu perfil LinkedIn.",
        )
    try:
        result = social_media_agent.regenerate_linkedin_post(
            analysis,
            payload.post,
            public_profile_data=payload.public_profile_data,
            profile_url=payload.profile_url,
            edit_instructions=payload.edit_instructions,
            language=payload.language,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Falha ao refazer post: {exc!s}") from exc
    return result if isinstance(result, dict) else {"post": {}}


@app.post("/agents/linkedin/generate-post-image")
def linkedin_generate_post_image(payload: LinkedInGeneratePostImageRequest) -> Dict[str, str]:
    """Gera imagem visual alinhada ao texto de um post LinkedIn aprovado.

    Usa o agente Designer (OpenAI / Nano Banana) para criar uma ilustração
    coerente com o conteúdo do post, sem exigir chatroom prévia.

    Argumentos:
        payload: Post com texto e metadados; dimensão opcional da imagem.

    Retorno:
        Dicionário com ``image_url``, ``prompt_used`` e ``provider``.

    Raises:
        HTTPException: 422 sem texto; 503 sem APIs de imagem; 502 em falha.
    """

    post = payload.post if isinstance(payload.post, dict) else {}
    body = str(post.get("body") or "").strip()
    if not body or body == "(sem texto)":
        raise HTTPException(
            status_code=422,
            detail="O post não tem texto suficiente para gerar uma imagem.",
        )
    if not designer_agent.is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Geração de imagem indisponível: configure OPENAI_API_KEY ou "
                "NANO_BANANA_API_KEY no servidor."
            ),
        )
    try:
        return designer_agent.generate_image_for_linkedin_post(
            post,
            size=payload.size,
            edit_instructions=payload.edit_instructions,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao gerar imagem do post: {exc!s}",
        ) from exc


@app.get("/agents/linkedin/connect-publish")
def linkedin_connect_publish(
    request: Request,
    return_path: Optional[str] = None,
) -> RedirectResponse:
    """Inicia OAuth LinkedIn com ``w_member_social`` para publicar posts.

    O login Supabase (OIDC) não inclui permissão ``ugcPosts.CREATE``; este
    fluxo obtém um access token dedicado à publicação.

    Argumentos:
        request: Pedido HTTP (usa ``base_url`` para o redirect_uri).
        return_path: Caminho relativo para redirecionar após sucesso (ex. página
            do calendário com ``?cal_day=...``).

    Retorno:
        Redireccionamento para a página de autorização do LinkedIn.

    Raises:
        HTTPException: 503 se credenciais LinkedIn em falta.
    """

    if not linkedin_oauth_configured():
        raise HTTPException(
            status_code=503,
            detail="Define LINKEDIN_CLIENT_ID e LINKEDIN_CLIENT_SECRET no .env.",
        )
    default_perfil = str(os.getenv("LINKEDIN_PERFIL_PATH") or "/agentes/linkedin-perfil").strip()
    if not default_perfil.startswith("/") or "://" in default_perfil:
        default_perfil = "/agentes/linkedin-perfil"
    rp = (return_path or default_perfil).strip()
    if not rp.startswith("/") or "://" in rp:
        rp = default_perfil
    base = str(request.base_url).rstrip("/")
    try:
        url = create_publish_authorization_url(base_url=base, return_path=rp)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return RedirectResponse(url=url, status_code=302)


@app.get("/agents/linkedin/connect-publish/callback")
def linkedin_connect_publish_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
) -> HTMLResponse:
    """Callback OAuth: guarda o token de publicação no browser (sessionStorage).

    Argumentos:
        request: Pedido HTTP.
        code: Authorization code do LinkedIn.
        state: State CSRF.
        error: Erro opcional devolvido pelo LinkedIn.
        error_description: Descrição do erro LinkedIn.

    Retorno:
        Página HTML mínima que grava o token e redireciona para o agente.
    """

    default_perfil = str(os.getenv("LINKEDIN_PERFIL_PATH") or "/agentes/linkedin-perfil").strip()
    if not default_perfil.startswith("/") or "://" in default_perfil:
        default_perfil = "/agentes/linkedin-perfil"
    return_path = default_perfil
    if error:
        msg = error_description or error
        return HTMLResponse(
            _linkedin_publish_callback_html(
                success=False,
                message=f"LinkedIn recusou autorização: {msg}",
                return_path=return_path,
            ),
            status_code=400,
        )

    state_meta = pop_oauth_state(state or "")
    if not state_meta:
        return HTMLResponse(
            _linkedin_publish_callback_html(
                success=False,
                message="Sessão OAuth inválida ou expirada. Tenta outra vez.",
                return_path=return_path,
            ),
            status_code=400,
        )
    return_path = str(state_meta.get("return_path") or return_path)

    if not code:
        return HTMLResponse(
            _linkedin_publish_callback_html(
                success=False,
                message="Código de autorização em falta.",
                return_path=return_path,
            ),
            status_code=400,
        )

    base = str(request.base_url).rstrip("/")
    try:
        token_data = exchange_code_for_publish_token(code, base_url=base)
    except RuntimeError as exc:
        return HTMLResponse(
            _linkedin_publish_callback_html(
                success=False,
                message=str(exc),
                return_path=return_path,
            ),
            status_code=502,
        )

    return HTMLResponse(
        _linkedin_publish_callback_html(
            success=True,
            message="Publicação autorizada. A redirecionar…",
            return_path=return_path,
            access_token=token_data.get("access_token"),
            expires_in=token_data.get("expires_in"),
            person_urn=token_data.get("person_urn"),
        )
    )


def _linkedin_publish_callback_html(
    *,
    success: bool,
    message: str,
    return_path: str,
    access_token: Optional[str] = None,
    expires_in: Optional[int] = None,
    person_urn: Optional[str] = None,
) -> str:
    """Gera HTML do callback que persiste o token de publicação no sessionStorage.

    Argumentos:
        success: Se a autorização foi bem-sucedida.
        message: Mensagem para o utilizador.
        return_path: Caminho de retorno na app.
        access_token: Token com ``w_member_social``.
        expires_in: Segundos até expirar.
        person_urn: URN do membro LinkedIn.

    Retorno:
        Documento HTML completo.
    """

    token_js = json.dumps(access_token or "")
    urn_js = json.dumps(person_urn or "")
    expires_js = int(expires_in or 0)
    path_js = json.dumps(return_path)
    ok_flag = "true" if success else "false"
    return f"""<!doctype html>
<html lang="pt"><head><meta charset="utf-8"/><title>LinkedIn — publicação</title></head>
<body style="font-family:system-ui;background:#0f1117;color:#f4f6fb;padding:2rem">
<p id="msg">{message}</p>
<script>
(function() {{
  var ok = {ok_flag};
  var path = {path_js};
  if (ok) {{
    try {{
      sessionStorage.setItem("plataforma_linkedin_publish_token", {token_js});
      sessionStorage.setItem("plataforma_linkedin_publish_person_urn", {urn_js});
      sessionStorage.setItem("plataforma_linkedin_publish_expires_at",
        String(Date.now() + {expires_js} * 1000));
    }} catch (e) {{}}
    var sepOk = path.indexOf("?") >= 0 ? "&" : "?";
    window.location.replace(path + sepOk + "publish_connected=1");
  }} else {{
    setTimeout(function() {{
      var sepErr = path.indexOf("?") >= 0 ? "&" : "?";
      window.location.replace(path + sepErr + "publish_error=1");
    }}, 2500);
  }}
}})();
</script>
</body></html>"""


@app.post("/agents/linkedin/publish-auth/store")
def linkedin_publish_auth_store(payload: LinkedInPublishAuthStoreRequest) -> Dict[str, Any]:
    """Persiste a autorização OAuth de publicação LinkedIn do utilizador na Supabase.

    Chamado pelo browser após o callback OAuth, para não repetir o fluxo em cada
    publicação. O token fica associado ao ``user_id`` da sessão Supabase.

    Argumentos:
        payload: Sessão Supabase e token de publicação LinkedIn.

    Retorno:
        ``{"success": true}`` quando gravado com sucesso.

    Raises:
        HTTPException: 401 sessão inválida; 502 falha ao gravar.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    if not sup_url or not sup_anon:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_URL / SUPABASE_ANON_KEY não configurados no servidor.",
        )
    access_tok = payload.supabase_access_token.strip()
    try:
        user = fetch_supabase_auth_user(access_tok, sup_url, sup_anon)
    except error.HTTPError as exc:
        raise HTTPException(status_code=401, detail="Sessão Supabase inválida ou expirada.") from exc
    except (error.URLError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao validar sessão: {exc!s}") from exc

    uid = str(user.get("id") or "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Utilizador Supabase sem ID.")

    ok = upsert_user_linkedin_publish_oauth_to_database(
        access_tok,
        sup_url,
        sup_anon,
        uid,
        linkedin_access_token=payload.linkedin_publish_access_token.strip(),
        linkedin_person_urn=(payload.linkedin_person_urn or "").strip() or None,
        expires_in=payload.expires_in,
    )
    if not ok:
        raise HTTPException(
            status_code=502,
            detail=(
                "Não foi possível guardar a autorização. Executa a migration "
                "migrations/004_user_linkedin_publish_oauth.sql no Supabase."
            ),
        )
    return {"success": True}


@app.post("/agents/linkedin/publish-auth/status")
def linkedin_publish_auth_status(payload: LinkedInPublishAuthStatusRequest) -> Dict[str, Any]:
    """Indica se o utilizador já autorizou publicação no LinkedIn (sem expor o token).

    Argumentos:
        payload: JWT da sessão Supabase.

    Retorno:
        ``{"authorized": bool, "expires_at": ..., "authorized_at": ...}``.

    Raises:
        HTTPException: 401 sessão inválida.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    if not sup_url or not sup_anon:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_URL / SUPABASE_ANON_KEY não configurados no servidor.",
        )
    access_tok = payload.supabase_access_token.strip()
    try:
        user = fetch_supabase_auth_user(access_tok, sup_url, sup_anon)
    except error.HTTPError as exc:
        raise HTTPException(status_code=401, detail="Sessão Supabase inválida ou expirada.") from exc
    except (error.URLError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao validar sessão: {exc!s}") from exc

    uid = str(user.get("id") or "").strip()
    row = fetch_user_linkedin_publish_oauth_from_database(access_tok, sup_url, sup_anon)
    if row:
        stored_tok = str(row.get("linkedin_access_token") or "").strip()
        if stored_tok and not get_linkedin_person_urn(stored_tok):
            if uid:
                clear_user_linkedin_publish_oauth_from_database(
                    access_tok, sup_url, sup_anon, uid
                )
            row = None
    return publish_oauth_status_for_client(row)


@app.post("/agents/linkedin/publish-auth/clear")
def linkedin_publish_auth_clear(payload: LinkedInPublishAuthStatusRequest) -> Dict[str, Any]:
    """Apaga autorização de publicação LinkedIn (ex.: token revogado pelo utilizador).

    Argumentos:
        payload: JWT da sessão Supabase.

    Retorno:
        ``{"success": true}`` quando limpo ou já inexistente.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    if not sup_url or not sup_anon:
        raise HTTPException(status_code=503, detail="Supabase não configurado.")
    access_tok = payload.supabase_access_token.strip()
    try:
        user = fetch_supabase_auth_user(access_tok, sup_url, sup_anon)
    except error.HTTPError as exc:
        raise HTTPException(status_code=401, detail="Sessão Supabase inválida.") from exc
    uid = str(user.get("id") or "").strip()
    if uid:
        clear_user_linkedin_publish_oauth_from_database(access_tok, sup_url, sup_anon, uid)
    return {"success": True}


@app.post("/agents/linkedin/publish-post")
def linkedin_publish_post(payload: LinkedInPublishPostRequest) -> Dict[str, Any]:
    """Publica no LinkedIn o texto aprovado (e opcionalmente a imagem aprovada).

    Usa o ``provider_token`` OAuth da sessão Supabase para chamar a API UGC
    do LinkedIn na conta com que o utilizador fez login.

    Argumentos:
        payload: Sessão Supabase, post e modo ``include_image``.

    Retorno:
        ``{"success": true, "linkedin_post_urn": "..."}`` ou erro descritivo.

    Raises:
        HTTPException: 401 sem sessão/token LinkedIn; 422 validação; 502 falha API.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    if not sup_url or not sup_anon:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_URL / SUPABASE_ANON_KEY não configurados no servidor.",
        )
    access_tok = payload.supabase_access_token.strip()
    try:
        user = fetch_supabase_auth_user(access_tok, sup_url, sup_anon)
    except error.HTTPError as exc:
        raise HTTPException(status_code=401, detail="Sessão Supabase inválida ou expirada.") from exc
    except (error.URLError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao validar sessão: {exc!s}") from exc

    uid = str(user.get("id") or "").strip()
    oauth_row = fetch_user_linkedin_publish_oauth_from_database(access_tok, sup_url, sup_anon)
    if oauth_row:
        stored_tok = str(oauth_row.get("linkedin_access_token") or "").strip()
        if stored_tok and not get_linkedin_person_urn(stored_tok):
            if uid:
                clear_user_linkedin_publish_oauth_from_database(
                    access_tok, sup_url, sup_anon, uid
                )
            oauth_row = None

    publish_tok, person_urn = resolve_linkedin_publish_token_and_urn(
        client_token=(payload.linkedin_publish_access_token or "").strip(),
        client_person_urn=str(payload.linkedin_person_urn or "").strip(),
        oauth_row=oauth_row,
    )
    if not publish_tok:
        raise HTTPException(
            status_code=401,
            detail={
                "message": (
                    "Autorização de publicação em falta. Clica em «Autorizar publicação LinkedIn» "
                    "(permissão w_member_social — é separado do login de análise)."
                ),
                "need_reauth": True,
            },
        )
    access_token_for_api = publish_tok
    if not person_urn:
        person_urn = get_linkedin_person_urn(access_token_for_api) or ""

    post = payload.post if isinstance(payload.post, dict) else {}
    post_id = str(post.get("id") or "").strip()
    if not post_id:
        raise HTTPException(status_code=422, detail="Identificador do post em falta.")
    text = format_linkedin_post_text(post)
    if not text or text == "(sem texto)":
        raise HTTPException(status_code=422, detail="O post não tem texto aprovado para publicar.")

    image_url: Optional[str] = None
    if payload.include_image:
        image_url = str(post.get("generated_image_url") or "").strip() or None
        if not image_url:
            raise HTTPException(
                status_code=422,
                detail="Não há imagem aprovada para publicar. Gera e aprova a imagem primeiro.",
            )

    if not person_urn:
        raise HTTPException(
            status_code=401,
            detail={
                "message": (
                    "Não foi possível obter o URN do perfil LinkedIn. "
                    "Clica em «Reautorizar publicação LinkedIn»."
                ),
                "need_reauth": True,
            },
        )

    vis = payload.visibility.strip().upper()
    if vis not in ("PUBLIC", "CONNECTIONS"):
        vis = "PUBLIC"

    result = publish_to_linkedin(
        access_token_for_api,
        person_urn,
        text,
        image_url=image_url,
        visibility=vis,
    )
    if not result.get("success"):
        err = str(result.get("error") or "Falha ao publicar no LinkedIn.")
        token_revoked = bool(result.get("token_revoked"))
        if token_revoked and uid:
            clear_user_linkedin_publish_oauth_from_database(
                access_tok, sup_url, sup_anon, uid
            )
        status_code = 401 if token_revoked or "LinkedIn API 401" in err else 502
        if token_revoked:
            raise HTTPException(
                status_code=401,
                detail={"message": err, "need_reauth": True},
            )
        raise HTTPException(status_code=status_code, detail=err)
    return {
        "success": True,
        "linkedin_post_urn": result.get("linkedin_post_urn"),
        "published_with_image": bool(image_url),
        "post_id": post_id,
    }


@app.post("/agents/social-media/profile-analyze")
def social_media_profile_analyze(payload: SocialMediaProfileAnalysisRequest) -> Dict[str, Any]:
    """Gera análise a partir de identificador público (Instagram, LinkedIn, etc.).

    Para **Instagram**, resolve o @username, recolhe dados (Apify + fallback web)
    e chama o agente OpenAI. Para **LinkedIn**, com ``APIFY_API_TOKEN`` recolhe
    dados públicos via Apify (``APIFY_LINKEDIN_POSTS_ACTOR``, posts do perfil);
    Com sessão Supabase válida, resolve o URL do perfil autenticado (API
    LinkedIn + metadados OIDC), recolhe dados com Apify e analisa com OpenAI.

    Argumentos:
        payload: URL/username, plataforma, idioma e opcionalmente token Supabase.

    Retorno:
        Dicionário de análise com metadados da recolha executada.

    Raises:
        HTTPException: 422 quando o input do perfil é inválido; 503 quando OpenAI
            ou Supabase (para sessão) não estão configurados; 502 em falha Apify.
    """

    if not social_media_agent.is_configured():
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY nao configurada no servidor. Define a variavel de ambiente e reinicia o uvicorn.",
        )

    pl = normalize_social_platform(payload.platform)
    if pl == "instagram":
        username = _extract_instagram_username(payload.profile_input)
        if not username:
            raise HTTPException(
                status_code=422,
                detail="Input inválido. Usa um @username ou URL pública do Instagram.",
            )

        try:
            public_profile_data = _fetch_instagram_public_profile(username)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        history = [{"role": item.role, "content": item.content} for item in payload.messages]
        if not history:
            history = [
                {
                    "role": "user",
                    "content": (
                        f"Analisa o perfil @{username} com base nos dados públicos recolhidos e cria ações concretas de curto prazo."
                    ),
                }
            ]

        try:
            response = social_media_agent.analyze_instagram_data(
                messages=history,
                instagram_data=public_profile_data,
                language=payload.language,
                platform="instagram",
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=502,
                detail=f"Falha ao processar análise de perfil: {exc!s}",
            ) from exc

        response["source"] = "social-media-public-profile"
        response["profile_username"] = username
        response["public_profile_data"] = public_profile_data
        return response

    if pl == "linkedin":
        trimmed = payload.profile_input.strip()
        access_tok = (payload.supabase_access_token or "").strip()
        provider_tok = (payload.linkedin_provider_token or "").strip()
        stored_url = (payload.stored_linkedin_profile_url or "").strip() or None
        id_tok = (payload.linkedin_id_token or "").strip() or None
        profile_url: Optional[str] = None
        if access_tok:
            sup_url, sup_anon = get_supabase_public_credentials()
            if not sup_url or not sup_anon:
                raise HTTPException(
                    status_code=503,
                    detail="SUPABASE_URL / SUPABASE_ANON_KEY não configurados no servidor para validar a sessão.",
                )
            try:
                user = fetch_supabase_auth_user(access_tok, sup_url, sup_anon)
            except error.HTTPError as exc:
                raise HTTPException(
                    status_code=401,
                    detail="Sessão Supabase inválida ou expirada. Volta a iniciar sessão com LinkedIn.",
                ) from exc
            except (error.URLError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"Não foi possível validar a sessão Supabase: {exc!s}",
                ) from exc
            if trimmed:
                profile_url = canonicalize_linkedin_profile_url(trimmed)
                if not profile_url:
                    try:
                        profile_url = _normalize_linkedin_public_profile_input(trimmed)
                    except ValueError as exc:
                        raise HTTPException(
                            status_code=422,
                            detail=f"URL do perfil inválido: {exc!s}",
                        ) from exc
            elif payload.link_as_own_profile:
                db_url = _linkedin_profile_url_from_database(access_tok)
                profile_url = _resolve_authenticated_linkedin_profile_url(
                    user,
                    provider_tok or None,
                    stored_profile_url=stored_url,
                    database_profile_url=db_url,
                    id_token=id_tok,
                )
                if not profile_url:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            "Não foi possível obter o URL do teu perfil LinkedIn a partir da sessão. "
                            "Cola o URL em «O meu perfil LinkedIn» e guarda na base de dados, "
                            "ou usa o campo «Analisar outro perfil» com o URL completo."
                        ),
                    )
            else:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Cola o URL público do perfil que queres analisar "
                        "(campo «Analisar outro perfil»)."
                    ),
                )
            try:
                _assert_linkedin_profile_url_usable(profile_url, user)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if payload.link_as_own_profile:
                _save_linkedin_profile_to_database(access_tok, user, profile_url)
        elif trimmed:
            profile_url = canonicalize_linkedin_profile_url(trimmed)
            if not profile_url:
                try:
                    profile_url = _normalize_linkedin_public_profile_input(trimmed)
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
            try:
                _assert_linkedin_profile_url_usable(profile_url)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        else:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Inicia sessão com «Login LinkedIn (Supabase)» ou cola o URL público do LinkedIn."
                ),
            )

        apify_token = os.getenv("APIFY_API_TOKEN", "").strip()
        if apify_token:
            load_dotenv(BASE_DIR / ".env", override=True)
            actor_chain = _linkedin_apify_actor_chain_from_env()
            try:
                public_profile_data = _fetch_linkedin_public_profile_with_apify(profile_url)
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"{exc} "
                        f"(URL: {profile_url}; cadeia: {', '.join(actor_chain)}). "
                        "Preferir harvestapi/linkedin-profile-posts; dev_fusion exige aprovação "
                        "de permissões na conta Apify."
                    ),
                ) from exc
        else:
            public_profile_data = {
                "plataforma": pl,
                "perfil_input": profile_url,
                "nota": (
                    "APIFY_API_TOKEN não configurado; a análise IA usa só o URL. "
                    "Define APIFY_API_TOKEN e APIFY_LINKEDIN_POSTS_ACTOR=LQQIXN9Othf8f7R5n para dados via Apify."
                ),
            }

        username = profile_url.rstrip("/").rsplit("/", 1)[-1][:120]
        history = [{"role": item.role, "content": item.content} for item in payload.messages]
        if not history:
            history = [
                {
                    "role": "user",
                    "content": (
                        f"Análise de LinkedIn para o perfil público: {profile_url}. "
                        "Gera recomendações de curto prazo; lista lacunas quando faltarem métricas."
                    ),
                }
            ]

        try:
            response = social_media_agent.analyze_instagram_data(
                messages=history,
                instagram_data=public_profile_data,
                language=payload.language,
                platform=pl,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=502,
                detail=f"Falha ao processar análise de perfil: {exc!s}",
            ) from exc

        response = enrich_linkedin_analysis_metrics(
            response,
            public_profile_data,
            profile_url=profile_url,
        )
        response = apply_linkedin_harvest_overview_to_analysis(
            response,
            public_profile_data,
            profile_url=profile_url,
        )
        if isinstance(public_profile_data, dict) and public_profile_data.get("overview_source"):
            response["overview_data_source"] = public_profile_data.get("overview_source")
        response["source"] = "social-media-linkedin-apify" if apify_token else "social-media-linkedin-public"
        response["plataforma"] = pl
        response["plataforma_label"] = social_platform_label_pt(pl)
        response["profile_username"] = username
        response["profile_url"] = profile_url
        response["linkedin_page_kind"] = linkedin_page_kind_from_url(profile_url)
        response["linkedin_own_profile"] = bool(payload.link_as_own_profile)
        response["public_profile_data"] = public_profile_data
        if access_tok:
            response["authenticated_session"] = True
        return response

    trimmed = payload.profile_input.strip()
    if not trimmed:
        raise HTTPException(
            status_code=422,
            detail="Preenche o identificador ou URL do perfil para esta plataforma.",
        )
    history = [{"role": item.role, "content": item.content} for item in payload.messages]
    if not history:
        lbl = social_platform_label_pt(pl)
        history = [
            {
                "role": "user",
                "content": (
                    f"Análise de {lbl} para o identificador: {trimmed}. "
                    "Gera recomendações de curto prazo; lista lacunas de dados de forma explícita."
                ),
            }
        ]

    try:
        response = social_media_agent.analyze_instagram_data(
            messages=history,
            instagram_data=public_profile_data,
            language=payload.language,
            platform=pl,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao processar análise de perfil: {exc!s}",
        ) from exc

    response["source"] = "social-media-other-platform"
    response["profile_username"] = username
    response["public_profile_data"] = public_profile_data
    return response


@app.post("/agents/social-media/analyze")
def social_media_unified_analyze(payload: SocialMediaUnifiedAnalysisRequest) -> Dict[str, Any]:
    """Executa análise Instagram com perfil único e comparação temporal.

    Este endpoint recebe o perfil Instagram, recolhe dados pelo Apify Scraper,
    guarda snapshot local e compara evolução com snapshots anteriores
    (1 semana, 2 semanas e 1 mês). O pacote final segue para o agente IA para
    interpretar mudanças, causas prováveis e ações de melhoria.

    Argumentos:
        payload: Perfil Instagram, dados opcionais extra e idioma final.

    Retorno:
        Dicionário com análise estruturada, comparativos temporais e metadados.

    Raises:
        HTTPException: 422 quando o perfil é inválido; 503 quando OpenAI não
            está configurada; 502 quando a recolha no Apify falha.
    """

    if not social_media_agent.is_configured():
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY nao configurada no servidor. Define a variavel de ambiente e reinicia o uvicorn.",
        )

    pl_uni = normalize_social_platform(payload.platform)
    if pl_uni != "instagram":
        raise HTTPException(
            status_code=422,
            detail=(
                "A análise unificada com Apify e comparativos temporais está disponível apenas para Instagram. "
                "Para outras redes usa POST /agents/social-media/profile-analyze ou chat-analyze com métricas JSON."
            ),
        )

    profile_raw = str(payload.profile_input or "").strip()
    username = _extract_instagram_username(profile_raw)
    if not username:
        raise HTTPException(
            status_code=422,
            detail="`profile_input` inválido. Usa um @username ou URL pública do Instagram.",
        )

    connected_token = _instagram_auth_state.get("access_token", "").strip()
    connected_username = str(_instagram_auth_state.get("username", "")).strip().lower()
    should_use_authenticated = bool(connected_token and connected_username and connected_username == username.lower())

    if should_use_authenticated:
        try:
            profile_data = _fetch_authenticated_instagram_data(
                access_token=connected_token,
                ig_user_id=str(_instagram_auth_state.get("ig_user_id", "")).strip(),
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    else:
        try:
            profile_data = _fetch_instagram_public_profile(username)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    profile_username = str(profile_data.get("profile") or username).strip()
    snapshot = _build_social_snapshot(profile_username, profile_data)
    _save_social_snapshot(profile_username, snapshot)
    comparisons = _build_snapshot_comparisons(profile_username, snapshot)

    merged_data: Dict[str, Any] = {}
    merged_data.update(profile_data)
    manual_data = payload.instagram_data or {}
    if isinstance(manual_data, dict) and manual_data:
        merged_data.update(manual_data)
    merged_data["comparisons"] = comparisons
    if not should_use_authenticated:
        derived_public_metrics = _compute_public_instagram_metrics(merged_data)
        merged_data.update(derived_public_metrics)

    growth_one_week = ((comparisons.get("one_week") or {}).get("followers") or {}).get("delta")
    if growth_one_week is not None:
        merged_data["crescimento_seguidores_7d"] = growth_one_week

    user_prompt_context = (
        f"Analisa @{profile_username} com foco em evolução temporal: compara com 1 semana, "
        "2 semanas e 1 mês, identifica o que evoluiu e as causas prováveis dessa evolução."
    )
    history = [{"role": "user", "content": user_prompt_context}]
    try:
        response = social_media_agent.analyze_instagram_data(
            messages=history,
            instagram_data=merged_data,
            language=payload.language,
            platform="instagram",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao processar análise unificada: {exc!s}",
        ) from exc

    response["source"] = "social-media-unified-auth" if should_use_authenticated else "social-media-unified-public"
    response["profile_username"] = profile_username
    response["public_profile_data"] = merged_data
    response["comparisons"] = comparisons
    return response


@app.get("/agents/social-media/auth/start")
def social_media_auth_start() -> RedirectResponse:
    """Inicia o OAuth da Meta para autorização de análise completa.

    A função cria a URL de consentimento Meta com os scopes necessários para
    ler páginas e métricas de Instagram profissional. O utilizador é
    redirecionado para autenticar e autorizar a app.

    Argumentos:
        Nenhum.

    Retorno:
        `RedirectResponse` para a página de consentimento OAuth da Meta.

    Raises:
        HTTPException: 503 quando a app OAuth não está configurada no `.env`.
    """

    app_id = _get_env_setting("META_APP_ID")
    redirect_uri = _get_env_setting("META_REDIRECT_URI")
    if not app_id or not redirect_uri:
        raise HTTPException(
            status_code=503,
            detail="META_APP_ID e META_REDIRECT_URI têm de estar configurados no .env para login Instagram.",
        )
    _instagram_auth_state["last_error"] = ""

    scopes = ",".join(
        ["pages_show_list", "pages_read_engagement", "instagram_basic", "instagram_manage_insights"]
    )
    oauth_url = (
        f"{INSTAGRAM_OAUTH_AUTHORIZE_URL}?client_id={app_id}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        f"&scope={scopes}"
    )
    return RedirectResponse(url=oauth_url, status_code=302)


@app.get("/agents/social-media/auth/callback")
def social_media_auth_callback(code: str = "") -> RedirectResponse:
    """Processa callback OAuth e guarda token Instagram em memória.

    A função troca o `code` por `access_token`, tenta identificar a conta
    Instagram profissional associada e guarda esse contexto para análises
    autenticadas no MVP local.

    Argumentos:
        code: Código OAuth devolvido pela Meta na query string.

    Retorno:
        `RedirectResponse` de volta para a página do agente com indicação de
        sucesso/erro na query string.
    """

    if not code.strip():
        _instagram_auth_state["last_error"] = "missing_code"
        return RedirectResponse(url="/agentes/redes-sociais?auth=error&reason=missing_code", status_code=302)

    try:
        access_token = _exchange_meta_code_for_token(code)
        ig_context = _resolve_instagram_context_from_token(access_token)
    except RuntimeError as exc:
        reason = str(exc).replace(" ", "_")
        _instagram_auth_state["last_error"] = str(exc)
        return RedirectResponse(url=f"/agentes/redes-sociais?auth=error&reason={reason}", status_code=302)

    _instagram_auth_state["access_token"] = access_token
    _instagram_auth_state["ig_user_id"] = ig_context.get("ig_user_id", "")
    _instagram_auth_state["username"] = ig_context.get("username", "")
    _instagram_auth_state["last_error"] = ""
    return RedirectResponse(url="/agentes/redes-sociais?auth=ok", status_code=302)


@app.get("/agents/social-media/auth/status")
def social_media_auth_status() -> Dict[str, Any]:
    """Devolve estado atual de autenticação Instagram do MVP.

    A função permite à interface validar se já existe sessão autenticada para
    análise completa sem pedir login em cada operação.

    Argumentos:
        Nenhum.

    Retorno:
        Dicionário com:
        - `connected`: `True` quando há token válido em memória;
        - `username`: username da conta autorizada quando conhecido;
        - `ig_user_id`: identificador interno da conta IG autorizada.
    """

    token = _instagram_auth_state.get("access_token", "")
    return {
        "connected": bool(token),
        "username": _instagram_auth_state.get("username", ""),
        "ig_user_id": _instagram_auth_state.get("ig_user_id", ""),
        "last_error": _instagram_auth_state.get("last_error", ""),
    }


@app.post("/agents/social-media/authenticated-analyze")
def social_media_authenticated_analyze(
    platform: SocialMediaPlatform = Query(
        "instagram",
        description="Rede social; análise autenticada só está implementada para Instagram.",
    ),
) -> Dict[str, Any]:
    """Gera análise completa com dados oficiais via Instagram Graph API.

    O endpoint usa o token OAuth guardado no MVP para obter dados principais da
    conta autorizada (seguidores, seguidos, media count e métricas de media) e
    executar análise estratégica com o agente.

    Argumentos:
        Nenhum.

    Retorno:
        Dicionário de análise com fonte `social-media-authenticated`.

    Raises:
        HTTPException: 401 quando não existe sessão autenticada; 502 em falha de
            leitura na Graph API; 503 quando o agente IA não está configurado.
    """

    if not social_media_agent.is_configured():
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY nao configurada no servidor. Define a variavel de ambiente e reinicia o uvicorn.",
        )

    pl_auth = normalize_social_platform(platform)
    if pl_auth != "instagram":
        raise HTTPException(
            status_code=422,
            detail="Análise autenticada com Instagram Graph API só está disponível para a plataforma instagram.",
        )

    access_token = _instagram_auth_state.get("access_token", "").strip()
    ig_user_id = _instagram_auth_state.get("ig_user_id", "").strip()
    if not access_token or not ig_user_id:
        raise HTTPException(
            status_code=401,
            detail="Sem sessão Instagram autenticada. Usa o botão 'Login Instagram' primeiro.",
        )

    try:
        instagram_data = _fetch_authenticated_instagram_data(access_token=access_token, ig_user_id=ig_user_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    username = str(instagram_data.get("username") or _instagram_auth_state.get("username") or "").strip()
    history = [
        {
            "role": "user",
            "content": (
                f"Analisa a conta autenticada @{username or 'instagram'} com foco em crescimento e engagement "
                "e cria um plano de curto prazo com ações priorizadas."
            ),
        }
    ]
    try:
        response = social_media_agent.analyze_instagram_data(
            messages=history,
            instagram_data=instagram_data,
            language="pt-PT",
            platform="instagram",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao processar análise autenticada: {exc!s}",
        ) from exc

    response["source"] = "social-media-authenticated"
    response["profile_username"] = username
    response["public_profile_data"] = instagram_data
    return response


@app.post("/agents/designer/chat-reply")
def designer_chat_reply(payload: DesignerChatTurnRequest) -> Dict[str, str]:
    """Gera a próxima resposta do Agente Designer na chatroom.

    Este endpoint processa o histórico atual da conversa e devolve uma resposta
    objetiva para aprofundar o briefing visual antes da geração da imagem.

    Argumentos:
        payload: Histórico da conversa e preferências de idioma/estilo.

    Retorno:
        Dicionário com a chave `reply` para o próximo turno conversacional.
    """

    history = [{"role": item.role, "content": item.content} for item in payload.messages]
    reply = designer_agent.generate_chat_reply(
        messages=history,
        language=payload.language,
        style=payload.style,
        reference_image_urls=payload.reference_image_urls,
    )
    return {"reply": reply}


@app.post("/agents/designer/chat-generate-image")
def designer_chat_generate_image(payload: DesignerImageGenerateRequest) -> Dict[str, str]:
    """Gera imagem via Nano Banana com base na conversa da chatroom Designer.

    O endpoint transforma o histórico de mensagens num prompt visual único e
    chama a API Nano Banana para gerar a imagem final.

    Argumentos:
        payload: Histórico da conversa e parâmetros finais da geração.

    Retorno:
        Dicionário com URL da imagem, prompt usado e identificador do provider.

    Raises:
        HTTPException: 503 quando a API não está configurada; 502 em falha de geração.
    """

    if not designer_agent.is_configured():
        raise HTTPException(
            status_code=503,
            detail="NANO_BANANA_API_KEY ou NANO_BANANA_API_URL não configuradas no servidor.",
        )

    try:
        history = [{"role": item.role, "content": item.content} for item in payload.messages]
        return designer_agent.generate_image_from_chat(
            messages=history,
            size=payload.size,
            style=payload.style,
            reference_image_urls=payload.reference_image_urls,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao gerar imagem com Nano Banana: {exc!s}",
        ) from exc


@app.post("/agents/designer/upload-reference")
async def designer_upload_reference_image(file: UploadFile = File(...)) -> Dict[str, str]:
    """Recebe e guarda uma imagem de referência para a chatroom do Designer.

    O endpoint permite ao utilizador carregar uma imagem local (ex.: exemplo de
    composição, estilo, produto ou fotografia). O ficheiro é validado por tipo
    MIME, guardado em `static/generated/references` e devolve-se uma URL local
    que o frontend pode anexar ao contexto da geração.

    Argumentos:
        file: Ficheiro de imagem enviado pelo cliente em multipart/form-data.

    Retorno:
        Dicionário com:
        - `image_url`: URL local da imagem guardada para referência;
        - `filename`: nome final guardado no servidor.

    Raises:
        HTTPException: 400 quando o tipo de ficheiro não é imagem;
            500 quando ocorre erro ao gravar o ficheiro.
    """

    content_type = str(file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Só são permitidos ficheiros de imagem.")

    references_dir = STATIC_DIR / "generated" / "references"
    references_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "reference.png").suffix or ".png"
    safe_suffix = suffix if len(suffix) <= 10 else ".png"
    saved_name = f"ref-{os.urandom(8).hex()}{safe_suffix}"
    target_path = references_dir / saved_name

    try:
        data = await file.read()
        target_path.write_bytes(data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Erro ao guardar imagem de referência: {exc!s}") from exc
    finally:
        await file.close()

    return {
        "image_url": f"/static/generated/references/{saved_name}",
        "filename": saved_name,
    }


def _graph_get_json(path: str, access_token: str, query: str = "") -> Dict[str, Any]:
    """Executa pedido GET na Graph API e devolve JSON parseado.

    A função centraliza chamadas à Graph API com tratamento consistente de
    erros HTTP/rede, facilitando reutilização no fluxo de autenticação e na
    recolha de métricas de Instagram.

    Argumentos:
        path: Caminho da Graph API sem domínio (ex.: `/me/accounts`).
        access_token: Token OAuth do utilizador autenticado.
        query: Query string opcional sem `?` (ex.: `fields=id,name`).

    Retorno:
        Dicionário JSON devolvido pela Graph API.

    Raises:
        RuntimeError: Quando ocorre erro HTTP, rede ou resposta inválida.
    """

    safe_path = path if path.startswith("/") else f"/{path}"
    query_segment = f"&{query}" if query else ""
    url = (
        f"{INSTAGRAM_GRAPH_API_BASE_URL}{safe_path}?access_token={access_token}{query_segment}"
    )
    headers = {"Accept": "application/json"}
    http_request = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(http_request, timeout=25) as response:
            body = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            error_body = ""
        raise RuntimeError(
            f"Graph API HTTP {exc.code}. Body: {error_body[:400] or 'sem detalhe'}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Erro de ligação à Graph API: {exc!s}") from exc
    except (TimeoutError, OSError) as exc:
        raise RuntimeError(f"Timeout/erro de sistema na Graph API: {exc!s}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Resposta inválida da Graph API: {body[:250]}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Resposta Graph API inválida (não objeto JSON).")
    return data


def _exchange_meta_code_for_token(code: str) -> str:
    """Troca `code` OAuth por `access_token` de utilizador Meta.

    A função chama o endpoint oficial de troca de código OAuth e devolve o
    token de acesso necessário para pedir dados de páginas e Instagram.

    Argumentos:
        code: Código OAuth devolvido pela Meta na fase de callback.

    Retorno:
        String com `access_token` de utilizador.

    Raises:
        RuntimeError: Quando configuração OAuth está incompleta ou a troca falha.
    """

    app_id = _get_env_setting("META_APP_ID")
    app_secret = _get_env_setting("META_APP_SECRET")
    redirect_uri = _get_env_setting("META_REDIRECT_URI")
    if not app_id or not app_secret or not redirect_uri:
        raise RuntimeError("Configuração OAuth incompleta (META_APP_ID/SECRET/REDIRECT_URI).")

    token_url = (
        f"{INSTAGRAM_GRAPH_API_BASE_URL}/oauth/access_token"
        f"?client_id={app_id}"
        f"&client_secret={app_secret}"
        f"&redirect_uri={redirect_uri}"
        f"&code={code}"
    )
    http_request = request.Request(token_url, headers={"Accept": "application/json"}, method="GET")
    try:
        with request.urlopen(http_request, timeout=25) as response:
            body = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            error_body = ""
        raise RuntimeError(f"Falha na troca OAuth: HTTP {exc.code} ({error_body[:250]})") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Falha na troca OAuth: {exc!s}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Resposta inválida no OAuth token exchange.") from exc
    token = str(data.get("access_token", "")).strip()
    if not token:
        raise RuntimeError("OAuth sem access_token devolvido.")
    return token


def _resolve_instagram_context_from_token(access_token: str) -> Dict[str, str]:
    """Resolve conta Instagram profissional associada a um token de utilizador.

    A função lista páginas do utilizador, procura a primeira página com
    `instagram_business_account` e devolve o `ig_user_id` e username da conta.

    Argumentos:
        access_token: Token OAuth de utilizador após consentimento Meta.

    Retorno:
        Dicionário com:
        - `ig_user_id`: ID interno da conta Instagram profissional;
        - `username`: username público da conta.

    Raises:
        RuntimeError: Quando não existe página ligada a conta Instagram.
    """

    accounts_data = _graph_get_json("/me/accounts", access_token=access_token)
    pages = accounts_data.get("data")
    if not isinstance(pages, list) or not pages:
        raise RuntimeError("Token sem páginas associadas em /me/accounts.")

    for page in pages:
        if not isinstance(page, dict):
            continue
        page_id = str(page.get("id", "")).strip()
        if not page_id:
            continue
        page_data = _graph_get_json(
            f"/{page_id}",
            access_token=access_token,
            query="fields=instagram_business_account",
        )
        ig_account = page_data.get("instagram_business_account")
        if not isinstance(ig_account, dict):
            continue
        ig_user_id = str(ig_account.get("id", "")).strip()
        if not ig_user_id:
            continue

        ig_profile = _graph_get_json(
            f"/{ig_user_id}",
            access_token=access_token,
            query="fields=username",
        )
        username = str(ig_profile.get("username", "")).strip()
        return {"ig_user_id": ig_user_id, "username": username}

    raise RuntimeError("Nenhuma página com Instagram Business Account associada.")


def _fetch_authenticated_instagram_data(access_token: str, ig_user_id: str) -> Dict[str, Any]:
    """Obtém dados de Instagram autenticados para análise completa.

    A função recolhe métricas principais da conta IG autorizada e últimas
    publicações com métricas públicas por media, entregando um bloco estruturado
    para análise estratégica com o agente de redes sociais.

    Argumentos:
        access_token: Token OAuth do utilizador autorizado.
        ig_user_id: ID da conta Instagram Business/Creator.

    Retorno:
        Dicionário com dados da conta, lista de posts recentes e resumo de
        método/fonte dos dados autenticados.

    Raises:
        RuntimeError: Quando a Graph API falha ou devolve payload inválido.
    """

    profile_data = _graph_get_json(
        f"/{ig_user_id}",
        access_token=access_token,
        query="fields=username,followers_count,follows_count,media_count",
    )
    media_data = _graph_get_json(
        f"/{ig_user_id}/media",
        access_token=access_token,
        query="fields=id,caption,media_type,timestamp,like_count,comments_count&limit=12",
    )
    media_items = media_data.get("data")
    normalized_media: List[Dict[str, Any]] = []
    if isinstance(media_items, list):
        for item in media_items:
            if isinstance(item, dict):
                normalized_media.append(
                    {
                        "id": item.get("id"),
                        "media_type": item.get("media_type"),
                        "caption": item.get("caption"),
                        "timestamp": item.get("timestamp"),
                        "like_count": item.get("like_count"),
                        "comments_count": item.get("comments_count"),
                    }
                )

    return {
        "platform": "instagram",
        "profile": profile_data.get("username"),
        "followers_count": profile_data.get("followers_count"),
        "following_count": profile_data.get("follows_count"),
        "posts_count": profile_data.get("media_count"),
        "recent_posts": normalized_media,
        "collection_method": "meta_graph_api_authenticated",
        "data_quality": "alta",
    }


def _load_social_snapshots() -> Dict[str, List[Dict[str, Any]]]:
    """Carrega snapshots históricos de perfis sociais guardados localmente.

    A função lê o ficheiro de snapshots do MVP e devolve uma estrutura por
    perfil. Quando o ficheiro não existe ou está inválido, devolve estrutura
    vazia para continuar o fluxo sem falha.

    Argumentos:
        Nenhum.

    Retorno:
        Dicionário no formato `{username: [snapshots...]}`.
    """

    if not SOCIAL_SNAPSHOTS_FILE.exists():
        return {}
    try:
        raw = SOCIAL_SNAPSHOTS_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def _save_all_social_snapshots(data: Dict[str, List[Dict[str, Any]]]) -> None:
    """Persiste no disco o histórico completo de snapshots sociais.

    A função grava os snapshots em JSON no diretório `data` do projeto para
    permitir comparações temporais em análises futuras.

    Argumentos:
        data: Dicionário completo de snapshots por username.

    Retorno:
        Nenhum.
    """

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SOCIAL_SNAPSHOTS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_social_snapshot(profile_username: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Cria snapshot normalizado do estado atual de um perfil Instagram.

    A função transforma os dados recolhidos pelo scraper num registo temporal
    único com timestamp UTC e métricas principais usadas nos comparativos.

    Argumentos:
        profile_username: Username do perfil analisado.
        profile_data: Dicionário bruto devolvido pelo scraper do perfil.

    Retorno:
        Dicionário de snapshot com métricas e timestamp de recolha.
    """

    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "captured_at": now_iso,
        "profile": profile_username,
        "followers_count": profile_data.get("followers_count"),
        "following_count": profile_data.get("following_count"),
        "posts_count": profile_data.get("posts_count"),
        "engagement_rate": profile_data.get("engagement_rate"),
    }


def _save_social_snapshot(profile_username: str, snapshot: Dict[str, Any]) -> None:
    """Guarda snapshot de um perfil mantendo histórico compacto no MVP.

    A função adiciona o snapshot ao histórico do perfil e limita o total de
    entradas para evitar crescimento excessivo do ficheiro local.

    Argumentos:
        profile_username: Username do perfil alvo.
        snapshot: Snapshot normalizado a persistir.

    Retorno:
        Nenhum.
    """

    all_snapshots = _load_social_snapshots()
    key = profile_username.lower().strip()
    history = all_snapshots.get(key)
    if not isinstance(history, list):
        history = []
    history.append(snapshot)
    history = history[-180:]
    all_snapshots[key] = history
    _save_all_social_snapshots(all_snapshots)


def _pick_closest_snapshot(
    snapshots: List[Dict[str, Any]], target_dt: datetime
) -> Optional[Dict[str, Any]]:
    """Seleciona snapshot mais próximo de uma data alvo.

    Argumentos:
        snapshots: Lista de snapshots do perfil.
        target_dt: Data alvo para comparação (1 semana, 2 semanas, 1 mês).

    Retorno:
        Snapshot mais próximo da data alvo ou `None` se não houver dados.
    """

    best_item: Optional[Dict[str, Any]] = None
    best_delta: Optional[float] = None
    for item in snapshots:
        captured_raw = str(item.get("captured_at", "")).strip()
        if not captured_raw:
            continue
        try:
            captured_dt = datetime.fromisoformat(captured_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        delta = abs((captured_dt - target_dt).total_seconds())
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_item = item
    return best_item


def _metric_delta(current: Any, previous: Any) -> Optional[Dict[str, Any]]:
    """Calcula variação absoluta e percentual entre duas métricas.

    Argumentos:
        current: Valor atual da métrica.
        previous: Valor de referência temporal da métrica.

    Retorno:
        Dicionário `{current, previous, delta, delta_pct}` ou `None` se valores
        não forem numéricos.
    """

    if current is None or previous is None:
        return None
    try:
        current_num = float(current)
        previous_num = float(previous)
    except (TypeError, ValueError):
        return None
    delta = current_num - previous_num
    delta_pct = (delta / previous_num * 100.0) if previous_num != 0 else None
    return {
        "current": current_num,
        "previous": previous_num,
        "delta": delta,
        "delta_pct": delta_pct,
    }


def _compute_public_instagram_metrics(profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calcula métricas derivadas a partir dos dados públicos do scraper.

    A função reduz lacunas de análise estimando engagement e agregados de
    interações com base nos posts recentes recolhidos (likes/comentários).

    Argumentos:
        profile_data: Dados de perfil já normalizados pelo coletor público.

    Retorno:
        Dicionário com campos derivados para enriquecer o input analítico.
    """

    followers = profile_data.get("followers_count")
    posts = profile_data.get("recent_posts")
    if not isinstance(posts, list) or not posts:
        return {}

    total_likes = 0.0
    total_comments = 0.0
    counted_posts = 0
    for post in posts:
        if not isinstance(post, dict):
            continue
        likes = post.get("likesCount")
        comments = post.get("commentsCount")
        likes_num = float(likes) if isinstance(likes, (int, float)) else 0.0
        comments_num = float(comments) if isinstance(comments, (int, float)) else 0.0
        total_likes += likes_num
        total_comments += comments_num
        counted_posts += 1
    if counted_posts == 0:
        return {}

    avg_likes = total_likes / counted_posts
    avg_comments = total_comments / counted_posts
    engagement_rate = None
    if isinstance(followers, (int, float)) and float(followers) > 0:
        engagement_rate = ((avg_likes + avg_comments) / float(followers)) * 100.0

    return {
        "avg_interactions_per_post": {
            "likes": round(avg_likes, 2),
            "comments": round(avg_comments, 2),
            "shares": None,
            "saves": None,
        },
        "engagement_rate": round(engagement_rate, 4) if engagement_rate is not None else None,
    }


def _build_snapshot_comparisons(profile_username: str, current_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Constrói comparações temporais 1 semana, 2 semanas e 1 mês.

    A função consulta o histórico persistido do perfil, procura snapshots de
    referência para os períodos pedidos e calcula evolução de followers,
    following, posts e engagement.

    Argumentos:
        profile_username: Username do perfil analisado.
        current_snapshot: Snapshot mais recente já recolhido.

    Retorno:
        Dicionário com chaves `one_week`, `two_weeks`, `one_month` contendo
        variações por métrica e disponibilidade de dados históricos.
    """

    all_snapshots = _load_social_snapshots()
    history = all_snapshots.get(profile_username.lower().strip(), [])
    if not isinstance(history, list) or len(history) < 2:
        return {
            "one_week": {"available": False},
            "two_weeks": {"available": False},
            "one_month": {"available": False},
        }

    now_dt = datetime.now(timezone.utc)
    targets = {
        "one_week": now_dt - timedelta(days=7),
        "two_weeks": now_dt - timedelta(days=14),
        "one_month": now_dt - timedelta(days=30),
    }
    output: Dict[str, Any] = {}
    for key, target_dt in targets.items():
        reference = _pick_closest_snapshot(history[:-1], target_dt)
        if not reference:
            output[key] = {"available": False}
            continue
        output[key] = {
            "available": True,
            "reference_captured_at": reference.get("captured_at"),
            "followers": _metric_delta(current_snapshot.get("followers_count"), reference.get("followers_count")),
            "following": _metric_delta(current_snapshot.get("following_count"), reference.get("following_count")),
            "posts": _metric_delta(current_snapshot.get("posts_count"), reference.get("posts_count")),
            "engagement_rate": _metric_delta(
                current_snapshot.get("engagement_rate"),
                reference.get("engagement_rate"),
            ),
        }
    return output


def _extract_instagram_username(profile_input: str) -> Optional[str]:
    """Extrai username de Instagram a partir de `@nome` ou URL pública.

    A função normaliza o input recebido no frontend e tenta identificar um
    username válido de perfil Instagram. Suporta formatos comuns:
    `@username`, `username`, `https://instagram.com/username` e variantes com
    `www`/barra final.

    Argumentos:
        profile_input: Texto livre introduzido pelo utilizador com username ou
            link de perfil do Instagram.

    Retorno:
        Username limpo sem `@` quando o formato é válido; `None` quando não foi
        possível extrair um identificador consistente.
    """

    raw = str(profile_input or "").strip()
    if not raw:
        return None

    if raw.startswith("@"):
        candidate = raw[1:].strip().strip("/")
        return candidate if re.fullmatch(r"[A-Za-z0-9._]{1,30}", candidate) else None

    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        host = (parsed.netloc or "").lower()
        if "instagram.com" not in host:
            return None
        path_parts = [part for part in parsed.path.split("/") if part.strip()]
        if not path_parts:
            return None
        candidate = path_parts[0].strip()
        if candidate.lower() in {"p", "reel", "stories", "explore"}:
            return None
        return candidate if re.fullmatch(r"[A-Za-z0-9._]{1,30}", candidate) else None

    candidate = raw.strip().strip("/")
    return candidate if re.fullmatch(r"[A-Za-z0-9._]{1,30}", candidate) else None


def _parse_human_number(value: str) -> Optional[int]:
    """Converte texto numérico humano para inteiro.

    A função interpreta formatos frequentes em páginas públicas, incluindo:
    separadores (`1,234`/`1.234`) e sufixos curtos (`1.2k`, `3,4m`).

    Argumentos:
        value: Texto com número potencialmente formatado.

    Retorno:
        Inteiro convertido quando possível; `None` em caso de formato inválido.
    """

    text = str(value or "").strip().lower()
    if not text:
        return None

    multiplier = 1
    if text.endswith("k"):
        multiplier = 1_000
        text = text[:-1]
    elif text.endswith("m"):
        multiplier = 1_000_000
        text = text[:-1]

    normalized = text.replace(" ", "")
    if multiplier == 1:
        normalized = normalized.replace(".", "").replace(",", "")
        if not normalized.isdigit():
            return None
        return int(normalized)

    normalized = normalized.replace(",", ".")
    try:
        base = float(normalized)
    except ValueError:
        return None
    return int(base * multiplier)


def _fetch_instagram_public_profile(username: str) -> Dict[str, Any]:
    """Recolhe métricas públicas de perfil com Apify como fonte primária.

    A função tenta primeiro obter dados através do `Apify Instagram Scraper`,
    permitindo resultados mais estáveis para o modo de análise rápida do MVP.
    Quando o Apify não está configurado (sem `APIFY_API_TOKEN`) ou falha
    temporariamente, faz fallback automático para scraping web básico local
    (`_fetch_instagram_public_profile_web`). Assim, o utilizador consegue
    analisar perfis mesmo sem configurar Apify.

    Argumentos:
        username: Nome público do perfil a consultar (sem `@`).

    Retorno:
        Dicionário estruturado com métricas básicas de perfil, método de recolha
        e classificação de qualidade dos dados. O campo `collection_method`
        identifica a origem efectiva (`apify:<actor>` ou `public_web_profile`).
        Quando o Apify falha mas o fallback funciona, é incluído também o
        campo `apify_error` com a razão do salto, para diagnóstico.

    Raises:
        RuntimeError: Quando não consegue recolher dados nem pelo Apify nem pelo
            fallback web local.
    """

    apify_token = os.getenv("APIFY_API_TOKEN", "").strip()
    apify_error: Optional[str] = None
    result: Dict[str, Any]

    if apify_token:
        try:
            result = _fetch_instagram_public_profile_with_apify(username)
        except RuntimeError as exc:
            apify_error = str(exc)
            try:
                result = _fetch_instagram_public_profile_web(username)
            except RuntimeError as web_exc:
                raise RuntimeError(
                    f"Não foi possível recolher dados do perfil. Apify: {apify_error}. Web: {web_exc}"
                ) from web_exc
            result["apify_error"] = apify_error
    else:
        try:
            result = _fetch_instagram_public_profile_web(username)
        except RuntimeError as exc:
            raise RuntimeError(
                f"Não foi possível recolher dados do perfil (sem APIFY_API_TOKEN). Web: {exc}"
            ) from exc
        result["apify_error"] = "APIFY_API_TOKEN não configurado; a usar fallback web."

    if apify_token:
        enrichment_errors: List[str] = []
        posts_extra: List[Dict[str, Any]] = []
        reels_extra: List[Dict[str, Any]] = []

        try:
            posts_extra = _fetch_instagram_posts_with_apify(username)
        except RuntimeError as exc:
            enrichment_errors.append(f"post_scraper: {exc}")

        try:
            reels_extra = _fetch_instagram_reels_with_apify(username)
        except RuntimeError as exc:
            enrichment_errors.append(f"reel_scraper: {exc}")

        if posts_extra:
            result["recent_posts_extended"] = posts_extra
            if not result.get("recent_posts"):
                result["recent_posts"] = [
                    {
                        "id": p.get("id"),
                        "type": p.get("type"),
                        "caption": p.get("caption"),
                        "likesCount": p.get("likesCount"),
                        "commentsCount": p.get("commentsCount"),
                        "timestamp": p.get("timestamp"),
                        "url": p.get("url"),
                    }
                    for p in posts_extra[:12]
                ]
        if reels_extra:
            result["recent_reels"] = reels_extra

        enrichment = _build_apify_enriched_metrics(
            followers_count=result.get("followers_count"),
            posts=posts_extra,
            reels=reels_extra,
        )
        if enrichment:
            result["apify_enrichment"] = enrichment

        if enrichment_errors:
            result["apify_enrichment_errors"] = enrichment_errors

    return result


def _fetch_instagram_public_profile_with_apify(username: str) -> Dict[str, Any]:
    """Obtém métricas públicas via Apify Instagram Scraper.

    A função executa o actor do Apify com URL direta do perfil e interpreta o
    primeiro item do dataset devolvido para extrair métricas principais.

    Variáveis de ambiente suportadas:
        - `APIFY_API_TOKEN`: token obrigatório para autenticar no Apify.
        - `APIFY_INSTAGRAM_SCRAPER_ACTOR`: actor id opcional. Por defeito usa
          `apify/instagram-scraper`.

    Argumentos:
        username: Username Instagram sem `@`.

    Retorno:
        Dicionário com métricas de perfil e metadados da recolha via Apify.

    Raises:
        RuntimeError: Quando o token não existe, o actor falha ou devolve
            payload sem itens utilizáveis.
    """

    apify_token = os.getenv("APIFY_API_TOKEN", "").strip()
    actor_id = os.getenv("APIFY_INSTAGRAM_SCRAPER_ACTOR", "apify/instagram-scraper").strip()
    if not apify_token:
        raise RuntimeError("APIFY_API_TOKEN não configurado.")
    if not actor_id:
        raise RuntimeError("APIFY_INSTAGRAM_SCRAPER_ACTOR inválido.")

    actor_path = actor_id.replace("/", "~")
    apify_url = (
        f"https://api.apify.com/v2/acts/{actor_path}/run-sync-get-dataset-items?token={apify_token}"
    )
    payload = {
        "directUrls": [f"https://www.instagram.com/{username}/"],
        "resultsType": "details",
        "resultsLimit": 1,
        "searchType": "user",
    }
    http_request = request.Request(
        apify_url,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=90) as response:
            body = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            error_body = ""
        raise RuntimeError(f"Apify HTTP {exc.code}: {error_body[:280] or 'sem detalhe'}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Falha de ligação ao Apify: {exc!s}") from exc
    except (TimeoutError, OSError) as exc:
        raise RuntimeError(f"Timeout/erro de sistema no Apify: {exc!s}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Resposta inválida do Apify: {body[:240]}") from exc

    items = data if isinstance(data, list) else []
    if not items:
        raise RuntimeError("Apify devolveu dataset vazio para este perfil.")
    first = items[0]
    if not isinstance(first, dict):
        raise RuntimeError("Apify devolveu item inválido (não objeto).")

    followers_count = first.get("followersCount")
    following_count = first.get("followsCount")
    posts_count = first.get("postsCount")
    engagement_rate = first.get("engagementRate")
    if followers_count is None:
        followers_count = first.get("followers")
    if following_count is None:
        following_count = first.get("following")
    if posts_count is None:
        posts_count = first.get("posts")
    if engagement_rate is None:
        engagement_rate = first.get("engagement")

    latest_posts_raw = first.get("latestPosts") or first.get("latestIgtvVideos") or []
    recent_posts: List[Dict[str, Any]] = []
    if isinstance(latest_posts_raw, list):
        for post in latest_posts_raw[:12]:
            if not isinstance(post, dict):
                continue
            recent_posts.append(
                {
                    "id": post.get("id"),
                    "type": post.get("type") or post.get("shortCode"),
                    "caption": post.get("caption"),
                    "likesCount": post.get("likesCount"),
                    "commentsCount": post.get("commentsCount"),
                    "timestamp": post.get("timestamp"),
                    "url": post.get("url"),
                }
            )

    profile_name = (
        str(first.get("username") or first.get("userName") or username).strip() or username
    )
    filled_fields = sum(
        value is not None for value in [followers_count, following_count, posts_count]
    )
    data_quality = "baixa"
    if filled_fields >= 3:
        data_quality = "alta"
    elif filled_fields == 2:
        data_quality = "media"

    result = {
        "platform": "instagram",
        "profile": profile_name,
        "followers_count": followers_count,
        "following_count": following_count,
        "posts_count": posts_count,
        "engagement_rate": engagement_rate,
        "recent_posts": recent_posts,
        "biography": first.get("biography"),
        "category": first.get("businessCategoryName") or first.get("categoryName"),
        "collection_method": f"apify:{actor_id}",
        "data_quality": data_quality,
    }
    if result.get("engagement_rate") is None:
        derived = _compute_public_instagram_metrics(result)
        if derived.get("engagement_rate") is not None:
            result["engagement_rate"] = derived["engagement_rate"]
        if derived.get("avg_interactions_per_post"):
            result["avg_interactions_per_post"] = derived["avg_interactions_per_post"]
    return result


def _run_apify_actor_sync(actor_id: str, payload: Dict[str, Any], timeout: int = 120) -> List[Any]:
    """Executa um actor do Apify em modo síncrono e devolve o dataset.

    A função abstrai a chamada HTTP ao endpoint
    `run-sync-get-dataset-items` da Apify, reutilizável por vários actors
    (perfil, posts, reels, etc.).

    Argumentos:
        actor_id: Identificador do actor Apify no formato `user/actor`.
        payload: Dicionário com o input JSON específico do actor.
        timeout: Tempo máximo, em segundos, para esperar pela resposta.

    Retorno:
        Lista de itens do dataset (objetos `dict`). Lista vazia se a
        resposta não devolver itens.

    Raises:
        RuntimeError: Quando o token está em falta, o actor falha, há
            problemas de rede ou o JSON é inválido.
    """

    apify_token = os.getenv("APIFY_API_TOKEN", "").strip()
    if not apify_token:
        raise RuntimeError("APIFY_API_TOKEN não configurado.")
    if not actor_id:
        raise RuntimeError("Apify actor id inválido.")
    if _is_linkedin_apify_actor_blocked(actor_id):
        raise RuntimeError(
            f"Actor Apify bloqueado: {actor_id}. "
            "Remove sourabhbgp/linkedin-profile-scraper do .env e reinicia o uvicorn."
        )

    actor_path = actor_id.replace("/", "~")
    apify_url = (
        f"https://api.apify.com/v2/acts/{actor_path}/run-sync-get-dataset-items?token={apify_token}"
    )
    http_request = request.Request(
        apify_url,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            error_body = ""
        raise RuntimeError(
            f"Apify ({actor_id}) HTTP {exc.code}: {error_body[:280] or 'sem detalhe'}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Falha de ligação ao Apify ({actor_id}): {exc!s}") from exc
    except (TimeoutError, OSError) as exc:
        raise RuntimeError(f"Timeout/erro de sistema no Apify ({actor_id}): {exc!s}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Resposta inválida do Apify ({actor_id}): {body[:240]}") from exc

    return data if isinstance(data, list) else []


def _normalize_linkedin_public_profile_input(raw: str) -> str:
    """Normaliza um URL ou slug de perfil/página públicos no LinkedIn.

    Aceita URL completo, caminho relativo ou slug (``williamhgates``). Exige
    ``linkedin.com/in/`` (pessoa), ``/company/`` (empresa) ou ``/school/`` (escola).

    Argumentos:
        raw: Texto introduzido pelo utilizador.

    Retorno:
        URL ``https`` sem fragmento ``#`` (query opcional removida para
        estabilidade do scraper).

    Raises:
        ValueError: Se não for possível interpretar como URL público LinkedIn.
    """

    s = str(raw or "").strip()
    if not s:
        raise ValueError("Identificador LinkedIn vazio.")
    canonical = canonicalize_linkedin_profile_url(s)
    if canonical:
        return canonical
    if not s.lower().startswith("http"):
        if "/" not in s and "linkedin.com" not in s.lower():
            s = f"https://www.linkedin.com/in/{s.strip('/')}"
        else:
            s = "https://" + s.lstrip("/")
    parsed = urlparse(s)
    host = (parsed.netloc or "").lower()
    path_lower = (parsed.path or "").lower()
    if "linkedin.com" not in host:
        raise ValueError("O URL tem de ser do domínio linkedin.com.")
    if not any(m in path_lower for m in ("/in/", "/company/", "/school/")):
        raise ValueError(
            "Usa um URL de perfil (/in/...), empresa (/company/...) ou escola (/school/...)."
        )
    clean = s.split("#", 1)[0].rstrip("/")
    slug = extract_linkedin_public_vanity_slug(clean)
    if slug and not is_linkedin_public_vanity_slug(slug):
        raise ValueError(
            f"O slug «{slug}» não parece um URL público LinkedIn válido "
            "(pode ser um ID interno da conta). Cola o URL completo do teu perfil "
            "(ex.: https://www.linkedin.com/in/o-teu-nome-publico/)."
        )
    return clean


def _linkedin_subject_id_from_supabase_user(user: Dict[str, Any]) -> Optional[str]:
    """Obtém o ``sub`` OIDC LinkedIn guardado no utilizador Supabase.

    Argumentos:
        user: Objecto ``GET /auth/v1/user``.

    Retorno:
        Valor de ``sub`` se existir, ou ``None``.
    """

    for key in ("sub",):
        val = user.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    meta = user.get("user_metadata")
    if isinstance(meta, dict):
        sub = meta.get("sub")
        if isinstance(sub, str) and sub.strip():
            return sub.strip()
    for ident in user.get("identities") or []:
        if not isinstance(ident, dict):
            continue
        prov = str(ident.get("provider", "")).lower()
        if prov not in ("linkedin_oidc", "linkedin"):
            continue
        data = ident.get("identity_data")
        if isinstance(data, dict):
            sub = data.get("sub")
            if isinstance(sub, str) and sub.strip():
                return sub.strip()
    return None


def _assert_linkedin_profile_url_usable(profile_url: str, user: Optional[Dict[str, Any]] = None) -> None:
    """Garante que o URL LinkedIn é adequado para Apify antes de iniciar um run.

    Argumentos:
        profile_url: URL normalizado ``https://www.linkedin.com/in/...``.
        user: Utilizador Supabase opcional (para detectar ``sub`` = slug interno).

    Raises:
        ValueError: Slug inválido ou igual ao ID interno OIDC.
    """

    slug = extract_linkedin_public_vanity_slug(profile_url)
    if not slug:
        raise ValueError("URL de perfil LinkedIn sem slug /in/, /company/ ou /school/.")
    path_l = profile_url.lower()
    if "/school/" in path_l or "/company/" in path_l:
        if not re.match(r"^[a-zA-Z0-9\-_]+$", slug):
            raise ValueError(
                f"O slug «{slug}» não parece um identificador público LinkedIn válido."
            )
        return
    if not is_linkedin_public_vanity_slug(slug):
        raise ValueError(
            f"O slug «{slug}» não é um nome público LinkedIn válido. "
            "Abre o teu perfil no browser e cola o URL completo "
            "(ex.: https://www.linkedin.com/in/nome-aparece-na-barra/)."
        )
    if user:
        sub = _linkedin_subject_id_from_supabase_user(user)
        if sub and linkedin_slug_matches_internal_subject_id(slug, sub):
            raise ValueError(
                f"O URL resolvido ({profile_url}) usa o ID interno da conta, não o nome público. "
                "Cola manualmente o URL que vês no LinkedIn ou confirma scopes openid+profile "
                "e que o provider_token chega ao servidor."
            )


def _linkedin_profile_url_from_database(access_token: str) -> Optional[str]:
    """Obtém o URL LinkedIn guardado em ``user_linkedin_profiles`` para esta sessão.

    Argumentos:
        access_token: JWT ``access_token`` Supabase.

    Retorno:
        URL público ou ``None`` se não existir registo / BD indisponível.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    if not access_token or not sup_url or not sup_anon:
        return None
    try:
        return fetch_user_linkedin_profile_from_database(access_token, sup_url, sup_anon)
    except (error.HTTPError, error.URLError, OSError, json.JSONDecodeError, TypeError):
        return None


def _save_linkedin_profile_to_database(
    access_token: str,
    user: Dict[str, Any],
    profile_url: str,
    *,
    display_name: Optional[str] = None,
) -> bool:
    """Persiste o URL do perfil LinkedIn na BD Supabase para o utilizador autenticado.

    Argumentos:
        access_token: JWT da sessão.
        user: Objecto utilizador GoTrue.
        profile_url: URL público a guardar.
        display_name: Nome opcional.

    Retorno:
        ``True`` se gravado com sucesso.
    """

    sup_url, sup_anon = get_supabase_public_credentials()
    uid = str((user or {}).get("id") or "").strip()
    if not access_token or not sup_url or not sup_anon or not uid:
        return False
    try:
        return upsert_user_linkedin_profile_to_database(
            access_token,
            sup_url,
            sup_anon,
            uid,
            profile_url,
            display_name=display_name,
        )
    except (error.HTTPError, error.URLError, OSError, TypeError):
        return False


def _resolve_authenticated_linkedin_profile_url(
    user: Dict[str, Any],
    provider_token: Optional[str] = None,
    *,
    stored_profile_url: Optional[str] = None,
    database_profile_url: Optional[str] = None,
    id_token: Optional[str] = None,
) -> Optional[str]:
    """Resolve o URL público LinkedIn do utilizador autenticado (sessão Supabase).

    Ordem: BD Supabase, URL no browser, API LinkedIn, metadados OIDC.

    Argumentos:
        user: Objecto devolvido por ``GET /auth/v1/user``.
        provider_token: ``provider_token`` da sessão Supabase (opcional).
        stored_profile_url: URL de ``localStorage`` (opcional).
        database_profile_url: URL lido de ``user_linkedin_profiles`` (opcional).
        id_token: JWT OIDC LinkedIn capturado no login (opcional).

    Retorno:
        URL normalizado ``https://www.linkedin.com/in/...`` ou ``None``.
    """

    raw_url = resolve_linkedin_profile_url_for_session(
        user,
        provider_token,
        stored_profile_url=stored_profile_url,
        database_profile_url=database_profile_url,
        id_token=id_token,
    )
    if not raw_url:
        return None
    try:
        return _normalize_linkedin_public_profile_input(raw_url)
    except ValueError:
        return None


def _linkedin_profile_url_from_supabase_user(user: Dict[str, Any]) -> Optional[str]:
    """Wrapper: metadados Supabase → URL LinkedIn normalizado.

    Argumentos:
        user: Resposta ``GET /auth/v1/user``.

    Retorno:
        URL ``https://www.linkedin.com/in/...`` ou ``None``.
    """

    raw = extract_linkedin_profile_url_from_supabase_user(user)
    if not raw:
        return None
    try:
        return _normalize_linkedin_public_profile_input(raw)
    except ValueError:
        return None


def _linkedin_harvest_profile_scraper_actor() -> str:
    """Actor Apify para a Visão Geral (perfil detalhado sem cookies).

    Argumentos:
        Nenhum.

    Retorno:
        Identificador do actor (por defeito ``harvestapi/linkedin-profile-scraper``).
    """

    return os.getenv(
        "APIFY_LINKEDIN_PROFILE_SCRAPER_ACTOR",
        "harvestapi/linkedin-profile-scraper",
    ).strip()


def _map_apify_linkedin_profile_record(first: Dict[str, Any], source_url: str) -> Dict[str, Any]:
    """Converte um registo do actor Apify LinkedIn para o formato interno de perfil.

    Suporta o formato ``harvestapi/linkedin-profile-scraper`` (``connectionsCount``,
    ``experience``, ``education``, etc.) e formatos genéricos de profile scraper.

    Argumentos:
        first: Primeiro item do dataset Apify (dicionário).
        source_url: URL pedido ao actor (fallback de identificação).

    Retorno:
        Dicionário alinhado com o usado em ``profile-analyze`` / UI (seguidores,
        headline, ``harvest_profile`` bruto, ``apify_enrichment`` quando há posts).
    """

    followers = first.get("followerCount")
    if followers is None:
        followers = first.get("followers_count") or first.get("followers")

    connections = first.get("connectionsCount")
    if connections is None:
        connections = first.get("connections") or first.get("connectionCount")

    headline = first.get("jobTitle") or first.get("headline")
    summary = first.get("description") or first.get("about") or first.get("summary")
    profile_slug = (
        str(first.get("publicIdentifier") or first.get("username") or "").strip()
        or source_url.rsplit("/", 1)[-1][:80]
    )

    employer: Optional[str] = first.get("employer")
    if not employer:
        current = first.get("currentPosition")
        if isinstance(current, list) and current and isinstance(current[0], dict):
            employer = current[0].get("companyName")

    location_val = first.get("location")
    location_text: Optional[str] = None
    if isinstance(location_val, str):
        location_text = location_val.strip() or None
    elif isinstance(location_val, dict):
        parsed = location_val.get("parsed")
        if isinstance(parsed, dict):
            location_text = str(parsed.get("text") or "").strip() or None
        if not location_text:
            location_text = str(
                location_val.get("linkedinText") or location_val.get("text") or ""
            ).strip() or None

    recent_raw = first.get("recentPosts") if isinstance(first.get("recentPosts"), list) else []
    posts_norm: List[Dict[str, Any]] = []
    for post in recent_raw[:30]:
        if not isinstance(post, dict):
            continue
        ts = post.get("datePublished") or post.get("publishedAt") or post.get("timestamp")
        posts_norm.append(
            {
                "type": "linkedin_post",
                "caption": post.get("text") or post.get("headline"),
                "likesCount": post.get("likeCount") or post.get("likesCount") or 0,
                "commentsCount": post.get("commentsCount") or post.get("commentCount") or 0,
                "timestamp": ts,
                "url": post.get("url"),
            }
        )

    enrichment: Dict[str, Any] = {}
    if posts_norm:
        enrichment = _build_linkedin_enriched_metrics(followers, posts_norm) or {}

    engagement_rate: Optional[float] = None
    if isinstance(enrichment, dict) and enrichment.get("avg_engagement_pct") is not None:
        try:
            engagement_rate = float(enrichment["avg_engagement_pct"])
        except (TypeError, ValueError):
            engagement_rate = None

    filled = sum(1 for v in (followers, connections, headline, summary) if v)
    data_quality = "alta" if filled >= 2 else ("media" if filled == 1 else "baixa")

    profile_image = (
        first.get("profileImageUrl")
        or first.get("photo")
        or first.get("profilePictureUrl")
    )

    return {
        "platform": "linkedin",
        "profile": profile_slug,
        "profile_url": first.get("profileUrl")
        or first.get("linkedinUrl")
        or first.get("linkedinPublicUrl")
        or source_url,
        "followers_count": followers,
        "connections_count": connections,
        "posts_count": len(posts_norm) if posts_norm else first.get("postsCount"),
        "engagement_rate": engagement_rate,
        "headline": headline,
        "summary": summary,
        "location": location_text or location_val,
        "employer": employer,
        "education": first.get("education"),
        "experience": first.get("experience"),
        "profile_image_url": profile_image,
        "recent_posts": posts_norm,
        "collection_method": "apify_linkedin_profile",
        "data_quality": data_quality,
        "apify_raw_headline": first.get("jobTitle"),
        "apify_enrichment": enrichment,
        "harvest_profile": first,
    }


def _apify_actor_api_path(actor_id: str) -> str:
    """Normaliza o identificador do actor para URLs da API Apify v2.

    Argumentos:
        actor_id: ID curto (ex.: ``LQQIXN9Othf8f7R5n``) ou ``user/actor-name``.

    Retorno:
        Segmento de path aceite por ``/v2/acts/{id}/...``.
    """

    aid = str(actor_id or "").strip()
    return aid.replace("/", "~") if "/" in aid else aid


def _run_apify_actor_start_and_poll(
    actor_id: str,
    payload: Dict[str, Any],
    *,
    poll_interval_sec: float = 5.0,
    max_wait_sec: int = 180,
) -> List[Any]:
    """Inicia um actor Apify, espera conclusão e devolve itens do dataset.

    Usa o mesmo fluxo da app Next.js (``POST /acts/{id}/runs`` + polling), mais
    fiável que ``run-sync`` para actors de posts LinkedIn.

    Argumentos:
        actor_id: Identificador do actor Apify.
        payload: Input JSON do actor.
        poll_interval_sec: Intervalo entre polls de estado.
        max_wait_sec: Tempo máximo de espera.

    Retorno:
        Lista de registos do dataset.

    Raises:
        RuntimeError: Token em falta, run falhou ou timeout.
    """

    apify_token = os.getenv("APIFY_API_TOKEN", "").strip()
    if not apify_token:
        raise RuntimeError("APIFY_API_TOKEN não configurado.")
    if not actor_id:
        raise RuntimeError("Apify actor id inválido.")
    if _is_linkedin_apify_actor_blocked(actor_id):
        raise RuntimeError(
            f"Actor Apify bloqueado: {actor_id}. "
            "Remove sourabhbgp/linkedin-profile-scraper do .env e reinicia o uvicorn."
        )

    actor_path = _apify_actor_api_path(actor_id)
    start_url = f"https://api.apify.com/v2/acts/{actor_path}/runs?token={apify_token}"
    start_req = request.Request(
        start_url,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    try:
        with request.urlopen(start_req, timeout=60) as resp:
            start_data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(
            f"Apify ({actor_id}) HTTP {exc.code} ao iniciar run: {err_body[:320] or 'sem detalhe'}"
        ) from exc
    except (error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Falha ao iniciar Apify ({actor_id}): {exc!s}") from exc

    run_id = (start_data.get("data") or {}).get("id")
    if not run_id:
        raise RuntimeError(f"Apify ({actor_id}) não devolveu run id.")

    import time

    deadline = time.time() + max_wait_sec
    run_status = "RUNNING"
    dataset_id: Optional[str] = None
    while run_status in ("RUNNING", "READY") and time.time() < deadline:
        time.sleep(poll_interval_sec)
        status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={apify_token}"
        status_req = request.Request(status_url, method="GET")
        try:
            with request.urlopen(status_req, timeout=30) as resp:
                status_data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except (error.HTTPError, error.URLError, json.JSONDecodeError, TimeoutError, OSError):
            continue
        run_status = str((status_data.get("data") or {}).get("status") or "UNKNOWN")
        dataset_id = (status_data.get("data") or {}).get("defaultDatasetId")

    if run_status != "SUCCEEDED":
        raise RuntimeError(
            f"Apify ({actor_id}) run {run_id} terminou com estado {run_status}. "
            "Confirma no Apify Console se o actor está activo e se o URL do perfil é público."
        )
    if not dataset_id:
        raise RuntimeError(f"Apify ({actor_id}) run {run_id} sem dataset.")

    items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={apify_token}"
    items_req = request.Request(items_url, method="GET")
    try:
        with request.urlopen(items_req, timeout=120) as resp:
            items = json.loads(resp.read().decode("utf-8", errors="replace"))
    except error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(
            f"Apify ({actor_id}) HTTP {exc.code} ao ler dataset: {err_body[:280] or 'sem detalhe'}"
        ) from exc
    except (error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Falha ao ler dataset Apify ({actor_id}): {exc!s}") from exc

    return items if isinstance(items, list) else []


def _parse_linkedin_post_timestamp(ts_raw: Any) -> Optional[datetime]:
    """Converte vários formatos de data de posts LinkedIn (Apify) para ``datetime`` UTC.

    Aceita ISO-8601, timestamps Unix (s ou ms) e datas simples ``YYYY-MM-DD``.

    Argumentos:
        ts_raw: Valor de data vindo do actor Apify.

    Retorno:
        ``datetime`` com timezone UTC, ou ``None`` se não for interpretável.
    """

    if ts_raw is None:
        return None
    if isinstance(ts_raw, datetime):
        return ts_raw if ts_raw.tzinfo else ts_raw.replace(tzinfo=timezone.utc)
    if isinstance(ts_raw, (int, float)):
        try:
            val = float(ts_raw)
            if val > 1e12:
                val /= 1000.0
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return None
    text = str(ts_raw).strip()
    if not text or text.lower() in {"null", "none", "n/a"}:
        return None
    if text.isdigit():
        try:
            val = float(text)
            if val > 1e12:
                val /= 1000.0
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            parsed = datetime.strptime(text[:19], fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _extract_linkedin_followers_from_apify_posts(raw_posts: List[Any]) -> Optional[Any]:
    """Tenta obter seguidores/ligações a partir de metadados nos posts Apify.

    Alguns actors incluem ``followerCount`` no autor ou na página da organização.

    Argumentos:
        raw_posts: Itens crus do dataset Apify.

    Retorno:
        Número de seguidores/ligações, ou ``None`` se não encontrado.
    """

    for post in raw_posts:
        if not isinstance(post, dict):
            continue
        for key in (
            "followerCount",
            "followersCount",
            "followers_count",
            "followers",
            "companyFollowerCount",
            "pageFollowerCount",
        ):
            val = post.get(key)
            if isinstance(val, (int, float)) and val > 0:
                return val
        for nested_key in ("author", "company", "organization", "page", "school"):
            nested = post.get(nested_key)
            if not isinstance(nested, dict):
                continue
            for key in ("followerCount", "followersCount", "followers_count", "followers"):
                val = nested.get(key)
                if isinstance(val, (int, float)) and val > 0:
                    return val
    return None


def _linkedin_profile_type_from_url(profile_url: str) -> str:
    """Identifica o tipo de página LinkedIn a partir do URL.

    Argumentos:
        profile_url: URL público normalizado.

    Retorno:
        ``school``, ``company`` ou ``personal``.
    """

    lower = str(profile_url or "").lower()
    if "/school/" in lower:
        return "school"
    if "/company/" in lower:
        return "company"
    return "personal"


def _normalize_linkedin_apify_posts(raw_posts: List[Any]) -> List[Dict[str, Any]]:
    """Normaliza posts devolvidos por actors LinkedIn (Apify) para métricas internas.

    Suporta formatos ``apimaestro`` (``text``, ``numLikes``), ``harvestapi``
    (``content``, ``engagement.likes``) e variantes legadas.

    Argumentos:
        raw_posts: Lista crua do dataset Apify.

    Retorno:
        Lista de posts no formato usado por ``_build_apify_enriched_metrics``.
    """

    posts_norm: List[Dict[str, Any]] = []
    for post in raw_posts:
        if not isinstance(post, dict):
            continue
        engagement = post.get("engagement")
        likes = post.get("numLikes") or post.get("likesCount") or post.get("likeCount")
        comments = post.get("numComments") or post.get("commentsCount") or post.get("commentCount")
        if isinstance(engagement, dict):
            likes = engagement.get("likes") or engagement.get("likeCount") or likes
            comments = engagement.get("comments") or engagement.get("commentCount") or comments
        posts_norm.append(
            {
                "type": "linkedin_post",
                "caption": post.get("text") or post.get("content") or post.get("headline"),
                "likesCount": likes or 0,
                "commentsCount": comments or 0,
                "timestamp": post.get("postedAt")
                or post.get("postedDate")
                or post.get("date")
                or post.get("timestamp")
                or post.get("publishedAt")
                or post.get("createdAt")
                or post.get("time"),
                "url": post.get("url") or post.get("postUrl") or post.get("linkedinUrl"),
            }
        )
    return posts_norm


_LINKEDIN_APIFY_BLOCKED_ACTORS = frozenset(
    {
        "sourabhbgp/linkedin-profile-scraper",
        "sourabhbgp~linkedin-profile-scraper",
        "9giyykld4qn2ddnp4",  # ID curto Apify do sourabhbgp/linkedin-profile-scraper
    }
)


def _is_linkedin_apify_actor_blocked(actor_id: str) -> bool:
    """Indica se um actor LinkedIn está na lista negra (nunca deve correr).

    Argumentos:
        actor_id: Identificador ``user/actor`` ou ID curto Apify.

    Retorno:
        ``True`` para ``sourabhbgp`` e aliases conhecidos; ``False`` caso contrário.
    """

    aid = str(actor_id or "").strip().lower().replace("~", "/")
    if not aid:
        return True
    if aid in _LINKEDIN_APIFY_BLOCKED_ACTORS:
        return True
    if aid.replace("/", "~") in _LINKEDIN_APIFY_BLOCKED_ACTORS:
        return True
    if "sourabhbgp" in aid:
        return True
    return False


def _sanitize_linkedin_apify_actor_chain(chain: List[str]) -> List[str]:
    """Remove actors bloqueados e duplicados, preservando a ordem.

    Argumentos:
        chain: Lista bruta de actors (ex.: variável de ambiente).

    Retorno:
        Lista filtrada sem ``sourabhbgp`` nem entradas vazias.
    """

    seen: set[str] = set()
    out: List[str] = []
    for actor_id in chain:
        aid = str(actor_id or "").strip()
        if not aid or _is_linkedin_apify_actor_blocked(aid):
            continue
        key = aid.lower().replace("~", "/")
        if key in seen:
            continue
        seen.add(key)
        out.append(aid)
    return out


def _linkedin_apify_actor_chain_from_env() -> List[str]:
    """Lê a ordem de actors LinkedIn a tentar (variável ``APIFY_LINKEDIN_ACTOR_CHAIN``).

    Por defeito: ``harvestapi/linkedin-profile-posts`` → empregados (só ``/company/``)
    → ``APIFY_LINKEDIN_POSTS_ACTOR`` (apimaestro). ``sourabhbgp`` é sempre removido.

    Argumentos:
        Nenhum.

    Retorno:
        Lista de identificadores Apify (``user/actor`` ou ID curto).
    """

    raw = os.getenv("APIFY_LINKEDIN_ACTOR_CHAIN", "").strip()
    posts_fallback = os.getenv("APIFY_LINKEDIN_POSTS_ACTOR", "LQQIXN9Othf8f7R5n").strip()
    if raw:
        chain = [part.strip() for part in raw.split(",") if part.strip()]
    else:
        chain = [
            "harvestapi/linkedin-profile-posts",
            "harvestapi/linkedin-company-employees",
        ]
        if posts_fallback:
            chain.append(posts_fallback)
    return _sanitize_linkedin_apify_actor_chain(chain)


@app.on_event("startup")
def _log_linkedin_apify_chain_on_startup() -> None:
    """Regista no log a cadeia Apify LinkedIn activa (diagnóstico de actors antigos)."""

    load_dotenv(BASE_DIR / ".env", override=True)
    chain = _linkedin_apify_actor_chain_from_env()
    print(
        "[PlataformaV1] LinkedIn Apify actors:",
        ", ".join(chain) if chain else "(nenhum — define APIFY_LINKEDIN_ACTOR_CHAIN)",
        flush=True,
    )


def _linkedin_apify_actor_kind(actor_id: str) -> str:
    """Classifica um actor Apify LinkedIn para escolher payload e parser.

    Argumentos:
        actor_id: Identificador do actor (``user/actor`` ou ID curto).

    Retorno:
        Uma de: ``blocked``, ``company_employees``, ``harvest_posts``,
        ``profile_scraper``, ``apimaestro_posts``, ``posts_generic``.
    """

    if _is_linkedin_apify_actor_blocked(actor_id):
        return "blocked"
    aid = str(actor_id or "").strip().lower().replace("~", "/")
    if "linkedin-company-employees" in aid:
        return "company_employees"
    if "harvestapi" in aid and "linkedin-profile-posts" in aid:
        return "harvest_posts"
    if "harvestapi" in aid and "linkedin-profile-scraper" in aid:
        return "harvest_profile_scraper"
    if "linkedin-profile-scraper" in aid or aid.endswith("/linkedin-profile-scraper"):
        return "profile_scraper"
    if aid == "lqqixn9othf8f7r5n" or "apimaestro" in aid:
        return "apimaestro_posts"
    return "posts_generic"


def _should_skip_linkedin_apify_actor(actor_id: str, profile_url: str) -> bool:
    """Indica se um actor deve ser ignorado para o URL dado.

    O actor de empregados só aplica a páginas ``/company/``. Actors bloqueados
    (ex.: ``sourabhbgp``) nunca correm.

    Argumentos:
        actor_id: Actor Apify candidato.
        profile_url: URL normalizado do perfil ou empresa.

    Retorno:
        ``True`` para saltar este actor na cadeia.
    """

    kind = _linkedin_apify_actor_kind(actor_id)
    if kind == "blocked":
        return True
    if kind == "company_employees" and "/company/" not in profile_url.lower():
        return True
    return False


def _build_linkedin_apify_actor_payload(profile_url: str, actor_id: str) -> Dict[str, Any]:
    """Constrói o JSON de input do actor Apify consoante o tipo.

    Argumentos:
        profile_url: URL LinkedIn público (perfil ou empresa).
        actor_id: Identificador do actor na cadeia.

    Retorno:
        Dicionário pronto para ``POST /acts/{id}/runs``.
    """

    limit = max(1, min(int(os.getenv("APIFY_LINKEDIN_POSTS_LIMIT", "50") or "50"), 100))
    kind = _linkedin_apify_actor_kind(actor_id)
    if kind == "harvest_posts":
        return {
            "targetUrls": [profile_url],
            "maxPosts": limit,
            "includeQuotePosts": True,
            "includeReposts": True,
            "scrapeReactions": False,
            "scrapeComments": False,
        }
    if kind == "harvest_profile_scraper":
        mode = os.getenv(
            "APIFY_LINKEDIN_PROFILE_SCRAPER_MODE",
            "Profile details no email ($4 per 1k)",
        ).strip()
        return {
            "profileScraperMode": mode or "Profile details no email ($4 per 1k)",
            "queries": [profile_url],
        }
    if kind == "profile_scraper":
        return {"profileUrls": [profile_url]}
    if kind == "company_employees":
        return {
            "companies": [profile_url],
            "maxItems": min(limit, 25),
            "profileScraperMode": "Short",
        }
    if kind == "apimaestro_posts":
        return {"username": profile_url, "limit": limit, "page_number": 1}
    return {"username": profile_url, "limit": limit, "page_number": 1}


def _linkedin_profile_bundle_has_usable_content(bundle: Dict[str, Any]) -> bool:
    """Indica se os dados recolhidos chegam para análise OpenAI.

    Argumentos:
        bundle: Dicionário ``public_profile_data`` parcial ou completo.

    Retorno:
        ``True`` se houver posts, perfil rico ou amostra de empregados.
    """

    if _linkedin_apify_posts_have_usable_content(bundle.get("recent_posts") or []):
        return True
    employees = bundle.get("employees_sample")
    if isinstance(employees, list) and employees:
        return True
    if bundle.get("headline") or bundle.get("summary"):
        return True
    followers = bundle.get("followers_count")
    if isinstance(followers, (int, float)) and followers > 0:
        return True
    return False


def _linkedin_profile_bundle_from_company_employees(
    profile_url: str,
    raw_items: List[Any],
    actor_id: str,
) -> Dict[str, Any]:
    """Monta dados de empresa a partir do actor ``harvestapi/linkedin-company-employees``.

    Argumentos:
        profile_url: URL ``https://www.linkedin.com/company/...``.
        raw_items: Registos do dataset (perfis de colaboradores).
        actor_id: Actor utilizado.

    Retorno:
        Estrutura ``public_profile_data`` com ``employees_sample``.
    """

    employees: List[Dict[str, Any]] = [e for e in raw_items if isinstance(e, dict)]
    slug = profile_url.rstrip("/").rsplit("/", 1)[-1][:80]
    return {
        "platform": "linkedin",
        "profile": slug,
        "profile_url": profile_url,
        "profile_type": "company",
        "employees_count": len(employees),
        "employees_sample": employees[:15],
        "posts_count": 0,
        "recent_posts": [],
        "collection_method": f"apify:{actor_id}",
        "data_quality": "media" if employees else "baixa",
    }


def _fetch_linkedin_apify_actor(profile_url: str, actor_id: str) -> Dict[str, Any]:
    """Executa um actor Apify LinkedIn e devolve o bundle normalizado.

    Argumentos:
        profile_url: URL público normalizado.
        actor_id: Actor da cadeia ``APIFY_LINKEDIN_ACTOR_CHAIN``.

    Retorno:
        Dicionário ``public_profile_data`` para análise.

    Raises:
        RuntimeError: Run falhou, dataset vazio ou dados inúteis.
    """

    kind = _linkedin_apify_actor_kind(actor_id)
    payload = _build_linkedin_apify_actor_payload(profile_url, actor_id)
    items = _run_apify_actor_start_and_poll(actor_id, payload, max_wait_sec=300)
    if not items:
        raise RuntimeError(f"Apify ({actor_id}) devolveu dataset vazio.")

    if kind == "company_employees":
        bundle = _linkedin_profile_bundle_from_company_employees(profile_url, items, actor_id)
    elif kind in ("harvest_posts", "apimaestro_posts", "posts_generic"):
        post_items = [i for i in items if isinstance(i, dict) and i.get("type") != "profile"]
        if not post_items and kind == "harvest_posts":
            post_items = items
        bundle = _linkedin_profile_bundle_from_posts(profile_url, post_items, actor_id)
    elif kind in ("harvest_profile_scraper", "profile_scraper"):
        first = items[0]
        if not isinstance(first, dict):
            raise RuntimeError(f"Apify ({actor_id}) devolveu item inválido.")
        bundle = _map_apify_linkedin_profile_record(first, profile_url)
        bundle["collection_method"] = f"apify:{actor_id}"
        bundle["overview_source"] = f"apify:{actor_id}"
    else:
        first = items[0]
        if not isinstance(first, dict):
            raise RuntimeError(f"Apify ({actor_id}) devolveu item inválido.")
        bundle = _map_apify_linkedin_profile_record(first, profile_url)
        bundle["collection_method"] = f"apify:{actor_id}"

    if not _linkedin_profile_bundle_has_usable_content(bundle):
        raise RuntimeError(
            f"Apify ({actor_id}) devolveu dados insuficientes para {profile_url}."
        )
    return bundle


def _linkedin_profile_bundle_from_posts(
    profile_url: str,
    raw_posts: List[Any],
    actor_id: str,
) -> Dict[str, Any]:
    """Monta o dicionário de perfil LinkedIn a partir de posts Apify.

    Argumentos:
        profile_url: URL público do perfil analisado.
        raw_posts: Itens do dataset (posts).
        actor_id: Actor Apify utilizado.

    Retorno:
        Estrutura ``public_profile_data`` para análise OpenAI.
    """

    posts_norm = _normalize_linkedin_apify_posts(raw_posts)
    slug = profile_url.rstrip("/").rsplit("/", 1)[-1][:80]
    followers = _extract_linkedin_followers_from_apify_posts(raw_posts)
    enrichment = _build_linkedin_enriched_metrics(followers, posts_norm) or {}
    engagement_rate: Optional[float] = None
    if enrichment.get("avg_engagement_pct") is not None:
        try:
            engagement_rate = float(enrichment["avg_engagement_pct"])
        except (TypeError, ValueError):
            engagement_rate = None
    data_quality = "alta" if len(posts_norm) >= 10 else ("media" if posts_norm else "baixa")
    return {
        "platform": "linkedin",
        "profile": slug,
        "profile_url": profile_url,
        "profile_type": _linkedin_profile_type_from_url(profile_url),
        "followers_count": followers,
        "posts_count": len(posts_norm),
        "engagement_rate": engagement_rate,
        "recent_posts": posts_norm,
        "collection_method": f"apify:{actor_id}",
        "data_quality": data_quality,
        "apify_enrichment": enrichment,
    }


def _fetch_linkedin_via_apify_posts_actor(profile_url: str, actor_id: str) -> Dict[str, Any]:
    """Recolhe posts públicos LinkedIn via um actor de posts Apify.

    Argumentos:
        profile_url: URL ``https://www.linkedin.com/in/...`` ou ``/company/...``.
        actor_id: Actor Apify (ex.: ``harvestapi/linkedin-profile-posts``).

    Retorno:
        Dicionário de perfil com posts recentes e métricas derivadas.

    Raises:
        RuntimeError: Run falhou ou dados inúteis.
    """

    return _fetch_linkedin_apify_actor(profile_url, actor_id)


def _linkedin_apify_posts_have_usable_content(posts: List[Dict[str, Any]]) -> bool:
    """Indica se a lista de posts do Apify tem conteúdo útil para análise.

    O actor de posts pode devolver 1 registo vazio quando o slug do URL é um ID
    interno (ex.: ``juGxdU4AEW``) em vez do vanity name público.

    Argumentos:
        posts: Lista normalizada ``recent_posts``.

    Retorno:
        ``True`` se existir pelo menos um post com texto, URL ou engagement.
    """

    for post in posts:
        if not isinstance(post, dict):
            continue
        caption = str(post.get("caption") or "").strip()
        url = str(post.get("url") or "").strip()
        likes = post.get("likesCount")
        comments = post.get("commentsCount")
        ts = post.get("timestamp")
        if caption or url:
            return True
        if (isinstance(likes, (int, float)) and likes > 0) or (
            isinstance(comments, (int, float)) and comments > 0
        ):
            return True
        if ts:
            return True
    return False


def _merge_harvest_profile_into_bundle(
    bundle: Dict[str, Any],
    harvest_bundle: Dict[str, Any],
) -> Dict[str, Any]:
    """Combina dados de posts com o perfil harvestapi para Visão Geral e análise IA.

    Mantém ``recent_posts`` e ``apify_enrichment`` do bundle principal; acrescenta
    ``harvest_profile`` e campos de perfil (ligações, headline, experiência).

    Argumentos:
        bundle: Dados recolhidos pela cadeia de posts (ou vazio).
        harvest_bundle: Resultado de ``harvestapi/linkedin-profile-scraper``.

    Retorno:
        Dicionário unificado para ``public_profile_data``.
    """

    merged: Dict[str, Any] = dict(bundle) if isinstance(bundle, dict) else {}
    if not isinstance(harvest_bundle, dict):
        return merged

    harvest_raw = harvest_bundle.get("harvest_profile")
    if isinstance(harvest_raw, dict):
        merged["harvest_profile"] = harvest_raw

    merged["overview_source"] = (
        harvest_bundle.get("overview_source")
        or harvest_bundle.get("collection_method")
        or merged.get("overview_source")
    )

    for key in (
        "headline",
        "summary",
        "followers_count",
        "connections_count",
        "location",
        "employer",
        "education",
        "experience",
        "profile_image_url",
        "profile_url",
    ):
        if merged.get(key) in (None, "", []):
            val = harvest_bundle.get(key)
            if val not in (None, "", []):
                merged[key] = val

    if merged.get("followers_count") is None:
        merged["followers_count"] = harvest_bundle.get("followers_count")
    if merged.get("connections_count") is None:
        merged["connections_count"] = harvest_bundle.get("connections_count")

    if merged.get("data_quality") in (None, "baixa") and harvest_bundle.get("data_quality"):
        merged["data_quality"] = harvest_bundle["data_quality"]

    return merged


def _enrich_linkedin_bundle_with_harvest_profile_scraper(
    bundle: Dict[str, Any],
    profile_url: str,
) -> Dict[str, Any]:
    """Executa ``harvestapi/linkedin-profile-scraper`` e funde no bundle de análise.

    Falhas do actor de perfil não interrompem a análise (posts podem ter sucesso).

    Argumentos:
        bundle: ``public_profile_data`` já recolhido (posts).
        profile_url: URL LinkedIn normalizado.

    Retorno:
        Bundle com ``harvest_profile`` quando o scrape de perfil tiver sucesso.
    """

    actor = _linkedin_harvest_profile_scraper_actor()
    if not actor or _is_linkedin_apify_actor_blocked(actor):
        return bundle

    try:
        harvest_bundle = _fetch_linkedin_apify_actor(profile_url, actor)
        return _merge_harvest_profile_into_bundle(bundle, harvest_bundle)
    except RuntimeError as exc:
        out = dict(bundle)
        out["harvest_profile_error"] = str(exc)[:320]
        return out


def _fetch_linkedin_public_profile_with_apify(profile_url: str) -> Dict[str, Any]:
    """Recolhe dados públicos de um perfil LinkedIn via cadeia de actors Apify.

    Ordem por defeito (``APIFY_LINKEDIN_ACTOR_CHAIN``):

    1. ``harvestapi/linkedin-profile-posts`` — posts sem cookies
    2. ``harvestapi/linkedin-company-employees`` — só URLs ``/company/``
    3. ``APIFY_LINKEDIN_POSTS_ACTOR`` (ex.: ``LQQIXN9Othf8f7R5n`` / apimaestro)

    Depois, sempre que configurado, corre ``APIFY_LINKEDIN_PROFILE_SCRAPER_ACTOR``
    (por defeito ``harvestapi/linkedin-profile-scraper``) para a Visão Geral.

    ``sourabhbgp/linkedin-profile-scraper`` nunca corre (bloqueado no código).

    Argumentos:
        profile_url: URL normalizado do perfil (``/in/`` ou ``/company/``).

    Retorno:
        Dicionário de métricas e texto para a análise OpenAI.

    Raises:
        RuntimeError: Todos os actors da cadeia de posts falharam.
    """

    chain = _linkedin_apify_actor_chain_from_env()
    if not chain:
        raise RuntimeError(
            "Define APIFY_LINKEDIN_ACTOR_CHAIN ou APIFY_LINKEDIN_POSTS_ACTOR no .env."
        )

    errors: List[str] = []
    bundle: Optional[Dict[str, Any]] = None
    for actor_id in chain:
        if _should_skip_linkedin_apify_actor(actor_id, profile_url):
            continue
        try:
            bundle = _fetch_linkedin_apify_actor(profile_url, actor_id)
            break
        except RuntimeError as exc:
            msg = str(exc)
            if "full-permission-actor-not-approved" in msg or "full access" in msg.lower():
                msg = (
                    f"{msg} — Aprova o actor em Apify Console → Settings → "
                    "Third-party actors / full access, ou remove-o da cadeia."
                )
            errors.append(f"[{actor_id}] {msg}")

    if bundle is None:
        raise RuntimeError(
            f"Nenhum actor Apify conseguiu dados para {profile_url}. "
            + " | ".join(errors[:4])
            + (
                " Cadeia actual: "
                + ", ".join(chain)
                + ". Ajusta APIFY_LINKEDIN_ACTOR_CHAIN no .env."
            )
        )

    return _enrich_linkedin_bundle_with_harvest_profile_scraper(bundle, profile_url)


def _fetch_instagram_posts_with_apify(username: str, results_limit: int = 30) -> List[Dict[str, Any]]:
    """Recolhe posts públicos recentes do Instagram via Apify Post Scraper.

    A função executa um actor Apify orientado a posts (`apify/instagram-post-scraper`
    por defeito) e devolve uma lista normalizada de posts recentes com
    métricas de engagement públicas.

    Variáveis de ambiente suportadas:
        - `APIFY_API_TOKEN`: token de autenticação.
        - `APIFY_INSTAGRAM_POST_SCRAPER_ACTOR`: actor id opcional. Por
          defeito `apify/instagram-post-scraper`.

    Argumentos:
        username: Username Instagram sem `@`.
        results_limit: Número máximo de posts a recolher (default 30).

    Retorno:
        Lista de dicionários com os campos: `id`, `type`, `caption`,
        `likesCount`, `commentsCount`, `videoPlayCount`, `videoViewCount`,
        `timestamp`, `url`, `hashtags`, `mentions`. Lista vazia se o actor
        não devolver posts.

    Raises:
        RuntimeError: Quando o actor falha ou devolve payload inválido.
    """

    actor_id = os.getenv(
        "APIFY_INSTAGRAM_POST_SCRAPER_ACTOR", "apify/instagram-post-scraper"
    ).strip()
    payload = {
        "username": [username],
        "resultsLimit": max(1, min(int(results_limit or 30), 100)),
    }
    items = _run_apify_actor_sync(actor_id, payload, timeout=120)
    posts: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        posts.append(
            {
                "id": item.get("id") or item.get("shortCode"),
                "type": item.get("type") or item.get("productType"),
                "caption": item.get("caption"),
                "likesCount": item.get("likesCount"),
                "commentsCount": item.get("commentsCount"),
                "videoPlayCount": item.get("videoPlayCount"),
                "videoViewCount": item.get("videoViewCount"),
                "timestamp": item.get("timestamp"),
                "url": item.get("url"),
                "hashtags": item.get("hashtags"),
                "mentions": item.get("mentions"),
            }
        )
    return posts


def _fetch_instagram_reels_with_apify(username: str, results_limit: int = 20) -> List[Dict[str, Any]]:
    """Recolhe reels públicos recentes do Instagram via Apify Reel Scraper.

    A função executa um actor Apify orientado a reels
    (`apify/instagram-reel-scraper` por defeito) e devolve uma lista
    normalizada com métricas públicas relevantes (playCount, likes,
    comentários, duração).

    Variáveis de ambiente suportadas:
        - `APIFY_API_TOKEN`: token de autenticação.
        - `APIFY_INSTAGRAM_REEL_SCRAPER_ACTOR`: actor id opcional. Por
          defeito `apify/instagram-reel-scraper`.

    Argumentos:
        username: Username Instagram sem `@`.
        results_limit: Número máximo de reels a recolher (default 20).

    Retorno:
        Lista de dicionários com os campos: `id`, `caption`, `likesCount`,
        `commentsCount`, `videoPlayCount`, `videoViewCount`,
        `videoDuration`, `timestamp`, `url`. Lista vazia se o actor não
        devolver reels.

    Raises:
        RuntimeError: Quando o actor falha ou devolve payload inválido.
    """

    actor_id = os.getenv(
        "APIFY_INSTAGRAM_REEL_SCRAPER_ACTOR", "apify/instagram-reel-scraper"
    ).strip()
    payload = {
        "username": [username],
        "resultsLimit": max(1, min(int(results_limit or 20), 100)),
    }
    items = _run_apify_actor_sync(actor_id, payload, timeout=120)
    reels: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        reels.append(
            {
                "id": item.get("id") or item.get("shortCode"),
                "caption": item.get("caption"),
                "likesCount": item.get("likesCount"),
                "commentsCount": item.get("commentsCount"),
                "videoPlayCount": item.get("videoPlayCount") or item.get("playCount"),
                "videoViewCount": item.get("videoViewCount") or item.get("viewCount"),
                "videoDuration": item.get("videoDuration") or item.get("duration"),
                "timestamp": item.get("timestamp"),
                "url": item.get("url"),
            }
        )
    return reels


def _classify_linkedin_post_format(post: Dict[str, Any]) -> str:
    """Classifica uma publicação LinkedIn por tipo de conteúdo.

    Argumentos:
        post: Dicionário normalizado de publicação LinkedIn (Apify).

    Retorno:
        Uma de: ``texto``, ``artigo``, ``documento``, ``poll``, ``imagem``,
        ``video``, ``evento``, ``partilha``, ``desconhecido``.
    """

    raw_type = str(post.get("type") or post.get("contentType") or "").strip().lower()
    caption = str(post.get("caption") or post.get("text") or "").lower()
    combined = f"{raw_type} {caption}"
    if "poll" in combined:
        return "poll"
    if "article" in combined or "newsletter" in combined:
        return "artigo"
    if "document" in combined or "pdf" in combined or "carousel" in combined:
        return "documento"
    if "event" in combined:
        return "evento"
    if "reshared" in combined or "repost" in combined or "shared" in combined:
        return "partilha"
    if "video" in combined or post.get("videoPlayCount") is not None:
        return "video"
    if "image" in combined or "photo" in combined:
        return "imagem"
    if raw_type in ("linkedin_post", "post", "text", ""):
        return "texto"
    return "texto" if caption else "desconhecido"


def _build_linkedin_enriched_metrics(
    followers_count: Optional[Any],
    posts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Agrega métricas derivadas de publicações LinkedIn (Apify).

    Calcula distribuição por tipo de conteúdo LinkedIn, top publicações por
    reações, cadência e médias de engagement — sem terminologia Instagram.

    Argumentos:
        followers_count: Número de ligações (seguidores) quando disponível.
        posts: Lista normalizada de publicações LinkedIn.

    Retorno:
        Dicionário com ``content_type_distribution``, ``top_posts``,
        ``posting_cadence``, médias de reações/comentários e ``avg_engagement_pct``.
    """

    if not posts:
        return {}

    type_counter: Dict[str, int] = {}
    type_engagement: Dict[str, List[float]] = {}
    timestamps: List[datetime] = []
    total_reactions = 0.0
    total_comments = 0.0
    followers_num = _safe_float(followers_count)

    for item in posts:
        if not isinstance(item, dict):
            continue
        fmt = _classify_linkedin_post_format(item)
        type_counter[fmt] = type_counter.get(fmt, 0) + 1
        likes = _safe_float(item.get("likesCount")) or 0.0
        comments = _safe_float(item.get("commentsCount")) or 0.0
        total_reactions += likes
        total_comments += comments
        interactions = likes + comments
        if followers_num and followers_num > 0:
            er = (interactions / followers_num) * 100.0
        else:
            er = interactions
        type_engagement.setdefault(fmt, []).append(er)
        parsed_ts = _parse_linkedin_post_timestamp(item.get("timestamp"))
        if parsed_ts is not None:
            timestamps.append(parsed_ts)

    n = len(posts) or 1
    total_types = sum(type_counter.values()) or 1
    content_type_distribution = {
        fmt: {
            "count": count,
            "share_pct": round(count / total_types * 100.0, 2),
            "avg_engagement_pct": round(
                sum(type_engagement.get(fmt, [])) / len(type_engagement.get(fmt, [])),
                4,
            )
            if type_engagement.get(fmt)
            else None,
        }
        for fmt, count in type_counter.items()
    }

    def _top_posts(limit: int = 5) -> List[Dict[str, Any]]:
        scored: List[Tuple[Dict[str, Any], float]] = []
        for item in posts:
            if not isinstance(item, dict):
                continue
            likes = _safe_float(item.get("likesCount")) or 0.0
            comments = _safe_float(item.get("commentsCount")) or 0.0
            scored.append((item, likes + comments))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        out: List[Dict[str, Any]] = []
        for item, score in scored[:limit]:
            out.append(
                {
                    "url": item.get("url"),
                    "type": _classify_linkedin_post_format(item),
                    "likes": item.get("likesCount"),
                    "comments": item.get("commentsCount"),
                    "reactions_total": score,
                    "caption_preview": str(item.get("caption") or "")[:160],
                    "timestamp": item.get("timestamp"),
                }
            )
        return out

    posting_cadence: Dict[str, Any] = {}
    if timestamps:
        timestamps_sorted = sorted(timestamps)
        if len(timestamps_sorted) >= 2:
            deltas = [
                (timestamps_sorted[i] - timestamps_sorted[i - 1]).total_seconds() / 86400.0
                for i in range(1, len(timestamps_sorted))
            ]
            posting_cadence["avg_days_between_posts"] = round(sum(deltas) / len(deltas), 2)
        now_dt = datetime.now(timezone.utc)
        posting_cadence["posts_last_30_days"] = sum(
            1 for ts in timestamps_sorted if (now_dt - ts).days <= 30
        )
        posting_cadence["last_post_at"] = timestamps_sorted[-1].isoformat()
        posting_cadence["months_span"] = max(
            1,
            round((timestamps_sorted[-1] - timestamps_sorted[0]).days / 30.0, 1),
        )

    avg_engagement_pct: Optional[float] = None
    if followers_num and followers_num > 0:
        avg_engagement_pct = round(((total_reactions + total_comments) / n) / followers_num * 100.0, 4)
    elif n > 0:
        avg_engagement_pct = round((total_reactions + total_comments) / n, 4)

    return {
        "content_type_distribution": content_type_distribution,
        "format_distribution": content_type_distribution,
        "top_posts": _top_posts(5),
        "top_posts_by_reactions": _top_posts(5),
        "posting_cadence": posting_cadence,
        "avg_reactions_per_post": round(total_reactions / n, 2),
        "avg_comments_per_post": round(total_comments / n, 2),
        "avg_engagement_pct": avg_engagement_pct,
        "posts_analyzed": len(posts),
    }


def _classify_post_format(post: Dict[str, Any]) -> str:
    """Classifica um post Instagram num dos formatos universais.

    A função normaliza vários valores de `type` que o Apify devolve
    (`Image`, `Sidecar`, `Video`, `Reel`, etc.) num pequeno conjunto
    fixo de categorias, útil para análise de distribuição.

    Argumentos:
        post: Dicionário de post recolhido pelo Apify.

    Retorno:
        Uma das strings: `reel`, `video`, `carousel`, `image` ou
        `desconhecido`.
    """

    raw_type = str(post.get("type") or "").strip().lower()
    if "reel" in raw_type or "clip" in raw_type:
        return "reel"
    if "sidecar" in raw_type or "carousel" in raw_type:
        return "carousel"
    if "video" in raw_type or "igtv" in raw_type:
        return "video"
    if "image" in raw_type or "photo" in raw_type:
        return "image"
    if post.get("videoPlayCount") is not None or post.get("videoViewCount") is not None:
        return "video"
    return "desconhecido"


def _safe_float(value: Any) -> Optional[float]:
    """Converte um valor arbitrário para `float` quando possível.

    Argumentos:
        value: Qualquer valor potencialmente numérico.

    Retorno:
        `float` se a conversão for bem sucedida; `None` caso contrário.
    """

    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_apify_enriched_metrics(
    followers_count: Optional[Any],
    posts: List[Dict[str, Any]],
    reels: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Agrega métricas derivadas de posts e reels recolhidos pelo Apify.

    A função calcula, **sem precisar de login Instagram**, métricas úteis
    para o agente de IA:

    - Distribuição por formato (reel/carrossel/imagem/vídeo).
    - Top posts e top reels por likes/comentários/playCount.
    - Cadência de publicação (média de dias entre posts e total de posts
      nos últimos 30 dias).
    - PlayCount médio e mediano dos Reels.
    - Hashtags mais frequentes.

    Argumentos:
        followers_count: Número de seguidores (para engagement por post).
        posts: Lista normalizada de posts pelo Apify Post Scraper.
        reels: Lista normalizada de reels pelo Apify Reel Scraper.

    Retorno:
        Dicionário com chaves `format_distribution`, `top_posts`,
        `top_reels`, `posting_cadence`, `reels_playcount_stats` e
        `top_hashtags`. Devolve dicionário vazio quando não há dados
        suficientes.
    """

    if not posts and not reels:
        return {}

    all_items: List[Dict[str, Any]] = []
    for item in posts:
        if isinstance(item, dict):
            all_items.append(item)
    for item in reels:
        if isinstance(item, dict):
            entry = dict(item)
            entry["type"] = entry.get("type") or "Reel"
            all_items.append(entry)

    format_counter: Dict[str, int] = {}
    format_engagement: Dict[str, List[float]] = {}
    timestamps: List[datetime] = []
    hashtag_counter: Dict[str, int] = {}

    followers_num = _safe_float(followers_count)

    for item in all_items:
        fmt = _classify_post_format(item)
        format_counter[fmt] = format_counter.get(fmt, 0) + 1

        likes = _safe_float(item.get("likesCount")) or 0.0
        comments = _safe_float(item.get("commentsCount")) or 0.0
        interactions = likes + comments
        if followers_num and followers_num > 0:
            er = (interactions / followers_num) * 100.0
        else:
            er = interactions
        format_engagement.setdefault(fmt, []).append(er)

        ts_raw = item.get("timestamp")
        if isinstance(ts_raw, str) and ts_raw.strip():
            try:
                timestamps.append(
                    datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                )
            except ValueError:
                pass

        hashtags = item.get("hashtags")
        if isinstance(hashtags, list):
            for tag in hashtags:
                tag_str = str(tag).strip().lstrip("#").lower()
                if tag_str:
                    hashtag_counter[tag_str] = hashtag_counter.get(tag_str, 0) + 1

    total_items = sum(format_counter.values()) or 1
    format_distribution = {
        fmt: {
            "count": count,
            "share_pct": round(count / total_items * 100.0, 2),
            "avg_engagement_pct": round(
                sum(format_engagement.get(fmt, [])) / len(format_engagement.get(fmt, [])),
                4,
            )
            if format_engagement.get(fmt)
            else None,
        }
        for fmt, count in format_counter.items()
    }

    def _top_n(items: List[Dict[str, Any]], key: str, limit: int = 3) -> List[Dict[str, Any]]:
        scored = [
            (item, _safe_float(item.get(key)) or 0.0)
            for item in items
            if isinstance(item, dict)
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [
            {
                "url": item.get("url"),
                "type": item.get("type"),
                "likes": item.get("likesCount"),
                "comments": item.get("commentsCount"),
                "playCount": item.get("videoPlayCount") or item.get("videoViewCount"),
                "timestamp": item.get("timestamp"),
            }
            for item, _ in scored[:limit]
            if item.get("url") or item.get("id")
        ]

    top_posts = _top_n(posts, "likesCount", 3)
    top_reels = _top_n(reels, "videoPlayCount", 3)

    posting_cadence: Dict[str, Any] = {}
    if timestamps:
        timestamps_sorted = sorted(timestamps)
        if len(timestamps_sorted) >= 2:
            deltas = [
                (timestamps_sorted[i] - timestamps_sorted[i - 1]).total_seconds() / 86400.0
                for i in range(1, len(timestamps_sorted))
            ]
            avg_gap_days = sum(deltas) / len(deltas)
            posting_cadence["avg_days_between_posts"] = round(avg_gap_days, 2)
        now_dt = datetime.now(timezone.utc)
        posts_last_30 = sum(1 for ts in timestamps_sorted if (now_dt - ts).days <= 30)
        posting_cadence["posts_last_30_days"] = posts_last_30
        posting_cadence["last_post_at"] = timestamps_sorted[-1].isoformat()

    reels_playcounts = [
        _safe_float(reel.get("videoPlayCount") or reel.get("videoViewCount"))
        for reel in reels
        if isinstance(reel, dict)
    ]
    reels_playcounts = [v for v in reels_playcounts if v is not None]
    reels_stats: Dict[str, Any] = {}
    if reels_playcounts:
        reels_playcounts_sorted = sorted(reels_playcounts)
        mid = len(reels_playcounts_sorted) // 2
        if len(reels_playcounts_sorted) % 2 == 1:
            median = reels_playcounts_sorted[mid]
        else:
            median = (reels_playcounts_sorted[mid - 1] + reels_playcounts_sorted[mid]) / 2.0
        reels_stats = {
            "count": len(reels_playcounts_sorted),
            "avg_play_count": round(sum(reels_playcounts_sorted) / len(reels_playcounts_sorted), 2),
            "median_play_count": round(median, 2),
            "max_play_count": max(reels_playcounts_sorted),
        }

    top_hashtags = sorted(hashtag_counter.items(), key=lambda pair: pair[1], reverse=True)[:10]
    top_hashtags_list = [{"tag": tag, "count": count} for tag, count in top_hashtags]

    return {
        "format_distribution": format_distribution,
        "top_posts": top_posts,
        "top_reels": top_reels,
        "posting_cadence": posting_cadence,
        "reels_playcount_stats": reels_stats,
        "top_hashtags": top_hashtags_list,
    }


def _fetch_instagram_public_profile_web(username: str) -> Dict[str, Any]:
    """Recolhe métricas públicas básicas por leitura direta da página web.

    Esta função é usada como fallback quando o Apify não está disponível. A
    extração procura contagens no HTML e, em último caso, no campo
    `og:description`.

    Argumentos:
        username: Nome público do perfil a consultar (sem `@`).

    Retorno:
        Dicionário com contagens básicas e metadados da recolha.

    Raises:
        RuntimeError: Quando não consegue aceder ao perfil público.
    """

    url = f"https://www.instagram.com/{username}/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9,pt-PT;q=0.8",
    }
    http_request = request.Request(url, headers=headers, method="GET")

    try:
        with request.urlopen(http_request, timeout=25) as response:
            html = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError("Perfil Instagram não encontrado (404).") from exc
        raise RuntimeError(f"Instagram respondeu com HTTP {exc.code}.") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Falha de ligação ao Instagram: {exc!s}") from exc
    except (TimeoutError, OSError) as exc:
        raise RuntimeError(f"Timeout/erro de sistema ao ler perfil Instagram: {exc!s}") from exc

    followers_match = re.search(r'"edge_followed_by"\s*:\s*\{"count"\s*:\s*(\d+)\}', html)
    following_match = re.search(r'"edge_follow"\s*:\s*\{"count"\s*:\s*(\d+)\}', html)
    posts_match = re.search(r'"edge_owner_to_timeline_media"\s*:\s*\{"count"\s*:\s*(\d+)\}', html)

    followers_count = int(followers_match.group(1)) if followers_match else None
    following_count = int(following_match.group(1)) if following_match else None
    posts_count = int(posts_match.group(1)) if posts_match else None

    if followers_count is None or following_count is None or posts_count is None:
        og_match = re.search(
            r'<meta\s+property="og:description"\s+content="([^"]+)"',
            html,
            flags=re.IGNORECASE,
        )
        if og_match:
            description = og_match.group(1)
            parts = [part.strip() for part in description.split(",")]
            if len(parts) >= 3:
                parsed_followers = _parse_human_number(parts[0].split(" ")[0])
                parsed_following = _parse_human_number(parts[1].split(" ")[0])
                parsed_posts = _parse_human_number(parts[2].split(" ")[0])
                followers_count = followers_count or parsed_followers
                following_count = following_count or parsed_following
                posts_count = posts_count or parsed_posts

    filled_fields = sum(value is not None for value in [followers_count, following_count, posts_count])
    data_quality = "baixa"
    if filled_fields == 3:
        data_quality = "media"
    elif filled_fields >= 1:
        data_quality = "baixa"

    return {
        "platform": "instagram",
        "profile": username,
        "followers_count": followers_count,
        "following_count": following_count,
        "posts_count": posts_count,
        "collection_method": "public_web_profile",
        "data_quality": data_quality,
    }


def _build_copywriter_brief(payload: CopywriterRequest) -> str:
    """Converte o formulário avançado do Copywriter num brief textual único.

    A função agrega os vários campos estruturados (objetivo, público, canal,
    tom, restrições e estratégia) numa instrução detalhada para o modelo de IA,
    preservando o contexto necessário para gerar copy de alta qualidade.

    Argumentos:
        payload: Objeto validado com todos os campos do formulário de copy.

    Retorno:
        String multilinha com seções organizadas e apenas campos preenchidos.
    """

    def _flag(value: Optional[bool]) -> Optional[str]:
        if value is None:
            return None
        return "Sim" if value else "Não"

    lines = [
        "## Contexto Base",
        f"Brief principal: {payload.brief}",
        "",
        "## Objetivo e Conversão",
        f"Objetivo principal: {payload.objective or 'Não especificado'}",
        f"CTA desejado: {payload.cta or 'Não especificado'}",
        f"Etapa do funil: {payload.funnel_stage or 'Não especificado'}",
        "",
        "## Público-Alvo",
        f"Persona/público: {payload.persona or 'Não especificado'}",
        f"Nível de conhecimento: {payload.knowledge_level or 'Não especificado'}",
        f"Dores principais: {payload.pains or 'Não especificado'}",
        f"Desejos/motivações: {payload.desires or 'Não especificado'}",
        "",
        "## Configuração do Texto",
        f"Mínimo de palavras: {payload.min_words if payload.min_words is not None else 'Sem mínimo'}",
        f"Máximo de palavras: {payload.max_words if payload.max_words is not None else 'Sem máximo'}",
        f"Formato do output: {payload.output_format or 'Não especificado'}",
        f"Idioma: {payload.language}",
        f"Tipo de copy: {payload.copy_type or 'Não especificado'}",
        "",
        "## Tom e Estilo",
        f"Tom de voz: {payload.tone or 'Não especificado'}",
        f"Nível de formalidade: {payload.formality_level or 'Não especificado'}",
        f"Personalidade da marca: {payload.brand_personality or 'Não especificado'}",
        f"Marcas de referência: {payload.reference_brands or 'Não especificado'}",
        "",
        "## Canal e Contexto",
        f"Canal de distribuição: {payload.channel or 'Não especificado'}",
        f"Tipo de peça: {payload.asset_type or 'Não especificado'}",
        f"Posicionamento da marca: {payload.brand_positioning or 'Não especificado'}",
        "",
        "## Restrições",
        f"Palavras a evitar: {payload.avoid_words or 'Não especificado'}",
        f"Termos obrigatórios: {payload.required_terms or 'Não especificado'}",
        f"Limitações legais/compliance: {payload.legal_limits or 'Não especificado'}",
        f"Evitar promessas exageradas: {_flag(payload.avoid_exaggeration) or 'Não especificado'}",
        "",
        "## Estratégia de Copy",
        f"Framework: {payload.framework or 'Não especificado'}",
        f"Ângulo principal: {payload.main_angle or 'Não especificado'}",
        f"Incluir prova social: {_flag(payload.include_social_proof) or 'Não especificado'}",
        "",
        "## Extras",
        f"Número de variações desejado: {payload.variations}",
        f"Nível de criatividade: {payload.creativity_level or 'Não especificado'}",
        f"Incluir emojis: {_flag(payload.include_emojis) or 'Não especificado'}",
        f"Incluir hashtags: {_flag(payload.include_hashtags) or 'Não especificado'}",
        f"Exemplo de output esperado: {payload.expected_output_example or 'Não especificado'}",
    ]
    return "\n".join(lines).strip()


def _build_copywriter_chat_brief(payload: CopywriterChatRequest) -> str:
    """Converte o histórico da chatroom num brief textual para geração final.

    A função percorre todas as mensagens em ordem cronológica e monta um
    documento de contexto que identifica claramente quem falou (utilizador ou
    agente). Este documento é enviado ao gerador para produzir uma copy final
    alinhada com tudo o que foi discutido na sala.

    Argumentos:
        payload: Objeto validado com mensagens da conversa e preferências de saída.

    Retorno:
        String multilinha pronta para ser usada como `brief` no
        `copywriter_agent.generate_marketing_copy`.
    """

    transcript_lines: List[str] = []
    for message in payload.messages:
        content = message.content.strip()
        if not content:
            continue
        author = "Utilizador" if message.role == "user" else "Agente Copywriter"
        transcript_lines.append(f"- {author}: {content}")

    lines = [
        "## Conversa da Chatroom (ordem cronológica)",
        *transcript_lines,
        "",
        "## Instrução de saída",
        "Com base apenas no histórico acima, gera a copy final com foco em conversão.",
        f"Idioma pretendido: {payload.language}",
        f"Tom desejado: {payload.tone or 'Não especificado'}",
        f"Variações pedidas: {payload.variations}",
    ]
    return "\n".join(lines).strip()


@app.get("/assets/copywriter-photo")
def copywriter_photo() -> FileResponse:
    """Serve a imagem personalizada do Agente Copywriter para a interface.

    Esta rota fornece a fotografia/ícone selecionado pelo utilizador para
    personalizar a chatroom do Copywriter. A imagem é carregada a partir do
    caminho configurado em `COPYWRITER_PHOTO_PATH`.

    Argumentos:
        Nenhum.

    Retorno:
        `FileResponse` com o conteúdo da imagem PNG pronta para renderização no browser.

    Raises:
        HTTPException: 404 quando o ficheiro da imagem não existe no caminho esperado.
    """

    if not COPYWRITER_PHOTO_PATH.exists():
        raise HTTPException(status_code=404, detail="Imagem do Copywriter não encontrada.")
    return FileResponse(COPYWRITER_PHOTO_PATH, media_type="image/png")


@app.get("/assets/designer-photo")
def designer_photo() -> FileResponse:
    """Serve a imagem personalizada do Agente Designer para a interface.

    Esta rota fornece o avatar/ícone do Designer definido pelo utilizador e
    usado no topo da chatroom do agente.

    Argumentos:
        Nenhum.

    Retorno:
        `FileResponse` com o conteúdo da imagem PNG.

    Raises:
        HTTPException: 404 quando o ficheiro da imagem não existe.
    """

    if not DESIGNER_PHOTO_PATH.exists():
        raise HTTPException(status_code=404, detail="Imagem do Designer não encontrada.")
    return FileResponse(DESIGNER_PHOTO_PATH, media_type="image/png")


def _render_linkedin_perfil_agent_page() -> str:
    """Monta a página HTML do agente *LinkedIn (perfil)*.

    Inclui login OAuth LinkedIn (OIDC) via Supabase e análise de perfil público
    através do endpoint ``POST /agents/social-media/profile-analyze``. Usa o
    HTML embutido em ``agents.linkedin_perfil_page.LINKEDIN_PERFIL_PAGE_HTML`` e
    injecta a URL do projecto e a chave ``anon`` obtidas com
    ``get_supabase_public_credentials``.

    Argumentos:
        Nenhum.

    Retorno:
        Documento HTML completo (string) pronto para servir como resposta da
        rota ``/agentes/linkedin-perfil``.
    """

    u, a = get_supabase_public_credentials()
    html = (
        LINKEDIN_PERFIL_PAGE_HTML.replace("___SUPABASE_URL_JSON___", json.dumps(u))
        .replace("___SUPABASE_ANON_JSON___", json.dumps(a))
    )
    return html.encode("utf-16", "surrogatepass").decode("utf-16")


@app.get("/agentes/{agent_slug}", response_class=HTMLResponse)
def agent_page(agent_slug: str) -> str:
    """Renderiza a página de conversa de um agente específico.

    A função recebe o slug da URL, valida se existe no catálogo de agentes e
    devolve uma página dedicada. Para `copywriter`, a página inclui formulário
    para geração de textos com OpenAI; para os restantes agentes, apresenta um
    espaço profissional preparado para conversa e próximos passos.

    Argumentos:
        agent_slug: Identificador do agente na URL (ex.: `copywriter`).

    Retorno:
        String HTML completa da página do agente correspondente.

    Raises:
        HTTPException: 404 quando o slug não corresponde a nenhum agente.
    """

    agent_name = SLUG_TO_AGENT.get(agent_slug)
    if not agent_name:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")

    if agent_slug == "linkedin-perfil":
        return _render_linkedin_perfil_agent_page()

    if agent_slug == "copywriter":
        return """
        <!doctype html>
        <html lang="pt">
          <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>Agente Copywriter</title>
            <style>
              :root {
                --bg: #0f172a;
                --surface: #1e293b;
                --surface-2: #172334;
                --line: rgba(255, 255, 255, 0.1);
                --text: #e2e8f0;
                --muted: #94a3b8;
                --user: #2563eb;
                --assistant: #0f766e;
              }
              body {
                font-family: "Segoe UI", system-ui, sans-serif;
                margin: 0;
                background: radial-gradient(circle at 10% 10%, #1e293b 0%, #0f172a 60%);
                color: var(--text);
                padding: 24px 16px;
              }
              .wrap { max-width: 980px; margin: 0 auto; }
              .card {
                background: var(--surface);
                border: 1px solid var(--line);
                border-radius: 14px;
                padding: 20px;
                box-shadow: 0 18px 40px -24px rgba(0, 0, 0, 0.6);
              }
              .top { display: flex; gap: 14px; align-items: center; margin-bottom: 10px; }
              .top img {
                width: 72px;
                height: 72px;
                border-radius: 50%;
                border: 2px solid rgba(255,255,255,0.15);
                background: #fff;
              }
              .title { margin: 0; font-size: 1.4rem; }
              .subtitle { margin: 4px 0 0; color: var(--muted); font-size: 0.92rem; }
              .top { display: flex; gap: 14px; align-items: center; margin-bottom: 10px; }
              .top img {
                width: 72px;
                height: 72px;
                border-radius: 50%;
                border: 2px solid rgba(255,255,255,0.15);
                background: #fff;
                object-fit: contain;
                padding: 3px;
              }
              .chat-log {
                margin-top: 16px;
                border: 1px solid var(--line);
                border-radius: 12px;
                background: var(--surface-2);
                padding: 14px;
                min-height: 320px;
                max-height: 420px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 10px;
              }
              .msg {
                max-width: 82%;
                padding: 10px 12px;
                border-radius: 10px;
                line-height: 1.45;
                font-size: 0.93rem;
                white-space: pre-wrap;
              }
              .msg.user { align-self: flex-end; background: var(--user); }
              .msg.assistant { align-self: flex-start; background: var(--assistant); }
              .msg.typing {
                align-self: flex-start;
                background: var(--assistant);
                display: inline-flex;
                align-items: center;
                gap: 5px;
                min-width: 54px;
              }
              .typing-dot {
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.92);
                animation: typingBounce 1.1s infinite ease-in-out;
              }
              .typing-dot:nth-child(2) { animation-delay: 0.15s; }
              .typing-dot:nth-child(3) { animation-delay: 0.3s; }
              @keyframes typingBounce {
                0%, 80%, 100% { transform: translateY(0); opacity: 0.55; }
                40% { transform: translateY(-4px); opacity: 1; }
              }
              .controls { margin-top: 14px; display: grid; grid-template-columns: 1fr 170px 130px; gap: 10px; }
              .controls textarea, .controls input {
                width: 100%;
                box-sizing: border-box;
                border-radius: 10px;
                border: 1px solid var(--line);
                background: #0b1220;
                color: var(--text);
                padding: 10px 12px;
                font-family: inherit;
              }
              .controls textarea { min-height: 56px; resize: vertical; }
              .actions { margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap; }
              button {
                border: none;
                border-radius: 9px;
                padding: 10px 14px;
                color: #fff;
                font-weight: 600;
                cursor: pointer;
              }
              .send-btn { background: linear-gradient(180deg, #2563eb, #1d4ed8); }
              .generate-btn { background: linear-gradient(180deg, #10b981, #059669); }
              .reset-btn { background: linear-gradient(180deg, #64748b, #475569); }
              .hint { color: var(--muted); font-size: 0.84rem; margin-top: 8px; }
              .result {
                margin-top: 16px;
                border: 1px solid var(--line);
                border-radius: 12px;
                background: #0f172a;
                padding: 14px;
              }
              .result h3 { margin-top: 0; color: #93c5fd; }
              .meta { color: var(--muted); font-size: 0.82rem; margin-bottom: 8px; }
              a { color: #93c5fd; text-decoration: none; }
              @media (max-width: 820px) { .controls { grid-template-columns: 1fr; } .msg { max-width: 94%; } }
            </style>
          </head>
          <body>
            <div class="wrap">
              <p><a href="/">← Voltar ao Diretor</a></p>
              <div class="card">
                <div class="top">
                  <img src="/assets/copywriter-photo" alt="Avatar do Agente Copywriter" />
                  <div>
                    <h1 class="title">Agente Copywriter · Chatroom</h1>
                    <p class="subtitle">Conversa comigo, afina o contexto e no fim gero a copy com base em todo o histórico.</p>
                  </div>
                </div>
                <div id="chatLog" class="chat-log"></div>
                <div class="controls">
                  <textarea id="chatInput" placeholder="Escreve aqui a tua mensagem (objetivo, público, dor, oferta, canal, CTA, etc.)"></textarea>
                  <input id="toneInput" placeholder="Tom (ex.: direto)" />
                  <input id="languageInput" value="pt-PT" placeholder="Idioma" />
                </div>
                <div class="actions">
                  <button type="button" class="send-btn" onclick="sendMessage()">Enviar mensagem</button>
                  <button type="button" class="generate-btn" onclick="generateFromChat()">Gerar copy final</button>
                  <button type="button" class="reset-btn" onclick="resetChat()">Limpar conversa</button>
                </div>
                <p class="hint">Dica: quanto melhor a conversa (mais contexto), melhor fica a copy final.</p>
                <div id="result" class="result"></div>
              </div>
            </div>
            <script>
              const chatLog = document.getElementById("chatLog");
              const chatInput = document.getElementById("chatInput");
              const toneInput = document.getElementById("toneInput");
              const languageInput = document.getElementById("languageInput");
              const result = document.getElementById("result");
              const messages = [];

              function addMessage(role, content) {
                messages.push({ role, content });
                const bubble = document.createElement("div");
                bubble.className = `msg ${role}`;
                bubble.textContent = content;
                chatLog.appendChild(bubble);
                chatLog.scrollTop = chatLog.scrollHeight;
              }

              function showTypingIndicator() {
                const bubble = document.createElement("div");
                bubble.className = "msg assistant typing";
                bubble.id = "typingIndicator";
                bubble.innerHTML = `
                  <span class="typing-dot"></span>
                  <span class="typing-dot"></span>
                  <span class="typing-dot"></span>
                `;
                chatLog.appendChild(bubble);
                chatLog.scrollTop = chatLog.scrollHeight;
              }

              function hideTypingIndicator() {
                const el = document.getElementById("typingIndicator");
                if (el) {
                  el.remove();
                }
              }

              async function getAssistantReplyFromLLM() {
                const payload = {
                  messages,
                  tone: toneInput.value.trim() || null,
                  language: languageInput.value.trim() || "pt-PT"
                };
                const response = await fetch("/agents/copywriter/chat-reply", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (!response.ok) {
                  const detailText = data.detail || JSON.stringify(data);
                  throw new Error(detailText);
                }
                return (data.reply || "").trim();
              }

              async function sendMessage() {
                const content = chatInput.value.trim();
                if (!content) {
                  return;
                }
                addMessage("user", content);
                chatInput.value = "";
                result.innerHTML = "<p>A processar mensagem com gpt-4o-mini…</p>";
                showTypingIndicator();
                try {
                  const reply = await getAssistantReplyFromLLM();
                  hideTypingIndicator();
                  addMessage("assistant", reply || "Percebi. Podes detalhar um pouco mais para eu refinar a orientação?");
                  result.innerHTML = "<p>Mensagem processada. Continua a conversa ou clica em 'Gerar copy final'.</p>";
                } catch (err) {
                  hideTypingIndicator();
                  const errorMessage = err instanceof Error ? err.message : String(err);
                  addMessage("assistant", "Não consegui responder agora. Verifica a OPENAI_API_KEY e tenta novamente.");
                  result.innerHTML = `<p><strong>Erro:</strong> ${errorMessage}</p>`;
                }
              }

              async function generateFromChat() {
                if (!messages.length) {
                  result.innerHTML = "<p><strong>Erro:</strong> A conversa está vazia. Envia pelo menos uma mensagem antes de gerar.</p>";
                  return;
                }

                result.innerHTML = "<p>A gerar copy final com base na chatroom…</p>";
                const payload = {
                  messages,
                  tone: toneInput.value.trim() || null,
                  language: languageInput.value.trim() || "pt-PT",
                  variations: 3
                };

                const response = await fetch("/agents/copywriter/chat-generate", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (!response.ok) {
                  let detailText = data.detail || JSON.stringify(data);
                  if (Array.isArray(data.detail)) {
                    detailText = data.detail
                      .map(item => {
                        const loc = Array.isArray(item.loc) ? item.loc.join(" > ") : "campo";
                        return `${loc}: ${item.msg}`;
                      })
                      .join(" | ");
                  }
                  result.innerHTML = `<p><strong>Erro:</strong> ${detailText}</p>`;
                  return;
                }

                const h = (data.headlines || []).map(x => `<li>${x}</li>`).join("");
                const c = (data.ctas || []).map(x => `<li>${x}</li>`).join("");
                const variations = (data.main_text_variations || [])
                  .map(v => `<li><strong>${v.angle || "Ângulo"}:</strong> ${v.text || ""}</li>`)
                  .join("");
                const improvements = data.improvement_suggestions || {};
                const abTests = (improvements.ab_test_ideas || []).map(x => `<li>${x}</li>`).join("");
                const notes = data.notes ? `<p><strong>Notas:</strong> ${data.notes}</p>` : "";
                result.innerHTML = `
                  <h3>Copy gerada</h3>
                  <p class="meta">Histórico usado: ${data.conversation_turns || messages.length} mensagens</p>
                  <p><strong>3 variações de texto principal:</strong></p>
                  <ol>${variations}</ol>
                  <p><strong>5 headlines curtas e agressivas:</strong></p>
                  <ol>${h}</ol>
                  <p><strong>3 CTAs orientados para ação:</strong></p>
                  <ol>${c}</ol>
                  <p><strong>Sugestões de melhoria:</strong></p>
                  <p><strong>Fraquezas no ângulo:</strong> ${improvements.weaknesses_in_angle || ""}</p>
                  <p><strong>Como tornar mais específico:</strong> ${improvements.how_to_be_more_specific || ""}</p>
                  <p><strong>Ideias de testes A/B:</strong></p>
                  <ol>${abTests}</ol>
                  ${notes}
                `;
              }

              function resetChat() {
                messages.length = 0;
                chatLog.innerHTML = "";
                result.innerHTML = "<p>Conversa limpa. Podes começar um novo contexto.</p>";
                addMessage("assistant", "Olá. Sou o teu Copywriter AI. Diz-me o objetivo e eu respondo com base no que fores dizendo.");
              }

              addMessage("assistant", "Olá. Sou o teu Copywriter AI. Diz-me o objetivo e eu respondo com base no que fores dizendo.");
              chatInput.addEventListener("keydown", (event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              });
            </script>
          </body>
        </html>
        """

    if agent_slug == "redes-sociais":
        return """
        <!doctype html>
        <html lang="pt">
          <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>Agente Redes Sociais</title>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
            <style>
              :root {
                --bg-0: #08090d;
                --bg-1: #0f1117;
                --bg-2: #151823;
                --surface: #1a1d2a;
                --surface-2: #20243a;
                --line: rgba(255,255,255,0.08);
                --line-strong: rgba(255,255,255,0.16);
                --text: #f4f6fb;
                --muted: #8a90a6;
                --muted-soft: #b3b8c9;
                --primary: #ff3d7f;
                --primary-2: #ff6a00;
                --accent: #38bdf8;
                --accent-2: #818cf8;
                --good: #34d399;
                --bad: #f87171;
                --warn: #fbbf24;
                --shadow: 0 20px 60px rgba(0,0,0,0.45);
              }
              * { box-sizing: border-box; }
              html, body { height: 100%; }
              body {
                margin: 0;
                font-family: "Inter", "Segoe UI", system-ui, sans-serif;
                background:
                  radial-gradient(1200px 800px at 85% -10%, rgba(255,61,127,0.16), transparent 60%),
                  radial-gradient(1000px 700px at -10% 110%, rgba(56,189,248,0.12), transparent 60%),
                  var(--bg-0);
                color: var(--text);
                -webkit-font-smoothing: antialiased;
                font-feature-settings: "ss01" on, "cv11" on;
                padding: 28px 18px 64px;
              }
              .wrap { max-width: 1180px; margin: 0 auto; }
              .nav {
                display: flex; align-items: center; justify-content: space-between;
                margin-bottom: 16px;
              }
              .nav a.back {
                color: var(--muted-soft); text-decoration: none; font-weight: 500;
                font-size: 0.92rem; display: inline-flex; gap: 6px; align-items: center;
                padding: 6px 10px; border-radius: 8px; border: 1px solid var(--line);
                background: rgba(255,255,255,0.02);
              }
              .nav a.back:hover { color: #fff; border-color: var(--line-strong); }
              .brand {
                display: flex; align-items: center; gap: 10px;
                font-weight: 700; color: var(--muted-soft); font-size: 0.92rem;
              }
              .brand .logo-dot {
                width: 10px; height: 10px; border-radius: 50%;
                background: linear-gradient(135deg, var(--primary), var(--primary-2));
                box-shadow: 0 0 12px rgba(255,61,127,0.6);
              }

              /* Hero */
              .hero {
                background: linear-gradient(180deg, var(--surface) 0%, var(--bg-1) 100%);
                border: 1px solid var(--line);
                border-radius: 20px;
                padding: 22px 22px 18px;
                box-shadow: var(--shadow);
                position: relative;
                overflow: hidden;
              }
              .hero::before {
                content: ""; position: absolute; inset: -1px;
                background: linear-gradient(135deg, rgba(255,61,127,0.25), transparent 35%, rgba(56,189,248,0.18) 70%, transparent 100%);
                opacity: 0.6; pointer-events: none; border-radius: 20px;
                mask: linear-gradient(#000, transparent 60%);
                -webkit-mask: linear-gradient(#000, transparent 60%);
              }
              .hero-top { display: flex; align-items: center; gap: 14px; }
              .hero-icon {
                width: 44px; height: 44px; border-radius: 12px;
                background: linear-gradient(135deg, var(--primary), var(--primary-2));
                display: flex; align-items: center; justify-content: center;
                color: #fff; font-weight: 800; box-shadow: 0 6px 24px rgba(255,61,127,0.4);
                font-size: 1.05rem;
              }
              .title { margin: 0; font-size: 1.45rem; letter-spacing: -0.01em; }
              .subtitle { margin: 4px 0 0; color: var(--muted); font-size: 0.92rem; }

              .form { margin-top: 18px; display: grid; grid-template-columns: 1fr minmax(140px, 160px) auto auto; gap: 10px; }
              .input-wrap {
                position: relative;
              }
              .input-wrap::before {
                content: "@"; position: absolute; left: 14px; top: 50%; transform: translateY(-50%);
                color: var(--muted); font-weight: 600;
              }
              .input-wrap.no-at::before {
                content: none;
              }
              .input-wrap.no-at input.profile {
                padding-left: 14px;
              }
              input.profile {
                width: 100%;
                border-radius: 12px;
                border: 1px solid var(--line);
                background: rgba(8,9,13,0.6);
                color: var(--text);
                padding: 12px 14px 12px 30px;
                font-family: inherit; font-size: 0.95rem;
                outline: none; transition: border-color 0.15s, box-shadow 0.15s;
              }
              input.profile:focus { border-color: rgba(255,61,127,0.6); box-shadow: 0 0 0 4px rgba(255,61,127,0.12); }
              button {
                border: none; border-radius: 12px; padding: 11px 16px;
                color: #fff; font-weight: 600; cursor: pointer; font-family: inherit;
                font-size: 0.93rem; letter-spacing: 0.01em; transition: transform 0.05s, filter 0.15s;
              }
              button:hover { filter: brightness(1.06); }
              button:active { transform: translateY(1px); }
              .btn-login { background: rgba(255,255,255,0.06); border: 1px solid var(--line-strong); }
              .btn-analyze {
                background: linear-gradient(135deg, var(--primary), var(--primary-2));
                box-shadow: 0 8px 22px rgba(255,61,127,0.35);
              }
              .auth-row {
                display: flex; align-items: center; justify-content: space-between;
                flex-wrap: wrap; gap: 8px;
                margin-top: 12px; color: var(--muted); font-size: 0.83rem;
              }
              .badge {
                display: inline-flex; align-items: center; gap: 6px;
                padding: 4px 10px; border-radius: 999px;
                font-size: 0.78rem; font-weight: 600; border: 1px solid var(--line);
                background: rgba(255,255,255,0.03); color: var(--muted-soft);
              }
              .badge.ok { color: var(--good); border-color: rgba(52,211,153,0.35); background: rgba(52,211,153,0.08); }
              .badge.warn { color: var(--warn); border-color: rgba(251,191,36,0.35); background: rgba(251,191,36,0.08); }
              .badge.bad { color: var(--bad); border-color: rgba(248,113,113,0.35); background: rgba(248,113,113,0.08); }
              .badge.info { color: var(--accent); border-color: rgba(56,189,248,0.35); background: rgba(56,189,248,0.08); }
              .badge .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }

              /* Results */
              .results { margin-top: 18px; display: grid; gap: 16px; }
              .empty {
                border: 1px dashed var(--line-strong); border-radius: 16px;
                padding: 28px; text-align: center; color: var(--muted);
                background: rgba(255,255,255,0.02);
              }
              .empty .big { font-size: 1.05rem; color: var(--muted-soft); margin-bottom: 4px; }

              .loading {
                display: flex; align-items: center; gap: 12px;
                background: var(--surface); border: 1px solid var(--line);
                border-radius: 16px; padding: 18px 22px; color: var(--muted-soft);
              }
              .spinner {
                width: 22px; height: 22px; border-radius: 50%;
                border: 3px solid rgba(255,255,255,0.12);
                border-top-color: var(--primary);
                animation: spin 0.8s linear infinite;
              }
              @keyframes spin { to { transform: rotate(360deg); } }

              /* Header da análise */
              .analysis-header {
                background: var(--surface); border: 1px solid var(--line);
                border-radius: 16px; padding: 18px 20px; display: flex; gap: 16px;
                align-items: center; justify-content: space-between; flex-wrap: wrap;
              }
              .analysis-header .who {
                display: flex; align-items: center; gap: 14px;
              }
              .ig-avatar {
                width: 56px; height: 56px; border-radius: 50%;
                background: linear-gradient(135deg, #ffd76a, #ff3d7f 35%, #a855f7 70%, #38bdf8);
                display: flex; align-items: center; justify-content: center;
                color: #fff; font-weight: 800; font-size: 1.4rem;
                box-shadow: 0 8px 22px rgba(168,85,247,0.25);
              }
              .analysis-header h2 { margin: 0; font-size: 1.18rem; letter-spacing: -0.01em; }
              .analysis-header .who small { display: block; color: var(--muted); font-size: 0.82rem; margin-top: 2px; }
              .analysis-header .header-badges { display: flex; gap: 8px; flex-wrap: wrap; }

              /* KPI cards */
              .kpi-grid {
                display: grid; gap: 12px;
                grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
              }
              .kpi {
                background: linear-gradient(180deg, var(--surface), var(--surface-2));
                border: 1px solid var(--line);
                border-radius: 14px;
                padding: 14px 16px;
                position: relative; overflow: hidden;
              }
              .kpi .label { font-size: 0.78rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; }
              .kpi .value { font-size: 1.6rem; font-weight: 800; margin-top: 4px; letter-spacing: -0.02em; }
              .kpi .sub { font-size: 0.82rem; color: var(--muted-soft); margin-top: 2px; }
              .kpi.accent { border-color: rgba(255,61,127,0.35); }
              .kpi.accent::after {
                content: ""; position: absolute; right: -20px; bottom: -20px;
                width: 90px; height: 90px; border-radius: 50%;
                background: radial-gradient(circle, rgba(255,61,127,0.25), transparent 70%);
              }

              /* Tabs */
              .tabs {
                display: flex; gap: 6px; padding: 6px;
                background: var(--surface); border: 1px solid var(--line);
                border-radius: 14px; overflow-x: auto;
              }
              .tab {
                flex: 1; min-width: 100px; padding: 9px 12px;
                border-radius: 10px; cursor: pointer; font-weight: 600;
                color: var(--muted-soft); font-size: 0.88rem; text-align: center;
                transition: background 0.15s, color 0.15s;
                user-select: none; white-space: nowrap;
              }
              .tab:hover { color: #fff; }
              .tab.active {
                background: linear-gradient(135deg, var(--primary), var(--primary-2));
                color: #fff;
              }

              .panel { display: none; }
              .panel.active { display: grid; gap: 14px; }

              .section {
                background: var(--surface); border: 1px solid var(--line);
                border-radius: 16px; padding: 18px 20px;
              }
              .section h3 {
                margin: 0 0 12px; font-size: 1rem; letter-spacing: 0.01em;
                display: flex; align-items: center; gap: 10px;
              }
              .section h3 .pill {
                font-size: 0.7rem; font-weight: 600; padding: 3px 8px;
                border-radius: 999px; background: rgba(255,61,127,0.12); color: var(--primary);
                border: 1px solid rgba(255,61,127,0.25); letter-spacing: 0.04em; text-transform: uppercase;
              }
              .section h3 .pill.cool { background: rgba(56,189,248,0.12); color: var(--accent); border-color: rgba(56,189,248,0.25); }
              .section h3 .pill.violet { background: rgba(129,140,248,0.12); color: var(--accent-2); border-color: rgba(129,140,248,0.25); }

              /* Listas estilizadas */
              .insight-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
              .insight-list li {
                background: rgba(255,255,255,0.02);
                border: 1px solid var(--line);
                border-left: 3px solid var(--accent);
                border-radius: 10px;
                padding: 10px 14px; font-size: 0.94rem; line-height: 1.5;
              }
              .insight-list.problems li { border-left-color: var(--bad); }
              .insight-list.opps li { border-left-color: var(--good); }
              .insight-list.actions li { border-left-color: var(--primary); counter-increment: actcount; }
              .insight-list.actions { counter-reset: actcount; }
              .insight-list.actions li::before {
                content: counter(actcount); display: inline-flex;
                width: 22px; height: 22px; border-radius: 50%;
                background: rgba(255,61,127,0.18); color: var(--primary);
                font-weight: 700; font-size: 0.78rem; align-items: center; justify-content: center;
                margin-right: 8px; vertical-align: middle;
              }
              .insight-list.violet li { border-left-color: var(--accent-2); }

              /* Format distribution bars */
              .format-grid { display: grid; gap: 10px; }
              .format-row {
                display: grid; grid-template-columns: 110px 1fr 70px; gap: 10px;
                align-items: center; font-size: 0.9rem;
              }
              .format-label { font-weight: 600; color: var(--muted-soft); text-transform: capitalize; }
              .format-bar {
                position: relative; height: 10px; border-radius: 999px;
                background: rgba(255,255,255,0.06); overflow: hidden;
              }
              .format-fill {
                position: absolute; inset: 0;
                background: linear-gradient(90deg, var(--primary), var(--primary-2));
                border-radius: 999px; transform-origin: left;
              }
              .format-pct { text-align: right; font-variant-numeric: tabular-nums; color: var(--muted-soft); }
              .format-er { grid-column: 2 / 4; font-size: 0.78rem; color: var(--muted); margin-top: 2px; }

              /* Top items */
              .top-grid { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
              .top-card {
                border: 1px solid var(--line); border-radius: 12px;
                background: rgba(255,255,255,0.02); padding: 12px 14px;
                display: flex; gap: 12px; align-items: flex-start;
              }
              .top-card .rank {
                width: 28px; height: 28px; border-radius: 8px;
                background: rgba(255,61,127,0.15); color: var(--primary);
                display: flex; align-items: center; justify-content: center;
                font-weight: 800; flex-shrink: 0; font-size: 0.85rem;
              }
              .top-card .meta-row { display: flex; gap: 12px; flex-wrap: wrap; color: var(--muted-soft); font-size: 0.82rem; }
              .top-card a { color: var(--accent); text-decoration: none; font-size: 0.82rem; }
              .top-card a:hover { text-decoration: underline; }

              /* Comparações temporais */
              .compare-grid { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
              .compare-card {
                border: 1px solid var(--line); border-radius: 12px;
                background: rgba(255,255,255,0.02); padding: 12px 14px;
              }
              .compare-card .label { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); font-weight: 700; }
              .compare-card .rows { margin-top: 8px; display: grid; gap: 4px; font-size: 0.88rem; }
              .compare-card .delta { font-weight: 700; font-variant-numeric: tabular-nums; }
              .delta.up { color: var(--good); }
              .delta.down { color: var(--bad); }
              .compare-card.empty-card { color: var(--muted); font-size: 0.88rem; text-align: center; padding: 18px; }

              /* Hashtags */
              .hashtag-grid { display: flex; flex-wrap: wrap; gap: 8px; }
              .hashtag {
                display: inline-flex; align-items: center; gap: 6px;
                padding: 6px 10px; border-radius: 999px;
                background: rgba(56,189,248,0.10); color: var(--accent);
                border: 1px solid rgba(56,189,248,0.25);
                font-size: 0.82rem; font-weight: 600;
              }
              .hashtag .count { color: var(--muted-soft); font-weight: 500; font-size: 0.75rem; }

              /* Metric pills */
              .metric-pills { display: flex; flex-wrap: wrap; gap: 8px; }
              .metric-pill {
                background: rgba(255,255,255,0.04); border: 1px solid var(--line);
                border-radius: 10px; padding: 8px 12px; font-size: 0.84rem;
                color: var(--muted-soft);
              }
              .metric-pill strong { color: var(--text); margin-right: 4px; }

              .gap-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 6px; }
              .gap-list li {
                background: rgba(251,191,36,0.06); border: 1px solid rgba(251,191,36,0.25);
                color: #fde68a; border-radius: 10px;
                padding: 8px 12px; font-size: 0.86rem;
              }

              .err {
                background: rgba(248,113,113,0.08); border: 1px solid rgba(248,113,113,0.3);
                color: #fecaca; border-radius: 12px; padding: 12px 14px; font-size: 0.9rem;
              }

              @media (max-width: 680px) {
                .form { grid-template-columns: 1fr; }
                .analysis-header { flex-direction: column; align-items: flex-start; }
              }
            </style>
          </head>
          <body>
            <div class="wrap">
              <div class="nav">
                <a class="back" href="/">← Voltar ao Diretor</a>
                <div class="brand"><span class="logo-dot"></span> Agente Redes Sociais</div>
              </div>
              <div class="hero">
                <div class="hero-top">
                  <div class="hero-icon">IG</div>
                  <div>
                    <h1 class="title">Análise inteligente de redes sociais</h1>
                    <p class="subtitle">Escolhe a plataforma, insere o perfil e obtém insights de IA. <strong>Login Instagram</strong> (Meta) para dados oficiais da tua conta. Histórico temporal completo: Instagram. Para <strong>LinkedIn com OAuth Supabase</strong>, abre o agente <a href="/agentes/linkedin-perfil" style="color:var(--accent)">LinkedIn (perfil)</a>.</p>
                  </div>
                </div>
                <div class="form">
                  <div class="input-wrap" id="profileInputWrap">
                    <input id="profileInput" class="profile" placeholder="username ou link do Instagram" />
                  </div>
                  <select id="platformSelect" class="profile" style="padding-left:12px;" aria-label="Plataforma social">
                    <option value="instagram">Instagram</option>
                    <option value="linkedin">LinkedIn</option>
                    <option value="facebook">Facebook</option>
                    <option value="tiktok">TikTok</option>
                    <option value="youtube">YouTube</option>
                  </select>
                  <button type="button" class="btn-login" onclick="startInstagramLogin()">Login Instagram</button>
                  <button type="button" class="btn-analyze" onclick="runInstagramAnalysis()">Analisar</button>
                </div>
                <div class="auth-row">
                  <span id="authStatus" class="badge"><span class="dot"></span> a verificar login...</span>
                  <span class="badge info"><span class="dot"></span> Multi-plataforma · Apify unificado = Instagram</span>
                </div>
              </div>

              <div id="result" class="results">
                <div class="empty">
                  <div class="big">Sem análise ainda</div>
                  <div>Coloca o <strong>identificador do perfil</strong> em cima, escolhe a <strong>plataforma</strong> e clica <strong>Analisar</strong>. Fluxo completo com histórico temporal: só Instagram.</div>
                </div>
              </div>
            </div>

            <script>
              const profileInput = document.getElementById("profileInput");
              const platformSelect = document.getElementById("platformSelect");
              const result = document.getElementById("result");
              const authStatus = document.getElementById("authStatus");

              function updatePlatformHints() {
                const pl = platformSelect ? platformSelect.value : "instagram";
                const hints = {
                  instagram: "username ou link do Instagram",
                  linkedin: "https://www.linkedin.com/in/... ou URL da empresa",
                  facebook: "URL da página Facebook",
                  tiktok: "@utilizador ou URL TikTok",
                  youtube: "URL do canal YouTube",
                };
                if (profileInput) profileInput.placeholder = hints[pl] || hints.instagram;
                const wrap = document.getElementById("profileInputWrap");
                if (wrap) {
                  if (pl === "instagram") wrap.classList.remove("no-at");
                  else wrap.classList.add("no-at");
                }
                const loginBtn = document.querySelector(".btn-login");
                if (loginBtn) {
                  loginBtn.disabled = pl !== "instagram";
                  loginBtn.style.opacity = pl === "instagram" ? "1" : "0.55";
                }
              }
              if (platformSelect) platformSelect.addEventListener("change", updatePlatformHints);
              updatePlatformHints();

              function escapeHtml(value) {
                return String(value ?? "")
                  .replace(/&/g, "&amp;")
                  .replace(/</g, "&lt;")
                  .replace(/>/g, "&gt;")
                  .replace(/"/g, "&quot;")
                  .replace(/'/g, "&#39;");
              }

              function formatNumber(value) {
                if (value === null || value === undefined || value === "") return "—";
                const num = Number(value);
                if (Number.isNaN(num)) return String(value);
                if (Math.abs(num) >= 1e9) return (num / 1e9).toFixed(1).replace(/\\.0$/, "") + "B";
                if (Math.abs(num) >= 1e6) return (num / 1e6).toFixed(1).replace(/\\.0$/, "") + "M";
                if (Math.abs(num) >= 1e3) return (num / 1e3).toFixed(1).replace(/\\.0$/, "") + "k";
                return Number.isInteger(num) ? String(num) : num.toFixed(2);
              }

              function formatPct(value) {
                if (value === null || value === undefined) return "—";
                const num = Number(value);
                if (Number.isNaN(num)) return "—";
                return num.toFixed(2) + "%";
              }

              function formatDelta(delta, pct) {
                if (delta === null || delta === undefined) return { text: "—", cls: "" };
                const num = Number(delta);
                if (Number.isNaN(num)) return { text: "—", cls: "" };
                const sign = num > 0 ? "+" : "";
                const pctTxt = (pct !== null && pct !== undefined && !Number.isNaN(Number(pct)))
                  ? ` (${sign}${Number(pct).toFixed(1)}%)`
                  : "";
                const cls = num > 0 ? "up" : (num < 0 ? "down" : "");
                return { text: `${sign}${formatNumber(num)}${pctTxt}`, cls };
              }

              function arrow(cls) {
                if (cls === "up") return "▲";
                if (cls === "down") return "▼";
                return "—";
              }

              function listSection(items, klass = "") {
                if (!Array.isArray(items) || !items.length) {
                  return `<li style="color: var(--muted)">Sem dados suficientes.</li>`;
                }
                return items.map(item => `<li>${escapeHtml(item)}</li>`).join("");
              }

              function renderHeader(data) {
                const username = data.profile_username || "n/d";
                const confidence = (data.confianca_analise || "baixa").toLowerCase();
                const confCls = confidence === "alta" ? "ok" : (confidence === "media" ? "warn" : "bad");
                const profile = data.public_profile_data || {};
                const quality = (profile.data_quality || "—").toString();
                const qCls = quality === "alta" ? "ok" : (quality === "media" ? "warn" : "bad");
                const initial = escapeHtml(username.charAt(0).toUpperCase() || "?");
                const followers = profile.followers_count !== undefined && profile.followers_count !== null
                  ? formatNumber(profile.followers_count) + " seguidores"
                  : "perfil Instagram";

                return `
                  <div class="analysis-header">
                    <div class="who">
                      <div class="ig-avatar">${initial}</div>
                      <div>
                        <h2>@${escapeHtml(username)}</h2>
                        <small>${escapeHtml(followers)}</small>
                      </div>
                    </div>
                    <div class="header-badges">
                      <span class="badge ${confCls}"><span class="dot"></span> Confiança: ${escapeHtml(confidence)}</span>
                      <span class="badge ${qCls}"><span class="dot"></span> Qualidade dados: ${escapeHtml(quality)}</span>
                    </div>
                  </div>
                `;
              }

              function renderKpis(data) {
                const profile = data.public_profile_data || {};
                const enrichment = profile.apify_enrichment || {};
                const cadence = enrichment.posting_cadence || {};
                const reelsStats = enrichment.reels_playcount_stats || {};

                const kpis = [
                  { label: "Seguidores", value: formatNumber(profile.followers_count), sub: profile.following_count !== undefined ? `Segue ${formatNumber(profile.following_count)}` : "", accent: true },
                  { label: "Posts", value: formatNumber(profile.posts_count), sub: cadence.posts_last_30_days !== undefined ? `${cadence.posts_last_30_days} nos últimos 30d` : "" },
                  { label: "Engagement", value: profile.engagement_rate !== null && profile.engagement_rate !== undefined ? formatPct(profile.engagement_rate) : "—", sub: "média recente" },
                  { label: "Reels (avg plays)", value: reelsStats.avg_play_count !== undefined ? formatNumber(reelsStats.avg_play_count) : "—", sub: reelsStats.count ? `${reelsStats.count} reels analisados` : "" },
                ];

                return `
                  <div class="kpi-grid">
                    ${kpis.map(k => `
                      <div class="kpi ${k.accent ? "accent" : ""}">
                        <div class="label">${k.label}</div>
                        <div class="value">${k.value}</div>
                        ${k.sub ? `<div class="sub">${escapeHtml(k.sub)}</div>` : ""}
                      </div>
                    `).join("")}
                  </div>
                `;
              }

              function renderFormatBars(distribution) {
                if (!distribution || typeof distribution !== "object") {
                  return `<div style="color: var(--muted)">Sem dados de formato.</div>`;
                }
                const entries = Object.entries(distribution);
                if (!entries.length) return `<div style="color: var(--muted)">Sem dados de formato.</div>`;
                entries.sort((a, b) => (b[1].share_pct || 0) - (a[1].share_pct || 0));
                return `
                  <div class="format-grid">
                    ${entries.map(([fmt, info]) => {
                      const share = typeof info.share_pct === "number" ? info.share_pct : 0;
                      const er = info.avg_engagement_pct;
                      return `
                        <div class="format-row">
                          <div class="format-label">${escapeHtml(fmt)}</div>
                          <div>
                            <div class="format-bar"><div class="format-fill" style="width:${Math.max(2, share)}%"></div></div>
                            ${er !== null && er !== undefined ? `<div class="format-er">engagement médio ${Number(er).toFixed(2)}%</div>` : ""}
                          </div>
                          <div class="format-pct">${share.toFixed(1)}%</div>
                        </div>
                      `;
                    }).join("")}
                  </div>
                `;
              }

              function renderTopCards(items, type) {
                if (!Array.isArray(items) || !items.length) {
                  return `<div style="color: var(--muted)">Sem ${type}.</div>`;
                }
                return `
                  <div class="top-grid">
                    ${items.map((item, idx) => `
                      <div class="top-card">
                        <div class="rank">#${idx + 1}</div>
                        <div style="flex:1; min-width:0">
                          <div class="meta-row">
                            <span>♥ ${formatNumber(item.likes)}</span>
                            <span>💬 ${formatNumber(item.comments)}</span>
                            ${item.playCount !== null && item.playCount !== undefined ? `<span>▶ ${formatNumber(item.playCount)}</span>` : ""}
                          </div>
                          ${item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener">abrir no Instagram ↗</a>` : ""}
                        </div>
                      </div>
                    `).join("")}
                  </div>
                `;
              }

              function renderComparisons(comparisons) {
                const blocks = [
                  { key: "one_week", label: "1 semana" },
                  { key: "two_weeks", label: "2 semanas" },
                  { key: "one_month", label: "1 mês" },
                ];
                return `
                  <div class="compare-grid">
                    ${blocks.map(b => {
                      const obj = (comparisons || {})[b.key];
                      if (!obj || !obj.available) {
                        return `<div class="compare-card empty-card"><div class="label">${b.label}</div><div style="margin-top:6px">sem histórico ainda</div></div>`;
                      }
                      const f = obj.followers || {};
                      const e = obj.engagement_rate || {};
                      const p = obj.posts || {};
                      const df = formatDelta(f.delta, f.delta_pct);
                      const de = formatDelta(e.delta, e.delta_pct);
                      const dp = formatDelta(p.delta, p.delta_pct);
                      return `
                        <div class="compare-card">
                          <div class="label">${b.label}</div>
                          <div class="rows">
                            <div>Followers <span class="delta ${df.cls}">${arrow(df.cls)} ${df.text}</span></div>
                            <div>Engagement <span class="delta ${de.cls}">${arrow(de.cls)} ${de.text}</span></div>
                            <div>Posts <span class="delta ${dp.cls}">${arrow(dp.cls)} ${dp.text}</span></div>
                          </div>
                        </div>
                      `;
                    }).join("")}
                  </div>
                `;
              }

              function renderMetricPills(obj) {
                if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
                  return `<div style="color: var(--muted)">Sem dados.</div>`;
                }
                const entries = Object.entries(obj);
                if (!entries.length) return `<div style="color: var(--muted)">Sem dados.</div>`;
                return `
                  <div class="metric-pills">
                    ${entries.map(([k, v]) => `<span class="metric-pill"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(v)}</span>`).join("")}
                  </div>
                `;
              }

              function renderHashtags(hashtags) {
                if (!Array.isArray(hashtags) || !hashtags.length) return `<div style="color: var(--muted)">Sem hashtags.</div>`;
                return `
                  <div class="hashtag-grid">
                    ${hashtags.map(h => `<span class="hashtag">#${escapeHtml(h.tag)} <span class="count">${h.count}x</span></span>`).join("")}
                  </div>
                `;
              }

              function renderCadence(cadence, reelsStats) {
                const pills = [];
                if (cadence.posts_last_30_days !== undefined) pills.push(["Posts (30d)", cadence.posts_last_30_days]);
                if (cadence.avg_days_between_posts !== undefined) pills.push(["Intervalo médio", `${cadence.avg_days_between_posts} dias`]);
                if (cadence.last_post_at) {
                  const d = new Date(cadence.last_post_at);
                  pills.push(["Último post", isNaN(d) ? cadence.last_post_at : d.toLocaleDateString("pt-PT")]);
                }
                if (reelsStats && reelsStats.count !== undefined) {
                  pills.push(["Reels analisados", reelsStats.count]);
                  pills.push(["Plays mediano", formatNumber(reelsStats.median_play_count)]);
                  pills.push(["Plays máximo", formatNumber(reelsStats.max_play_count)]);
                }
                if (!pills.length) return `<div style="color: var(--muted)">Sem dados.</div>`;
                return `
                  <div class="metric-pills">
                    ${pills.map(([k, v]) => `<span class="metric-pill"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(v)}</span>`).join("")}
                  </div>
                `;
              }

              function renderTabs() {
                return `
                  <div class="tabs">
                    <div class="tab active" data-target="overview">Visão Geral</div>
                    <div class="tab" data-target="actions">Ações &amp; Ideias</div>
                    <div class="tab" data-target="content">Conteúdo</div>
                    <div class="tab" data-target="evolution">Evolução</div>
                  </div>
                `;
              }

              function attachTabHandlers() {
                document.querySelectorAll(".tab").forEach(tab => {
                  tab.addEventListener("click", () => {
                    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
                    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
                    tab.classList.add("active");
                    const target = tab.getAttribute("data-target");
                    const panel = document.getElementById("panel-" + target);
                    if (panel) panel.classList.add("active");
                  });
                });
              }

              function startInstagramLogin() {
                window.location.href = "/agents/social-media/auth/start";
              }

              async function refreshAuthStatus() {
                try {
                  const response = await fetch("/agents/social-media/auth/status");
                  const data = await response.json();
                  if (!response.ok) {
                    authStatus.className = "badge bad";
                    authStatus.innerHTML = `<span class="dot"></span> erro ao validar login`;
                    return;
                  }
                  if (data.connected) {
                    const username = data.username ? `@${data.username}` : "conta ligada";
                    authStatus.className = "badge ok";
                    authStatus.innerHTML = `<span class="dot"></span> Ligado · ${escapeHtml(username)}`;
                    return;
                  }
                  authStatus.className = "badge";
                  authStatus.innerHTML = `<span class="dot"></span> Sem login Instagram`;
                } catch (err) {
                  authStatus.className = "badge bad";
                  authStatus.innerHTML = `<span class="dot"></span> indisponível`;
                }
              }

              async function runInstagramAnalysis() {
                const profileValue = profileInput.value.trim();
                const pl = platformSelect ? platformSelect.value : "instagram";
                const emptyHint = {
                  instagram: "Preenche o @username ou o link do perfil Instagram.",
                  linkedin: "Preenche o URL público do LinkedIn (perfil ou empresa).",
                  facebook: "Preenche o URL da página Facebook.",
                  tiktok: "Preenche o @utilizador ou o link do TikTok.",
                  youtube: "Preenche o URL do canal YouTube.",
                };
                if (!profileValue) {
                  result.innerHTML = `<div class="err"><strong>Erro:</strong> ${emptyHint[pl] || emptyHint.instagram}</div>`;
                  return;
                }
                const useUnifiedIg = pl === "instagram";
                const endpoint = useUnifiedIg ? "/agents/social-media/analyze" : "/agents/social-media/profile-analyze";
                const payload = useUnifiedIg
                  ? {
                      profile_input: profileValue,
                      instagram_data: {},
                      language: "pt-PT",
                      platform: pl,
                    }
                  : {
                      profile_input: profileValue,
                      messages: [],
                      language: "pt-PT",
                      platform: pl,
                    };
                result.innerHTML = `
                  <div class="loading">
                    <div class="spinner"></div>
                    <div>
                      <div style="color: var(--text); font-weight:600">A processar análise</div>
                      <div style="font-size:0.85rem">Plataforma: ${escapeHtml(platformSelect ? platformSelect.options[platformSelect.selectedIndex].text : "Instagram")} — pode demorar alguns segundos…</div>
                    </div>
                  </div>
                `;
                try {
                  const response = await fetch(endpoint, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                  });
                  const data = await response.json();
                  if (!response.ok) {
                    const detailText = data.detail || JSON.stringify(data);
                    result.innerHTML = `<div class="err"><strong>Erro:</strong> ${escapeHtml(detailText)}</div>`;
                    return;
                  }

                  const profile = data.public_profile_data || {};
                  const enrichment = profile.apify_enrichment || {};

                  result.innerHTML = `
                    ${renderHeader(data)}
                    ${renderKpis(data)}
                    ${renderTabs()}

                    <div id="panel-overview" class="panel active">
                      <div class="section">
                        <h3>Principais Insights <span class="pill cool">IA</span></h3>
                        <ul class="insight-list">${listSection(data.principais_insights)}</ul>
                      </div>
                      <div class="section">
                        <h3>Problemas Identificados <span class="pill">atenção</span></h3>
                        <ul class="insight-list problems">${listSection(data.problemas_identificados)}</ul>
                      </div>
                      <div class="section">
                        <h3>Oportunidades <span class="pill cool">crescimento</span></h3>
                        <ul class="insight-list opps">${listSection(data.oportunidades)}</ul>
                      </div>
                      <div class="section">
                        <h3>Métricas Universais</h3>
                        ${renderMetricPills(data.metricas_universais)}
                      </div>
                      <div class="section">
                        <h3>Métricas específicas (${escapeHtml(data.plataforma_label || "Instagram")})</h3>
                        ${renderMetricPills(data.metricas_instagram)}
                      </div>
                    </div>

                    <div id="panel-actions" class="panel">
                      <div class="section">
                        <h3>Ações Prioritárias <span class="pill">agora</span></h3>
                        <ul class="insight-list actions">${listSection(data.acoes_prioritarias)}</ul>
                      </div>
                      <div class="section">
                        <h3>Ideias de Conteúdo <span class="pill violet">criativo</span></h3>
                        <ul class="insight-list violet">${listSection(data.ideias_conteudo)}</ul>
                      </div>
                      <div class="section">
                        <h3>Plano de Crescimento (curto prazo)</h3>
                        <ul class="insight-list">${listSection(data.plano_crescimento_curto_prazo)}</ul>
                      </div>
                    </div>

                    <div id="panel-content" class="panel">
                      <div class="section">
                        <h3>Distribuição por Formato</h3>
                        ${renderFormatBars(enrichment.format_distribution)}
                      </div>
                      <div class="section">
                        <h3>Top Posts <span class="pill cool">likes</span></h3>
                        ${renderTopCards(enrichment.top_posts, "top posts")}
                      </div>
                      <div class="section">
                        <h3>Top Reels <span class="pill violet">plays</span></h3>
                        ${renderTopCards(enrichment.top_reels, "top reels")}
                      </div>
                      <div class="section">
                        <h3>Cadência &amp; Reels</h3>
                        ${renderCadence(enrichment.posting_cadence || {}, enrichment.reels_playcount_stats || {})}
                      </div>
                      <div class="section">
                        <h3>Top Hashtags</h3>
                        ${renderHashtags(enrichment.top_hashtags)}
                      </div>
                    </div>

                    <div id="panel-evolution" class="panel">
                      <div class="section">
                        <h3>Comparação Temporal</h3>
                        ${renderComparisons(data.comparisons)}
                      </div>
                      <div class="section">
                        <h3>Lacunas de Dados</h3>
                        <ul class="gap-list">${listSection(data.lacunas_de_dados)}</ul>
                      </div>
                    </div>
                  `;
                  attachTabHandlers();
                } catch (err) {
                  const errorMessage = err instanceof Error ? err.message : String(err);
                  result.innerHTML = `<div class="err"><strong>Erro:</strong> ${escapeHtml(errorMessage)}</div>`;
                }
              }

              profileInput.addEventListener("keydown", (ev) => {
                if (ev.key === "Enter") {
                  ev.preventDefault();
                  runInstagramAnalysis();
                }
              });
              refreshAuthStatus();
            </script>
          </body>
        </html>
        """

    if agent_slug == "designer":
        return """
        <!doctype html>
        <html lang="pt">
          <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>Agente Designer</title>
            <style>
              :root {
                --bg: #0b1220;
                --surface: #172033;
                --surface-2: #111a2a;
                --line: rgba(255, 255, 255, 0.12);
                --text: #e2e8f0;
                --muted: #94a3b8;
                --user: #2563eb;
                --assistant: #7c3aed;
              }
              body {
                font-family: "Segoe UI", system-ui, sans-serif;
                margin: 0;
                background: radial-gradient(circle at 15% 15%, #1f2a44 0%, #0b1220 60%);
                color: var(--text);
                padding: 24px 16px;
              }
              .wrap { max-width: 980px; margin: 0 auto; }
              .card {
                background: var(--surface);
                border: 1px solid var(--line);
                border-radius: 14px;
                padding: 20px;
              }
              .top { display: flex; gap: 14px; align-items: center; margin-bottom: 10px; }
              .avatar {
                width: 72px;
                height: 72px;
                border-radius: 50%;
                overflow: hidden;
                border: 2px solid rgba(255,255,255,0.15);
                background: #fff;
                flex-shrink: 0;
              }
              .avatar img { width: 100%; height: 100%; object-fit: cover; }
              .title { margin: 0; font-size: 1.4rem; }
              .subtitle { margin: 4px 0 0; color: var(--muted); font-size: 0.92rem; }
              .chat-log {
                margin-top: 16px;
                border: 1px solid var(--line);
                border-radius: 12px;
                background: var(--surface-2);
                padding: 14px;
                min-height: 320px;
                max-height: 420px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 10px;
              }
              .msg {
                max-width: 82%;
                padding: 10px 12px;
                border-radius: 10px;
                line-height: 1.45;
                font-size: 0.93rem;
                white-space: pre-wrap;
              }
              .msg.user { align-self: flex-end; background: var(--user); }
              .msg.assistant { align-self: flex-start; background: var(--assistant); }
              .msg.typing {
                align-self: flex-start;
                background: var(--assistant);
                display: inline-flex;
                align-items: center;
                gap: 5px;
                min-width: 54px;
              }
              .typing-dot {
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.92);
                animation: typingBounce 1.1s infinite ease-in-out;
              }
              .typing-dot:nth-child(2) { animation-delay: 0.15s; }
              .typing-dot:nth-child(3) { animation-delay: 0.3s; }
              @keyframes typingBounce {
                0%, 80%, 100% { transform: translateY(0); opacity: 0.55; }
                40% { transform: translateY(-4px); opacity: 1; }
              }
              .controls { margin-top: 14px; display: grid; grid-template-columns: 1fr 180px 150px; gap: 10px; }
              .controls textarea, .controls input, .controls select {
                width: 100%;
                box-sizing: border-box;
                border-radius: 10px;
                border: 1px solid var(--line);
                background: #0b1220;
                color: var(--text);
                padding: 10px 12px;
                font-family: inherit;
              }
              .controls textarea { min-height: 56px; resize: vertical; }
              .actions { margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap; }
              button {
                border: none;
                border-radius: 9px;
                padding: 10px 14px;
                color: #fff;
                font-weight: 600;
                cursor: pointer;
              }
              .send-btn { background: linear-gradient(180deg, #2563eb, #1d4ed8); }
              .generate-btn { background: linear-gradient(180deg, #f59e0b, #d97706); }
              .reset-btn { background: linear-gradient(180deg, #64748b, #475569); }
              .download-btn {
                margin-top: 12px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                border: none;
                border-radius: 9px;
                padding: 10px 14px;
                color: #fff;
                font-weight: 700;
                cursor: pointer;
                text-decoration: none;
                background: linear-gradient(180deg, #22c55e, #16a34a);
                box-shadow: 0 10px 20px -14px rgba(34, 197, 94, 0.7);
                transition: transform 0.12s ease, filter 0.12s ease;
              }
              .download-btn:hover { filter: brightness(1.06); transform: translateY(-1px); }
              .hint { color: var(--muted); font-size: 0.84rem; margin-top: 8px; }
              .result {
                margin-top: 16px;
                border: 1px solid var(--line);
                border-radius: 12px;
                background: #0f172a;
                padding: 14px;
              }
              .result img {
                margin-top: 10px;
                width: 100%;
                max-width: 460px;
                border-radius: 10px;
                border: 1px solid var(--line);
              }
              .references {
                margin-top: 10px;
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
              }
              .references img {
                width: 74px;
                height: 74px;
                object-fit: cover;
                border-radius: 8px;
                border: 1px solid var(--line);
              }
              a { color: #93c5fd; text-decoration: none; }
              @media (max-width: 860px) { .controls { grid-template-columns: 1fr; } .msg { max-width: 94%; } }
            </style>
          </head>
          <body>
            <div class="wrap">
              <p><a href="/">← Voltar ao Diretor</a></p>
              <div class="card">
                <div class="top">
                  <div class="avatar">
                    <img src="/assets/designer-photo" alt="Avatar do Agente Designer" />
                  </div>
                  <div>
                    <h1 class="title">Agente Designer · Chatroom</h1>
                    <p class="subtitle">Faz briefing visual no chat e depois gera a imagem.</p>
                  </div>
                </div>
                <div id="chatLog" class="chat-log"></div>
                <div class="controls">
                  <textarea id="chatInput" placeholder="Descreve a imagem que queres: objetivo, cenário, elementos, estilo, cores, formato..."></textarea>
                  <input id="styleInput" placeholder="Estilo (ex.: realista)" />
                  <select id="sizeInput">
                    <option value="1024x1024">1024x1024</option>
                    <option value="1024x1536">1024x1536</option>
                    <option value="1536x1024">1536x1024</option>
                    <option value="1280x720">1280x720</option>
                    <option value="1366x768">1366x768</option>
                    <option value="1600x900">1600x900</option>
                    <option value="1920x1080">1920x1080</option>
                    <option value="1080x1920">1080x1920</option>
                  </select>
                </div>
                <div class="actions">
                  <input id="referenceFileInput" type="file" accept="image/*" />
                  <button type="button" class="send-btn" onclick="uploadReferenceImage()">Anexar imagem de referência</button>
                </div>
                <div id="references" class="references"></div>
                <div class="actions">
                  <button type="button" class="send-btn" onclick="sendMessage()">Enviar mensagem</button>
                  <button type="button" class="generate-btn" onclick="generateImage()">Gerar imagem</button>
                  <button type="button" class="reset-btn" onclick="resetChat()">Limpar conversa</button>
                </div>
                <p class="hint">Dica: quanto mais detalhado for o briefing, melhor será a imagem final.</p>
                <div id="result" class="result"></div>
              </div>
            </div>
            <script>
              const chatLog = document.getElementById("chatLog");
              const chatInput = document.getElementById("chatInput");
              const styleInput = document.getElementById("styleInput");
              const sizeInput = document.getElementById("sizeInput");
              const referenceFileInput = document.getElementById("referenceFileInput");
              const referencesContainer = document.getElementById("references");
              const result = document.getElementById("result");
              const messages = [];
              const referenceImageUrls = [];

              function addMessage(role, content) {
                messages.push({ role, content });
                const bubble = document.createElement("div");
                bubble.className = `msg ${role}`;
                bubble.textContent = content;
                chatLog.appendChild(bubble);
                chatLog.scrollTop = chatLog.scrollHeight;
              }

              function showTypingIndicator() {
                const bubble = document.createElement("div");
                bubble.className = "msg assistant typing";
                bubble.id = "typingIndicator";
                bubble.innerHTML = `
                  <span class="typing-dot"></span>
                  <span class="typing-dot"></span>
                  <span class="typing-dot"></span>
                `;
                chatLog.appendChild(bubble);
                chatLog.scrollTop = chatLog.scrollHeight;
              }

              function hideTypingIndicator() {
                const el = document.getElementById("typingIndicator");
                if (el) {
                  el.remove();
                }
              }

              function renderReferences() {
                referencesContainer.innerHTML = "";
                referenceImageUrls.forEach((url) => {
                  const img = document.createElement("img");
                  img.src = url;
                  img.alt = "Imagem de referência";
                  referencesContainer.appendChild(img);
                });
              }

              async function uploadReferenceImage() {
                const file = referenceFileInput.files && referenceFileInput.files[0];
                if (!file) {
                  result.innerHTML = "<p><strong>Erro:</strong> Escolhe uma imagem para anexar.</p>";
                  return;
                }
                result.innerHTML = "<p>A fazer upload da imagem de referência…</p>";

                const formData = new FormData();
                formData.append("file", file);
                const response = await fetch("/agents/designer/upload-reference", {
                  method: "POST",
                  body: formData
                });
                const data = await response.json();
                if (!response.ok) {
                  const detailText = data.detail || JSON.stringify(data);
                  result.innerHTML = `<p><strong>Erro:</strong> ${detailText}</p>`;
                  return;
                }

                referenceImageUrls.push(data.image_url);
                renderReferences();
                referenceFileInput.value = "";
                addMessage("assistant", "Imagem de referência recebida. Vou usá-la no contexto da geração.");
                result.innerHTML = "<p>Imagem anexada com sucesso.</p>";
              }

              async function sendMessage() {
                const content = chatInput.value.trim();
                if (!content) {
                  return;
                }
                addMessage("user", content);
                chatInput.value = "";
                result.innerHTML = "<p>A processar mensagem do Designer…</p>";
                showTypingIndicator();

                const payload = {
                  messages,
                  language: "pt-PT",
                  style: styleInput.value.trim() || null,
                  reference_image_urls: referenceImageUrls
                };

                try {
                  const response = await fetch("/agents/designer/chat-reply", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                  });
                  const data = await response.json();
                  hideTypingIndicator();
                  if (!response.ok) {
                    const detailText = data.detail || JSON.stringify(data);
                    addMessage("assistant", "Não consegui responder agora. Tenta novamente.");
                    result.innerHTML = `<p><strong>Erro:</strong> ${detailText}</p>`;
                    return;
                  }

                  addMessage("assistant", data.reply || "Percebi. Podes acrescentar mais detalhes visuais?");
                  result.innerHTML = "<p>Conversa atualizada. Quando estiveres pronto, clica em «Gerar imagem».</p>";
                } catch (err) {
                  hideTypingIndicator();
                  const errorMessage = err instanceof Error ? err.message : String(err);
                  addMessage("assistant", "Não consegui responder agora. Verifica a ligação e tenta novamente.");
                  result.innerHTML = `<p><strong>Erro:</strong> ${errorMessage}</p>`;
                }
              }

              async function generateImage() {
                if (!messages.length) {
                  result.innerHTML = "<p><strong>Erro:</strong> A conversa está vazia.</p>";
                  return;
                }
                showTypingIndicator();
                const payload = {
                  messages,
                  size: sizeInput.value,
                  style: styleInput.value.trim() || null,
                  reference_image_urls: referenceImageUrls
                };

                try {
                  const response = await fetch("/agents/designer/chat-generate-image", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                  });
                  const data = await response.json();
                  hideTypingIndicator();
                  if (!response.ok) {
                    const detailText = data.detail || JSON.stringify(data);
                    addMessage("assistant", "Não consegui gerar a imagem agora. Ajusta o pedido e tenta novamente.");
                    result.innerHTML = `<p><strong>Erro:</strong> ${detailText}</p>`;
                    return;
                  }

                  const imageUrl = data.image_url || "";
                  result.innerHTML = `
                    <h3>Imagem gerada</h3>
                    ${imageUrl ? `<img src="${imageUrl}" alt="Imagem gerada" />` : "<p>Sem URL de imagem devolvida.</p>"}
                    ${imageUrl ? `<br /><a class="download-btn" href="${imageUrl}" download="imagem-gerada.png">Download da imagem</a>` : ""}
                  `;
                  addMessage("assistant", "Imagem gerada com sucesso. Podes fazer download no botão abaixo.");
                } catch (err) {
                  hideTypingIndicator();
                  const errorMessage = err instanceof Error ? err.message : String(err);
                  addMessage("assistant", "Não consegui gerar a imagem por agora. Verifica a ligação e tenta de novo.");
                  result.innerHTML = `<p><strong>Erro:</strong> ${errorMessage}</p>`;
                }
              }

              function resetChat() {
                messages.length = 0;
                referenceImageUrls.length = 0;
                chatLog.innerHTML = "";
                renderReferences();
                result.innerHTML = "<p>Conversa limpa.</p>";
                addMessage("assistant", "Olá. Sou o Agente Designer. Vamos criar um conceito visual e depois gerar a imagem.");
              }

              addMessage("assistant", "Olá. Sou o Agente Designer. Vamos criar um conceito visual e depois gerar a imagem.");
              chatInput.addEventListener("keydown", (event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              });
            </script>
          </body>
        </html>
        """

    return f"""
    <!doctype html>
    <html lang="pt">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>{agent_name}</title>
        <style>
          body {{ font-family: "Segoe UI", system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; padding: 30px 18px; }}
          .wrap {{ max-width: 900px; margin: 0 auto; }}
          .card {{ background: #1e293b; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 20px; }}
          a {{ color: #93c5fd; text-decoration: none; }}
          .hint {{ color: #94a3b8; }}
        </style>
      </head>
      <body>
        <div class="wrap">
          <p><a href="/">← Voltar ao Diretor</a></p>
          <div class="card">
            <h1>{agent_name}</h1>
            <p>Esta é a página dedicada do agente selecionado pelo Diretor.</p>
            <p class="hint">
              Aqui podes continuar a conversa específica deste agente.
              No próximo passo posso ligar cada página ao motor próprio de execução.
            </p>
          </div>
        </div>
      </body>
    </html>
    """
