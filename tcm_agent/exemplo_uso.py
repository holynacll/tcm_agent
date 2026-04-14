"""
Exemplos de uso do agente TCM-BA.

Execute com:
    GEMINI_API_KEY=AIza... python exemplo_uso.py
"""

import json
import os
import sys
from pathlib import Path

# permite importar tcm_agent do diretório atual
sys.path.insert(0, str(Path(__file__).parent))

from tcm_agent import Pipeline, gerar_pdf_marcado


# ──────────────────────────────────────────────────────────────────────────────
# Exemplo 1: Analisar um PDF completo
# ──────────────────────────────────────────────────────────────────────────────
def exemplo_pdf_completo():
    """Analisa todas as páginas de um PDF."""
    pipeline = Pipeline(verbose=True)

    resultado = pipeline.analisar_pdf(
        caminho_pdf="tcm_2026-03-07_completo.pdf",
        metadados={
            "edicao": "2765",
            "data_publicacao": "2026-03-07",
        },
    )

    # exibe resumo
    print(f"\n{'=' * 60}")
    print(f"Arquivo: {resultado.arquivo}")
    print(
        f"Páginas analisadas: {resultado.paginas_analisadas}/{resultado.total_paginas}"
    )
    print(f"Ocorrências encontradas: {resultado.total_ocorrencias}")
    print(f"Tokens utilizados: {resultado.tokens_totais:,}")

    # salva JSON completo
    with open("resultado_completo.json", "w", encoding="utf-8") as f:
        f.write(resultado.to_json())
    print("Resultado salvo em resultado_completo.json")

    # salva apenas ocorrências
    with open("ocorrencias.json", "w", encoding="utf-8") as f:
        f.write(resultado.to_ocorrencias_json())
    print("Ocorrências salvas em ocorrencias.json")

    # gera PDF com trechos marcados
    pdf_marcado = gerar_pdf_marcado("tcm_2026-03-07_completo.pdf", resultado)
    print(f"PDF marcado salvo em {pdf_marcado}")


# ──────────────────────────────────────────────────────────────────────────────
# Exemplo 2: Analisar apenas páginas específicas
# ──────────────────────────────────────────────────────────────────────────────
def exemplo_paginas_selecionadas():
    """Analisa apenas as páginas 16 a 24 (seção de Atos Normativos)."""
    pipeline = Pipeline(verbose=True)

    resultado = pipeline.analisar_pdf(
        caminho_pdf="tcm_2026-03-04_completo.pdf",
        paginas=list(range(16, 25)),  # páginas 16-24
        metadados={"edicao": "2762", "data_publicacao": "2026-03-04"},
    )

    print(f"\nOcorrências: {resultado.total_ocorrencias}")
    for oc in resultado.ocorrencias:
        print(f"  p.{oc.pagina} [{oc.secao}] {', '.join(oc.entidade_identificada)}")


# ──────────────────────────────────────────────────────────────────────────────
# Exemplo 3: Analisar texto já extraído (sem PDF)
# ──────────────────────────────────────────────────────────────────────────────
def exemplo_texto_direto():
    """
    Para quando o texto já foi extraído externamente.
    Útil em notebooks ou integrações com outros pipelines.
    """
    pipeline = Pipeline(verbose=True)

    textos = {
        1: """
        RESOLUÇÃO Nº 1506/2026
        Divulga as entidades selecionadas para fins de instrução e julgamento,
        referentes ao exercício de 2025.
        PREFEITURAS CONTAS MENSAIS
        SALVADOR Consolidada
        CAMAÇARI Consolidada
        LAURO DE FREITAS Consolidada
        """,
        2: """
        CÂMARAS CONTAS MENSAIS
        SALVADOR Individualizada
        CAMAÇARI Individualizada
        DESCENTRALIZADAS SELECIONADAS MUNICÍPIOS
        Fundação Cidade Mãe SALVADOR FCM SALVADOR Individualizada
        Fundação Gregório de Matos SALVADOR FGM SALVADOR Individualizada
        Fundação Mário Leal Ferreira SALVADOR FMLF SALVADOR Individualizada
        Companhia de Desenvolvimento Urbano de Salvador DESAL SALVADOR Individualizada
        Companhia de Governança Eletrônica do Salvador COGEL SALVADOR Individualizada
        Guarda Civil Municipal GCM SALVADOR Individualizada
        SECRETARIAS
        Secretaria de Educação de Salvador Consolidada
        Secretaria de Saúde de Salvador Consolidada
        """,
        3: """
        EDITAL Nº 233/2026
        O PRESIDENTE DO TRIBUNAL DE CONTAS DOS MUNICÍPIOS DO ESTADO DA BAHIA,
        notifica o Sr. Virgílio Teixeira Daltro, Diretor-Presidente da
        Companhia de Desenvolvimento Urbano de Salvador - DESAL,
        para que apresente manifestação no prazo de 05 (cinco) dias corridos,
        acerca dos fatos constantes dos autos do Processo e-TCM nº 04913e26.
        """,
    }

    resultado = pipeline.analisar_textos(
        textos=textos,
        nome_arquivo="edicao_2762_trecho",
        metadados={"edicao": "2762", "data_publicacao": "2026-03-04"},
    )

    print(f"\n{resultado.total_ocorrencias} ocorrência(s) encontrada(s):")
    ocorrencias_json = json.loads(resultado.to_ocorrencias_json())
    for oc in ocorrencias_json:
        print(f"""
  Página:    {oc["pagina"]}
  Seção:     {oc["secao"]}
  Entidade:  {", ".join(oc["entidade_identificada"])}
  Trecho:    {oc["trecho"][:120]}…
""")


# ──────────────────────────────────────────────────────────────────────────────
# Exemplo 4: Processar múltiplos PDFs em lote
# ──────────────────────────────────────────────────────────────────────────────
def exemplo_lote():
    """Processa todas as edições de um diretório."""
    diretorio = Path("./diarios")
    if not diretorio.exists():
        print("Diretório ./diarios não encontrado. Pulando exemplo de lote.")
        return

    pipeline = Pipeline(verbose=True)
    todas_ocorrencias = []

    for pdf in sorted(diretorio.glob("tcm_*.pdf")):
        print(f"\nProcessando: {pdf.name}")
        resultado = pipeline.analisar_pdf(pdf)
        todas_ocorrencias.extend([oc.model_dump() for oc in resultado.ocorrencias])

    # consolida tudo em um único JSON
    saida = json.dumps(todas_ocorrencias, ensure_ascii=False, indent=2)
    Path("ocorrencias_consolidadas.json").write_text(saida, encoding="utf-8")
    print(f"\nTotal consolidado: {len(todas_ocorrencias)} ocorrência(s)")


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("ERRO: Variável GEMINI_API_KEY não definida.")
        print("      Execute: export GEMINI_API_KEY=sk-ant-...")
        sys.exit(1)

    print("Executando Exemplo 3 (texto direto — não requer PDF)…\n")
    exemplo_texto_direto()

    # Descomente para executar os demais exemplos:
    # exemplo_pdf_completo()
    # exemplo_paginas_selecionadas()
    # exemplo_lote()
