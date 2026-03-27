"""
Modelos de dados do agente TCM-BA.
Usa dataclasses + validação manual para manter compatibilidade sem pydantic obrigatório.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass
class Ocorrencia:
    """Representa uma ocorrência identificada no Diário Oficial."""

    pagina: int
    tema_principal: str
    subtema: Optional[str]
    trecho: str
    entidade_identificada: str

    # metadados opcionais gerados pelo pipeline
    edicao: Optional[str] = field(default=None)
    data_publicacao: Optional[str] = field(default=None)
    arquivo_origem: Optional[str] = field(default=None)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict, pagina: int) -> "Ocorrencia":
        return cls(
            pagina=data.get("pagina", pagina),
            tema_principal=data.get("tema_principal", "Outro"),
            subtema=data.get("subtema") or None,
            trecho=data.get("trecho", ""),
            entidade_identificada=data.get("entidade_identificada", ""),
        )


@dataclass
class ResultadoPagina:
    """Resultado da análise de uma única página."""

    pagina: int
    texto_original: str
    passou_prefiltro: bool
    ocorrencias: list[Ocorrencia] = field(default_factory=list)
    erro: Optional[str] = field(default=None)
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

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(
            {
                "metadados": {
                    "arquivo": self.arquivo,
                    "total_paginas": self.total_paginas,
                    "paginas_analisadas": self.paginas_analisadas,
                    "paginas_com_ocorrencias": self.paginas_com_ocorrencias,
                    "total_ocorrencias": self.total_ocorrencias,
                    "tokens_totais": self.tokens_totais,
                    "erros": self.erros,
                },
                "ocorrencias": [o.to_dict() for o in self.ocorrencias],
            },
            ensure_ascii=False,
            indent=indent,
        )

    def to_ocorrencias_json(self, indent: int = 2) -> str:
        """Exporta apenas o array de ocorrências (formato solicitado)."""
        return json.dumps(
            [o.to_dict() for o in self.ocorrencias],
            ensure_ascii=False,
            indent=indent,
        )
