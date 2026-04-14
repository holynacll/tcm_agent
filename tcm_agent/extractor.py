"""
Módulo de extração de texto do PDF.

Usa PyMuPDF para extração precisa por página, com recorte de regiões para
excluir cabeçalhos e rodapés. Suporta layout de duas colunas e sobreposição
de contexto entre páginas consecutivas para capturar referências anafóricas.

Também extrai o mapa de seções a partir do índice da primeira página,
enriquecendo cada página com o rótulo da seção em que ela se encontra.

Para calibrar as constantes de recorte, use:
    python -m tcm_agent.cli --inspecionar arquivo.pdf
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constantes de recorte — ajuste com base na saída de --inspecionar
# Valores em pontos (pt). 1 pt ≈ 0,353 mm.
# ─────────────────────────────────────────────────────────────────────────────

# Páginas 2 em diante
HEADER_H: float = 80  # cabeçalho ocupa 0–80pt
FOOTER_H: float = 15  # rodapé mínimo

# Página 1 tem cabeçalho e rodapé maiores
HEADER_H_P1: float = 160  # cabeçalho + logo ocupa 0–160pt
FOOTER_H_P1: float = 160  # assinatura digital + marca d'água

# Layout em duas colunas
COL_GAP: float = 12  # espaço entre as colunas (pt) — dividido ao meio

# Palavras finais da página anterior a incluir como contexto
OVERLAP_WORDS = 150


# ─────────────────────────────────────────────────────────────────────────────
# Mapeamento de seções — extração do índice da página 1
# ─────────────────────────────────────────────────────────────────────────────

# Parseia linhas do índice no formato "Nome da Seção ████████ 42"
# O separador pode ser pontos ("....") ou caracteres de bloco Unicode
# (░▒▓█ e similares) — o TCM-BA usa esses glifos como dot-leader no PDF.
# [^\w\s]{3,} captura qualquer sequência de 3+ chars que não seja letra/dígito/espaço.
_TOC_LINE = re.compile(r"^(.+?)\s*[^\w\s]{3,}\s*(\d+)\s*$")


@dataclass
class SecaoDocumento:
    """Representa uma seção identificada no índice do diário."""

    nome: str  # exatamente como aparece no índice
    pagina_inicio: int


def extrair_mapa_secoes(texto_pagina1: str) -> list[SecaoDocumento]:
    """
    Parseia o índice da primeira página e retorna as seções com seus
    números de página, ordenadas por página.

    Preserva o nome bruto da seção — mesmo tipos desconhecidos ficam
    legíveis para o LLM sem precisar de mapeamento explícito.
    """
    secoes: list[SecaoDocumento] = []
    for linha in texto_pagina1.splitlines():
        m = _TOC_LINE.match(linha.strip())
        if not m:
            continue
        nome = m.group(1).strip()
        pagina = int(m.group(2))
        secoes.append(SecaoDocumento(nome=nome, pagina_inicio=pagina))
    return sorted(secoes, key=lambda s: s.pagina_inicio)


def secao_da_pagina(mapa: list[SecaoDocumento], pagina: int) -> str:
    """
    Retorna o nome da seção à qual a página pertence.

    Propaga a última seção cujo início é <= pagina (seções cobrem múltiplas
    páginas). Retorna string vazia se o mapa estiver vazio.
    """
    secao: SecaoDocumento | None = None
    for s in mapa:
        if s.pagina_inicio <= pagina:
            secao = s
        else:
            break
    return secao.nome if secao else ""


# ─────────────────────────────────────────────────────────────────────────────
# Extração de texto por página
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PaginaTexto:
    numero: int  # 1-based
    texto: str  # texto limpo da página
    contexto_anterior: str  # últimas N palavras da página anterior (para anáforas)
    secao: str = field(default="")  # nome da seção, vindo do índice da p.1

    @property
    def texto_com_contexto(self) -> str:
        """Texto completo enviado ao LLM: seção + contexto anterior + texto da página."""
        parts: list[str] = []
        if self.secao:
            parts.append(f"[SEÇÃO DO DOCUMENTO: {self.secao}]")
        if self.contexto_anterior:
            parts.append(
                f"[CONTEXTO DA PÁGINA ANTERIOR — apenas para referência anafórica]\n"
                f"{self.contexto_anterior}"
            )
        parts.append(f"[INÍCIO DA PÁGINA {self.numero}]\n{self.texto}")
        return "\n".join(parts)


def _limpar_texto(texto: str) -> str:
    """Remove artefatos comuns de extração de PDF do TCM-BA."""
    if not texto:
        return ""
    # remove quebras de linha dentro de palavras (hifenação de coluna)
    texto = re.sub(r"-\n(\w)", r"\1", texto)
    # remove linhas de assinatura/local-data do TCM-BA:
    #   "Salvador, 03 de março de 2026."  /  "Salvador - BA, 03 de março de 2026."
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


def _extrair_conteudo_pagina(page: fitz.Page, is_first_page: bool) -> str:
    """
    Extrai texto da área de conteúdo da página, excluindo cabeçalho e rodapé,
    em ordem de leitura (coluna esquerda → coluna direita).
    """
    header_h = HEADER_H_P1 if is_first_page else HEADER_H
    footer_h = FOOTER_H_P1 if is_first_page else FOOTER_H

    w = page.rect.width
    h = page.rect.height
    top = header_h
    bottom = h - footer_h

    if bottom <= top:
        # fallback: página muito pequena ou constantes mal calibradas
        return _limpar_texto(str(page.get_text("text", sort=True)))

    col_mid = w / 2
    half_gap = COL_GAP / 2

    rect_esq = fitz.Rect(0, top, col_mid - half_gap, bottom)
    rect_dir = fitz.Rect(col_mid + half_gap, top, w, bottom)

    texto_esq = _limpar_texto(str(page.get_text("text", clip=rect_esq, sort=True)))
    texto_dir = _limpar_texto(str(page.get_text("text", clip=rect_dir, sort=True)))

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
        Lista de PaginaTexto ordenada por número de página, cada item com
        o nome da seção extraído do índice da primeira página.
    """
    caminho = Path(caminho_pdf)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    return _extrair_pymupdf(caminho, paginas, overlap)


