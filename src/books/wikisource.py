"""Pesquisa na Wikisource e exportação oficial por meio do WS Export."""
from urllib.parse import urlencode

import requests

from books.cache import cachear_paginas
from books.catalog import CapacidadesCatalogo
from books.http import criar_cliente
from books.models import FORMATOS, HEADERS, Livro, PaginaLivros
from books.urls import validar_url_download

IDIOMAS = {"pt": "pt", "en": "en", "es": "es", "fr": "fr"}
FORMATOS_EXPORT = {"epub": "epub-3", "pdf": "pdf"}


class Wikisource:
    nome = "Wikisource"
    capacidades = CapacidadesCatalogo(frozenset(FORMATOS_EXPORT), frozenset(IDIOMAS))

    def __init__(self, http=None):
        self.http = http or criar_cliente()

    def buscar(self, termo, formato="epub", pagina=0, idioma=""):
        return self.buscar_pagina(termo, formato, pagina, idioma).livros

    @cachear_paginas()
    def buscar_pagina(self, termo, formato="epub", pagina=0, idioma=""):
        termo = termo.strip()
        if not termo:
            raise ValueError("Digite o título ou autor do livro.")
        if formato not in FORMATOS or pagina < 0:
            raise ValueError("Formato ou página inválidos.")
        if formato not in FORMATOS_EXPORT:
            return PaginaLivros([], False, " A Wikisource oferece EPUB e PDF.")
        lingua = IDIOMAS.get(idioma or "pt")
        if not lingua:
            return PaginaLivros([], False)
        consulta = termo.replace('"', " ").replace("\\", " ")
        resposta = self.http.get(
            f"https://{lingua}.wikisource.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": f'intitle:"{consulta}"',
                    "srnamespace": 0, "srlimit": 20, "sroffset": pagina * 20,
                    "srprop": "snippet", "format": "json", "utf8": 1},
            headers=HEADERS, timeout=(5, 12),
        )
        resposta.raise_for_status()
        dados = resposta.json()
        resultados = dados.get("query", {}).get("search")
        if not isinstance(resultados, list):
            raise ValueError("A Wikisource retornou uma resposta inesperada.")
        livros = []
        for item in resultados:
            titulo = str(item.get("title", "")).strip()
            # Subpáginas normalmente são capítulos, índices ou páginas digitalizadas.
            if not titulo or "/" in titulo:
                continue
            url = "https://ws-export.wmcloud.org/?" + urlencode({
                "lang": lingua, "page": titulo, "format": FORMATOS_EXPORT[formato]
            })
            validar_url_download(url, self.nome)
            livros.append(Livro(titulo, url, formato, self.nome, idioma=lingua))
        return PaginaLivros(livros, "continue" in dados)

    def obter_sinopse(self, livro):
        return livro.sinopse
