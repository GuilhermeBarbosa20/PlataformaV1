"""Agente Copywriter com geração de textos via API OpenAI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import dotenv_values
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent.parent


class CopywriterAgent:
    """Gera copy de marketing em português com base num brief, usando OpenAI.

    Este agente encapsula chamadas ao modelo configurado (por defeito
    `gpt-4o-mini`), pedindo sempre uma resposta em JSON estruturado para
    facilitar consumo pela API e pela interface web.

    Argumentos (atributos de instância):
        Nenhum obrigatório no construtor; a chave e o modelo vêm de variáveis
        de ambiente.

    Retorno:
        Os métodos públicos devolvem dicionários prontos para serialização JSON.
    """

    def __init__(self) -> None:
        """Inicializa o cliente OpenAI a partir de variáveis de ambiente.

        Lê `OPENAI_API_KEY` (obrigatório para gerar texto) e opcionalmente
        `OPENAI_MODEL` (por defeito `gpt-4o-mini`).

        Argumentos:
            Nenhum.

        Retorno:
            Nenhum.
        """

        self._api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    def _refresh_from_env(self) -> None:
        """Atualiza chave e modelo a partir das variáveis de ambiente.

        A função é chamada antes de validações e antes do pedido ao modelo para
        permitir que mudanças em `.env` ou variáveis do sistema sejam aplicadas
        sem necessidade de recriar manualmente a instância do agente.

        Argumentos:
            Nenhum.

        Retorno:
            Nenhum.
        """

        dotenv_path = BASE_DIR / ".env"
        dotenv_data = dotenv_values(dotenv_path) if dotenv_path.exists() else {}
        env_api_key = os.getenv("OPENAI_API_KEY", "")
        env_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        # Dá prioridade ao .env do projeto para evitar conflito com variáveis
        # globais antigas da sessão/sistema.
        self._api_key = str(dotenv_data.get("OPENAI_API_KEY") or env_api_key).strip()
        self._model = str(dotenv_data.get("OPENAI_MODEL") or env_model).strip()

    def is_configured(self) -> bool:
        """Indica se existe chave API configurada para chamadas à OpenAI.

        Argumentos:
            Nenhum.

        Retorno:
            `True` se `OPENAI_API_KEY` estiver definida e não vazia; caso
            contrário `False`.
        """

        self._refresh_from_env()
        return bool(self._api_key)

    def generate_marketing_copy(
        self,
        brief: str,
        tone: Optional[str] = None,
        language: str = "pt-PT",
    ) -> Dict[str, Any]:
        """Gera copy sénior de marketing orientada a conversão a partir do brief.

        Envia o brief ao modelo com instruções para responder apenas com um
        objeto JSON com estrutura estratégica obrigatória: 3 variações de texto
        principal por ângulo, 5 headlines agressivas, 3 CTAs e sugestões de
        melhoria com foco em especificidade e testes A/B.

        Argumentos:
            brief: Descrição do produto, objetivo, público, restrições e formato
                desejado (ex.: anúncio Instagram, email, landing).
            tone: Tom de voz opcional (ex.: "profissional", "descontraído").
                Se omitido, o modelo infere um tom adequado ao brief.
            language: Código de idioma/região para a copy (por defeito `pt-PT`).

        Retorno:
            Dicionário normalizado com as chaves:
            - `main_text_variations` (lista com 3 objetos `{angle, text}`)
            - `headlines` (lista com 5 strings)
            - `ctas` (lista com 3 strings)
            - `improvement_suggestions` (objeto com pontos fracos,
              especificidade e ideias de A/B)
            Também mantém `primary_text` e `notes` por compatibilidade com
            versões anteriores da interface.

        Raises:
            RuntimeError: Se `OPENAI_API_KEY` não estiver configurada.
        """

        if not self.is_configured():
            raise RuntimeError(
                "OPENAI_API_KEY nao definida. Define a variavel de ambiente antes de gerar copy."
            )

        self._refresh_from_env()
        client = OpenAI(api_key=self._api_key)
        system_prompt = self._build_system_prompt(language=language, tone=tone)
        user_content = brief.strip()
        if tone:
            user_content = f"Tom desejado: {tone}\n\n{user_content}"

        response = client.chat.completions.create(
            model=self._model,
            temperature=0.7,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        return self._parse_copy_json(raw)

    def generate_chat_reply(
        self,
        messages: List[Dict[str, str]],
        tone: Optional[str] = None,
        language: str = "pt-PT",
    ) -> str:
        """Gera resposta conversacional autónoma para a chatroom do Copywriter.

        A função recebe o histórico da conversa (utilizador e assistente), envia
        esse contexto ao modelo e devolve a próxima resposta do agente. O foco é
        responder diretamente ao que foi perguntado, sem seguir um guião rígido,
        mantendo consistência com o objetivo de copywriting e com o contexto já
        partilhado no chat.

        Argumentos:
            messages: Lista cronológica de mensagens, onde cada item contém
                `role` (`user` ou `assistant`) e `content` textual.
            tone: Tom de voz opcional para orientar o estilo da resposta.
            language: Idioma/região da resposta conversacional (por defeito `pt-PT`).

        Retorno:
            String com a resposta textual do agente para a próxima mensagem da chatroom.

        Raises:
            RuntimeError: Se `OPENAI_API_KEY` não estiver configurada.
        """

        if not self.is_configured():
            raise RuntimeError(
                "OPENAI_API_KEY nao definida. Define a variavel de ambiente antes de conversar com o Copywriter."
            )

        self._refresh_from_env()
        client = OpenAI(api_key=self._api_key)
        system_prompt = self._build_chat_system_prompt(language=language, tone=tone)

        sanitized_messages: List[Dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "")).strip()
            content = str(message.get("content", "")).strip()
            if role not in {"user", "assistant"} or not content:
                continue
            sanitized_messages.append({"role": role, "content": content})

        response = client.chat.completions.create(
            model=self._model,
            temperature=0.4,
            messages=[{"role": "system", "content": system_prompt}, *sanitized_messages],
        )
        return (response.choices[0].message.content or "").strip()

    def _build_system_prompt(self, language: str, tone: Optional[str]) -> str:
        """Monta a mensagem de sistema para o modelo gerar JSON de copy.

        Argumentos:
            language: Idioma alvo (ex.: pt-PT).
            tone: Tom opcional já comunicado ao modelo no user message.

        Retorno:
            String com regras de formato e conteúdo para o assistente.
        """

        tone_hint = (
            "Se o utilizador indicar um tom de voz, respeita-o."
            if tone
            else "Escolhe um tom coerente com o brief."
        )
        return (
            "És um copywriter sénior de performance, especializado em conversão e estratégia avançada. "
            f"Escreve sempre em {language}. {tone_hint} "
            "Evita linguagem genérica, clichés e frases vagas. "
            "Prioriza clareza, especificidade e impacto. Frases curtas. "
            "Tom obrigatório: confiante, direto e orientado a resultados.\n\n"
            "Responde APENAS com JSON válido, sem markdown, com esta estrutura exata:\n"
            "{"
            "\"main_text_variations\":["
            "{\"angle\":\"Direto à dor\",\"text\":\"...\"},"
            "{\"angle\":\"Focado em benefício/resultados\",\"text\":\"...\"},"
            "{\"angle\":\"Padrão de interrupção (hook forte)\",\"text\":\"...\"}"
            "],"
            "\"headlines\":[\"...\",\"...\",\"...\",\"...\",\"...\"],"
            "\"ctas\":[\"...\",\"...\",\"...\"],"
            "\"improvement_suggestions\":{"
            "\"weaknesses_in_angle\":\"...\","
            "\"how_to_be_more_specific\":\"...\","
            "\"ab_test_ideas\":[\"...\",\"...\",\"...\"]"
            "},"
            "\"notes\":\"opcional\""
            "}\n\n"
            "Regras obrigatórias:\n"
            "1) Entregar exatamente 3 variações de texto principal, cada uma no ângulo pedido.\n"
            "2) Entregar exatamente 5 headlines curtas, agressivas e orientadas a dor/curiosidade.\n"
            "3) Entregar exatamente 3 CTAs claros e acionáveis.\n"
            "4) Em melhoria, explicar fraqueza do ângulo, como especificar melhor e 3 ideias de A/B.\n"
            "5) Sempre que possível, incluir consequências reais, números plausíveis e contexto concreto.\n"
            "6) Nunca usar expressões vagas como 'melhorar a presença digital'."
        )

    def _build_chat_system_prompt(self, language: str, tone: Optional[str]) -> str:
        """Constrói o prompt de sistema para respostas autónomas na chatroom.

        Este prompt orienta o agente para responder de forma contextual e útil,
        lendo o histórico completo da conversa. Em vez de perguntas fixas, o
        modelo decide autonomamente quando perguntar, quando sugerir e quando
        consolidar briefing, para que a interação pareça uma conversa real.

        Argumentos:
            language: Idioma/região esperado nas respostas da conversa.
            tone: Tom opcional indicado pelo utilizador para estilo de resposta.

        Retorno:
            String com regras comportamentais para o modo conversacional.
        """

        tone_hint = tone or "profissional e direto"
        return (
            "És o Agente Copywriter numa chatroom de briefing de marketing. "
            f"Responde sempre em {language}, com tom {tone_hint}. "
            "Lê cuidadosamente o histórico e responde diretamente ao que o utilizador perguntou. "
            "Se faltar contexto essencial para gerar copy de alta qualidade, faz 1 pergunta objetiva por vez. "
            "Se o utilizador já tiver dado contexto suficiente, resume o entendimento e avança com orientação prática. "
            "Não uses respostas genéricas nem repetitivas. "
            "Sê autónomo: adapta a resposta ao conteúdo real da conversa."
        )

    def _parse_copy_json(self, raw: str) -> Dict[str, Any]:
        """Faz parse seguro do JSON devolvido pelo modelo.

        Argumentos:
            raw: Corpo textual da resposta do modelo (esperado JSON).

        Retorno:
            Dicionário normalizado com listas/strings ou um objeto com `error`.
        """

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {"error": "resposta_nao_json", "raw_content": raw}

        headlines = self._normalize_string_list(data.get("headlines"), fallback_size=5)
        ctas = self._normalize_string_list(data.get("ctas"), fallback_size=3)
        main_text_variations = self._normalize_variations(data.get("main_text_variations"))
        improvement_suggestions = self._normalize_improvement_suggestions(data.get("improvement_suggestions"))

        primary_text = "\n\n".join(
            f"[{item['angle']}] {item['text']}" for item in main_text_variations if item["text"]
        ).strip()

        return {
            "main_text_variations": main_text_variations,
            "headlines": headlines,
            "ctas": ctas,
            "improvement_suggestions": improvement_suggestions,
            "primary_text": primary_text,
            "notes": str(data.get("notes", "")).strip() or None,
        }

    def _normalize_string_list(self, value: Any, fallback_size: int) -> list[str]:
        """Normaliza uma lista textual para tamanho previsível.

        Argumentos:
            value: Valor potencialmente devolvido pelo modelo (lista/string/None).
            fallback_size: Quantidade mínima-alvo para preservar consistência.

        Retorno:
            Lista de strings não vazias, preenchida/truncada para `fallback_size`
            quando necessário.
        """

        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
        elif value is None:
            items = []
        else:
            normalized = str(value).strip()
            items = [normalized] if normalized else []

        while len(items) < fallback_size:
            items.append("Sem conteúdo específico gerado.")
        return items[:fallback_size]

    def _normalize_variations(self, value: Any) -> list[Dict[str, str]]:
        """Normaliza as 3 variações principais de texto por ângulo.

        Argumentos:
            value: Conteúdo bruto de `main_text_variations` devolvido pelo modelo.

        Retorno:
            Lista de 3 objetos com chaves `angle` e `text`, respeitando os três
            ângulos obrigatórios da estratégia.
        """

        required_angles = [
            "Direto à dor",
            "Focado em benefício/resultados",
            "Padrão de interrupção (hook forte)",
        ]
        parsed: list[Dict[str, str]] = []
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    angle = str(item.get("angle", "")).strip()
                    text = str(item.get("text", "")).strip()
                    parsed.append({"angle": angle, "text": text})

        normalized: list[Dict[str, str]] = []
        for idx, angle in enumerate(required_angles):
            text = ""
            if idx < len(parsed) and parsed[idx].get("text"):
                text = parsed[idx]["text"]
            normalized.append(
                {
                    "angle": angle,
                    "text": text or "Sem conteúdo específico gerado para este ângulo.",
                }
            )
        return normalized

    def _normalize_improvement_suggestions(self, value: Any) -> Dict[str, Any]:
        """Normaliza a secção de melhorias e testes A/B.

        Argumentos:
            value: Objeto bruto devolvido pelo modelo para melhorias.

        Retorno:
            Dicionário com `weaknesses_in_angle`, `how_to_be_more_specific` e
            `ab_test_ideas` (lista de 3 ideias).
        """

        if not isinstance(value, dict):
            value = {}
        ab_test_ideas = self._normalize_string_list(value.get("ab_test_ideas"), fallback_size=3)
        return {
            "weaknesses_in_angle": str(value.get("weaknesses_in_angle", "")).strip()
            or "Sem diagnóstico explícito de fraquezas.",
            "how_to_be_more_specific": str(value.get("how_to_be_more_specific", "")).strip()
            or "Sem recomendações de especificidade.",
            "ab_test_ideas": ab_test_ideas,
        }


copywriter_agent = CopywriterAgent()
