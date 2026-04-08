"""
Configurações centrais do agente TCM-BA Salvador.
Contém o organograma completo, lista de servidores e builder do system prompt.
"""

ORGAOS: dict[str, str] = {
    "GABP": "Gabinete do Prefeito",
    "SACPB": "Secretaria Municipal de Articulação Comunitária e Prefeituras-Bairro",
    "SEGOV": "Secretaria de Governo",
    "GABVP": "Gabinete da Vice-Prefeitura",
    "CGM": "Controladoria Geral do Município",
    "PGMS": "Procuradoria Geral do Município de Salvador",
    "CASACIVIL": "Casa Civil",
    "SECOM": "Secretaria Municipal de Comunicação",
    "SEMGE": "Secretaria Municipal de Gestão",
    "SEMIT": "Secretaria Municipal de Inovação e Tecnologia",
    "SEFAZ": "Secretaria Municipal da Fazenda",
    "SEDUR": "Secretaria Municipal de Desenvolvimento Urbano",
    "SECIS": "Secretaria Municipal de Sustentabilidade, Resiliência e Bem-Estar e Proteção Animal",
    "SECULT": "Secretaria Municipal de Cultura e Turismo",
    "SEMDEC": "Secretaria Municipal de Desenvolvimento Econômico, Emprego e Renda",
    "SMED": "Secretaria Municipal da Educação",
    "SMS": "Secretaria Municipal da Saúde",
    "SEMPRE": "Secretaria Municipal de Promoção Social, Combate à Pobreza, Esportes e Lazer",
    "SEMUR": "Secretaria Municipal da Reparação",
    "SPMJ": "Secretaria Municipal de Políticas para Mulheres, Infância e Juventude",
    "SEINFRA": "Secretaria Municipal de Infraestrutura e Obras Públicas",
    "SEMAN": "Secretaria Municipal de Manutenção da Cidade",
    "SEMOP": "Secretaria Municipal de Ordem Pública",
    "SEMOB": "Secretaria Municipal de Mobilidade",
    "ARSAL": "Agência Reguladora e Fiscalizadora dos Serviços Públicos de Salvador",
    "SUCOP": "Superintendência de Conservação e Obras Públicas",
    "SALTUR": "Empresa Salvador Turismo",
    "FCM": "Fundação Cidade Mãe",
    "FGM": "Fundação Gregório de Matos",
    "FMLF": "Fundação Mário Leal Ferreira",
    "DPR": "Diretoria de Previdência do Servidor",
    "FUMPRES": "Fundo Municipal de Previdência de Salvador",
    "DESAL": "Companhia de Desenvolvimento Urbano de Salvador",
    "GCM": "Guarda Civil Municipal",
    "COGEL": "Companhia de Governança Eletrônica de Salvador",
    "CODESAL": "Defesa Civil de Salvador",
    "CODECON": "Coordenadoria de Defesa do Consumidor",
    "LIMPURB": "Empresa de Limpeza Urbana de Salvador",
    "CDEMS": "Companhia de Desenvolvimento e Mobilização de Ativos de Salvador",
    "SALVADORPAR": "SalvadorPar",
    "TRANSALVADOR": "Superintendência de Trânsito de Salvador",
}

SERVIDORES: list[dict] = [
    {"nome_completo": "Bruno Soares Reis", "variacoes": ["Bruno Reis"]},
    {"nome_completo": "Luciano Ricardo Gomes de Sandes", "variacoes": ["Luciano Sandes"]},
    {"nome_completo": "Carlos Felipe Vazquez de Souza Leão", "variacoes": []},
    {"nome_completo": "Ana Paula Andrade Matos", "variacoes": ["Ana Paula Matos"]},
    {"nome_completo": "Maria Rita Góes Garrido", "variacoes": ["Rita Garrido"]},
    {"nome_completo": "Eduardo Carvalho Vaz Porto", "variacoes": ["Eduardo Porto"]},
    {"nome_completo": "Luiz Antônio Vasconcellos Carreira", "variacoes": ["Luiz Carreira"]},
    {"nome_completo": "Renata Gendiroba Vidal", "variacoes": []},
    {"nome_completo": "Alexandre Almeida Tinoco", "variacoes": []},
    {"nome_completo": "Alberto Vianna Braga Neto", "variacoes": ["Alberto Braga"]},
    {"nome_completo": "Giovanna Guiotti Testa Victer", "variacoes": ["Giovana Victer"]},
    {"nome_completo": "João Xavier Nunes Filho", "variacoes": ["João Xavier"]},
    {"nome_completo": "Ivan Euler Pereira de Paiva", "variacoes": ["Ivan Euler"]},
    {"nome_completo": "Mila Correia Gonçalves Paes Scarton", "variacoes": ["Mila Paes"]},
    {"nome_completo": "Thiago Martins Dantas", "variacoes": ["Thiago Dantas"]},
    {"nome_completo": "Rodrigo Santos Alves", "variacoes": ["Rodrigo Alves"]},
    {"nome_completo": "Antônio José da Cruz Júnior Magalhães", "variacoes": ["Júnior Magalhães"]},
    {"nome_completo": "Isaura Genoveva de Oliveira Neta", "variacoes": ["Isaura Genoveva"]},
    {"nome_completo": "Fernanda Silva Lordelo", "variacoes": ["Fernanda Lordelo"]},
    {"nome_completo": "Luiz Carlos de Souza", "variacoes": []},
    {"nome_completo": "Lázaro França Jezler Filho", "variacoes": []},
    {"nome_completo": "Décio Martins Mendes Filho", "variacoes": []},
    {"nome_completo": "Pablo Silva Souza", "variacoes": ["Pablo Souza"]},
    {"nome_completo": "Andrea Almeida Mendonça", "variacoes": []},
    {"nome_completo": "Jeancleydson de Almeida Sacramento", "variacoes": ["Jeancleydson Sacramento"]},
    {"nome_completo": "Orlando Cezar da Costa Castro", "variacoes": []},
    {"nome_completo": "Isaac Chaves Edington", "variacoes": []},
    {"nome_completo": "Isabela Argolo de Almeida", "variacoes": ["Isabela Almeida"]},
    {"nome_completo": "Fernando Ferreira de Carvalho", "variacoes": []},
    {"nome_completo": "Tânia Maria Scofield Souza Almeida", "variacoes": ["Tânia Scofield"]},
    {"nome_completo": "Daniel Ribeiro Silva", "variacoes": ["Daniel Ribeiro"]},
    {"nome_completo": "Virgílio Teixeira Daltro", "variacoes": ["Virgílio Daltro"]},
    {"nome_completo": "Humberto Costa Sturaro Filho", "variacoes": ["Humberto Sturaro"]},
    {"nome_completo": "Samuel Pereira Araújo", "variacoes": ["Samuel Araújo"]},
    {"nome_completo": "Sosthenes Tavares de Macêdo Almeida", "variacoes": ["Sosthenes Macêdo"]},
    {"nome_completo": "Talita Silva Vilarinho da Silva", "variacoes": []},
    {"nome_completo": "Carlos Augusto da Silva Gomes", "variacoes": ["Carlos Gomes"]},
    {"nome_completo": "Marcos Lessa Mendes", "variacoes": ["Marcos Lessa"]},
    {"nome_completo": "Diego Costa de Brito", "variacoes": []},
]

