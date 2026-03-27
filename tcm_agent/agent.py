"""
Módulo do agente LLM.

Responsável por:
- Chamar a API Anthropic com retry exponencial
- Parsear e validar a resposta JSON
- Normalizar campos para o modelo Ocorrencia
"""

from __future__ import annotations
import json
import logging
import re
import time
from typing import Optional

import anthropic

from .config import build_system_prompt, TEMAS_VALIDOS
from .models import Ocorrencia

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"
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
            api_key: Chave da API Anthropic. Se None, usa a variável de
                     ambiente ANTHROPIC_API_KEY.
        """
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self._system_prompt = build_system_prompt()
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
        tokens = raw_response.usage.input_tokens + raw_response.usage.output_tokens

        logger.debug(
            "Página %d: %d ocorrência(s), %d tokens",
            numero_pagina,
            len(ocorrencias),
            tokens,
        )
        return ocorrencias, tokens

    def _chamar_api_com_retry(self, prompt: str) -> anthropic.types.Message:
        """Chama a API com retry exponencial em caso de erro de rate limit ou servidor."""
        ultimo_erro: Exception | None = None

        for tentativa in range(1, MAX_RETRIES + 1):
            try:
                resposta = self._client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=self._system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
                return resposta

            except anthropic.RateLimitError as e:
                delay = RETRY_BASE_DELAY * (2 ** (tentativa - 1))
                logger.warning(
                    "Rate limit (tentativa %d/%d). Aguardando %.1fs…",
                    tentativa, MAX_RETRIES, delay,
                )
                time.sleep(delay)
                ultimo_erro = e

            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    delay = RETRY_BASE_DELAY * tentativa
                    logger.warning(
                        "Erro do servidor %d (tentativa %d/%d). Aguardando %.1fs…",
                        e.status_code, tentativa, MAX_RETRIES, delay,
                    )
                    time.sleep(delay)
                    ultimo_erro = e
                else:
                    raise

        raise RuntimeError(
            f"API falhou após {MAX_RETRIES} tentativas: {ultimo_erro}"
        ) from ultimo_erro

    def _parsear_resposta(
        self, resposta: anthropic.types.Message, numero_pagina: int
    ) -> list[Ocorrencia]:
        """Extrai e valida o array JSON retornado pelo modelo."""
        texto_raw = ""
        for bloco in resposta.content:
            if bloco.type == "text":
                texto_raw += bloco.text

        # Remove possíveis blocos de código markdown residuais
        texto_limpo = re.sub(r"```(?:json)?", "", texto_raw).strip()

        # Tenta parsear diretamente
        try:
            dados = json.loads(texto_limpo)
        except json.JSONDecodeError:
            # Tenta extrair o primeiro array JSON válido da string
            match = re.search(r"\[.*?\]", texto_limpo, re.DOTALL)
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
                logger.warning(
                    "Nenhum JSON encontrado na resposta da página %d", numero_pagina
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

    def _validar_item(
        self, item: dict, numero_pagina: int
    ) -> Optional[Ocorrencia]:
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

        # subtema pode ser None, string vazia ou string
        subtema = item.get("subtema")
        if subtema is not None:
            subtema = str(subtema).strip() or None

        # página: usa a fornecida ou a da resposta, prevalece a fornecida
        pagina = item.get("pagina", numero_pagina)
        try:
            pagina = int(pagina)
        except (ValueError, TypeError):
            pagina = numero_pagina

        return Ocorrencia(
            pagina=pagina,
            tema_principal=tema,
            subtema=subtema,
            trecho=trecho,
            entidade_identificada=entidade,
        )
