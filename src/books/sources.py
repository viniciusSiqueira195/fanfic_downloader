"""Registro e coordenação concorrente dos catálogos disponíveis."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import requests

from books.models import PaginaLivros
from books.gutenberg import Gutenberg
from books.visionvox import Visionvox
from scrapers.search_relevance import normalizar, termos_significativos


FONTES_INDIVIDUAIS = {"Visionvox": Visionvox, "Project Gutenberg": Gutenberg}


def _pontuacao(livro, termo):
    consulta = normalizar(termo)
    titulo = normalizar(livro.titulo)
    tokens = termos_significativos(consulta)
    encontrados = sum(token in titulo.split() for token in tokens)
    return (titulo == consulta, consulta in titulo, encontrados, -len(titulo))


def _duplicado(livro, existentes):
    tokens = set(termos_significativos(livro.titulo.rsplit(".", 1)[0]))
    if not tokens:
        return False
    for existente in existentes:
        outros = set(termos_significativos(existente.titulo.rsplit(".", 1)[0]))
        uniao = tokens | outros
        if livro.formato == existente.formato and uniao and len(tokens & outros) / len(uniao) >= .8:
            return True
    return False


class TodasFontes:
    nome = "Todas as fontes"

    def __init__(self, fontes=None):
        self.fontes = fontes or [fabrica() for fabrica in FONTES_INDIVIDUAIS.values()]

    def buscar_pagina(self, termo, formato="epub", pagina=0, progresso=None, cancel_event=None):
        livros, vistos, erros = [], set(), []
        tem_proxima = False
        nomes = {id(fonte): getattr(fonte, "nome", type(fonte).__name__) for fonte in self.fontes}
        if progresso:
            for fonte in self.fontes:
                progresso(nomes[id(fonte)], "consultando", 0, [])
        executor = ThreadPoolExecutor(max_workers=len(self.fontes), thread_name_prefix="catalogo")
        tarefas = {executor.submit(fonte.buscar_pagina, termo, formato, pagina): fonte
                   for fonte in self.fontes}
        respostas = []
        pendentes = set(tarefas)
        try:
            while pendentes:
                if cancel_event is not None and cancel_event.is_set():
                    raise requests.RequestException("Pesquisa cancelada.")
                concluidas, pendentes = wait(pendentes, timeout=.1, return_when=FIRST_COMPLETED)
                for tarefa in concluidas:
                    fonte = tarefas[tarefa]
                    try:
                        resultado = tarefa.result()
                        respostas.append((fonte, resultado))
                        if progresso:
                            progresso(nomes[id(fonte)], "concluída", len(resultado.livros),
                                      resultado.livros)
                    except (requests.RequestException, ValueError) as erro:
                        erros.append(f"{nomes[id(fonte)]}: {erro}")
                        if progresso:
                            progresso(nomes[id(fonte)], "falhou", 0, [])
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        # Mantém a ordem configurada estável, mesmo que as respostas cheguem fora de ordem.
        por_nome = {nomes[id(fonte)]: resultado for fonte, resultado in respostas}
        for fonte in self.fontes:
            resultado = por_nome.get(nomes[id(fonte)])
            if resultado is None:
                continue
            tem_proxima = tem_proxima or resultado.tem_proxima
            for livro in resultado.livros:
                chave = livro.url.casefold()
                if chave not in vistos and not _duplicado(livro, livros):
                    vistos.add(chave)
                    livros.append(livro)
        if not livros and len(erros) == len(self.fontes):
            raise requests.RequestException("Nenhuma fonte respondeu à pesquisa.")
        aviso = " Algumas fontes falharam: " + "; ".join(erros) if erros else ""
        livros.sort(key=lambda livro: _pontuacao(livro, termo), reverse=True)
        return PaginaLivros(livros, tem_proxima, aviso)

    def verificar_saude(self):
        estados = []
        for fonte in self.fontes:
            nome = getattr(fonte, "nome", type(fonte).__name__)
            try:
                fonte.buscar_pagina("Dom Casmurro", "epub", 0)
                estados.append((nome, True, "respondendo"))
            except (requests.RequestException, ValueError) as erro:
                estados.append((nome, False, str(erro)))
        return estados

    def obter_sinopse(self, livro):
        fabrica = FONTES_INDIVIDUAIS.get(livro.origem)
        return fabrica().obter_sinopse(livro) if fabrica else livro.sinopse


FONTES = {"Todas as fontes": TodasFontes, **FONTES_INDIVIDUAIS}
