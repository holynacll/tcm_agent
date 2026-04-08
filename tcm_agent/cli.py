#!/usr/bin/env python3
"""
CLI do agente TCM-BA.

Uso:
    python -m tcm_agent.cli arquivo.pdf
    python -m tcm_agent.cli arquivo.pdf --paginas 1 5 10 --saida resultado.json
    python -m tcm_agent.cli arquivo.pdf --sem-prefiltro --sem-overlap --verbose
    python -m tcm_agent.cli arquivo.pdf --edicao 2765 --data 2026-03-07

    # Calibrar constantes de recorte (header/footer/colunas):
    python -m tcm_agent.cli --inspecionar arquivo.pdf
    python -m tcm_agent.cli --inspecionar arquivo.pdf --paginas 1 2 3
"""

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="tcm_agent",
        description="Analisa edições do Diário Oficial do TCM-BA em busca de "
        "menções à Prefeitura de Salvador.",
    )

    parser.add_argument(
        "pdf",
        type=str,
        help="Caminho para o arquivo PDF do Diário Oficial TCM-BA",
    )
    parser.add_argument(
        "-p",
        "--paginas",
        nargs="+",
        type=int,
        metavar="N",
        default=None,
        help="Páginas específicas a analisar (1-based). Ex: --paginas 1 3 5",
    )
    parser.add_argument(
        "-s",
        "--saida",
        type=str,
        default=None,
        metavar="arquivo.json",
        help="Arquivo de saída JSON. Se omitido, imprime no stdout.",
    )
    parser.add_argument(
        "--sem-prefiltro",
        action="store_true",
        help="Desabilita o pré-filtro determinístico (analisa todas as páginas).",
    )
    parser.add_argument(
        "--sem-overlap",
        action="store_true",
        help="Desabilita o contexto de sobreposição entre páginas.",
    )
    parser.add_argument(
        "--apenas-ocorrencias",
        action="store_true",
        help="Saída contém apenas o array de ocorrências (sem metadados).",
    )
    parser.add_argument(
        "--edicao",
        type=str,
        default=None,
        help="Número da edição do Diário (ex: 2765).",
    )
    parser.add_argument(
        "--data",
        type=str,
        default=None,
        help="Data de publicação no formato YYYY-MM-DD.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Chave da API Gemini (alternativa às variáveis GEMINI_API_KEY / GOOGLE_API_KEY).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Exibe progresso detalhado.",
    )
    parser.add_argument(
        "--inspecionar",
        action="store_true",
        help=(
            "Inspeciona o layout do PDF (dimensões, trechos de topo/base) para "
            "calibrar as constantes de recorte em extractor.py. "
            "Use --paginas para escolher quais páginas inspecionar (padrão: 1 e 2)."
        ),
    )

    args = parser.parse_args()

    caminho = Path(args.pdf)
    if not caminho.exists():
        print(f"Erro: arquivo não encontrado: {caminho}", file=sys.stderr)
        sys.exit(1)

    if args.inspecionar:
        from tcm_agent.extractor import inspecionar_layout
        inspecionar_layout(caminho, paginas=args.paginas)
        return

    # importa aqui para evitar custo de importação em --help
    from tcm_agent import Pipeline

    metadados = {}
    if args.edicao:
        metadados["edicao"] = args.edicao
    if args.data:
        metadados["data_publicacao"] = args.data

    pipeline = Pipeline(
        api_key=args.api_key,
        usar_prefiltro=not args.sem_prefiltro,
        usar_overlap=not args.sem_overlap,
        verbose=args.verbose,
    )

    resultado = pipeline.analisar_pdf(
        caminho_pdf=caminho,
        paginas=args.paginas,
        metadados=metadados or None,
    )

    # formata saída
    if args.apenas_ocorrencias:
        saida_json = resultado.to_ocorrencias_json()
    else:
        saida_json = resultado.to_json()

    if args.saida:
        Path(args.saida).write_text(saida_json, encoding="utf-8")
        if args.verbose:
            print(f"Resultado salvo em: {args.saida}")
    else:
        print(saida_json)


if __name__ == "__main__":
    main()
