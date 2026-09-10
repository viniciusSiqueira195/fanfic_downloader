"""Catálogo Project Gutenberg consultado pela API independente Gutendex."""
import requests

from books.models import Livro, PaginaLivros, HEADERS
from books.urls import validar_url_download

MIMES = {"epub": "application/epub+zip", "txt": "text/plain", "pdf": "application/pdf"}


class Gutenberg:
    nome = "Project Gutenberg"
    def __init__(self, http=None):
        self.http = http or requests

    def buscar(self, termo, formato="epub", pagina=0):
        return self.buscar_pagina(termo, formato, pagina).livros

    def buscar_pagina(self, termo, formato="epub", pagina=0):
        if not termo.strip():
            raise ValueError("Digite o título ou autor do livro.")
        if formato not in MIMES or pagina < 0:
            raise ValueError("Formato ou página inválidos.")
        resposta = self.http.get(
            "https://gutendex.com/books/",
            params={"search": termo.strip(), "mime_type": MIMES[formato], "page": pagina + 1},
            headers=HEADERS, timeout=(10, 30),
        )
        resposta.raise_for_status()
        dados = resposta.json()
        if not isinstance(dados, dict) or not isinstance(dados.get("results"), list):
            raise ValueError("O catálogo do Gutenberg retornou uma resposta inesperada.")
        livros, vistos = [], set()
        for item in dados["results"]:
            # Dá preferência ao TXT UTF-8, mantendo o arquivo original.
            formatos = sorted(item.get("formats", {}).items(), key=lambda par: "utf-8" not in par[0].lower())
            for mime, url in formatos:
                if mime.split(";", 1)[0].strip() != MIMES[formato]:
                    continue
                try:
                    validar_url_download(url, "Project Gutenberg")
                except ValueError:
                    continue
                if url not in vistos:
                    vistos.add(url)
                    titulo = item.get("title") or "Livro sem título"
                    autores = ", ".join(a["name"] for a in item.get("authors", []) if a.get("name"))
                    if autores:
                        titulo += " — " + autores
                    sinopse = "\n\n".join(str(s).strip() for s in item.get("summaries", []) if str(s).strip())
                    idiomas = ", ".join(item.get("languages", []))
                    livros.append(Livro(titulo, url, formato, "Project Gutenberg", sinopse,
                                        autores, idiomas))
                break
        return PaginaLivros(livros, bool(dados.get("next")))

    def obter_sinopse(self, livro):
        return livro.sinopse
