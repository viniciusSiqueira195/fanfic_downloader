"""Catálogo Project Gutenberg consultado pela API independente Gutendex."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests

from books.cache import cachear_paginas
from books.catalog import CapacidadesCatalogo
from books.http import criar_cliente
from books.models import Livro, PaginaLivros, HEADERS
from books.urls import validar_url_download

MIMES = {"epub": "application/epub+zip", "txt": "text/plain", "pdf": "application/pdf"}
OPDS = "https://www.gutenberg.org/ebooks/search.opds/"
ATOM = "{http://www.w3.org/2005/Atom}"
DCTERMS = "{http://purl.org/dc/terms/}"


class Gutenberg:
    nome = "Project Gutenberg"
    capacidades = CapacidadesCatalogo(frozenset(MIMES), frozenset({"pt", "en", "es", "fr"}), True)
    def __init__(self, http=None):
        self.http = http or criar_cliente()

    def buscar(self, termo, formato="epub", pagina=0, idioma=""):
        return self.buscar_pagina(termo, formato, pagina, idioma).livros

    @cachear_paginas()
    def buscar_pagina(self, termo, formato="epub", pagina=0, idioma=""):
        if not termo.strip():
            raise ValueError("Digite o título ou autor do livro.")
        if formato not in MIMES or pagina < 0:
            raise ValueError("Formato ou página inválidos.")
        parametros = {"search": termo.strip(), "mime_type": MIMES[formato], "page": pagina + 1}
        if idioma:
            parametros["languages"] = idioma
        return self._consultar(parametros, formato)

    @cachear_paginas()
    def explorar_pagina(self, formato="epub", pagina=0, idioma="pt", topico=""):
        if formato not in MIMES or pagina < 0:
            raise ValueError("Formato ou página inválidos.")
        parametros = {"mime_type": MIMES[formato], "page": pagina + 1, "sort": "popular"}
        if idioma:
            parametros["languages"] = idioma
        if topico:
            parametros["topic"] = topico
        return self._consultar(parametros, formato)

    def _consultar(self, parametros, formato):
        try:
            resposta = self.http.get(
                "https://gutendex.com/books/", params=parametros,
                headers=HEADERS, timeout=(5, 10),
            )
            resposta.raise_for_status()
            dados = resposta.json()
        except requests.RequestException:
            return self._consultar_opds(parametros, formato)
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

    def _consultar_opds(self, parametros, formato):
        consulta = parametros.get("search", "").strip()
        idioma = parametros.get("languages", "")
        if idioma:
            consulta = f"l.{idioma} {consulta}".strip()
        if parametros.get("topic"):
            consulta = f"{consulta} {parametros['topic']}".strip()
        opds_params = {"query": consulta}
        if parametros.get("sort") == "popular":
            opds_params["sort_order"] = "downloads"
        pagina = int(parametros.get("page", 1))
        if pagina > 1:
            opds_params["start_index"] = 1 + (pagina - 1) * 25
        resposta = self.http.get(OPDS, params=opds_params, headers=HEADERS, timeout=(5, 10))
        resposta.raise_for_status()
        try:
            raiz = ElementTree.fromstring(resposta.content)
        except ElementTree.ParseError as erro:
            raise ValueError("O catálogo oficial do Gutenberg retornou uma resposta inválida.") from erro
        detalhes = []
        for entrada in raiz.findall(f"{ATOM}entry")[:12]:
            link = next((item.get("href") for item in entrada.findall(f"{ATOM}link")
                         if item.get("rel") == "subsection"), None)
            if link:
                detalhes.append(urljoin(OPDS, link))
        livros = []
        with ThreadPoolExecutor(max_workers=6, thread_name_prefix="opds") as executor:
            tarefas = [executor.submit(self._obter_opds, url, formato) for url in detalhes]
            for tarefa in as_completed(tarefas):
                try:
                    livro = tarefa.result()
                except requests.RequestException:
                    continue
                if livro:
                    livros.append(livro)
        tem_proxima = any(link.get("rel") == "next" for link in raiz.findall(f"{ATOM}link"))
        return PaginaLivros(livros, tem_proxima,
                            " O catálogo alternativo oficial do Gutenberg foi utilizado.")

    def _obter_opds(self, url, formato):
        resposta = self.http.get(url, headers=HEADERS, timeout=(5, 10))
        resposta.raise_for_status()
        try:
            raiz = ElementTree.fromstring(resposta.content)
        except ElementTree.ParseError:
            return None
        for entrada in raiz.findall(f"{ATOM}entry"):
            aquisicao = next((link for link in entrada.findall(f"{ATOM}link")
                              if link.get("rel", "").endswith("acquisition")
                              and link.get("type", "").split(";", 1)[0] == MIMES[formato]), None)
            if aquisicao is None:
                continue
            endereco = urljoin(url, aquisicao.get("href", ""))
            try:
                validar_url_download(endereco, "Project Gutenberg")
            except ValueError:
                continue
            titulo = entrada.findtext(f"{ATOM}title") or "Livro sem título"
            autor = entrada.findtext(f"{ATOM}author/{ATOM}name") or ""
            idioma = entrada.findtext(f"{DCTERMS}language") or ""
            conteudo = " ".join("".join(entrada.find(f"{ATOM}content").itertext()).split()) \
                if entrada.find(f"{ATOM}content") is not None else ""
            achado = re.search(r"Summary:\s*(.+?)(?:Reading Level:|Author:|EBook No\.:)", conteudo)
            sinopse = achado.group(1).strip() if achado else ""
            rotulo = f"{titulo} — {autor}" if autor else titulo
            return Livro(rotulo, endereco, formato, "Project Gutenberg", sinopse, autor, idioma)
        return None

    def obter_sinopse(self, livro):
        return livro.sinopse
