"""Adaptador do Visionvox com descoberta temática por metadados externos."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit, parse_qs

import requests
from bs4 import BeautifulSoup
from books.cache import cachear_paginas
from books.catalog import CapacidadesCatalogo
from books.http import criar_cliente
from books.models import Livro, PaginaLivros, FORMATOS, HEADERS
from books.urls import validar_url_download
from scrapers.search_relevance import normalizar, termos_significativos

BASE_URL = "https://visionvox.com.br/"
OPEN_LIBRARY = "https://openlibrary.org/search.json"
TAMANHO_DESCOBERTA = 20
def validar_url(url):
    return validar_url_download(url, "Visionvox")


def extrair_livros(html):
    soup = BeautifulSoup(html, "html.parser")
    livros, vistos = [], set()
    for link in soup.find_all("a", href=True):
        url = urljoin(BASE_URL, link["href"].strip())
        try:
            partes = validar_url(url)
        except ValueError:
            continue
        formato = PurePosixPath(unquote(partes.path)).suffix.lower().lstrip(".")
        if formato not in FORMATOS or url in vistos:
            continue
        titulo = link.get_text(" ", strip=True)
        if not titulo:
            continue
        vistos.add(url)
        livros.append(Livro(titulo, url, formato, idioma="pt"))
    return livros


class Visionvox:
    nome = "Visionvox"
    capacidades = CapacidadesCatalogo(frozenset(FORMATOS), frozenset({"pt"}), True)
    def __init__(self, http=None):
        self.http = http or criar_cliente()

    def buscar(self, termo, formato="epub", pagina=0, idioma=""):
        return self.buscar_pagina(termo, formato, pagina, idioma).livros

    @cachear_paginas()
    def buscar_pagina(self, termo, formato="epub", pagina=0, idioma=""):
        if not termo.strip():
            raise ValueError("Digite o título ou autor do livro.")
        if formato not in FORMATOS or pagina < 0:
            raise ValueError("Formato ou página inválidos.")
        if idioma and idioma != "pt":
            return PaginaLivros([], False)
        resposta = self.http.get(
            urljoin(BASE_URL, "busca.php"),
            params={"busca": termo.strip(), "ext": formato,
                    "pagina": "Nao" if pagina == 0 else "sim", "num_page": pagina},
            headers=HEADERS, timeout=(10, 30),
        )
        resposta.raise_for_status()
        # O site usa UTF-8, mas algumas respostas omitem o charset HTTP/meta.
        livros = extrair_livros(resposta.content.decode("utf-8"))
        if not livros and "Encontramos 0" not in resposta.content.decode("utf-8"):
            soup = BeautifulSoup(resposta.content, "html.parser")
            if not soup.find("input", attrs={"name": "busca"}):
                raise ValueError("O Visionvox não retornou a página de pesquisa. Tente novamente mais tarde.")
        soup = BeautifulSoup(resposta.content.decode("utf-8"), "html.parser")
        tem_proxima = False
        for link in soup.find_all("a", href=True):
            parametros = parse_qs(urlsplit(link["href"]).query)
            numero = parametros.get("num_page", [""])[0]
            if numero.isdecimal() and int(numero) > pagina:
                tem_proxima = True
                break
        return PaginaLivros(livros, tem_proxima)

    @cachear_paginas(ttl=600)
    def explorar_pagina(self, formato="epub", pagina=0, idioma="pt", topico=""):
        if formato not in FORMATOS or pagina < 0:
            raise ValueError("Formato ou página inválidos.")
        if idioma and idioma != "pt":
            return PaginaLivros([], False)
        if not topico:
            return PaginaLivros([], False,
                                " Escolha um tema para descobrir livros no Visionvox.")
        resposta = self.http.get(
            OPEN_LIBRARY,
            params={
                "q": f'subject:"{topico}" language:por',
                "fields": "key,title,author_name,editions",
                "lang": "pt", "limit": TAMANHO_DESCOBERTA,
                "page": pagina + 1,
            },
            headers=HEADERS, timeout=(5, 20),
        )
        resposta.raise_for_status()
        dados = resposta.json()
        obras = dados.get("docs")
        if not isinstance(obras, list):
            raise ValueError("A Open Library retornou uma resposta inesperada.")

        consultas = []
        for obra in obras:
            titulos = [obra.get("title")]
            autores = [str(autor).strip() for autor in obra.get("author_name", []) if autor]
            edicoes = (obra.get("editions") or {}).get("docs", [])
            titulos.extend(edicao.get("title") for edicao in edicoes
                           if "por" in (edicao.get("language") or []))
            for titulo in dict.fromkeys(str(item).strip() for item in titulos if item):
                consultas.append((titulo, autores))

        encontrados = []
        with ThreadPoolExecutor(max_workers=6, thread_name_prefix="visionvox-genero") as executor:
            tarefas = {executor.submit(self.buscar_pagina, titulo, formato, 0, "pt"):
                       (titulo, autores) for titulo, autores in consultas}
            for tarefa in as_completed(tarefas):
                titulo, autores = tarefas[tarefa]
                try:
                    resultado = tarefa.result()
                except (requests.RequestException, ValueError):
                    continue
                esperados = set(termos_significativos(titulo))
                sobrenomes = {normalizar(autor).split()[-1] for autor in autores
                              if normalizar(autor).split()}
                for livro in resultado.livros:
                    titulo_principal = livro.titulo.rsplit(".", 1)[0].split("(", 1)[0]
                    palavras = set(termos_significativos(titulo_principal))
                    titulo_confere = (esperados and
                                      len(esperados & palavras) / len(esperados) >= .7)
                    autor_confere = not sobrenomes or bool(sobrenomes & palavras)
                    if titulo_confere and autor_confere:
                        encontrados.append(livro)

        livros, vistos = [], set()
        for livro in encontrados:
            if livro.url.casefold() not in vistos:
                vistos.add(livro.url.casefold())
                livros.append(livro)
        total = int(dados.get("numFound", 0))
        tem_proxima = (pagina + 1) * TAMANHO_DESCOBERTA < total
        return PaginaLivros(livros, tem_proxima)

    def obter_sinopse(self, livro):
        termo = livro.titulo.rsplit(".", 1)[0].replace("_", " ")
        tokens = termos_significativos(termo)
        consultas = [termo]
        # Os nomes de arquivo do acervo juntam autor e título. O catálogo de
        # sinopses não encontra essa string inteira, então tenta sufixos que
        # normalmente correspondem ao título sem inventar um corte de autor.
        palavras = termo.split()
        consultas.extend(" ".join(palavras[-quantidade:])
                         for quantidade in range(min(4, len(palavras) - 1), 0, -1))
        candidatos = []
        for consulta in dict.fromkeys(consultas):
            resposta = self.http.get(
                urljoin(BASE_URL, "sinopses/index.php"), params={"query": consulta},
                headers=HEADERS, timeout=(10, 30),
            )
            resposta.raise_for_status()
            soup = BeautifulSoup(resposta.content.decode("utf-8"), "html.parser")
            for link in soup.find_all("a", href=True):
                if "sinopse=" not in link["href"].lower():
                    continue
                texto = normalizar(link.get_text(" ", strip=True))
                pontos = sum(token in texto.split() for token in tokens)
                candidatos.append((pontos, link["href"]))
            if candidatos:
                break
        if not candidatos:
            return ""
        _, endereco = max(candidatos, key=lambda item: item[0])
        resposta = self.http.get(urljoin(BASE_URL + "sinopses/", endereco),
                                 headers=HEADERS, timeout=(10, 30))
        resposta.raise_for_status()
        linhas = [linha.strip() for linha in BeautifulSoup(
            resposta.content.decode("utf-8"), "html.parser").get_text("\n").splitlines()
                  if linha.strip()]
        try:
            inicio = linhas.index("Sinopse:") + 1
            fim = linhas.index("Copiar sinopse", inicio)
        except ValueError:
            return ""
        return "\n\n".join(linhas[inicio:fim]).strip()
