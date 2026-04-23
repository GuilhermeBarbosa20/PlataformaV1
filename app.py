from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple
import unicodedata
from urllib import error, request

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

from agents.copywriter import copywriter_agent
from agents.designer import designer_agent


STATIC_DIR = BASE_DIR / "static"
COPYWRITER_PHOTO_PATH = Path(
    r"C:\Users\Gui\.cursor\projects\c-Users-Gui-Desktop-Cursor-Teste-PlataformaV1\assets\c__Users_Gui_AppData_Roaming_Cursor_User_workspaceStorage_5cf04d98823b3ed471fa9fcf2f9a8995_images_image-086e2d41-4ac7-4b47-94ee-d5b6a9591ec8.png"
)
DESIGNER_PHOTO_PATH = Path(
    r"C:\Users\Gui\.cursor\projects\c-Users-Gui-Desktop-Cursor-Teste-PlataformaV1\assets\c__Users_Gui_AppData_Roaming_Cursor_User_workspaceStorage_5cf04d98823b3ed471fa9fcf2f9a8995_images_image-60079ec3-45f1-4734-bbfb-0c9b44f7606c.png"
)

app = FastAPI(
    title="Diretor de Marketing AI",
    description="Colaborador virtual que interpreta pedidos e encaminha para agentes de marketing.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

AGENT_SLUGS: Dict[str, str] = {
    "Agente Copywriter": "copywriter",
    "Agente Designer": "designer",
    "Agente Redes sociais": "redes-sociais",
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

    O frontend envia o histórico da conversa e o backend chama o modelo
    `gpt-4o-mini` para produzir uma resposta autónoma do Diretor, mantendo o
    tom de consultoria estratégica e educação com o utilizador.

    Argumentos:
        messages: Histórico cronológico da conversa na chatroom do Diretor.
        language: Idioma preferido da resposta (por defeito `pt-PT`).

    Retorno:
        Instância validada para o endpoint `POST /director/chat-reply`.
    """

    messages: List[DirectorChatMessage] = Field(
        ..., min_length=1, description="Histórico de mensagens da chatroom do Diretor."
    )
    language: str = Field("pt-PT", min_length=2, description="Idioma da resposta do Diretor.")


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


class MarketingDirector:
    """Orquestrador principal que encaminha instruções para agentes posteriores.

    Este agente atua como “Diretor de Marketing”: interpreta a intenção do
    utilizador, seleciona o agente especializado mais adequado e devolve uma
    resposta orientada para execução.
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
                "linkedin",
                "anuncios linkedin",
                "linkedin sponsorizado",
                "sponsored linkedin",
                "campanha linkedin",
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
        return selected_agent, str(rationale)

    def generate_chat_reply(self, messages: List[Dict[str, str]], language: str = "pt-PT") -> Dict[str, object]:
        """Gera resposta do Diretor e estado de encaminhamento na chatroom.

        A função usa `gpt-4o-mini` para analisar o histórico completo e produzir
        uma resposta educada e contextual. Além do texto, devolve se já existe
        contexto suficiente para encaminhar e, quando aplicável, qual agente
        especializado deve receber o pedido.

        Argumentos:
            messages: Lista cronológica de mensagens (`role` e `content`) da sala.
            language: Idioma da resposta do Diretor (por defeito `pt-PT`).

        Retorno:
            Dicionário com:
            - `reply`: resposta textual do Diretor;
            - `ready_to_route`: booleano indicando se já deve encaminhar;
            - `agent_name`: nome do agente quando `ready_to_route` é `True`.

        Raises:
            RuntimeError: Se `OPENAI_API_KEY` não estiver configurada.
        """

        self._openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not self._openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY nao configurada no servidor. Define a variavel de ambiente para usar a chatroom do Diretor."
            )

        client = OpenAI(api_key=self._openai_api_key)
        allowed_agents = ", ".join(self._agent_catalog)
        system_prompt = (
            "És o Diretor de Marketing AI numa chatroom de triagem. "
            f"Responde sempre em {language}, com educação e brevidade. "
            "O teu papel é APENAS perceber o pedido, fazer perguntas curtas quando faltar contexto, "
            "e encaminhar para UM agente especializado. "
            "PROIBIÇÃO ABSOLUTA: não escrevas copy, posts, anúncios, roteiros, emails, headlines, CTAs, "
            "legendas, hashtags nem texto pronto para publicar. Isso é trabalho dos agentes posteriores. "
            "Se o utilizador pedir texto para publicação/post/legenda/copy (mesmo sem dar tema), "
            "NÃO peças tema/público/tom aqui — isso é feito na chatroom do Agente Copywriter. "
            "Nesse caso define logo `ready_to_route` como true e `agent_name` como `Agente Copywriter`, "
            "e em `reply` diz só que o utilizador deve clicar em «Encaminhar para o agente». "
            "Quando já tiveres contexto suficiente para encaminhar, escolhe exatamente um agente da lista. "
            f"Agentes permitidos: {allowed_agents}. "
            "O campo `reply` deve ter no máximo cerca de 3 frases curtas. "
            "Responde APENAS com JSON válido no formato: "
            '{"reply":"<resposta ao utilizador>","ready_to_route":true|false,"agent_name":"<agente permitido ou vazio>"}'
        )

        sanitized_messages: List[Dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "")).strip()
            content = str(message.get("content", "")).strip()
            if role not in {"user", "assistant"} or not content:
                continue
            sanitized_messages.append({"role": role, "content": content})

        fast_route = self._infer_route_from_last_user_message(sanitized_messages)
        if fast_route is not None:
            return fast_route

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.4,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system_prompt}, *sanitized_messages],
        )
        raw = (response.choices[0].message.content or "").strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return self._coerce_director_chat_decision(
                reply=raw or "Percebi. Podes detalhar mais para eu decidir o melhor encaminhamento?",
                ready_to_route=False,
                agent_name=None,
                sanitized_messages=sanitized_messages,
            )

        reply = str(data.get("reply", "")).strip() or "Percebi. Podes detalhar mais para eu decidir o melhor encaminhamento?"
        ready_to_route = bool(data.get("ready_to_route", False))
        raw_agent_name = str(data.get("agent_name", "")).strip()
        agent_name = raw_agent_name if raw_agent_name in self._agent_catalog else None
        if ready_to_route and not agent_name:
            ready_to_route = False

        return self._coerce_director_chat_decision(
            reply=reply,
            ready_to_route=ready_to_route,
            agent_name=agent_name,
            sanitized_messages=sanitized_messages,
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


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    """Renderiza interface web simples para conversar por instrução.

    A função devolve uma página HTML com identidade visual profissional,
    avatar do Diretor servido em `/static/diretor-avatar.png`, campo de texto
    e botão “Enviar”, permitindo ao utilizador interagir com o colaborador
    virtual sem precisar de ferramentas externas.

    Argumentos:
        Nenhum.

    Retorno:
        String HTML completa da interface de chat.
    """

    return """
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
          .forward-btn {
            margin-top: 12px;
            width: 100%;
            max-width: 320px;
            display: block;
            padding: 12px 16px;
            border-radius: 10px;
            border: none;
            font-weight: 700;
            cursor: pointer;
            color: #fff;
            background: linear-gradient(180deg, #10b981, #059669);
          }
          .forward-btn:hover { filter: brightness(1.06); }
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
                <p class="subtitle">Descreve o que precisas: eu esclareço em poucas palavras e, quando fizer sentido, indico o agente certo. Não escrevo aqui textos finais para publicar — isso fica com o especialista.</p>
              </div>
            </div>

            <div id="chatLog" class="chat-log"></div>
            <div class="controls">
              <textarea id="chatInput" placeholder="Escreve o que pretendes fazer no marketing do teu negócio..."></textarea>
              <input id="languageInput" value="pt-PT" placeholder="Idioma" />
            </div>
            <div class="actions">
              <button type="button" class="send-btn" onclick="sendMessage()">Enviar</button>
              <button type="button" class="reset-btn" onclick="resetChat()">Limpar conversa</button>
            </div>
            <p class="hint">Triagem por `gpt-4o-mini`: o Diretor não publica copy final; quando estiver claro, aparece o botão para o agente certo.</p>
            <div id="result" class="result"></div>
          </section>
          <footer>PlataformaV1 · Diretor de Marketing AI</footer>
        </div>
        <script>
          const chatLog = document.getElementById("chatLog");
          const chatInput = document.getElementById("chatInput");
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

          async function sendMessage() {
            const content = chatInput.value.trim();
            if (!content) return;
            addMessage("user", content);
            chatInput.value = "";
            result.innerHTML = "<p>A processar resposta com gpt-4o-mini…</p>";
            showTypingIndicator();

            const payload = {
              messages,
              language: languageInput.value.trim() || "pt-PT"
            };

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

              addMessage("assistant", data.reply || "Percebi. Podes detalhar melhor o objetivo para eu te orientar?");
              if (data.ready_to_route && data.agent_name && data.agent_url) {
                const safeUrl = data.agent_url.replace(/'/g, "%27");
                result.innerHTML = `
                  <h3>Agente recomendado</h3>
                  <p><strong>${data.agent_name}</strong></p>
                  <button type="button" class="forward-btn" onclick="window.location.href='${safeUrl}'">Encaminhar para o agente</button>
                `;
              } else {
                result.innerHTML = "<p>Resposta enviada. O Diretor ainda está a recolher contexto antes do encaminhamento.</p>";
              }
            } catch (err) {
              hideTypingIndicator();
              const errorMessage = err instanceof Error ? err.message : String(err);
              addMessage("assistant", "Não consegui responder agora. Verifica a ligação e tenta novamente.");
              result.innerHTML = `<p><strong>Erro:</strong> ${errorMessage}</p>`;
            }
          }

          function resetChat() {
            messages.length = 0;
            chatLog.innerHTML = "";
            result.innerHTML = "<p>Conversa reiniciada.</p>";
            addMessage("assistant", "Olá! Sou o Diretor de Marketing AI. O que desejas fazer hoje no teu marketing?");
          }

          addMessage("assistant", "Olá! Sou o Diretor de Marketing AI. O que desejas fazer hoje no teu marketing?");
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


@app.post("/chat")
def chat(payload: ChatRequest) -> Dict[str, object]:
    """Processa o input do utilizador e devolve encaminhamento do diretor.

    Esta função é o endpoint principal para conversa. Recebe a instrução,
    chama o Diretor de Marketing e devolve o agente especializado selecionado
    juntamente com um plano de ação.

    Argumentos:
        payload: Objeto validado contendo o texto do utilizador.

    Retorno:
        Dicionário serializável com `agent_name`, `action_plan`,
        `justification` e `agent_url` para apresentação no frontend e
        navegação para a página do agente.
    """

    result = director.route(payload.user_input)
    return {
        "agent_name": result.agent_name,
        "action_plan": result.action_plan,
        "justification": result.justification,
        "agent_url": _agent_page_url(result.agent_name),
    }


@app.post("/director/chat-reply")
def director_chat_reply(payload: DirectorChatTurnRequest) -> Dict[str, object]:
    """Gera a próxima resposta autónoma do Diretor de Marketing na chatroom.

    O endpoint recebe o histórico da conversa e chama o LLM (`gpt-4o-mini`) para
    produzir uma resposta contextual e educada do Diretor. A resposta não segue
    um guião fixo; é processada com base no conteúdo real enviado pelo
    utilizador e no contexto acumulado.

    Argumentos:
        payload: Histórico validado da chatroom e idioma pretendido.

    Retorno:
        Dicionário com:
        - `reply`: resposta textual do Diretor;
        - `ready_to_route`: sinal de encaminhamento;
        - `agent_name`: agente recomendado quando aplicável;
        - `agent_url`: URL do agente para navegação direta.

    Raises:
        HTTPException: 503 quando a chave OpenAI não está configurada;
            502 quando a geração da resposta falha no cliente OpenAI.
    """

    try:
        history = [{"role": item.role, "content": item.content} for item in payload.messages]
        decision = director.generate_chat_reply(messages=history, language=payload.language)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — expor mensagem genérica ao cliente
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao contactar OpenAI: {exc!s}",
        ) from exc

    agent_name = decision.get("agent_name")
    agent_url = _agent_page_url(str(agent_name)) if agent_name else None
    return {
        "reply": str(decision.get("reply") or "Percebi. Explica-me um pouco mais para eu orientar-te melhor."),
        "ready_to_route": bool(decision.get("ready_to_route", False)),
        "agent_name": agent_name,
        "agent_url": agent_url,
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
