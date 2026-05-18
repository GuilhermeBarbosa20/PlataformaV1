"""Agente Designer com chatroom e geração de imagem via Nano Banana."""

from __future__ import annotations

import base64
import io
import json
import os
import time
import tempfile
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, request
from uuid import uuid4
from openai import OpenAI
try:
    from PIL import Image, ImageOps
except Exception:  # noqa: BLE001
    Image = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_GENERATED_DIR = BASE_DIR / "static" / "generated"


class DesignerAgent:
    """Suporta conversa de briefing visual e geração de imagem no Nano Banana.

    O agente tem dois papéis:
    1) Conduzir uma conversa curta para recolher contexto de design.
    2) Transformar esse contexto num prompt e pedir uma imagem à API Nano Banana.

    Argumentos (atributos de instância):
        Nenhum obrigatório no construtor; URL e chaves vêm apenas de variáveis
        de ambiente.

    Retorno:
        Os métodos públicos devolvem texto de chat (string) ou dicionários
        serializáveis com dados da imagem gerada.
    """

    def __init__(self) -> None:
        """Inicializa configuração base da API Nano Banana.

        A função lê:
        - `NANO_BANANA_API_KEY` para autenticação;
        - `NANO_BANANA_API_URL` para o endpoint de geração;
        - outras variáveis opcionais (`GOOGLE_API_KEY`, `HF_API_TOKEN`, etc.).
        As credenciais vêm apenas do ambiente (ficheiro `.env` local, nunca do código).

        Argumentos:
            Nenhum.

        Retorno:
            Nenhum.
        """

        self._api_key = os.getenv("NANO_BANANA_API_KEY", "").strip()
        self._api_url = os.getenv("NANO_BANANA_API_URL", "").strip()
        self._google_api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        self._google_model = os.getenv(
            "GOOGLE_IMAGE_MODEL",
            "gemini-2.5-flash-image-preview",
        ).strip()
        self._hf_api_token = (
            os.getenv("HF_API_TOKEN", "").strip()
            or os.getenv("HUGGINGFACE_API_TOKEN", "").strip()
        )
        self._hf_model = os.getenv(
            "HF_IMAGE_MODEL",
            "black-forest-labs/FLUX.1-schnell",
        ).strip()
        self._openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self._openai_image_model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip()

    def _refresh_from_env(self) -> None:
        """Atualiza credenciais e endpoint a partir das variáveis de ambiente.

        Esta função permite alterar chave/URL em runtime sem reiniciar o
        servidor, útil para trocar ambientes (dev/staging/prod) rapidamente.

        Argumentos:
            Nenhum.

        Retorno:
            Nenhum.
        """

        self._api_key = os.getenv("NANO_BANANA_API_KEY", "").strip() or self._api_key
        self._api_url = os.getenv("NANO_BANANA_API_URL", self._api_url).strip()
        self._google_api_key = os.getenv("GOOGLE_API_KEY", "").strip() or self._google_api_key
        self._google_model = os.getenv("GOOGLE_IMAGE_MODEL", self._google_model).strip()
        self._hf_api_token = (
            os.getenv("HF_API_TOKEN", "").strip()
            or os.getenv("HUGGINGFACE_API_TOKEN", "").strip()
            or self._hf_api_token
        )
        self._hf_model = os.getenv("HF_IMAGE_MODEL", self._hf_model).strip()
        self._openai_api_key = os.getenv("OPENAI_API_KEY", "").strip() or self._openai_api_key
        self._openai_image_model = os.getenv("OPENAI_IMAGE_MODEL", self._openai_image_model).strip()

    def is_configured(self) -> bool:
        """Verifica se existem dados mínimos para chamar a API Nano Banana.

        Argumentos:
            Nenhum.

        Retorno:
            `True` quando existe chave API e URL válidas; caso contrário `False`.
        """

        self._refresh_from_env()
        return bool(self._api_key or self._hf_api_token or self._google_api_key or self._openai_api_key)

    def generate_chat_reply(
        self,
        messages: List[Dict[str, str]],
        language: str = "pt-PT",
        style: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
    ) -> str:
        """Gera resposta conversacional com OpenAI para a chatroom do Designer.

        A função envia o histórico da conversa para um modelo OpenAI e devolve
        a próxima resposta do agente. O modelo atua como designer criativo:
        orienta o briefing visual, faz perguntas objetivas quando falta contexto
        e confirma quando já existe informação suficiente para gerar imagem.

        Argumentos:
            messages: Histórico cronológico da conversa com `role` e `content`.
            language: Idioma/região da resposta do agente (ex.: `pt-PT`).
            style: Estilo visual opcional indicado pelo utilizador.
            reference_image_urls: Lista opcional de referências visuais anexadas.

        Retorno:
            String com a próxima resposta textual do Agente Designer.
        """

        sanitized_messages: List[Dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "")).strip()
            content = str(message.get("content", "")).strip()
            if role not in {"user", "assistant"} or not content:
                continue
            sanitized_messages.append({"role": role, "content": content})

        if not self._openai_api_key:
            return (
                "Posso ajudar-te a construir o conceito visual. "
                "Para respostas automáticas mais inteligentes neste chat, define a OPENAI_API_KEY no servidor."
            )

        style_hint = style or "livre, coerente com o objetivo do utilizador"
        references_count = len(reference_image_urls or [])
        system_prompt = (
            "És o Agente Designer numa chatroom de criação visual. "
            f"Responde sempre em {language}, com tom profissional e direto. "
            "Objetivo: ajudar o utilizador a definir um briefing visual claro para gerar imagem. "
            "Quando faltar contexto essencial, faz apenas 1 pergunta curta por vez. "
            "Quando o contexto já estiver suficiente, confirma isso e orienta para clicar em «Gerar imagem». "
            "Evita respostas longas e genéricas. "
            f"Estilo visual preferido atual: {style_hint}. "
            f"Número de imagens de referência já anexadas: {references_count}."
        )

        try:
            client = OpenAI(api_key=self._openai_api_key)
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                temperature=0.4,
                messages=[{"role": "system", "content": system_prompt}, *sanitized_messages],
            )
            reply = (response.choices[0].message.content or "").strip()
        except Exception:  # noqa: BLE001
            return (
                "Percebi o pedido. Se quiseres, posso avançar já para a geração, "
                "ou podes dar mais detalhes de cenário, enquadramento e estilo."
            )

        return reply or (
            "Percebi. Podes indicar mais um detalhe visual (cenário, iluminação ou enquadramento) "
            "ou clicar em «Gerar imagem»."
        )

    def generate_image_from_chat(
        self,
        messages: List[Dict[str, str]],
        size: str = "1024x1024",
        style: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Gera uma imagem na API Nano Banana a partir do histórico da chatroom.

        A função constrói um prompt final com base na conversa, envia o pedido
        ao endpoint Nano Banana e normaliza a resposta para um formato único.
        Se a API devolver base64, a imagem é gravada localmente em `static/generated`.

        Argumentos:
            messages: Histórico cronológico com mensagens de utilizador/assistente.
            size: Dimensão pedida à API (ex.: `1024x1024`).
            style: Estilo visual opcional para reforçar o prompt final.
            reference_image_urls: Lista opcional de URLs de imagens de referência
                enviadas pelo utilizador para orientar a geração.

        Retorno:
            Dicionário com:
            - `image_url`: URL pública da imagem ou rota local servida pelo backend;
            - `prompt_used`: Prompt final enviado à API;
            - `provider`: Identificador do motor usado (`nano-banana`).

        Raises:
            RuntimeError: Quando a API não está configurada ou devolve erro.
        """

        if not self.is_configured():
            raise RuntimeError("NANO_BANANA_API_KEY ou NANO_BANANA_API_URL não configuradas.")

        chat_context = self._extract_chat_context(messages)
        latest_user_request = chat_context["latest_user_request"]

        normalized_references = self._normalize_reference_images(reference_image_urls or [])
        use_reference_for_generation = self._should_use_reference_for_generation(
            latest_user_request=latest_user_request,
            normalized_references=normalized_references,
        )
        if not use_reference_for_generation:
            normalized_references = {"public_urls": [], "data_urls": [], "total_count": 0}

        has_references = normalized_references["total_count"] > 0

        prompt = self._build_image_prompt(
            messages=messages,
            style=style,
            reference_image_urls=reference_image_urls,
        )
        errors: List[str] = []
        tried_providers: set[str] = set()

        # Quando há referência de identidade (rosto), evitamos começar por
        # motores text-to-image para não perder semelhança facial.
        if has_references and normalized_references["public_urls"] or normalized_references["data_urls"]:
            try:
                prioritized_provider = "https://nanobananapro.cloud/api/v1/image/nano-banana"
                data = self._call_nanobananapro(
                    prioritized_provider,
                    prompt=prompt,
                    reference_image_urls=normalized_references["public_urls"],
                    reference_image_data_urls=normalized_references["data_urls"],
                )
                tried_providers.add(prioritized_provider)
                image_url = self._extract_image_url(data)
                if image_url:
                    return {
                        "image_url": image_url,
                        "prompt_used": prompt,
                        "provider": "https://nanobananapro.cloud/api/v1/image/nano-banana",
                    }
                b64_image = self._extract_base64_image(data)
                if b64_image:
                    return {
                        "image_url": self._save_base64_image(b64_image),
                        "prompt_used": prompt,
                        "provider": "https://nanobananapro.cloud/api/v1/image/nano-banana",
                    }
                errors.append("nanobananapro: sem imagem no resultado para image-to-image.")
            except RuntimeError as exc:
                errors.append(
                    f"nanobananapro(image-to-image): {self._format_provider_error_message(str(exc))}"
                )

        if self._openai_api_key and normalized_references["data_urls"]:
            try:
                openai_result = self._generate_with_openai_edit(
                    prompt=prompt,
                    size=size,
                    reference_image_data_urls=normalized_references["data_urls"],
                )
                return {
                    "image_url": openai_result,
                    "prompt_used": prompt,
                    "provider": f"openai-{self._openai_image_model}",
                }
            except RuntimeError as exc:
                errors.append(
                    f"openai-{self._openai_image_model}: {self._format_provider_error_message(str(exc))}"
                )

        # Se não estivermos a usar referência (ou não houver referência válida),
        # tentamos text-to-image na OpenAI para manter máxima aderência ao pedido.
        if self._openai_api_key and not has_references:
            try:
                openai_text_result = self._generate_with_openai_text(
                    prompt=prompt,
                    size=size,
                )
                return {
                    "image_url": openai_text_result,
                    "prompt_used": prompt,
                    "provider": f"openai-{self._openai_image_model}-text",
                }
            except RuntimeError as exc:
                errors.append(
                    f"openai-{self._openai_image_model}-text: {self._format_provider_error_message(str(exc))}"
                )

        if self._hf_api_token and not has_references:
            try:
                hf_result = self._generate_with_huggingface(prompt=prompt, size=size)
                return {
                    "image_url": hf_result,
                    "prompt_used": prompt,
                    "provider": f"huggingface-{self._hf_model}",
                }
            except RuntimeError as exc:
                errors.append(
                    f"huggingface-{self._hf_model}: {self._format_provider_error_message(str(exc))}"
                )
        elif self._hf_api_token and has_references:
            errors.append(
                "huggingface ignorado: fluxo atual usa text-to-image e não preserva identidade facial com referência."
            )

        if self._google_api_key:
            try:
                google_result = self._generate_with_google(
                    prompt=prompt,
                    reference_image_data_urls=normalized_references["data_urls"],
                    reference_image_urls=normalized_references["public_urls"],
                )
                return {
                    "image_url": google_result,
                    "prompt_used": prompt,
                    "provider": f"google-{self._google_model}",
                }
            except RuntimeError as exc:
                errors.append(
                    f"google-{self._google_model}: {self._format_provider_error_message(str(exc))}"
                )

        providers_to_try = self._resolve_provider_urls()
        for provider in providers_to_try:
            if provider in tried_providers:
                continue
            try:
                data = self._call_provider(
                    provider=provider,
                    prompt=prompt,
                    size=size,
                    reference_image_urls=normalized_references["public_urls"],
                    reference_image_data_urls=normalized_references["data_urls"],
                )
                image_url = self._extract_image_url(data)
                if image_url:
                    return {
                        "image_url": image_url,
                        "prompt_used": prompt,
                        "provider": provider,
                    }

                b64_image = self._extract_base64_image(data)
                if b64_image:
                    local_url = self._save_base64_image(b64_image)
                    return {
                        "image_url": local_url,
                        "prompt_used": prompt,
                        "provider": provider,
                    }
                errors.append(f"{provider}: resposta sem URL/base64.")
            except RuntimeError as exc:
                errors.append(f"{provider}: {self._format_provider_error_message(str(exc))}")
            finally:
                tried_providers.add(provider)

        raise RuntimeError(
            "Falha ao gerar imagem em todos os providers configurados. " + " | ".join(errors)
        )

    def generate_image_for_linkedin_post(
        self,
        post: Dict[str, Any],
        *,
        size: str = "1024x1024",
        edit_instructions: Optional[str] = None,
    ) -> Dict[str, str]:
        """Gera imagem ilustrativa alinhada ao texto de um post LinkedIn.

        A função constrói um briefing visual a partir do título, gancho e corpo
        do post e delega a geração ao fluxo standard do agente Designer
        (``generate_image_from_chat``), adequado a feeds B2B.

        Argumentos:
            post: Dicionário com campos do post (``body``, ``title``, ``hook``,
                ``content_type``, ``cta`` opcional).
            size: Dimensão pedida ao motor de imagem (por defeito ``1024x1024``).
            edit_instructions: Instruções opcionais ao refazer (ex.: tom, cores).

        Retorno:
            Dicionário com:
            - ``image_url``: URL pública ou rota local da imagem gerada;
            - ``prompt_used``: Prompt final enviado ao provider;
            - ``provider``: Identificador do motor utilizado.

        Raises:
            RuntimeError: Quando nenhum provider de imagem está configurado ou
                todos falham na geração.
        """

        body = str(post.get("body") or "").strip()
        title = str(post.get("title") or "").strip() or "Post LinkedIn"
        hook = str(post.get("hook") or "").strip()
        cta = str(post.get("cta") or "").strip()
        content_type = str(post.get("content_type") or "texto").strip().lower()
        body_excerpt = body[:2400]
        instr = str(edit_instructions or "").strip()

        brief_parts = [
            "Cria uma imagem profissional para acompanhar um post no LinkedIn (feed B2B).",
            f"Tipo de conteúdo: {content_type}.",
            f"Título: {title}.",
        ]
        if hook:
            brief_parts.append(f"Gancho de abertura: {hook}.")
        if cta:
            brief_parts.append(f"CTA do post: {cta}.")
        brief_parts.extend(
            [
                "",
                "Texto completo do post:",
                body_excerpt,
                "",
                "Requisitos da imagem:",
                "- Estilo corporativo e moderno, adequado ao LinkedIn",
                "- Ilustra visualmente o tema central (sem copiar o texto literalmente)",
                "- Sem blocos de texto longos nem letras ilegíveis sobrepostas",
                "- Composição limpa, boa iluminação, cores profissionais",
                "- Formato adequado a feed (quadrado ou vertical suave)",
            ]
        )
        if instr:
            brief_parts.extend(
                [
                    "",
                    "Instruções do utilizador para esta versão da imagem (prioridade):",
                    instr,
                ]
            )
        messages = [{"role": "user", "content": "\n".join(brief_parts)}]
        return self.generate_image_from_chat(
            messages=messages,
            size=size,
            style="LinkedIn B2B profissional",
        )

    def _format_provider_error_message(self, raw_error: str) -> str:
        """Normaliza erros de providers para mensagens curtas e acionáveis.

        A função analisa mensagens de erro HTTP/API devolvidas pelos providers
        de imagem e mapeia padrões conhecidos para texto claro com ação
        recomendada. Mantém a mensagem original quando não reconhece o padrão.

        Argumentos:
            raw_error: Mensagem de erro original capturada no fluxo de geração.

        Retorno:
            String normalizada e amigável para logs e resposta ao utilizador.
        """

        normalized = str(raw_error or "").strip()
        lowered = normalized.lower()
        if "error code: 1010" in lowered:
            return (
                "acesso bloqueado pelo provider (Cloudflare 1010). "
                "Valida whitelist/IP/chave e tenta outro endpoint."
            )
        if "billing_hard_limit_reached" in lowered or "billing hard limit has been reached" in lowered:
            return (
                "conta OpenAI sem saldo disponível (billing hard limit reached). "
                "Atualiza faturação/crédito e volta a tentar."
            )
        if "invalid image file or mode" in lowered or "invalid_image_file" in lowered:
            return (
                "imagem de referência inválida/incompatível para edição OpenAI. "
                "Converte a imagem para PNG/JPG (RGB), evita ficheiros corrompidos e tenta novamente."
            )
        return normalized

    def _should_use_reference_for_generation(
        self,
        latest_user_request: str,
        normalized_references: Dict[str, object],
    ) -> bool:
        """Decide se a geração deve usar imagens de referência anexadas.

        A função define se as referências anexadas devem ser usadas na geração.
        Para o fluxo atual do produto, se o utilizador anexou imagens, assume-se
        por defeito que quer usá-las. Só desativa quando o último pedido contém
        instruções explícitas para ignorar a referência.

        Argumentos:
            latest_user_request: Último pedido textual do utilizador na chatroom.
            normalized_references: Dicionário produzido por
                `_normalize_reference_images`, contendo referências válidas.

        Retorno:
            `True` quando deve usar referência visual na geração; `False` apenas
            quando não há anexos válidos ou quando o utilizador pede
            explicitamente para ignorar as referências.
        """

        total_count = int(normalized_references.get("total_count") or 0)
        if total_count <= 0:
            return False

        request = str(latest_user_request or "").lower()
        disable_reference_markers = (
            "ignora a imagem",
            "ignorar a imagem",
            "sem usar a imagem",
            "não uses a imagem",
            "nao uses a imagem",
            "não usar referência",
            "nao usar referencia",
            "sem referência",
            "sem referencia",
        )
        if any(marker in request for marker in disable_reference_markers):
            return False
        return True

    def _generate_with_openai_edit(
        self,
        prompt: str,
        size: str,
        reference_image_data_urls: List[str],
    ) -> str:
        """Gera imagem por edição com referência usando OpenAI `gpt-image-1`.

        A função usa a primeira imagem de referência disponível, enviando-a como
        ficheiro para o endpoint de edição de imagens da OpenAI. O objetivo é
        manter identidade (rosto/traços) e alterar apenas cenário/ação conforme
        o prompt final construído na chatroom.

        Argumentos:
            prompt: Prompt final da geração com instruções de estilo e contexto.
            size: Dimensão final (`1024x1024`, `1024x1536`, `1536x1024`).
            reference_image_data_urls: Lista de referências em data URL.

        Retorno:
            URL local da imagem resultante guardada em `/static/generated/...`.

        Raises:
            RuntimeError: Quando a referência é inválida ou a OpenAI falha.
        """

        if not reference_image_data_urls:
            raise RuntimeError("Sem imagem de referência válida para edição OpenAI.")

        image_bytes, image_ext = self._data_url_to_binary(reference_image_data_urls[0])
        if not image_bytes:
            raise RuntimeError("Não foi possível converter a referência para binário.")
        image_bytes, image_ext = self._normalize_openai_edit_image(image_bytes, image_ext)

        openai_size = self._size_to_openai_size(size)
        identity_prompt = (
            f"{prompt} Mantém obrigatoriamente a mesma pessoa da imagem de referência, "
            "preservando identidade facial, cabelo e proporções do rosto."
        )

        client = OpenAI(api_key=self._openai_api_key)
        temp_suffix = image_ext if image_ext in {".png", ".jpg", ".jpeg", ".webp"} else ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=temp_suffix) as temp_file:
            temp_file.write(image_bytes)
            temp_path = Path(temp_file.name)

        try:
            with temp_path.open("rb") as image_file:
                response = client.images.edit(
                    model=self._openai_image_model,
                    image=image_file,
                    prompt=identity_prompt,
                    size=openai_size,
                )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Falha na OpenAI image-edit: {exc!s}") from exc
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass

        # Tenta URL primeiro; se não existir, tenta base64.
        image_url = ""
        try:
            image_url = str(response.data[0].url or "").strip()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            image_url = ""
        if image_url:
            return image_url

        b64_image = ""
        try:
            b64_image = str(response.data[0].b64_json or "").strip()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            b64_image = ""
        if b64_image:
            return self._save_base64_image(b64_image)

        raise RuntimeError("OpenAI não devolveu URL nem `b64_json` na edição.")

    def _normalize_openai_edit_image(self, image_bytes: bytes, image_ext: str) -> tuple[bytes, str]:
        """Normaliza imagem para formato compatível com `images.edit` da OpenAI.

        A função tenta garantir que a imagem enviada para edição na OpenAI está
        num formato estável e suportado. Quando Pillow está disponível, abre o
        binário, corrige orientação EXIF e converte para PNG em modo RGB para
        evitar erros de validação como `invalid_image_file` ou `invalid mode`.
        Sem Pillow, mantém o binário original.

        Argumentos:
            image_bytes: Conteúdo binário original da referência.
            image_ext: Extensão inferida a partir da data URL (`.png`, `.jpg`...).

        Retorno:
            Tuplo `(normalized_bytes, normalized_ext)` pronto para upload no
            endpoint `images.edit` da OpenAI.
        """

        normalized_ext = image_ext if image_ext in {".png", ".jpg", ".jpeg", ".webp"} else ".png"
        if not image_bytes:
            return image_bytes, normalized_ext

        if Image is None or ImageOps is None:
            return image_bytes, normalized_ext

        try:
            with Image.open(io.BytesIO(image_bytes)) as source_image:
                safe_image = ImageOps.exif_transpose(source_image)
                if safe_image.mode not in {"RGB", "RGBA"}:
                    safe_image = safe_image.convert("RGB")
                elif safe_image.mode == "RGBA":
                    # A API de edit da OpenAI é mais estável com RGB sem alpha.
                    safe_image = safe_image.convert("RGB")

                buffer = io.BytesIO()
                safe_image.save(buffer, format="PNG", optimize=True)
                normalized_bytes = buffer.getvalue()
            if normalized_bytes:
                return normalized_bytes, ".png"
        except Exception:  # noqa: BLE001
            return image_bytes, normalized_ext

        return image_bytes, normalized_ext

    def _generate_with_openai_text(self, prompt: str, size: str) -> str:
        """Gera imagem por texto com OpenAI quando não há referência obrigatória.

        Esta função usa o endpoint de geração textual da OpenAI (`images.generate`)
        para produzir uma imagem que siga diretamente o conteúdo do chatroom,
        sem tentar preservar identidade de uma referência visual.

        Argumentos:
            prompt: Prompt final consolidado a partir da conversa.
            size: Dimensão solicitada no frontend (será mapeada para formato
                suportado pela OpenAI).

        Retorno:
            URL da imagem (quando devolvida pela API) ou URL local após guardar
            base64 em `/static/generated/...`.

        Raises:
            RuntimeError: Se a OpenAI não conseguir gerar ou não devolver imagem.
        """

        openai_size = self._size_to_openai_size(size)
        client = OpenAI(api_key=self._openai_api_key)
        try:
            response = client.images.generate(
                model=self._openai_image_model,
                prompt=prompt,
                size=openai_size,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Falha na OpenAI text-to-image: {exc!s}") from exc

        image_url = ""
        try:
            image_url = str(response.data[0].url or "").strip()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            image_url = ""
        if image_url:
            return image_url

        b64_image = ""
        try:
            b64_image = str(response.data[0].b64_json or "").strip()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            b64_image = ""
        if b64_image:
            return self._save_base64_image(b64_image)

        raise RuntimeError("OpenAI não devolveu URL nem `b64_json` na geração textual.")

    def _generate_with_huggingface(self, prompt: str, size: str) -> str:
        """Gera imagem via Hugging Face Inference API e devolve URL local.

        A função chama o endpoint `api-inference.huggingface.co/models/<model>`
        com um prompt textual. Quando a API devolve bytes de imagem, guarda o
        ficheiro em `static/generated` e devolve a rota pública local.

        Argumentos:
            prompt: Prompt final preparado a partir da conversa.
            size: Tamanho pedido no frontend, usado para inferir largura/altura.

        Retorno:
            URL relativa da imagem guardada localmente.

        Raises:
            RuntimeError: Se a API devolver erro, JSON sem imagem ou resposta inválida.
        """

        width, height = self._size_to_dimensions(size)
        requested_model = self._hf_model
        fallback_models = [
            requested_model,
            "black-forest-labs/FLUX.1-schnell",
            "stabilityai/stable-diffusion-3.5-large",
            "stabilityai/stable-diffusion-xl-base-1.0",
        ]
        models_to_try: List[str] = []
        for model in fallback_models:
            normalized = model.strip()
            if normalized and normalized not in models_to_try:
                models_to_try.append(normalized)

        errors: List[str] = []
        for model in models_to_try:
            candidate_urls = [
                f"https://router.huggingface.co/hf-inference/models/{model}",
                f"https://api-inference.huggingface.co/models/{model}",
                f"https://api-inference.huggingface.co/pipeline/text-to-image/{model}",
            ]
            for url in candidate_urls:
                try:
                    return self._call_hf_image_endpoint(
                        url=url,
                        prompt=prompt,
                        width=width,
                        height=height,
                    )
                except RuntimeError as exc:
                    errors.append(f"{model} @ {url}: {exc}")

        raise RuntimeError(" ; ".join(errors[:6]))

    def _call_hf_image_endpoint(self, url: str, prompt: str, width: int, height: int) -> str:
        """Chama um endpoint Hugging Face de geração e devolve URL local.

        A função tenta obter imagem binária diretamente. Se vier JSON de loading,
        faz pequena espera e repete uma vez. Se vier JSON de erro, devolve detalhe.

        Argumentos:
            url: Endpoint completo do provider Hugging Face.
            prompt: Prompt textual para geração da imagem.
            width: Largura alvo.
            height: Altura alvo.

        Retorno:
            URL local da imagem guardada em `/static/generated`.

        Raises:
            RuntimeError: Quando o endpoint não gera imagem válida.
        """

        headers = {
            "Authorization": f"Bearer {self._hf_api_token}",
            "Content-Type": "application/json",
            "Accept": "image/png",
        }
        payload = {
            "inputs": prompt,
            "parameters": {"width": width, "height": height},
            "options": {"wait_for_model": True, "use_cache": False},
        }

        for attempt in range(2):
            http_request = request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with request.urlopen(http_request, timeout=120) as response:
                    content_type = str(response.headers.get("Content-Type", "")).lower()
                    body_bytes = response.read()
            except error.HTTPError as exc:
                error_body = ""
                try:
                    error_body = exc.read().decode("utf-8", errors="replace")
                except Exception:  # noqa: BLE001
                    error_body = ""
                raise RuntimeError(
                    f"HTTP {exc.code} {exc.reason}. Body: {error_body[:350] or 'sem detalhe'}"
                ) from exc
            except error.URLError as exc:
                reason = getattr(exc, "reason", None)
                raise RuntimeError(f"erro de rede/URL ({reason or exc!s})") from exc
            except (TimeoutError, OSError) as exc:
                raise RuntimeError(f"timeout/erro de sistema ({exc!s})") from exc

            if "application/json" in content_type:
                try:
                    body_json = json.loads(body_bytes.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    raise RuntimeError("JSON inválido na resposta do Hugging Face.")
                if isinstance(body_json, dict):
                    # Alguns modelos devolvem loading com estimated_time antes de estarem prontos.
                    estimated_time = body_json.get("estimated_time")
                    if attempt == 0 and estimated_time is not None:
                        try:
                            wait_seconds = min(max(int(float(estimated_time)), 2), 15)
                        except (TypeError, ValueError):
                            wait_seconds = 4
                        time.sleep(wait_seconds)
                        continue
                    error_message = str(body_json.get("error", "")).strip() or str(body_json)
                    raise RuntimeError(f"resposta JSON sem imagem: {error_message[:350]}")
                raise RuntimeError("resposta JSON inesperada (não objeto).")

            if not body_bytes:
                raise RuntimeError("resposta vazia.")
            return self._save_binary_image(body_bytes)

        raise RuntimeError("modelo em loading sem resposta útil após retry.")

    def _size_to_dimensions(self, size: str) -> tuple[int, int]:
        """Converte o formato textual de tamanho em dimensões numéricas.

        Argumentos:
            size: String no formato `LxA` (ex.: `1024x1024`).

        Retorno:
            Tuplo `(width, height)` com dimensões válidas para a API.
            Quando o formato não é reconhecido, usa `1024x1024` como fallback.
        """

        normalized = str(size or "").strip().lower()
        if "x" not in normalized:
            return (1024, 1024)
        left, right = normalized.split("x", 1)
        try:
            width = int(left)
            height = int(right)
        except ValueError:
            return (1024, 1024)

        if width < 256 or height < 256:
            return (1024, 1024)
        # Limite máximo pedido pelo utilizador para a interface atual.
        width = min(width, 1920)
        height = min(height, 1920)
        return (width, height)

    def _size_to_openai_size(self, size: str) -> str:
        """Mapeia tamanhos livres para os formatos suportados pela OpenAI.

        A API de edição de imagem da OpenAI não aceita qualquer resolução
        arbitrária. Esta função converte o tamanho pedido no frontend para o
        formato mais próximo permitido (`1024x1024`, `1024x1536`, `1536x1024`)
        preservando o máximo possível a orientação.

        Argumentos:
            size: String de tamanho pedida na interface (ex.: `1920x1080`).

        Retorno:
            String num dos tamanhos suportados pela OpenAI para `images.edit`.
        """

        width, height = self._size_to_dimensions(size)
        if width == height:
            return "1024x1024"
        if width > height:
            return "1536x1024"
        return "1024x1536"

    def _generate_with_google(
        self,
        prompt: str,
        reference_image_data_urls: Optional[List[str]] = None,
        reference_image_urls: Optional[List[str]] = None,
    ) -> str:
        """Gera imagem via Google Gemini e devolve URL local da imagem.

        A função chama o endpoint `generateContent` da API Google Generative
        Language com um modelo de geração de imagem. Quando a resposta inclui
        `inlineData` com bytes da imagem, grava o ficheiro localmente e devolve
        a rota pública servida pelo backend.

        Argumentos:
            prompt: Prompt final preparado a partir do chat do utilizador.
            reference_image_data_urls: Lista opcional de referências em data URL.
            reference_image_urls: Lista opcional de URLs públicas de referência.

        Retorno:
            URL relativa da imagem gerada em `/static/generated/...`.

        Raises:
            RuntimeError: Se a API Google falhar ou não devolver imagem.
        """

        models_to_try = [
            self._google_model,
            "gemini-2.5-flash-image-preview",
            "gemini-2.0-flash-preview-image-generation",
        ]
        normalized_models: List[str] = []
        for model in models_to_try:
            value = str(model or "").strip()
            if value and value not in normalized_models:
                normalized_models.append(value)

        inline_parts: List[dict] = []
        for data_url in reference_image_data_urls or []:
            part = self._data_url_to_google_part(data_url)
            if part:
                inline_parts.append(part)

        # Se vierem URLs públicas sem data URL, adicionamos no prompt para guiar
        # o modelo. Em algumas contas o fetch direto de URL pode não estar ativo.
        extra_reference_text = ""
        if reference_image_urls:
            joined = "; ".join(reference_image_urls[:4])
            extra_reference_text = (
                " Usa também estas referências visuais e mantém identidade facial: "
                f"{joined}."
            )

        full_prompt = (
            f"{prompt}{extra_reference_text} "
            "É obrigatório manter a mesma identidade da pessoa da referência "
            "(mesmo rosto, traços faciais, proporções e cabelo), "
            "mudando apenas cenário/ação conforme pedido."
        ).strip()

        errors: List[str] = []
        for model in normalized_models:
            endpoint = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={self._google_api_key}"
            )
            payload = {
                "contents": [{"parts": [{"text": full_prompt}, *inline_parts]}],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
            }
            try:
                data = self._post_json_without_auth(url=endpoint, payload=payload)
                b64_image = self._extract_google_inline_image(data)
                if b64_image:
                    return self._save_base64_image(b64_image)
                errors.append(f"{model}: resposta sem inlineData de imagem.")
            except RuntimeError as exc:
                errors.append(f"{model}: {exc}")

        raise RuntimeError(" | ".join(errors))

    def _data_url_to_google_part(self, data_url: str) -> Optional[dict]:
        """Converte data URL de imagem para `inlineData` da API Google.

        Argumentos:
            data_url: String no formato `data:<mime>;base64,<bytes>`.

        Retorno:
            Dicionário com `inlineData` para incluir em `contents.parts`, ou
            `None` se o formato não for válido.
        """

        value = str(data_url or "").strip()
        if not value.startswith("data:") or ";base64," not in value:
            return None
        meta, payload = value.split(";base64,", 1)
        mime_type = meta.replace("data:", "", 1).strip() or "image/png"
        if not payload.strip():
            return None
        return {"inlineData": {"mimeType": mime_type, "data": payload.strip()}}

    def _data_url_to_binary(self, data_url: str) -> tuple[bytes, str]:
        """Converte uma data URL para bytes de imagem e extensão recomendada.

        Argumentos:
            data_url: String no formato `data:<mime>;base64,<bytes>`.

        Retorno:
            Tuplo `(image_bytes, extension)` onde:
            - `image_bytes` contém o binário da imagem (ou bytes vazios);
            - `extension` sugere extensão (`.png`, `.jpg`, `.webp`...).
        """

        value = str(data_url or "").strip()
        if not value.startswith("data:") or ";base64," not in value:
            return b"", ".png"

        meta, payload = value.split(";base64,", 1)
        mime_type = meta.replace("data:", "", 1).strip().lower()
        extension = ".png"
        if "jpeg" in mime_type or "jpg" in mime_type:
            extension = ".jpg"
        elif "webp" in mime_type:
            extension = ".webp"
        elif "gif" in mime_type:
            extension = ".gif"

        try:
            binary = base64.b64decode(payload.strip(), validate=False)
        except Exception:  # noqa: BLE001
            return b"", extension
        return binary, extension

    def _extract_google_inline_image(self, data: dict) -> Optional[str]:
        """Extrai imagem em base64 da estrutura `candidates` da API Google.

        A resposta do Gemini para geração de imagem pode incluir `inlineData`
        em partes de conteúdo. Esta função percorre os candidatos e devolve os
        bytes base64 da primeira imagem encontrada.

        Argumentos:
            data: JSON completo devolvido pelo endpoint `generateContent`.

        Retorno:
            Base64 da imagem encontrada ou `None` quando não existe.
        """

        candidates = data.get("candidates")
        if not isinstance(candidates, list):
            return None
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                inline_data = part.get("inlineData") or part.get("inline_data")
                if not isinstance(inline_data, dict):
                    continue
                data_b64 = str(inline_data.get("data", "")).strip()
                if data_b64:
                    return data_b64
        return None

    def _resolve_provider_urls(self) -> List[str]:
        """Resolve a lista de endpoints/provedores a testar para geração.

        A função prioriza `NANO_BANANA_API_URL` quando definida e, em seguida,
        usa uma sequência de fallbacks conhecidos para evitar falhas de DNS num
        único host.

        Argumentos:
            Nenhum.

        Retorno:
            Lista ordenada de identificadores de provider/URL.
        """

        candidates: List[str] = []
        if self._api_url:
            candidates.append(self._api_url)
        candidates.extend(
            [
                "https://api.nanobananaapi.ai/api/v1/nanobanana/generate",
                "https://nanophoto.ai/api/nano-banana-2/generate",
                "https://nanobananapro.cloud/api/v1/image/nano-banana",
            ]
        )
        # Remove duplicados preservando ordem.
        seen = set()
        unique: List[str] = []
        for item in candidates:
            normalized = item.strip()
            if normalized and normalized not in seen:
                unique.append(normalized)
                seen.add(normalized)
        return unique

    def _call_provider(
        self,
        provider: str,
        prompt: str,
        size: str,
        reference_image_urls: Optional[List[str]] = None,
        reference_image_data_urls: Optional[List[str]] = None,
    ) -> dict:
        """Executa a chamada ao provider escolhido e devolve JSON normalizado.

        A função identifica o tipo de API pelo domínio/URL e envia o payload
        adequado. Quando a API é assíncrona, faz polling até obter resultado.

        Argumentos:
            provider: URL de geração do provider alvo.
            prompt: Prompt final da imagem.
            size: Tamanho pedido no frontend (ex.: `1024x1024`).
            reference_image_urls: Lista opcional de URLs de imagens de referência.
            reference_image_data_urls: Lista opcional de imagens em data URL.

        Retorno:
            Dicionário JSON devolvido pelo provider com dados da geração.
        """

        if "nanobananaapi.ai" in provider:
            return self._call_nanobananaapi(provider, prompt=prompt)
        if "nanophoto.ai" in provider:
            return self._call_nanophoto(
                provider,
                prompt=prompt,
                size=size,
                reference_image_urls=reference_image_urls,
            )
        if "nanobananapro.cloud" in provider:
            return self._call_nanobananapro(
                provider,
                prompt=prompt,
                reference_image_urls=reference_image_urls,
                reference_image_data_urls=reference_image_data_urls,
            )
        return self._call_generic_generation_api(provider, prompt=prompt, size=size)

    def _call_generic_generation_api(self, provider: str, prompt: str, size: str) -> dict:
        """Chama endpoint genérico de geração em JSON (prompt + size).

        Argumentos:
            provider: URL do endpoint HTTP POST.
            prompt: Prompt da imagem.
            size: Tamanho solicitado.

        Retorno:
            JSON devolvido pelo endpoint, já convertido para `dict`.
        """

        payload = {"prompt": prompt, "size": size}
        return self._post_json(url=provider, payload=payload)

    def _call_nanobananaapi(self, provider: str, prompt: str) -> dict:
        """Chama API `nanobananaapi.ai` com fluxo assíncrono por `taskId`.

        Argumentos:
            provider: Endpoint `/generate` da API.
            prompt: Prompt da imagem.

        Retorno:
            JSON final da tarefa, após polling em `record-info`.
        """

        payload = {"prompt": prompt, "type": "TEXTTOIAMGE", "numImages": 1}
        data = self._post_json(url=provider, payload=payload)
        task_id = str((data.get("data") or {}).get("taskId") or data.get("taskId") or "").strip()
        if not task_id:
            return data

        status_url = provider.replace("/generate", "/record-info")
        for _ in range(15):
            status_data = self._get_json(url=f"{status_url}?taskId={task_id}")
            image_url = self._extract_image_url(status_data)
            if image_url:
                return status_data
            status_flag = str((status_data.get("data") or {}).get("statusFlag", "")).upper()
            if status_flag in {"FAILED", "FAIL", "ERROR"}:
                return status_data
            time.sleep(2)
        return data

    def _call_nanophoto(
        self,
        provider: str,
        prompt: str,
        size: str,
        reference_image_urls: Optional[List[str]] = None,
    ) -> dict:
        """Chama API `nanophoto.ai` e faz polling por `generationId`.

        Argumentos:
            provider: Endpoint `/generate` do NanoPhoto.
            prompt: Prompt da imagem.
            size: Tamanho solicitado para inferir `aspectRatio`.
            reference_image_urls: Lista opcional de referências para modo `edit`.

        Retorno:
            JSON final com resultado disponível, quando existir.
        """

        aspect_ratio = "1:1"
        if size == "1024x1536":
            aspect_ratio = "2:3"
        elif size == "1536x1024":
            aspect_ratio = "3:2"

        references = [item for item in (reference_image_urls or []) if str(item).strip()]
        payload = {
            "prompt": prompt,
            "mode": "edit" if references else "generate",
            "aspectRatio": aspect_ratio,
            "imageQuality": "1K",
        }
        if references:
            payload["inputImageUrls"] = references[:8]
        data = self._post_json(url=provider, payload=payload)
        generation_id = str(data.get("generationId", "")).strip()
        if not generation_id:
            return data

        status_url = provider.replace("/generate", "/check-status")
        for _ in range(15):
            status_data = self._post_json(url=status_url, payload={"generationId": generation_id})
            image_url = self._extract_image_url(status_data)
            if image_url:
                return status_data
            status_name = str(status_data.get("status", "")).lower()
            if status_name in {"failed", "error"}:
                return status_data
            time.sleep(2)
        return data

    def _call_nanobananapro(
        self,
        provider: str,
        prompt: str,
        reference_image_urls: Optional[List[str]] = None,
        reference_image_data_urls: Optional[List[str]] = None,
    ) -> dict:
        """Chama API `nanobananapro.cloud` com payload JSON básico.

        Argumentos:
            provider: Endpoint do serviço.
            prompt: Prompt da imagem.
            reference_image_urls: Lista opcional de imagens para image-to-image.
            reference_image_data_urls: Lista opcional de imagens em base64/data URL.

        Retorno:
            JSON inicial do provider (pode já incluir URL final).
        """

        references = [item for item in (reference_image_urls or []) if str(item).strip()]
        payload = {
            "prompt": prompt,
            "model": "nano-banana-2",
            "mode": "image-to-image" if references else "text-to-image",
            "imageSize": "1K",
            "outputFormat": "png",
        }
        if references:
            payload["imageUrl"] = references[:8]
        data_references = [item for item in (reference_image_data_urls or []) if str(item).strip()]
        if data_references:
            payload["imageData"] = data_references[:8]
        return self._post_json(url=provider, payload=payload)

    def _post_json(self, url: str, payload: dict) -> dict:
        """Executa POST JSON com autenticação e tratamento detalhado de erros.

        Argumentos:
            url: Endpoint HTTP para envio do pedido.
            payload: Corpo JSON do pedido.

        Retorno:
            Dicionário JSON devolvido pelo endpoint.

        Raises:
            RuntimeError: Em erros HTTP/rede ou resposta inválida.
        """

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "x-api-key": self._api_key,
            "api-key": self._api_key,
        }
        http_request = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        return self._execute_http_request(http_request, url)

    def _post_json_without_auth(self, url: str, payload: dict) -> dict:
        """Executa POST JSON sem header de autenticação dedicado.

        Esta função é usada para endpoints que autenticam pela query string
        (por exemplo `?key=...`) e não exigem `Authorization` no header.

        Argumentos:
            url: Endpoint HTTP para envio do pedido.
            payload: Corpo JSON do pedido.

        Retorno:
            Dicionário JSON devolvido pelo endpoint.
        """

        headers = {"Content-Type": "application/json"}
        http_request = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        return self._execute_http_request(http_request, url)

    def _get_json(self, url: str) -> dict:
        """Executa GET JSON autenticado e devolve resposta parseada.

        Argumentos:
            url: Endpoint HTTP GET.

        Retorno:
            Dicionário JSON devolvido pelo endpoint.
        """

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "x-api-key": self._api_key,
            "api-key": self._api_key,
        }
        http_request = request.Request(url, headers=headers, method="GET")
        return self._execute_http_request(http_request, url)

    def _execute_http_request(self, http_request: request.Request, url: str) -> dict:
        """Executa request HTTP e converte resposta JSON com mensagens úteis.

        Argumentos:
            http_request: Objeto `urllib.request.Request` já configurado.
            url: URL usada apenas para detalhar mensagens de erro.

        Retorno:
            Dicionário JSON da resposta.
        """

        try:
            with request.urlopen(http_request, timeout=45) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                error_body = ""
            raise RuntimeError(
                f"HTTP {exc.code} {exc.reason}. URL: {url}. Body: {error_body[:600] or 'sem detalhe devolvido'}"
            ) from exc
        except error.URLError as exc:
            reason = getattr(exc, "reason", None)
            raise RuntimeError(f"erro de rede/URL ({reason or exc!s}). URL: {url}") from exc
        except (TimeoutError, OSError) as exc:
            raise RuntimeError(f"timeout ou erro de sistema ({exc!s}). URL: {url}") from exc

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"resposta inválida (não JSON). URL: {url}. Body parcial: {body[:300]}") from exc
        if isinstance(data, dict):
            return data
        raise RuntimeError(f"resposta JSON inesperada (não objeto). URL: {url}")

    def _build_image_prompt(
        self,
        messages: List[Dict[str, str]],
        style: Optional[str],
        reference_image_urls: Optional[List[str]] = None,
    ) -> str:
        """Constrói o prompt final da imagem a partir do histórico conversacional.

        A função recolhe mensagens do utilizador, concatena o contexto e aplica
        uma instrução de qualidade visual para gerar resultados mais consistentes.

        Argumentos:
            messages: Histórico completo da chatroom.
            style: Estilo visual opcional para acrescentar ao prompt.
            reference_image_urls: Lista opcional com URLs de referências visuais.

        Retorno:
            String com o prompt final enviado ao motor de imagem.
        """

        chat_context = self._extract_chat_context(messages)
        latest_user_request = chat_context["latest_user_request"]
        accumulated_user_requirements = chat_context["accumulated_user_requirements"]
        condensed_assistant_direction = chat_context["condensed_assistant_direction"]

        if not latest_user_request:
            latest_user_request = (
                "Criar uma imagem visualmente forte e coerente com o briefing da conversa."
            )
        if not accumulated_user_requirements:
            accumulated_user_requirements = (
                "Sem requisitos adicionais explícitos no histórico."
            )

        style_block = f" Estilo visual: {style}." if style else ""
        references = [item.strip() for item in (reference_image_urls or []) if str(item).strip()]
        references_block = ""
        if references:
            references_list = "; ".join(references[:8])
            references_block = (
                " Imagens de referência para seguir composição/estética: "
                f"{references_list}."
            )
        return (
            "Gera uma imagem estritamente alinhada com a conversa da chatroom."
            f"{style_block}{references_block} "
            f"Pedido MAIS RECENTE do utilizador (prioridade máxima): {latest_user_request}. "
            f"Requisitos acumulados dados pelo utilizador ao longo da conversa: {accumulated_user_requirements}. "
            f"Orientação anterior do agente no chat (usar apenas se não entrar em conflito com o pedido mais recente): {condensed_assistant_direction}. "
            "Mantém consistência total com o pedido mais recente; não inventes tema diferente. "
            "Se houver conflito entre mensagens antigas e a última mensagem do utilizador, segue a última mensagem. "
            "Entrega composição equilibrada, iluminação coerente, bom contraste, detalhes nítidos e sem texto ilegível."
        )

    def _extract_chat_context(self, messages: List[Dict[str, str]]) -> Dict[str, str]:
        """Extrai contexto útil do chat para construir um prompt fiel à conversa.

        A função separa conteúdo do utilizador e do assistente, prioriza a
        última instrução do utilizador e condensa os requisitos anteriores para
        evitar que o modelo gere imagens genéricas ou fora de contexto.

        Argumentos:
            messages: Histórico cronológico com mensagens de `user` e `assistant`.

        Retorno:
            Dicionário com:
            - `latest_user_request`: último pedido explícito do utilizador;
            - `accumulated_user_requirements`: resumo textual dos requisitos do utilizador;
            - `condensed_assistant_direction`: resumo curto do que o agente sugeriu.
        """

        user_messages: List[str] = []
        assistant_messages: List[str] = []

        for item in messages:
            role = str(item.get("role", "")).strip()
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            if role == "user":
                user_messages.append(content)
            elif role == "assistant":
                assistant_messages.append(content)

        latest_user_request = user_messages[-1] if user_messages else ""
        # Mantém os últimos requisitos para não criar prompts demasiado longos.
        accumulated_user_requirements = " | ".join(user_messages[-5:]).strip()
        condensed_assistant_direction = " | ".join(assistant_messages[-2:]).strip()
        if not condensed_assistant_direction:
            condensed_assistant_direction = "Sem orientação anterior do agente."

        return {
            "latest_user_request": latest_user_request,
            "accumulated_user_requirements": accumulated_user_requirements,
            "condensed_assistant_direction": condensed_assistant_direction,
        }

    def _normalize_reference_images(self, reference_image_urls: List[str]) -> Dict[str, object]:
        """Normaliza referências em URLs públicas e data URLs utilizáveis.

        A função separa referências externas (http/https públicos) de caminhos
        locais do projeto (`/static/...`). Para caminhos locais, lê o ficheiro e
        converte para `data:image/...;base64,...`, permitindo enviar a referência
        para providers que aceitam imagem inline no payload.

        Argumentos:
            reference_image_urls: Lista bruta enviada pela interface.

        Retorno:
            Dicionário com:
            - `public_urls`: URLs acessíveis externamente;
            - `data_urls`: referências locais convertidas para data URL;
            - `total_count`: total de referências válidas processadas.
        """

        public_urls: List[str] = []
        data_urls: List[str] = []
        for raw_url in reference_image_urls:
            url = str(raw_url or "").strip()
            if not url:
                continue
            if self._is_public_remote_url(url):
                public_urls.append(url)
                continue

            data_url = self._local_static_url_to_data_url(url)
            if data_url:
                data_urls.append(data_url)

        return {
            "public_urls": public_urls,
            "data_urls": data_urls,
            "total_count": len(public_urls) + len(data_urls),
        }

    def _is_public_remote_url(self, url: str) -> bool:
        """Valida se a URL é remota e potencialmente acessível por APIs externas.

        Argumentos:
            url: URL textual da imagem de referência.

        Retorno:
            `True` quando a URL é `http/https` e não aponta para localhost;
            caso contrário `False`.
        """

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        host = (parsed.hostname or "").lower()
        if host in {"localhost", "127.0.0.1", "::1"}:
            return False
        return bool(host)

    def _local_static_url_to_data_url(self, local_url: str) -> Optional[str]:
        """Converte URL local `/static/...` para data URL base64.

        Argumentos:
            local_url: URL relativa guardada pelo endpoint de upload local.

        Retorno:
            `data:image/...;base64,...` quando o ficheiro existe; `None` quando
            o caminho é inválido ou não pode ser lido.
        """

        if not local_url.startswith("/static/"):
            return None
        relative_path = local_url[len("/static/") :].replace("/", os.sep)
        file_path = BASE_DIR / "static" / relative_path
        if not file_path.exists() or not file_path.is_file():
            return None

        suffix = file_path.suffix.lower()
        mime_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(suffix, "image/png")
        try:
            data_b64 = base64.b64encode(file_path.read_bytes()).decode("utf-8")
        except Exception:  # noqa: BLE001
            return None
        return f"data:{mime_type};base64,{data_b64}"

    def _extract_image_url(self, data: dict) -> Optional[str]:
        """Extrai URL de imagem de formatos de resposta comuns de APIs visuais.

        A função tenta vários formatos para robustez: `image_url` direto,
        `url` direto ou listas em `data` com objetos contendo `url`.

        Argumentos:
            data: Objeto JSON completo devolvido pela API.

        Retorno:
            URL da imagem quando encontrada; caso contrário `None`.
        """

        direct_url = str(data.get("image_url", "")).strip() or str(data.get("url", "")).strip()
        if direct_url:
            return direct_url

        data_list = data.get("data")
        if isinstance(data_list, list) and data_list:
            first = data_list[0]
            if isinstance(first, dict):
                nested_url = str(first.get("url", "")).strip() or str(first.get("image_url", "")).strip()
                if nested_url:
                    return nested_url
        return None

    def _extract_base64_image(self, data: dict) -> Optional[str]:
        """Extrai imagem em base64 de formatos comuns de resposta da API.

        A função suporta `b64_json` direto ou dentro de `data[0].b64_json`,
        mantendo compatibilidade com estruturas semelhantes ao ecossistema OpenAI.

        Argumentos:
            data: Objeto JSON completo devolvido pela API.

        Retorno:
            String base64 quando encontrada; caso contrário `None`.
        """

        direct_b64 = str(data.get("b64_json", "")).strip()
        if direct_b64:
            return direct_b64

        data_list = data.get("data")
        if isinstance(data_list, list) and data_list:
            first = data_list[0]
            if isinstance(first, dict):
                nested_b64 = str(first.get("b64_json", "")).strip()
                if nested_b64:
                    return nested_b64
        return None

    def _save_base64_image(self, image_base64: str) -> str:
        """Guarda imagem base64 em ficheiro PNG e devolve rota pública local.

        Argumentos:
            image_base64: Conteúdo base64 da imagem devolvida pela API.

        Retorno:
            URL relativa para servir o ficheiro gerado via `/static/generated/...`.

        Raises:
            RuntimeError: Se o base64 for inválido ou não puder ser gravado.
        """

        STATIC_GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"designer-{uuid4().hex}.png"
        file_path = STATIC_GENERATED_DIR / filename
        try:
            binary = base64.b64decode(image_base64, validate=False)
            file_path.write_bytes(binary)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Falha ao guardar imagem local gerada: {exc!s}") from exc
        return f"/static/generated/{filename}"

    def _save_binary_image(self, image_bytes: bytes) -> str:
        """Guarda bytes de imagem em ficheiro PNG e devolve rota pública.

        Argumentos:
            image_bytes: Conteúdo binário da imagem devolvido pela API.

        Retorno:
            URL relativa para servir o ficheiro em `/static/generated/...`.

        Raises:
            RuntimeError: Se ocorrer falha de escrita no disco.
        """

        STATIC_GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"designer-{uuid4().hex}.png"
        file_path = STATIC_GENERATED_DIR / filename
        try:
            file_path.write_bytes(image_bytes)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Falha ao guardar bytes da imagem gerada: {exc!s}") from exc
        return f"/static/generated/{filename}"


designer_agent = DesignerAgent()
