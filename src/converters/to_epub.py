 
import os
import re
from html import escape
from ebooklib import epub

MARCADOR_CAPITULO = re.compile(r'-{2,}\s*CAPITULO\s+(\d+)(?:\s*:\s*(.*?))?\s*-{2,}\s*$')


def _criar_conteudo_html(titulo, linhas):
    conteudo = [f"<h1>{escape(titulo)}</h1>"]
    for linha in linhas:
        if linha.strip():
            conteudo.append(f"<p>{escape(linha.strip())}</p>")
        else:
            conteudo.append("<br/>")
    return "".join(conteudo)


def salvar_epub(titulo, texto, pasta, metadados=None, capa=None):
    # Limpa o título para não dar erro no nome do arquivo do Windows
    nome_arquivo = re.sub(r'[\\/*?:"<>|]', "", titulo) + ".epub"
    caminho_completo = os.path.join(pasta, nome_arquivo)

    book = epub.EpubBook()
    metadados = metadados or {}
    book.set_identifier(metadados.get('origem') or "id_fanfic_12345")
    book.set_title(titulo)
    book.set_language("pt")
    if metadados.get('autor'):
        book.add_author(metadados['autor'])
    if metadados.get('descricao'):
        book.add_metadata('DC', 'description', metadados['descricao'])
    if metadados.get('origem'):
        book.add_metadata('DC', 'source', metadados['origem'])
    if capa:
        nome_capa = 'capa.png' if capa.startswith(b'\x89PNG') else 'capa.jpg'
        book.set_cover(nome_capa, capa)

    secoes = []
    titulo_secao = titulo
    linhas_secao = []
    for linha in texto.split('\n'):
        marcador = MARCADOR_CAPITULO.match(linha.strip())
        if marcador:
            if linhas_secao:
                secoes.append((titulo_secao, linhas_secao))
            titulo_secao = marcador.group(2).strip() if marcador.group(2) else f"Capítulo {marcador.group(1)}"
            linhas_secao = []
        else:
            linhas_secao.append(linha)

    if linhas_secao or not secoes:
        secoes.append((titulo_secao, linhas_secao))

    capitulos = []
    for indice, (titulo_secao, linhas) in enumerate(secoes, start=1):
        capitulo = epub.EpubHtml(
            title=titulo_secao,
            file_name=f'capitulo_{indice}.xhtml',
            lang='pt',
        )
        capitulo.content = _criar_conteudo_html(titulo_secao, linhas)
        book.add_item(capitulo)
        capitulos.append(capitulo)

    # Monta a estrutura obrigatória do EPUB
    book.toc = tuple(capitulos)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define a ordem de leitura
    book.spine = ['nav', *capitulos]

    # Salva o arquivo final
    epub.write_epub(caminho_completo, book, {})
    return caminho_completo