# Termos de busca diretos para o pré-filtro determinístico
TERMOS_DIRETOS: list[str] = [
    "salvador",
    "prefeitura de salvador",
    "município de salvador",
    # siglas do organograma
    *ORGAOS.keys(),
    # nomes completos das entidades
    *ORGAOS.values(),
]

# Temas principais válidos
TEMAS_VALIDOS: list[str] = [
    "Notificação",
    "Decisão Monocrática",
    "Denúncia",
    "Licitação",
    "Contrato",
    "Convênio",
    "Pauta de Sessão",
    "Ato da Presidência",
    "Resolução",
    "Prestação de Contas",
    "Outro",
]


def build_system_prompt() -> str:
    """Constrói o system prompt injetando o organograma e servidores completos."""

    orgaos_txt = "\n".join(
        f"  - {sigla}: {nome}" for sigla, nome in ORGAOS.items()
    )

    servidores_txt = "\n".join(
        "  - " + s["nome_completo"] +
        (f"  (também: {', '.join(s['variacoes'])})" if s["variacoes"] else "")
        for s in SERVIDORES
    )

    temas_txt = ", ".join(f'"{t}"' for t in TEMAS_VALIDOS)

    return f"""Você é um analista especializado em documentos do Diário Oficial do Tribunal de Contas dos Municípios do Estado da Bahia (TCM-BA).

MISSÃO: Identificar TODAS as menções diretas ou indiretas à Prefeitura de Salvador e às suas entidades vinculadas no texto fornecido.

━━━ ORGANOGRAMA DA PREFEITURA DE SALVADOR ━━━
{orgaos_txt}

━━━ SERVIDORES DA PREFEITURA DE SALVADOR ━━━
{servidores_txt}

━━━ REGRAS DE IDENTIFICAÇÃO ━━━
Considere como menção à Prefeitura de Salvador QUALQUER ocorrência de:
1. Nomes diretos: "Prefeitura de Salvador", "Prefeitura Municipal de Salvador", "Município de Salvador", "Municipalidade de Salvador"
2. Siglas do organograma acima (mesmo sem contexto explícito de Salvador)
3. Nomes completos das entidades do organograma acima
4. Variações como "Secretaria de Educação de Salvador", "Secretaria de Saúde de Salvador", "FCM SALVADOR", "FGM SALVADOR", "FMLF SALVADOR"
5. Servidores listados acima: tanto o nome completo quanto as variações
6. Referências anafóricas claras ("o referido município" após menção prévia a Salvador)

━━━ EXCLUSÕES — NÃO REGISTRE COMO OCORRÊNCIA ━━━
1. Linha de local/data de assinatura: frases como "Salvador, em DD de mês de AAAA", "Salvador - BA, DD de mês de AAAA", "Salvador (BA), DD de mês de AAAA" — indicam apenas onde o ato foi lavrado, não que a Prefeitura de Salvador é parte.
2. Notificações cujo CONTEÚDO não menciona entidade/servidor da Prefeitura: se "Salvador" aparece somente na assinatura/fecho ("Salvador, em..."), ignore o ato inteiramente.
3. Endereço do próprio TCM-BA: qualquer linha com "Centro Administrativo da Bahia", "CAB", "Salvador-BA" referindo-se ao endereço do tribunal.
4. Menções a "Salvador" como mera referência geográfica genérica sem relação com a Prefeitura (ex: "nascido em Salvador", "residente em Salvador").

━━━ FORMATO DE SAÍDA ━━━
Responda APENAS com um array JSON válido. Cada elemento deve ter EXATAMENTE estas chaves:
- "tema_principal": uma das opções: {temas_txt}
- "trecho": o parágrafo ou sentença COMPLETA onde a menção ocorre (mínimo uma frase com contexto)
- "entidade_identificada": entidade ou servidor identificado (ex: "Prefeitura de Salvador", "DESAL", "FCM", "Virgílio Teixeira Daltro", "Secretaria de Educação de Salvador")

Se não houver nenhuma menção: retorne []
NÃO inclua texto fora do JSON. NÃO use markdown. NÃO use blocos de código.
"""
