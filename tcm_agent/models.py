"""
Modelos de dados do agente TCM-BA.
Usa Pydantic para coerção e validação das respostas do LLM.
"""

import json
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, field_validator


class Ocorrencia(BaseModel):
    """Representa uma ocorrência identificada no Diário Oficial (saída do LLM)."""

    pagina: int
    secao: str = ""
    descricao: str = ""
    trecho: str
    entidade_identificada: list[str] = Field(default_factory=list)
    siglas_mapeadas: list[str] = Field(default_factory=list)
    entidades_mapeadas: list[str] = Field(default_factory=list)
    servidores_mapeados: list[str] = Field(default_factory=list)

    @field_validator("descricao", "trecho", mode="before")
    @classmethod
    def strip_str(cls, v: object) -> str:
        return str(v).strip()

    @field_validator(
        "entidade_identificada",
        "siglas_mapeadas",
        "entidades_mapeadas",
        "servidores_mapeados",
        mode="before",
    )
    @classmethod
    def coerce_list(cls, v: object) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if x]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []


@dataclass
class ResultadoPagina:
    """Resultado da análise de uma única página."""

    pagina: int
    texto_original: str
    passou_prefiltro: bool
    ocorrencias: list[Ocorrencia] = field(default_factory=list)
    erro: str | None = field(default=None)
    tokens_utilizados: int = 0

    @property
    def total_ocorrencias(self) -> int:
        return len(self.ocorrencias)


@dataclass
class ResultadoAnalise:
    """Resultado completo da análise de um documento ou conjunto de páginas."""

    arquivo: str
    total_paginas: int
    paginas_analisadas: int
    paginas_com_ocorrencias: int
    total_ocorrencias: int
    ocorrencias: list[Ocorrencia] = field(default_factory=list)
    erros: list[dict] = field(default_factory=list)
    tokens_totais: int = 0
    edicao: str | None = None
    data_publicacao: str | None = None

    def to_json(self, indent: int = 2) -> str:
        paginas_com_oc: set[int] = set()
        secoes: set[str] = set()
        siglas: set[str] = set()
        entidades: set[str] = set()
        servidores: set[str] = set()

        for oc in self.ocorrencias:
            paginas_com_oc.add(oc.pagina)
            if oc.secao:
                secoes.add(oc.secao)
            siglas.update(oc.siglas_mapeadas)
            entidades.update(oc.entidades_mapeadas)
            servidores.update(oc.servidores_mapeados)

        return json.dumps(
            {
                "diario": {
                    "edicao": self.edicao,
                    "data_publicacao": self.data_publicacao,
                    "arquivo_origem": self.arquivo,
                    "total_paginas": self.total_paginas,
                    "paginas_analisadas": self.paginas_analisadas,
                    "tokens_utilizados": self.tokens_totais,
                    "erros": self.erros,
                },
                "ocorrencias": [oc.model_dump() for oc in self.ocorrencias],
                "resumo": {
                    "total_ocorrencias": self.total_ocorrencias,
                    "paginas_com_ocorrencias": sorted(paginas_com_oc),
                    "secoes_unicas": sorted(secoes),
                    "siglas_unicas": sorted(siglas),
                    "entidades_unicas": sorted(entidades),
                    "servidores_unicos": sorted(servidores),
                },
            },
            ensure_ascii=False,
            indent=indent,
        )

    def to_ocorrencias_json(self, indent: int = 2) -> str:
        """Exporta apenas o array de ocorrências."""
        return json.dumps(
            [oc.model_dump() for oc in self.ocorrencias],
            ensure_ascii=False,
            indent=indent,
        )
