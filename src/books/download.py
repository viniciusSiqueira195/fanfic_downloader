"""Transferência limitada, cancelável e sem sobrescrever livros existentes."""
import os
import tempfile
import zipfile
from pathlib import Path

import requests

from books.models import FORMATOS, HEADERS
from books.urls import validar_url_download
from converters.filenames import nome_seguro


class DownloadCancelado(Exception):
    pass


class ErroPasta(ValueError):
    pass


def validar_pasta(pasta):
    # Path("") significa o diretório de trabalho, que pode ser System32.
    if not str(pasta).strip():
        raise ErroPasta("Escolha ou digite a pasta onde deseja salvar o livro.")
    pasta = Path(pasta)
    if not pasta.is_absolute():
        raise ErroPasta("Informe o caminho completo da pasta ou use Escolher pasta.")
    if not pasta.is_dir():
        raise ErroPasta("Escolha uma pasta de destino existente.")
    return pasta


def _verificar_cancelamento(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise DownloadCancelado("Download cancelado.")


def _validar_arquivo(caminho, formato):
    with open(caminho, "rb") as arquivo:
        inicio = arquivo.read(1024)
    if not inicio:
        raise ValueError("O site retornou um arquivo vazio.")
    if formato == "pdf" and not inicio.startswith(b"%PDF-"):
        raise ValueError("O site não retornou um PDF válido.")
    if formato == "epub":
        try:
            with zipfile.ZipFile(caminho) as arquivo:
                info = arquivo.getinfo("mimetype")
                if info.file_size > 100 or arquivo.read(info).strip() != b"application/epub+zip":
                    raise ValueError("O site não retornou um EPUB válido.")
        except (zipfile.BadZipFile, KeyError) as erro:
            raise ValueError("O site não retornou um EPUB válido.") from erro
    if formato == "txt":
        texto = inicio.lstrip(b"\xef\xbb\xbf \r\n\t").lower()
        if texto.startswith((b"<!doctype html", b"<html")) or b"\x00" in inicio:
            raise ValueError("O site não retornou um arquivo de texto válido.")


def baixar_livro(livro, pasta, cancel_event=None, progresso=None, http=None,
                 limite_bytes=100 * 1024 * 1024):
    http = http or requests
    if livro.formato not in FORMATOS:
        raise ValueError("Formato de livro não suportado.")
    pasta = validar_pasta(pasta)
    _verificar_cancelamento(cancel_event)
    url = livro.url
    temporario = None
    try:
        # Valida cada redirecionamento antes de fazer a próxima requisição.
        for _ in range(6):
            validar_url_download(url, livro.origem)
            with http.get(url, headers=HEADERS, stream=True, timeout=(10, 30),
                          allow_redirects=False) as resposta:
                if resposta.status_code in (301, 302, 303, 307, 308):
                    from urllib.parse import urljoin
                    if not resposta.headers.get("Location"):
                        raise ValueError("O site retornou um redirecionamento sem destino.")
                    url = urljoin(url, resposta.headers["Location"])
                    _verificar_cancelamento(cancel_event)
                    continue
                resposta.raise_for_status()
                if resposta.status_code != 200:
                    raise ValueError("O site não retornou o arquivo completo.")
                if "text/html" in resposta.headers.get("Content-Type", "").lower():
                    raise ValueError("O site retornou uma página em vez do livro.")
                tamanho = int(resposta.headers.get("Content-Length", 0))
                if tamanho > limite_bytes:
                    raise ValueError("O livro excede o limite de 100 MB desta versão.")
                with tempfile.NamedTemporaryFile(dir=pasta, suffix=".part", delete=False) as arquivo:
                    temporario = Path(arquivo.name)
                    recebido = 0
                    for bloco in resposta.iter_content(64 * 1024):
                        _verificar_cancelamento(cancel_event)
                        recebido += len(bloco)
                        if recebido > limite_bytes:
                            raise ValueError("O livro excede o limite de 100 MB desta versão.")
                        arquivo.write(bloco)
                        if progresso:
                            progresso(recebido, tamanho)
                if (tamanho and not resposta.headers.get("Content-Encoding")
                        and recebido != tamanho):
                    raise ValueError("O download ficou incompleto. Tente novamente.")
                break
        else:
            raise ValueError("O site redirecionou o download muitas vezes.")
        _verificar_cancelamento(cancel_event)
        _validar_arquivo(temporario, livro.formato)
        titulo = livro.titulo
        if titulo.lower().endswith("." + livro.formato):
            titulo = titulo[:-(len(livro.formato) + 1)]
        destino = pasta / (nome_seguro(titulo) + "." + livro.formato)
        # Hard link publica o arquivo pronto atomicamente e falha se já existir.
        # O temporário está no mesmo volume. Não há substituição silenciosa.
        try:
            os.link(temporario, destino)
        except FileExistsError as erro:
            raise ValueError("Já existe um livro com esse nome na pasta. Escolha outra pasta ou renomeie o arquivo existente.") from erro
        return destino
    except PermissionError as erro:
        raise ErroPasta(
            f"Não foi possível gravar na pasta {pasta}. "
            "Escolha outra pasta onde você possa salvar arquivos, como Downloads ou Documentos."
        ) from erro
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)
