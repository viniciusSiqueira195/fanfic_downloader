"""Registro e coordenação concorrente dos catálogos disponíveis."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

from books.models import PaginaLivros
from books.gutenberg import Gutenberg
from books.visionvox import Visionvox


FONTES_INDIVIDUAIS = {"Visionvox": Visionvox, "Project Gutenberg": Gutenberg}


class TodasFontes:
    nome = "Todas as fontes"

    def __init__(self, fontes=None):
        self.fontes = fontes or [fabrica() for fabrica in FONTES_INDIVIDUAIS.values()]

    def buscar_pagina(self, termo, formato="epub", pagina=0, progresso=None):
        livros, vistos, erros = [], set(), []
        tem_proxima = False
        nomes = {id(fonte): getattr(fonte, "nome", type(fonte).__name__) for fonte in self.fontes}
        if progresso:
            for fonte in self.fontes:
                progresso(nomes[id(fonte)], "consultando", 0)
        with ThreadPoolExecutor(max_workers=len(self.fontes), thread_name_prefix="catalogo") as executor:
            tarefas = {executor.submit(fonte.buscar_pagina, termo, formato, pagina): fonte
                       for fonte in self.fontes}
            respostas = []
            for tarefa in as_completed(tarefas):
                fonte = tarefas[tarefa]
                try:
                    resultado = tarefa.result()
                    respostas.append((fonte, resultado))
                    if progresso:
                        progresso(nomes[id(fonte)], "concluída", len(resultado.livros))
                except (requests.RequestException, ValueError) as erro:
                    erros.append(f"{nomes[id(fonte)]}: {erro}")
                    if progresso:
                        progresso(nomes[id(fonte)], "falhou", 0)
        # Mantém a ordem configurada estável, mesmo que as respostas cheguem fora de ordem.
        por_nome = {nomes[id(fonte)]: resultado for fonte, resultado in respostas}
        for fonte in self.fontes:
            resultado = por_nome.get(nomes[id(fonte)])
            if resultado is None:
                continue
            tem_proxima = tem_proxima or resultado.tem_proxima
            for livro in resultado.livros:
                chave = livro.url.casefold()
                if chave not in vistos:
                    vistos.add(chave)
                    livros.append(livro)
        if not livros and len(erros) == len(self.fontes):
            raise requests.RequestException("Nenhuma fonte respondeu à pesquisa.")
        aviso = " Algumas fontes falharam: " + "; ".join(erros) if erros else ""
        return PaginaLivros(livros, tem_proxima, aviso)

    def obter_sinopse(self, livro):
        fabrica = FONTES_INDIVIDUAIS.get(livro.origem)
        return fabrica().obter_sinopse(livro) if fabrica else livro.sinopse


FONTES = {"Todas as fontes": TodasFontes, **FONTES_INDIVIDUAIS}
