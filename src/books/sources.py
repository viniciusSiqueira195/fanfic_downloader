"""Registro e coordenação concorrente dos catálogos disponíveis."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from time import monotonic
import requests

from books.models import PaginaLivros
from books.gutenberg import Gutenberg
from books.internet_archive import InternetArchive
from books.visionvox import Visionvox
from books.wikisource import Wikisource
from scrapers.search_relevance import normalizar, termos_significativos


FONTES_INDIVIDUAIS = {
    "Visionvox": Visionvox,
    "Project Gutenberg": Gutenberg,
    "Wikisource": Wikisource,
    "Internet Archive": InternetArchive,
}
MINIMO_RESULTADOS_RAPIDOS = 5
MAX_ESPERA_DESCOBERTA = 18


def _pontuacao(livro, termo):
    consulta = normalizar(termo)
    titulo = normalizar(livro.titulo)
    tokens = termos_significativos(consulta)
    encontrados = sum(token in titulo.split() for token in tokens)
    return (titulo == consulta, consulta in titulo, encontrados, -len(titulo))


def _duplicado(livro, existentes):
    titulo_livro = livro.titulo.split(" — ", 1)[0] if livro.autor else livro.titulo
    tokens = set(termos_significativos(titulo_livro.rsplit(".", 1)[0]))
    if not tokens:
        return False
    for existente in existentes:
        titulo_existente = (existente.titulo.split(" — ", 1)[0]
                            if existente.autor else existente.titulo)
        outros = set(termos_significativos(titulo_existente.rsplit(".", 1)[0]))
        uniao = tokens | outros
        if livro.formato == existente.formato and uniao and len(tokens & outros) / len(uniao) >= .8:
            return True
    return False


class TodasFontes:
    nome = "Todas as fontes"
    capacidades = None

    def __init__(self, fontes=None):
        self.fontes = fontes or [fabrica() for fabrica in FONTES_INDIVIDUAIS.values()]

    def buscar_pagina(self, termo, formato="epub", pagina=0, idioma="", progresso=None,
                      cancel_event=None):
        livros, vistos, erros = [], set(), []
        tem_proxima = False
        nomes = {id(fonte): getattr(fonte, "nome", type(fonte).__name__) for fonte in self.fontes}
        if progresso:
            for fonte in self.fontes:
                progresso(nomes[id(fonte)], "consultando", 0, [])
        executor = ThreadPoolExecutor(max_workers=len(self.fontes), thread_name_prefix="catalogo")
        tarefas = {executor.submit(fonte.buscar_pagina, termo, formato, pagina, idioma): fonte
                   for fonte in self.fontes}
        respostas = []
        pendentes = set(tarefas)
        resposta_rapida = False
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
                        if len(resultado.livros) >= MINIMO_RESULTADOS_RAPIDOS:
                            resposta_rapida = bool(pendentes)
                            break
                    except (requests.RequestException, ValueError) as erro:
                        erros.append(f"{nomes[id(fonte)]}: {erro}")
                        if progresso:
                            progresso(nomes[id(fonte)], "falhou", 0, [])
                if resposta_rapida:
                    break
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
        if resposta_rapida:
            aviso = " Outros catálogos ainda estavam demorando; escolha uma fonte específica para consultá-los."
        else:
            aviso = " Algumas fontes falharam: " + "; ".join(erros) if erros else ""
        livros.sort(key=lambda livro: _pontuacao(livro, termo), reverse=True)
        return PaginaLivros(livros, tem_proxima, aviso)

    def explorar_pagina(self, formato="epub", pagina=0, idioma="pt", topico=""):
        fontes = [fonte for fonte in self.fontes
                  if getattr(getattr(fonte, "capacidades", None), "descoberta", False)
                  and formato in fonte.capacidades.formatos
                  and (not idioma or idioma in fonte.capacidades.idiomas)]
        if not fontes:
            return PaginaLivros([], False, " Nenhuma fonte oferece descoberta com esses filtros.")
        respostas, erros = [], []
        executor = ThreadPoolExecutor(max_workers=len(fontes), thread_name_prefix="descoberta")
        tarefas = {executor.submit(fonte.explorar_pagina, formato, pagina, idioma, topico): fonte
                   for fonte in fontes}
        pendentes = set(tarefas)
        limite = monotonic() + MAX_ESPERA_DESCOBERTA
        try:
            while pendentes and monotonic() < limite:
                concluidas, pendentes = wait(pendentes, timeout=max(0, min(.2, limite - monotonic())),
                                             return_when=FIRST_COMPLETED)
                for tarefa in concluidas:
                    fonte = tarefas[tarefa]
                    try:
                        respostas.append((fonte, tarefa.result()))
                    except (requests.RequestException, ValueError) as erro:
                        erros.append(f"{fonte.nome}: {erro}")
            for tarefa in pendentes:
                tarefa.cancel()
                erros.append(f"{tarefas[tarefa].nome}: tempo limite atingido")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        livros, vistos = [], set()
        tem_proxima = False
        por_nome = {fonte.nome: resultado for fonte, resultado in respostas}
        for fonte in fontes:
            resultado = por_nome.get(fonte.nome)
            if resultado is None:
                continue
            tem_proxima = tem_proxima or resultado.tem_proxima
            for livro in resultado.livros:
                if livro.url.casefold() not in vistos and not _duplicado(livro, livros):
                    vistos.add(livro.url.casefold())
                    livros.append(livro)
        # Catálogos que informam popularidade já chegam ordenados; intercala as fontes
        # para uma biblioteca não ocupar sozinha toda a primeira tela.
        grupos = [[livro for livro in livros if livro.origem == fonte.nome] for fonte in fontes]
        intercalados = [grupo[indice] for indice in range(max(map(len, grupos), default=0))
                        for grupo in grupos if indice < len(grupo)]
        aviso = " Algumas fontes falharam: " + "; ".join(erros) if erros else ""
        return PaginaLivros(intercalados, tem_proxima, aviso)

    def verificar_saude(self):
        estados = []
        for fonte in self.fontes:
            nome = getattr(fonte, "nome", type(fonte).__name__)
            try:
                fonte.buscar_pagina("Dom Casmurro", "epub", 0, "")
                estados.append((nome, True, "respondendo"))
            except (requests.RequestException, ValueError) as erro:
                estados.append((nome, False, str(erro)))
        return estados

    def obter_sinopse(self, livro):
        fabrica = FONTES_INDIVIDUAIS.get(livro.origem)
        return fabrica().obter_sinopse(livro) if fabrica else livro.sinopse


FONTES = {"Todas as fontes": TodasFontes, **FONTES_INDIVIDUAIS}
