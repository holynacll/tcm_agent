"""
Pré-filtro determinístico.

Antes de chamar a API (custo ~$), verifica rapidamente se a página
contém algum termo do organograma, nome de servidor ou variação.
Páginas sem nenhuma correspondência são ignoradas, economizando ~70%
das chamadas em edições sem menção a Salvador.
"""

from __future__ import annotations
import re
import unicodedata
from functools import lru_cache

from .config import ORGAOS, SERVIDORES


def _normalizar(texto: str) -> str:
    """Minúsculas + remove acentos + colapsa espaços extras."""
    sem_acento = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


@lru_cache(maxsize=1)
def _termos_normalizados() -> list[str]:
    """Constrói e cacheia a lista completa de termos para busca."""
    termos: set[str] = set()

    # termos fixos
    for t in [
        "salvador",
        "prefeitura de salvador",
        "municipio de salvador",
        "municipalidade de salvador",
        "secretaria de educacao de salvador",
        "secretaria de saude de salvador",
    ]:
        termos.add(_normalizar(t))

    # siglas e nomes do organograma
    for sigla, nome in ORGAOS.items():
        termos.add(_normalizar(sigla))
        termos.add(_normalizar(nome))
        # variações com "SALVADOR" sufixado
        termos.add(_normalizar(sigla + " SALVADOR"))
        termos.add(_normalizar(nome + " SALVADOR"))

    # servidores
    for srv in SERVIDORES:
        termos.add(_normalizar(srv["nome_completo"]))
        for v in srv.get("variacoes", []):
            termos.add(_normalizar(v))

    # remove termos muito curtos para evitar falsos positivos
    return [t for t in termos if len(t) >= 4]


def passou_prefiltro(texto: str) -> tuple[bool, list[str]]:
    """
    Verifica rapidamente se há qualquer menção a Salvador/entidades/servidores.

    Retorna:
        (passou, termos_encontrados)
        - passou: True se ao menos um termo foi encontrado
        - termos_encontrados: lista dos termos que geraram o match
    """
    texto_norm = _normalizar(texto)
    termos = _termos_normalizados()

    encontrados: list[str] = []
    for termo in termos:
        if termo in texto_norm:
            encontrados.append(termo)

    return bool(encontrados), encontrados
