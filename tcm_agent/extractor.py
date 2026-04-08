"""
Módulo de extração de texto do PDF.

Usa pdfplumber para extração precisa por página, com recorte de regiões para
excluir cabeçalhos e rodapés. Suporta layout de duas colunas e sobreposição
de contexto entre páginas consecutivas para capturar referências anafóricas.

Para calibrar as constantes de recorte, use:
    python -m tcm_agent.cli --inspecionar arquivo.pdf
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

PDFPLUMBER_OK = True
PYPDF_OK = True

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constantes de recorte — ajuste com base na saída de --inspecionar
# Valores em pontos (pt). 1 pt ≈ 0,353 mm.
# ─────────────────────────────────────────────────────────────────────────────

# Páginas 2 em diante
HEADER_H: float = 80    # cabeçalho ocupa 0–80pt (strip 80–160pt já é conteúdo)
FOOTER_H: float = 15    # rodapé mínimo; conteúdo vai até o fundo nessas páginas

# Página 1 tem cabeçalho e rodapé maiores
HEADER_H_P1: float = 160   # cabeçalho + logo ocupa 0–160pt
FOOTER_H_P1: float = 160   # assinatura digital (últimos 80pt) + marca d'água (80–160pt)

# Layout em duas colunas
COL_GAP: float = 12    # espaço entre as colunas (pt) — dividido ao meio

# Palavras finais da página anterior a incluir como contexto
OVERLAP_WORDS = 150


@dataclass
class PaginaTexto:
    numero: int  # 1-based
    texto: str  # texto limpo da página
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
    # remove linhas de assinatura/local-data do TCM-BA:
    #   "Salvador, 03 de março de 2026."
    #   "Salvador, em 03 de março de 2026."
    #   "Salvador - BA, 03 de março de 2026."
    # São linhas isoladas que indicam apenas onde o ato foi lavrado.
    texto = re.sub(
        r"^\s*Salvador(?:\s*[-–]\s*BA)?,?\s*(?:em\s+)?\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\.?\s*$",
        "",
        texto,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    # colapsa múltiplas linhas em branco
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    # remove caracteres de controle
    texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", texto)
    return texto.strip()


def _extrair_conteudo_pagina(page, is_first_page: bool) -> str:
    """
    Extrai texto da área de conteúdo da página, excluindo cabeçalho e rodapé,
    em ordem de leitura (coluna esquerda → coluna direita).
    """
    header_h = HEADER_H_P1 if is_first_page else HEADER_H
    footer_h = FOOTER_H_P1 if is_first_page else FOOTER_H

    w, h = page.width, page.height
    top = header_h
    bottom = h - footer_h

    if bottom <= top:
        # fallback: página muito pequena ou constantes mal calibradas
        return _limpar_texto(page.extract_text() or "")

    col_mid = w / 2
    half_gap = COL_GAP / 2

    col_esq = page.crop((0, top, col_mid - half_gap, bottom))
    col_dir = page.crop((col_mid + half_gap, top, w, bottom))

    texto_esq = _limpar_texto(col_esq.extract_text() or "")
    texto_dir = _limpar_texto(col_dir.extract_text() or "")

    partes = [t for t in (texto_esq, texto_dir) if t]
    return "\n\n".join(partes)


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
            is_first = num_pagina == 1

            if paginas_filtro and num_pagina not in paginas_filtro:
                # ainda precisamos do texto para o contexto de sobreposição
                texto = _extrair_conteudo_pagina(page, is_first)
                texto_anterior = " ".join(texto.split()[-OVERLAP_WORDS:])
                continue

            texto = _extrair_conteudo_pagina(page, is_first)

            contexto = texto_anterior if overlap else ""

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

        contexto = texto_anterior if overlap else ""

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


def inspecionar_layout(
    caminho_pdf: str | Path,
    paginas: list[int] | None = None,
) -> None:
    """
    Imprime dimensões e trechos do topo/base de cada página para calibrar
    as constantes HEADER_H, FOOTER_H, HEADER_H_P1 e FOOTER_H_P1.

    Args:
        caminho_pdf: Caminho para o arquivo PDF.
        paginas: Páginas a inspecionar (1-based). Padrão: [1, 2].
    """
    caminho = Path(caminho_pdf)
    paginas_alvo = paginas or [1, 2]

    with pdfplumber.open(caminho) as pdf:
        total = len(pdf.pages)
        print(f"\nArquivo : {caminho.name}")
        print(f"Páginas : {total} total — inspecionando {paginas_alvo}")
        print(f"{'─' * 64}")

        for num in paginas_alvo:
            if num > total:
                print(f"  Página {num}: fora do intervalo (total={total})")
                continue

            page = pdf.pages[num - 1]
            w, h = page.width, page.height
            print(f"\nPágina {num}  —  {w:.1f} x {h:.1f} pt  "
                  f"(coluna central estimada: x = {w / 2:.1f} pt)")

            for label, y0, y1 in [
                ("TOPO  0–80pt",        0,      80),
                ("TOPO  80–160pt",      80,     160),
                ("BASE  últimos 80pt",  h - 80, h),
                ("BASE  últimos 160pt", h - 160, h - 80),
            ]:
                strip = page.crop((0, y0, w, y1))
                txt = (strip.extract_text() or "").strip().replace("\n", " ↵ ")
                print(f"  [{label}]  {txt[:120]!r}")

        print(f"\n{'─' * 64}")
        print("Ajuste as constantes em extractor.py:")
        print("  HEADER_H, FOOTER_H          (páginas 2+)")
        print("  HEADER_H_P1, FOOTER_H_P1    (página 1)\n")
