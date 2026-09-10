"""Contrato comum implementado pelos catálogos de livros."""
from dataclasses import dataclass
from typing import Callable, Protocol

from books.models import Livro, PaginaLivros

ProgressoBusca = Callable[[str, str, int], None]


@dataclass(frozen=True)
class CapacidadesCatalogo:
    formatos: frozenset[str]
    idiomas: frozenset[str]
    descoberta: bool = False


class CatalogoLivros(Protocol):
    nome: str

    def buscar_pagina(self, termo: str, formato: str = "epub", pagina: int = 0,
                      idioma: str = "") -> PaginaLivros: ...

    def obter_sinopse(self, livro: Livro) -> str: ...
