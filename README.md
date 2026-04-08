# tcm_agent — Agente TCM-BA: Prefeitura de Salvador

Agente Python que analisa edições do **Diário Oficial Eletrônico do Tribunal de Contas dos Municípios do Estado da Bahia (TCM-BA)** e identifica automaticamente todas as menções à Prefeitura de Salvador — incluindo entidades vinculadas (FCM, DESAL, COGEL etc.) e servidores municipais.

---

## Instalação

```bash
pip install -r tcm_agent/requirements.txt
```

Configure a chave da API:

```bash
export GEMINI_API_KEY=AIza...
# ou crie um arquivo .env com GEMINI_API_KEY=AIza...
```

---

## Uso rápido

### Python

```python
from tcm_agent import Pipeline

pipeline = Pipeline(verbose=True)

# A partir de um PDF
resultado = pipeline.analisar_pdf(
    "tcm_2026-03-07_completo.pdf",
    metadados={"edicao": "2765", "data_publicacao": "2026-03-07"},
)

# Exportar ocorrências como JSON
print(resultado.to_ocorrencias_json())

# Salvar em arquivo
with open("ocorrencias.json", "w", encoding="utf-8") as f:
    f.write(resultado.to_ocorrencias_json())
```

### CLI

```bash
# Análise completa de um PDF
python -m tcm_agent.cli diario.pdf --verbose

# Apenas páginas específicas, com metadados, salvo em arquivo
python -m tcm_agent.cli diario.pdf \
    --paginas 1 5 16 17 18 \
    --edicao 2765 \
    --data 2026-03-07 \
    --saida ocorrencias.json \
    --apenas-ocorrencias \
    --verbose

# Desabilitar pré-filtro (analisa todas as páginas sem triagem prévia)
python -m tcm_agent.cli diario.pdf --sem-prefiltro
```

---

## Formato de saída

Cada ocorrência no JSON segue este schema:

```json
{
  "pagina": 17,
  "tema_principal": "Prestação de Contas",
  "subtema": "Seleção de Entidades",
  "trecho": "SALVADOR Consolidada",
  "entidade_identificada": "Prefeitura de Salvador",
  "edicao": "2762",
  "data_publicacao": "2026-03-04",
  "arquivo_origem": "tcm_2026-03-04_completo.pdf"
}
```

**Temas possíveis:** `Notificação`, `Decisão Monocrática`, `Denúncia`, `Licitação`, `Contrato`, `Convênio`, `Pauta de Sessão`, `Ato da Presidência`, `Resolução`, `Prestação de Contas`, `Outro`

---

## Arquitetura

```
tcm_agent/
├── __init__.py      Exporta Pipeline, modelos e configurações
├── config.py        Organograma, servidores, builder do system prompt
├── prefiltro.py     Triagem determinística (regex) — evita chamadas desnecessárias
├── extractor.py     Extração de texto por página via pdfplumber
├── agent.py         Chamada à API Anthropic com retry exponencial + parser JSON
├── pipeline.py      Orquestra extração → pré-filtro → LLM → resultado
├── models.py        Dataclasses: Ocorrencia, ResultadoPagina, ResultadoAnalise
├── cli.py           Interface de linha de comando
└── requirements.txt
```

### Fluxo de processamento

```
PDF
 └─► extractor.py   (pdfplumber, por página, com overlap de 150 palavras)
      └─► prefiltro.py  (regex/normalização — descarta páginas sem menção)
           └─► agent.py     (API Anthropic, Claude Sonnet, retry exponencial)
                └─► models.py   (parse JSON, validação, normalização de tema)
                     └─► ResultadoAnalise (.to_json() / .to_ocorrencias_json())
```

### Decisões de design

| Decisão | Justificativa |
|---------|---------------|
| **Pré-filtro determinístico** | Reduz ~70% das chamadas API. Edições sem menção a Salvador são frequentes. |
| **Overlap de 150 palavras** | Captura referências anafóricas entre páginas ("o referido município"). |
| **System prompt com organograma completo** | LLM reconhece siglas (FCM, DESAL) sem contexto explícito de Salvador. |
| **Retry exponencial** | API pode retornar 429 em análises grandes. Retry com backoff evita falhas. |
| **Validação de tema_principal** | Match parcial normaliza variações como "Notificação/Secretaria" → "Notificação". |
| **Separação config/agent/pipeline** | Facilita testes unitários de cada camada individualmente. |

---

## Exemplos de ocorrências identificadas nos PDFs fornecidos

| Página | Arquivo | Tema | Entidade |
|--------|---------|------|----------|
| 17 | tcm_2026-03-04 | Prestação de Contas | Prefeitura de Salvador |
| 19 | tcm_2026-03-04 | Prestação de Contas | Câmara Municipal de Salvador |
| 22 | tcm_2026-03-04 | Prestação de Contas | FCM (Fundação Cidade Mãe) |
| 22 | tcm_2026-03-04 | Prestação de Contas | FGM (Fundação Gregório de Matos) |
| 22 | tcm_2026-03-04 | Prestação de Contas | FMLF (Fundação Mário Leal Ferreira) |
| 22 | tcm_2026-03-04 | Prestação de Contas | DESAL |
| 22 | tcm_2026-03-04 | Prestação de Contas | COGEL |
| 22 | tcm_2026-03-04 | Prestação de Contas | GCM |
| 13 | tcm_2026-03-04 | Notificação | Virgílio Teixeira Daltro (DESAL) |
| 23 | tcm_2026-03-04 | Prestação de Contas | Secretaria de Educação de Salvador |
| 23 | tcm_2026-03-04 | Prestação de Contas | Secretaria de Saúde de Salvador |
