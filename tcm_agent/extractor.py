"""
Módulo de extração de texto do PDF.

Usa pdfplumber para extração precisa por página.
Suporta sobreposição de contexto entre páginas consecutivas para
capturar referências anafóricas que cruzam limites de página.
"""

from __future__ import annotations
import re
import logging
from pathlib import Path
from dataclasses import dataclass

try:
    import pdfplumber
    PDFPLUMBER_OK = True
except ImportError:
    PDFPLUMBER_OK = False

try:
    from pypdf import PdfReader
    PYPDF_OK = True
except ImportError:
    PYPDF_OK = False

logger = logging.getLogger(__name__)

# Palavras finais da página anterior a incluir como contexto
OVERLAP_WORDS = 150


@dataclass
class PaginaTexto:
    numero: int          # 1-based
    texto: str           # texto limpo da página
    contexto_anterior: str  # últimas N palavras da página anterior (para anáforas)

    @property
    def texto_com_contexto(self) -> str:
        """Texto completo enviado ao LLM: contexto anterior + texto da página."""
        if self.contexto_anterior:
            return (
                f"[CONTEXTO DA PÁGINA ANTERIOR — apenas para referência anafórica]\n"
                f"{self.contexto_anterior}\n"
                f"[INÍCIO DA PÁGINA {self.numero}]\n"
                f"{self.texto}"
            )
        return self.texto


def _limpar_texto(texto: str) -> str:
    """Remove artefatos comuns de extração de PDF do TCM-BA."""
    if not texto:
        return ""
    # remove quebras de linha dentro de palavras (hifenação de coluna)
    texto = re.sub(r"-\n(\w)", r"\1", texto)
    # colapsa múltiplas linhas em branco
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    # remove caracteres de controle
    texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", texto)
    return texto.strip()


def extrair_paginas(
    caminho_pdf: str | Path,
    paginas: list[int] | None = None,
    overlap: bool = True,
) -> list[PaginaTexto]:
    """
    Extrai texto de todas as páginas (ou das especificadas) de um PDF.

    Args:
        caminho_pdf: Caminho para o arquivo PDF.
        paginas: Lista de números de página (1-based) para processar.
                 None = todas as páginas.
        overlap: Se True, inclui contexto das últimas N palavras da
                 página anterior para ajudar com referências anafóricas.

    Returns:
        Lista de PaginaTexto ordenada por número de página.
    """
    caminho = Path(caminho_pdf)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    if PDFPLUMBER_OK:
        return _extrair_pdfplumber(caminho, paginas, overlap)
    elif PYPDF_OK:
        logger.warning("pdfplumber não disponível, usando pypdf (qualidade menor)")
        return _extrair_pypdf(caminho, paginas, overlap)
    else:
        raise ImportError("Instale pdfplumber ou pypdf: pip install pdfplumber")


def _extrair_pdfplumber(
    caminho: Path,
    paginas_filtro: list[int] | None,
    overlap: bool,
) -> list[PaginaTexto]:
    resultados: list[PaginaTexto] = []
    texto_anterior = ""

    with pdfplumber.open(caminho) as pdf:
        total = len(pdf.pages)
        logger.info(f"PDF aberto: {caminho.name} — {total} páginas")

        for idx, page in enumerate(pdf.pages):
            num_pagina = idx + 1

            if paginas_filtro and num_pagina not in paginas_filtro:
                # ainda precisamos do texto para o contexto de sobreposição
                raw = page.extract_text() or ""
                texto_anterior = " ".join(_limpar_texto(raw).split()[-OVERLAP_WORDS:])
                continue

            raw = page.extract_text() or ""
            texto = _limpar_texto(raw)

            contexto = ""
            if overlap and texto_anterior:
                contexto = texto_anterior

            resultados.append(
                PaginaTexto(
                    numero=num_pagina,
                    texto=texto,
                    contexto_anterior=contexto,
                )
            )

            texto_anterior = " ".join(texto.split()[-OVERLAP_WORDS:])

    return resultados


def _extrair_pypdf(
    caminho: Path,
    paginas_filtro: list[int] | None,
    overlap: bool,
) -> list[PaginaTexto]:
    resultados: list[PaginaTexto] = []
    texto_anterior = ""

    reader = PdfReader(caminho)
    total = len(reader.pages)
    logger.info(f"PDF aberto (pypdf): {caminho.name} — {total} páginas")

    for idx, page in enumerate(reader.pages):
        num_pagina = idx + 1

        if paginas_filtro and num_pagina not in paginas_filtro:
            raw = page.extract_text() or ""
            texto_anterior = " ".join(_limpar_texto(raw).split()[-OVERLAP_WORDS:])
            continue

        raw = page.extract_text() or ""
        texto = _limpar_texto(raw)

        contexto = ""
        if overlap and texto_anterior:
            contexto = texto_anterior

        resultados.append(
            PaginaTexto(
                numero=num_pagina,
                texto=texto,
                contexto_anterior=contexto,
            )
        )

        texto_anterior = " ".join(texto.split()[-OVERLAP_WORDS:])

    return resultados


def contar_paginas(caminho_pdf: str | Path) -> int:
    """Retorna o número total de páginas do PDF sem extrair texto."""
    caminho = Path(caminho_pdf)
    if PDFPLUMBER_OK:
        with pdfplumber.open(caminho) as pdf:
            return len(pdf.pages)
    elif PYPDF_OK:
        return len(PdfReader(caminho).pages)
    raise ImportError("Instale pdfplumber ou pypdf")
