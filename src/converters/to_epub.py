 
import os
import re
from ebooklib import epub

def salvar_epub(titulo, texto, pasta):
    # Limpa o título para não dar erro no nome do arquivo do Windows
    nome_arquivo = re.sub(r'[\\/*?:"<>|]', "", titulo) + ".epub"
    caminho_completo = os.path.join(pasta, nome_arquivo)

    book = epub.EpubBook()
    book.set_identifier("id_fanfic_12345")
    book.set_title(titulo)
    book.set_language("pt")

    # Cria a estrutura da página
    capitulo = epub.EpubHtml(title=titulo, file_name='historia.xhtml', lang='pt')
    
    # Converte o texto puro para HTML (parágrafo por parágrafo)
    html_content = f"<h1>{titulo}</h1>"
    for linha in texto.split('\n'):
        if linha.strip():
            html_content += f"<p>{linha.strip()}</p>"
        else:
            html_content += "<br/>"

    capitulo.content = html_content
    book.add_item(capitulo)

    # Monta a estrutura obrigatória do EPUB
    book.toc = (epub.Link('historia.xhtml', titulo, 'intro'), )
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define a ordem de leitura
    book.spine = ['nav', capitulo]

    # Salva o arquivo final
    epub.write_epub(caminho_completo, book, {})
    return caminho_completo