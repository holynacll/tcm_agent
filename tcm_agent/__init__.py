"""
tcm_agent — Agente de análise do Diário Oficial do TCM-BA.

Identifica menções à Prefeitura de Salvador (entidades, siglas, servidores)
em edições do Diário Oficial Eletrônico do Tribunal de Contas dos Municípios
do Estado da Bahia.

Uso rápido:
    from tcm_agent import Pipeline

    pipeline = Pipeline(verbose=True)
    resultado = pipeline.analisar_pdf("tcm_2026-03-07_completo.pdf")

    # JSON com todas as ocorrências
    print(resultado.to_ocorrencias_json())

    # salvar em arquivo
    with open("ocorrencias.json", "w", encoding="utf-8") as f:
        f.write(resultado.to_ocorrencias_json())
"""

from .pipeline import Pipeline
from .models import Ocorrencia, ResultadoAnalise, ResultadoPagina
from .config import ORGAOS, SERVIDORES

__all__ = [
    "Pipeline",
    "Ocorrencia",
    "ResultadoAnalise",
    "ResultadoPagina",
    "ORGAOS",
    "SERVIDORES",
]