def _extrair_pymupdf(
    caminho: Path,
    paginas_filtro: list[int] | None,
    overlap: bool,
) -> list[PaginaTexto]:
    resultados: list[PaginaTexto] = []
    texto_anterior = ""

    with fitz.open(str(caminho)) as doc:
        total = len(doc)
        logger.info("PDF aberto: %s — %d páginas", caminho.name, total)

        # Extrai o índice da página 1 para construir o mapa de seções.
        # A página 1 é sempre lida aqui, independente de paginas_filtro.
        texto_p1 = _extrair_conteudo_pagina(doc[0], is_first_page=True)
        mapa_secoes = extrair_mapa_secoes(texto_p1)
        if mapa_secoes:
            logger.info(
                "Mapa de seções: %d seção(ões) — %s",
                len(mapa_secoes),
                ", ".join(f"{s.nome}(p.{s.pagina_inicio})" for s in mapa_secoes),
            )
        else:
            logger.warning("Nenhuma seção identificada no índice da página 1")

        for idx in range(len(doc)):
            page = doc[idx]
            num_pagina = idx + 1
            is_first = num_pagina == 1

            # reutiliza o texto já extraído para a página 1
            texto = texto_p1 if is_first else _extrair_conteudo_pagina(page, is_first)

            if paginas_filtro and num_pagina not in paginas_filtro:
                # não inclui no resultado, mas mantém o overlap
                texto_anterior = " ".join(texto.split()[-OVERLAP_WORDS:])
                continue

            contexto = texto_anterior if overlap else ""

            resultados.append(
                PaginaTexto(
                    numero=num_pagina,
                    texto=texto,
                    contexto_anterior=contexto,
                    secao=secao_da_pagina(mapa_secoes, num_pagina),
                )
            )

            texto_anterior = " ".join(texto.split()[-OVERLAP_WORDS:])

    return resultados


def contar_paginas(caminho_pdf: str | Path) -> int:
    """Retorna o número total de páginas do PDF sem extrair texto."""
    with fitz.open(str(Path(caminho_pdf))) as doc:
        return len(doc)


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

    with fitz.open(str(caminho)) as doc:
        total = len(doc)
        print(f"\nArquivo : {caminho.name}")
        print(f"Páginas : {total} total — inspecionando {paginas_alvo}")
        print(f"{'─' * 64}")

        for num in paginas_alvo:
            if num > total:
                print(f"  Página {num}: fora do intervalo (total={total})")
                continue

            page = doc[num - 1]
            w = page.rect.width
            h = page.rect.height
            print(
                f"\nPágina {num}  —  {w:.1f} x {h:.1f} pt  "
                f"(coluna central estimada: x = {w / 2:.1f} pt)"
            )

            for label, y0, y1 in [
                ("TOPO  0–80pt", 0, 80),
                ("TOPO  80–160pt", 80, 160),
                ("BASE  últimos 80pt", h - 80, h),
                ("BASE  últimos 160pt", h - 160, h - 80),
            ]:
                txt = str(
                    page.get_text("text", clip=fitz.Rect(0, y0, w, y1), sort=True)
                )
                txt = txt.strip().replace("\n", " ↵ ")
                print(f"  [{label}]  {txt[:120]!r}")

        print(f"\n{'─' * 64}")
        print("Ajuste as constantes em extractor.py:")
        print("  HEADER_H, FOOTER_H          (páginas 2+)")
        print("  HEADER_H_P1, FOOTER_H_P1    (página 1)\n")


if __name__ == "__main__":
    caminho_pdf = "data/tcm_2026-03-07_completo.pdf"
    pages = extrair_paginas(caminho_pdf)
    for page in pages:
        print(f"Página {page.numero}")
        print(f"Seção: {page.secao!r}")
        print(f"Texto: {page.texto}")
        print(f"{'─' * 64}")
