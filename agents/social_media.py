"""Agente de Redes Sociais focado em análise de Instagram (MVP)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI


class SocialMediaAgent:
    """Analisa performance de Instagram e gera recomendações acionáveis.

    O agente está preparado para a fase MVP centrada em Instagram, mas organiza
    a análise em duas camadas:
    - métricas universais (reutilizáveis noutras plataformas);
    - métricas específicas do Instagram (ex.: Reels reach, guardados).

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
    ) -> Dict[str, Any]:
        """Produz análise estruturada de Instagram com foco em ações prioritárias.

        A função combina histórico da conversa e dados estruturados fornecidos
        (quando existirem), executa uma interpretação analítica e devolve um
        objeto JSON com secções fixas de output: insights, problemas,
        oportunidades, ações, ideias de conteúdo e plano de crescimento.
        A resposta separa também métricas universais de métricas específicas de
        Instagram, facilitando expansão futura para outras plataformas.

        Argumentos:
            messages: Histórico cronológico da chatroom com mensagens do
                utilizador e do agente.
            instagram_data: Dicionário opcional com métricas do Instagram
                (seguidores, engagement, posts, audiência, etc.).
            language: Idioma/região da análise final (por defeito `pt-PT`).

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

        instagram_payload = instagram_data or {}
        compact_data = json.dumps(instagram_payload, ensure_ascii=False, indent=2)

        system_prompt = (
            "És um Agente de Análise de Redes Sociais especializado em Instagram. "
            "Objetivo: analisar performance e recomendar ações concretas com impacto em crescimento e engagement. "
            f"Responde sempre em {language}. "
            "Fase atual: MVP focado exclusivamente em Instagram. "
            "Estrutura sempre o raciocínio de forma modular para futura expansão a Facebook, LinkedIn e TikTok. "
            "Não assumes dados inexistentes; quando faltar informação, explicita em `lacunas_de_dados`. "
            "Prioriza insight acionável, evita sugestões genéricas. "
            "Justifica cada conclusão com dados disponíveis (histórico e JSON). "
            "Separa o que é universal do que é específico de Instagram.\n\n"
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
            "\"metricas_instagram\":{"
            "\"reels_reach\":\"...\","
            "\"guardados\":\"...\","
            "\"partilhas\":\"...\""
            "},"
            "\"confianca_analise\":\"alta|media|baixa\","
            "\"lacunas_de_dados\":[\"...\"]"
            "}\n\n"
            "Regras obrigatórias:\n"
            "1) Incluir sempre as secções com conteúdo acionável.\n"
            "2) Referir possíveis causas para picos/quedas apenas quando suportado por dados.\n"
            "3) Recomendar frequência e horários de publicação apenas com base em padrões observáveis; "
            "se não houver padrão, indicar isso em `lacunas_de_dados`.\n"
            "4) Evitar texto vago como 'publicar melhor conteúdo'.\n"
            "5) Focar curto prazo (2 a 4 semanas) no plano de crescimento."
        )

        user_prompt = (
            "Dados estruturados de Instagram (podem estar incompletos):\n"
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
        return self._parse_analysis_json(raw_content)

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
        normalized["metricas_universais"] = (
            metricas_universais if isinstance(metricas_universais, dict) else {}
        )
        normalized["metricas_instagram"] = (
            metricas_instagram if isinstance(metricas_instagram, dict) else {}
        )

        confidence = str(parsed.get("confianca_analise", "baixa")).strip().lower()
        normalized["confianca_analise"] = confidence if confidence in {"alta", "media", "baixa"} else "baixa"
        return normalized

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


social_media_agent = SocialMediaAgent()
