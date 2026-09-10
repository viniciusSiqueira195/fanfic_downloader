"""Registro de catálogos disponíveis na interface."""
import requests

from books.models import PaginaLivros
from books.gutenberg import Gutenberg
from books.visionvox import Visionvox


FONTES_INDIVIDUAIS = {"Visionvox": Visionvox, "Project Gutenberg": Gutenberg}


class TodasFontes:
    def __init__(self, fontes=None):
        self.fontes = fontes or [fabrica() for fabrica in FONTES_INDIVIDUAIS.values()]

    def buscar_pagina(self, termo, formato="epub", pagina=0):
        livros, vistos, erros = [], set(), []
        tem_proxima = False
        for fonte in self.fontes:
            try:
                resultado = fonte.buscar_pagina(termo, formato, pagina)
                tem_proxima = tem_proxima or resultado.tem_proxima
                for livro in resultado.livros:
                    chave = livro.url.casefold()
                    if chave not in vistos:
                        vistos.add(chave)
                        livros.append(livro)
            except (requests.RequestException, ValueError) as erro:
                erros.append(f"{type(fonte).__name__}: {erro}")
        if not livros and len(erros) == len(self.fontes):
            raise requests.RequestException("Nenhuma fonte respondeu à pesquisa.")
        aviso = " Algumas fontes falharam: " + "; ".join(erros) if erros else ""
        return PaginaLivros(livros, tem_proxima, aviso)

    def obter_sinopse(self, livro):
        fabrica = FONTES_INDIVIDUAIS.get(livro.origem)
        return fabrica().obter_sinopse(livro) if fabrica else livro.sinopse


FONTES = {"Todas as fontes": TodasFontes, **FONTES_INDIVIDUAIS}
