"""
Pipeline principal de análise.

Orquestra o fluxo completo:
  PDF → extração por página → pré-filtro → LLM → JSON estruturado
"""

import logging
from pathlib import Path

from .agent import TCMAgente
from .extractor import PaginaTexto, contar_paginas, extrair_paginas
from .models import Ocorrencia, ResultadoAnalise, ResultadoPagina
from .prefiltro import passou_prefiltro

logger = logging.getLogger(__name__)


class Pipeline:
    """
    Pipeline de análise de edições do Diário Oficial do TCM-BA.

    Uso básico:
        from tcm_agent import Pipeline

        pipeline = Pipeline()
        resultado = pipeline.analisar_pdf("edicao.pdf")
        print(resultado.to_ocorrencias_json())

    Para textos já extraídos (sem PDF):
        resultado = pipeline.analisar_textos(
            textos={1: "texto da página 1", 2: "texto da página 2"},
            nome_arquivo="edicao_2026-03-07"
        )
    """

    def __init__(
        self,
        api_key: str | None = None,
        usar_prefiltro: bool = True,
        usar_overlap: bool = True,
        verbose: bool = False,
    ):
        """
        Args:
            api_key: Chave da API Gemini (ou use GEMINI_API_KEY / GOOGLE_API_KEY env var).
            usar_prefiltro: Se True, páginas sem termos de Salvador são ignoradas.
            usar_overlap: Se True, inclui contexto da página anterior no prompt.
            verbose: Se True, exibe progresso no stdout.
        """
        self._agente = TCMAgente(api_key=api_key)
        self._usar_prefiltro = usar_prefiltro
        self._usar_overlap = usar_overlap
        self._verbose = verbose

        if verbose:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            )

    # ─────────────────────────────────────────────
    # API pública
    # ─────────────────────────────────────────────

    def analisar_pdf(
        self,
        caminho_pdf: str | Path,
        paginas: list[int] | None = None,
        metadados: dict | None = None,
    ) -> ResultadoAnalise:
        """
        Analisa um arquivo PDF completo.

        Args:
            caminho_pdf: Caminho para o PDF.
            paginas: Lista de páginas (1-based) a processar. None = todas.
            metadados: Dicionário opcional com edicao, data_publicacao, etc.

        Returns:
            ResultadoAnalise com todas as ocorrências encontradas.
        """
        caminho = Path(caminho_pdf)
        self._log(f"Abrindo {caminho.name}…")

        total_paginas = contar_paginas(caminho)
        paginas_texto = extrair_paginas(
            caminho, paginas=paginas, overlap=self._usar_overlap
        )

        self._log(f"{len(paginas_texto)} página(s) extraídas de {total_paginas} total")

        resultados = self._processar_paginas(paginas_texto)
        return self._montar_resultado(
            nome_arquivo=caminho.name,
            total_paginas=total_paginas,
            resultados=resultados,
            metadados=metadados,
        )

    def analisar_textos(
        self,
        textos: dict[int, str],
        nome_arquivo: str = "texto_avulso",
        metadados: dict | None = None,
    ) -> ResultadoAnalise:
        """
        Analisa textos já extraídos (dict {numero_pagina: texto}).

        Útil para pipelines que já fazem a extração externamente ou
        para análise de páginas individuais via CLI/notebook.

        Args:
            textos: Dicionário {pagina: texto}.
            nome_arquivo: Nome do arquivo de origem (para metadados).
            metadados: Dicionário opcional com edicao, data_publicacao, etc.

        Returns:
            ResultadoAnalise com todas as ocorrências encontradas.
        """
        paginas_texto = []
        paginas_ordenadas = sorted(textos.keys())

        for i, num in enumerate(paginas_ordenadas):
            contexto = ""
            if self._usar_overlap and i > 0:
                anterior = textos[paginas_ordenadas[i - 1]]
                palavras = anterior.split()
                contexto = " ".join(palavras[-150:])

            paginas_texto.append(
                PaginaTexto(
                    numero=num,
                    texto=textos[num],
                    contexto_anterior=contexto,
                )
            )

        resultados = self._processar_paginas(paginas_texto)
        return self._montar_resultado(
            nome_arquivo=nome_arquivo,
            total_paginas=len(textos),
            resultados=resultados,
            metadados=metadados,
        )

    # ─────────────────────────────────────────────
    # Internos
    # ─────────────────────────────────────────────

    def _processar_paginas(self, paginas: list[PaginaTexto]) -> list[ResultadoPagina]:
        resultados: list[ResultadoPagina] = []

        for pagina in paginas:
            resultado = self._processar_pagina(pagina)
            resultados.append(resultado)

            if resultado.ocorrencias:
                self._log(
                    f"  → Página {pagina.numero}: "
                    f"{resultado.total_ocorrencias} ocorrência(s) encontrada(s)"
                )

        return resultados

    def _processar_pagina(self, pagina: PaginaTexto) -> ResultadoPagina:
        """Processa uma página: pré-filtro → LLM → ResultadoPagina."""
        # pré-filtro determinístico
        if self._usar_prefiltro:
            passou, termos = passou_prefiltro(pagina.texto)
            if not passou:
                self._log(f"  Página {pagina.numero}: ignorada pelo pré-filtro")
                return ResultadoPagina(
                    pagina=pagina.numero,
                    texto_original=pagina.texto,
                    passou_prefiltro=False,
                )
            self._log(
                f"  Página {pagina.numero}: pré-filtro OK "
                f"({len(termos)} termo(s): {', '.join(termos[:3])}…)"
            )
        else:
            passou = True

        # chamada ao LLM
        try:
            ocorrencias, tokens = self._agente.analisar_pagina(
                texto=pagina.texto_com_contexto,
                numero_pagina=pagina.numero,
            )
            return ResultadoPagina(
                pagina=pagina.numero,
                texto_original=pagina.texto,
                passou_prefiltro=passou,
                ocorrencias=ocorrencias,
                tokens_utilizados=tokens,
            )
        except Exception as e:
            logger.error("Erro ao analisar página %d: %s", pagina.numero, e)
            return ResultadoPagina(
                pagina=pagina.numero,
                texto_original=pagina.texto,
                passou_prefiltro=passou,
                erro=str(e),
            )

    def _montar_resultado(
        self,
        nome_arquivo: str,
        total_paginas: int,
        resultados: list[ResultadoPagina],
        metadados: dict | None,
    ) -> ResultadoAnalise:
        todas_ocorrencias: list[Ocorrencia] = []
        erros: list[dict] = []
        tokens_totais = 0
        paginas_com_ocorrencias = 0

        for r in resultados:
            tokens_totais += r.tokens_utilizados
            if r.erro:
                erros.append({"pagina": r.pagina, "erro": r.erro})
            if r.ocorrencias:
                paginas_com_ocorrencias += 1
                todas_ocorrencias.extend(r.ocorrencias)

        # ordena por página
        todas_ocorrencias.sort(key=lambda o: o.pagina)

        # deduplica: quando o LLM retorna o mesmo trecho múltiplas vezes,
        # mantém apenas a primeira ocorrência por (pagina, trecho).
        vistos: set[tuple[int, str]] = set()
        unicas: list[Ocorrencia] = []
        for oc in todas_ocorrencias:
            chave = (oc.pagina, oc.trecho.strip())
            if chave not in vistos:
                vistos.add(chave)
                unicas.append(oc)
        todas_ocorrencias = unicas

        analise = ResultadoAnalise(
            arquivo=nome_arquivo,
            total_paginas=total_paginas,
            paginas_analisadas=len(resultados),
            paginas_com_ocorrencias=paginas_com_ocorrencias,
            total_ocorrencias=len(todas_ocorrencias),
            ocorrencias=todas_ocorrencias,
            erros=erros,
            tokens_totais=tokens_totais,
            edicao=metadados.get("edicao") if metadados else None,
            data_publicacao=metadados.get("data_publicacao") if metadados else None,
        )

        self._log(
            f"\nAnálise concluída: {len(todas_ocorrencias)} ocorrência(s) "
            f"em {paginas_com_ocorrencias} página(s). "
            f"Tokens: {tokens_totais:,}"
        )
        return analise

    def _log(self, msg: str) -> None:
        if self._verbose:
            logger.info(msg)
