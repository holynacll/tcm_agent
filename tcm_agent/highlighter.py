"""
Módulo de geração de PDF marcado.

Recebe o PDF original e um ResultadoAnalise, e produz uma cópia com os
trechos das ocorrências marcados com highlight e anotações popup.

Uso:
    from tcm_agent import Pipeline, gerar_pdf_marcado

    resultado = Pipeline().analisar_pdf("edicao.pdf")
    gerar_pdf_marcado("edicao.pdf", resultado)
    # → salva "edicao_marcado.pdf" no mesmo diretório
"""

import logging
import re
from pathlib import Path

import fitz  # PyMuPDF

from .models import Ocorrencia, ResultadoAnalise

logger = logging.getLogger(__name__)

# Cor do highlight — amarelo
_HIGHLIGHT_COLOR = (1.0, 0.85, 0.0)

# Comprimento mínimo de uma linha para ser buscada individualmente
_MIN_LINE_LEN = 20

# Comprimentos candidatos para fallback progressivo (usado quando nenhuma linha bate)
_FALLBACK_LENGTHS = [80, 60, 40, 25]


def _linhas_busca(trecho: str) -> list[str]:
    """
    Extrai as linhas do trecho que têm conteúdo suficiente para busca.
    Cada linha é normalizada (colapsa espaços internos) mas mantém
    sua identidade — não mistura linhas entre si.
    """
    linhas: list[str] = []
    for linha in trecho.splitlines():
        normalizada = re.sub(r"\s+", " ", linha).strip()
        if len(normalizada) >= _MIN_LINE_LEN:
            linhas.append(normalizada)
    return linhas


def _fragmentos_fallback(trecho: str) -> list[str]:
    """
    Fragmentos de comprimento decrescente do trecho completo normalizado.
    Usado quando nenhuma linha individual foi encontrada no PDF.
    """
    normalizado = re.sub(r"\s+", " ", trecho).strip()
    candidatos: list[str] = []
    for length in _FALLBACK_LENGTHS:
        if len(normalizado) >= length:
            fragmento = normalizado[:length].strip()
            if fragmento not in candidatos:
                candidatos.append(fragmento)
    return candidatos


def _tooltip(oc: Ocorrencia) -> str:
    """Monta o texto exibido no popup da anotação."""
    partes: list[str] = []
    if oc.descricao:
        partes.append(oc.descricao)
    if oc.entidade_identificada:
        partes.append("Entidades: " + ", ".join(oc.entidade_identificada))
    if oc.siglas_mapeadas:
        partes.append("Siglas: " + ", ".join(oc.siglas_mapeadas))
    if oc.servidores_mapeados:
        partes.append("Servidores: " + ", ".join(oc.servidores_mapeados))
    return "\n".join(partes)


def _marcar_ocorrencia(
    page: fitz.Page,
    oc: Ocorrencia,
) -> bool:
    """
    Marca o trecho da ocorrência na página com highlight linha a linha.

    Deduplicação é feita localmente (por ocorrência) para evitar que a mesma
    região seja adicionada duas vezes na mesma anotação.

    Retorna True se ao menos uma linha/fragmento foi localizado.
    """
    tooltip = _tooltip(oc)
    vistos: set[tuple[float, ...]] = set()
    todos_quads: list[fitz.Quad] = []

    for linha in _linhas_busca(oc.trecho):
        for quad in page.search_for(linha, quads=True):
            chave = tuple(round(v, 2) for v in quad.rect)
            if chave not in vistos:
                vistos.add(chave)
                todos_quads.append(quad)

    if todos_quads:
        annot = page.add_highlight_annot(todos_quads)
        annot.set_colors(fill=_HIGHLIGHT_COLOR)
        annot.set_info(content=tooltip, title="TCM Agente")
        annot.update()
        return True

    # fallback: nenhuma linha individual encontrada
    for fragmento in _fragmentos_fallback(oc.trecho):
        quads_fragmento: list[fitz.Quad] = []
        for quad in page.search_for(fragmento, quads=True):
            chave = tuple(round(v, 2) for v in quad.rect)
            if chave not in vistos:
                vistos.add(chave)
                quads_fragmento.append(quad)
        if quads_fragmento:
            annot = page.add_highlight_annot(quads_fragmento)
            annot.set_colors(fill=_HIGHLIGHT_COLOR)
            annot.set_info(content=tooltip, title="TCM Agente")
            annot.update()
            return True

    return False


def gerar_pdf_marcado(
    caminho_pdf: str | Path,
    resultado: ResultadoAnalise,
    caminho_saida: str | Path | None = None,
) -> Path:
    """
    Gera uma cópia do PDF original com os trechos das ocorrências marcados.

    Args:
        caminho_pdf: Caminho para o PDF original.
        resultado: ResultadoAnalise com as ocorrências a marcar.
        caminho_saida: Caminho do PDF de saída. Se None, usa
                       ``{nome}_marcado.pdf`` no mesmo diretório.

    Returns:
        Path do arquivo PDF gerado.

    Raises:
        FileNotFoundError: Se o PDF original não existir.
    """
    caminho = Path(caminho_pdf)
    if not caminho.exists():
        raise FileNotFoundError(f"PDF não encontrado: {caminho}")

    saida = Path(caminho_saida) if caminho_saida else caminho.with_stem(caminho.stem + "_marcado")

    total = len(resultado.ocorrencias)
    marcadas = 0

    with fitz.open(str(caminho)) as doc:
        n_paginas = len(doc)

        for oc in resultado.ocorrencias:
            idx = oc.pagina - 1
            if idx < 0 or idx >= n_paginas:
                logger.warning("Página %d fora do intervalo (%d páginas)", oc.pagina, n_paginas)
                continue

            if _marcar_ocorrencia(doc[idx], oc):
                marcadas += 1
            else:
                logger.warning(
                    "Trecho não localizado na página %d: %.70s…",
                    oc.pagina,
                    oc.trecho.replace("\n", " "),
                )

        doc.save(str(saida), garbage=4, deflate=True)

    logger.info(
        "PDF marcado salvo: %s — %d/%d ocorrência(s) marcada(s)",
        saida.name,
        marcadas,
        total,
    )
    return saida
