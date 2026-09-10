"""Livros de acesso aberto no catálogo público do Internet Archive."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import requests

from books.models import FORMATOS, HEADERS, Livro, PaginaLivros
from books.urls import validar_url_download

FORMATOS_ARQUIVO = {
    "epub": ("EPUB",),
    "pdf": ("Text PDF", "PDF"),
    "txt": ("DjVuTXT", "Full Text"),
}
IDIOMAS = {"pt": "por", "en": "eng", "es": "spa", "fr": "fre"}


def _texto(valor):
    if isinstance(valor, list):
        return ", ".join(str(item) for item in valor)
    return str(valor or "")


class InternetArchive:
    nome = "Internet Archive"

    def __init__(self, http=None):
        self.http = http or requests

    def buscar(self, termo, formato="epub", pagina=0, idioma=""):
        return self.buscar_pagina(termo, formato, pagina, idioma).livros

    def buscar_pagina(self, termo, formato="epub", pagina=0, idioma=""):
        termo = termo.strip()
        if not termo:
            raise ValueError("Digite o título ou autor do livro.")
        if formato not in FORMATOS or pagina < 0:
            raise ValueError("Formato ou página inválidos.")
        termo_catalogo = termo.replace('"', " ").replace("\\", " ")
        consulta = (f'mediatype:texts AND (title:"{termo_catalogo}" OR creator:"{termo_catalogo}") '
                    'AND (licenseurl:* OR possible-copyright-status:"NOT_IN_COPYRIGHT")')
        if idioma in IDIOMAS:
            consulta += f" AND language:{IDIOMAS[idioma]}"
        resposta = self.http.get(
            "https://archive.org/advancedsearch.php",
            params={"q": consulta, "fl[]": ["identifier", "title", "creator", "language",
                                              "description", "licenseurl"],
                    "rows": 20, "page": pagina + 1, "output": "json"},
            headers=HEADERS, timeout=(5, 15),
        )
        resposta.raise_for_status()
        dados = resposta.json()
        documentos = dados.get("response", {}).get("docs")
        if not isinstance(documentos, list):
            raise ValueError("O Internet Archive retornou uma resposta inesperada.")
        livros = []
        with ThreadPoolExecutor(max_workers=6, thread_name_prefix="archive") as executor:
            tarefas = [executor.submit(self._obter_livro, item, formato) for item in documentos]
            for tarefa in as_completed(tarefas):
                try:
                    livro = tarefa.result()
                except requests.RequestException:
                    continue
                if livro:
                    livros.append(livro)
        total = int(dados.get("response", {}).get("numFound", 0))
        return PaginaLivros(livros, (pagina + 1) * 20 < total)

    def _obter_livro(self, item, formato):
        identificador = str(item.get("identifier", "")).strip()
        if not identificador:
            return None
        resposta = self.http.get(f"https://archive.org/metadata/{quote(identificador, safe='')}",
                                 headers=HEADERS, timeout=(5, 12))
        resposta.raise_for_status()
        dados = resposta.json()
        metadados = dados.get("metadata", {})
        if str(metadados.get("access-restricted-item", "false")).lower() == "true":
            return None
        licenca = metadados.get("licenseurl") or item.get("licenseurl")
        estado = (metadados.get("possible-copyright-status")
                  or item.get("possible-copyright-status") or "")
        if not licenca and str(estado).upper() != "NOT_IN_COPYRIGHT":
            return None
        preferidos = FORMATOS_ARQUIVO[formato]
        arquivos = dados.get("files", [])
        arquivo = next((arq for tipo in preferidos for arq in arquivos
                        if arq.get("format") == tipo and arq.get("name")
                        and str(arq.get("private", "false")).lower() != "true"), None)
        if not arquivo:
            return None
        nome = quote(str(arquivo["name"]), safe="")
        url = f"https://archive.org/download/{quote(identificador, safe='')}/{nome}"
        validar_url_download(url, self.nome)
        titulo = _texto(item.get("title")) or identificador
        autor = _texto(item.get("creator"))
        rotulo = f"{titulo} — {autor}" if autor else titulo
        sinopse = _texto(item.get("description"))
        lingua = _texto(item.get("language"))
        return Livro(rotulo, url, formato, self.nome, sinopse, autor, lingua)

    def obter_sinopse(self, livro):
        return livro.sinopse
