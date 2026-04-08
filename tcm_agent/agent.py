"""
Módulo do agente LLM.

Responsável por:
- Chamar a API Gemini com retry exponencial
- Parsear e validar a resposta JSON
- Normalizar campos para o modelo Ocorrencia
"""

import json
import logging
import os
import re
import time
from typing import Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from .config import TEMAS_VALIDOS, build_system_prompt
from .models import Ocorrencia

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"
MAX_TOKENS = 4096
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # segundos


class TCMAgente:
    """
    Agente de análise do Diário Oficial do TCM-BA.

    Identifica menções à Prefeitura de Salvador em texto extraído de PDF,
    classificando cada ocorrência com tema, subtema, trecho e entidade.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Chave da API Gemini. Se None, usa a variável de
                     ambiente GEMINI_API_KEY ou GOOGLE_API_KEY.
        """
        resolved_key = (
            api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        )
        self._client = genai.Client(api_key=resolved_key)
        self._system_prompt = build_system_prompt()
        self._generate_config = types.GenerateContentConfig(
            system_instruction=self._system_prompt,
            max_output_tokens=MAX_TOKENS,
            temperature=0.0,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        logger.debug("TCMAgente inicializado com modelo %s", MODEL)

    def analisar_pagina(
        self,
        texto: str,
        numero_pagina: int,
    ) -> tuple[list[Ocorrencia], int]:
        """
        Analisa o texto de uma página e retorna as ocorrências encontradas.

        Args:
            texto: Texto da página (pode incluir contexto de sobreposição).
            numero_pagina: Número da página (1-based) para preenchimento do modelo.

        Returns:
            (ocorrencias, tokens_usados)
        """
        prompt_usuario = (
            f"Analise a PÁGINA {numero_pagina} do Diário Oficial do TCM-BA "
            f"e identifique TODAS as menções à Prefeitura de Salvador e suas "
            f"entidades/servidores vinculados:\n\n{texto}"
        )

        raw_response = self._chamar_api_com_retry(prompt_usuario)
        ocorrencias = self._parsear_resposta(raw_response, numero_pagina)

        usage = raw_response.usage_metadata
        tokens = 0
        if usage:
            tokens = (usage.prompt_token_count or 0) + (
                usage.candidates_token_count or 0
            )

        logger.debug(
            "Página %d: %d ocorrência(s), %d tokens",
            numero_pagina,
            len(ocorrencias),
            tokens,
        )
        return ocorrencias, tokens

    def _chamar_api_com_retry(self, prompt: str):
        """Chama a API com retry exponencial em caso de erro de rate limit ou servidor."""
        ultimo_erro: Exception | None = None

        for tentativa in range(1, MAX_RETRIES + 1):
            try:
                return self._client.models.generate_content(
                    model=MODEL,
                    contents=prompt,
                    config=self._generate_config,
                )

            except genai_errors.ClientError as e:
                # 429 = rate limit / quota exceeded
                if e.code == 429:
                    delay = RETRY_BASE_DELAY * (2 ** (tentativa - 1))
                    logger.warning(
                        "Rate limit (tentativa %d/%d). Aguardando %.1fs…",
                        tentativa,
                        MAX_RETRIES,
                        delay,
                    )
                    time.sleep(delay)
                    ultimo_erro = e
                else:
                    raise

            except genai_errors.ServerError as e:
                delay = RETRY_BASE_DELAY * tentativa
                logger.warning(
                    "Erro do servidor (tentativa %d/%d). Aguardando %.1fs…",
                    tentativa,
                    MAX_RETRIES,
                    delay,
                )
                time.sleep(delay)
                ultimo_erro = e

        raise RuntimeError(
            f"API falhou após {MAX_RETRIES} tentativas: {ultimo_erro}"
        ) from ultimo_erro

    def _parsear_resposta(self, resposta, numero_pagina: int) -> list[Ocorrencia]:
        """Extrai e valida o array JSON retornado pelo modelo."""
        texto_raw = resposta.text or ""

        # Remove blocos de código markdown residuais e backticks soltos
        texto_limpo = re.sub(r"```(?:json)?", "", texto_raw).strip()

        # Tenta parsear diretamente
        try:
            dados = json.loads(texto_limpo)
        except json.JSONDecodeError:
            # Extrai o maior array JSON da string (greedy para capturar arrays aninhados)
            match = re.search(r"\[.*\]", texto_limpo, re.DOTALL)
            if match:
                try:
                    dados = json.loads(match.group(0))
                except json.JSONDecodeError:
                    logger.error(
                        "Falha ao parsear JSON da página %d. Resposta: %s",
                        numero_pagina,
                        texto_limpo[:300],
                    )
                    return []
            else:
                # Modelo respondeu com texto sem JSON — assume zero ocorrências
                logger.debug(
                    "Página %d sem JSON na resposta (assumindo []). Texto: %s",
                    numero_pagina,
                    texto_limpo[:200],
                )
                return []

        if not isinstance(dados, list):
            logger.warning("Resposta não é uma lista na página %d", numero_pagina)
            return []

        ocorrencias: list[Ocorrencia] = []
        for item in dados:
            if not isinstance(item, dict):
                continue
            ocorrencia = self._validar_item(item, numero_pagina)
            if ocorrencia:
                ocorrencias.append(ocorrencia)

        return ocorrencias

    def _validar_item(self, item: dict, numero_pagina: int) -> Optional[Ocorrencia]:
        """Valida e normaliza um item do array JSON."""
        # campos obrigatórios
        trecho = str(item.get("trecho", "")).strip()
        entidade = str(item.get("entidade_identificada", "")).strip()

        if not trecho or not entidade:
            logger.debug("Item descartado (campos obrigatórios ausentes): %s", item)
            return None

        # normaliza tema_principal
        tema = str(item.get("tema_principal", "Outro")).strip()
        if tema not in TEMAS_VALIDOS:
            # tenta match parcial (ex: "Notificação Secretaria" → "Notificação")
            tema_norm = next(
                (t for t in TEMAS_VALIDOS if t.lower() in tema.lower()), "Outro"
            )
            logger.debug("Tema '%s' normalizado para '%s'", tema, tema_norm)
            tema = tema_norm

        # página: usa a fornecida ou a da resposta, prevalece a fornecida
        pagina = item.get("pagina", numero_pagina)
        try:
            pagina = int(pagina)
        except (ValueError, TypeError):
            pagina = numero_pagina

        return Ocorrencia(
            pagina=pagina,
            tema_principal=tema,
            trecho=trecho,
            entidade_identificada=entidade,
        )
