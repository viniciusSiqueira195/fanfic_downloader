"""Tipos compartilhados pelos catálogos de livros."""
from dataclasses import dataclass

FORMATOS = {"epub", "txt", "pdf"}
HEADERS = {"User-Agent": "FanficDownloader/ books (desktop accessibility application)"}


@dataclass(frozen=True)
class Livro:
    titulo: str
    url: str
    formato: str
    origem: str = "Visionvox"


@dataclass(frozen=True)
class PaginaLivros:
    livros: list[Livro]
    tem_proxima: bool
