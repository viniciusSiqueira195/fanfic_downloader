import requests
import zipfile
import io
import os
from bs4 import BeautifulSoup
from converters.to_pdf import salvar_pdf  # <-- Importamos o seu conversor de PDF aqui!

def extrair_texto_de_epub(epub_bytes):
    # O FicHub entrega um arquivo EPUB (que nada mais é que um ZIP cheio de HTMLs).
    # Como QA de acessibilidade, sabemos que pra ler em TXT/PDF precisamos extrair só o texto puro.
    texto_completo = ""
    with zipfile.ZipFile(io.BytesIO(epub_bytes)) as z:
        # Pegamos todos os arquivos que são as páginas da história
        arquivos_pagina = [f for f in z.namelist() if f.endswith(('.html', '.xhtml', '.htm'))]
        arquivos_pagina.sort() # Ordenar garante que os capítulos fiquem na ordem certa
        
        for arquivo in arquivos_pagina:
            conteudo_html = z.read(arquivo)
            soup = BeautifulSoup(conteudo_html, 'html.parser')
            # Extrai apenas o texto legível pelo NVDA e adiciona uma linha divisória
            texto_completo += soup.get_text(separator="\n\n").strip() + "\n\n" + ("=" * 40) + "\n\n"
            
    return texto_completo

def baixar_fanfiction_net(url, modo, formato, pasta, progress_cb=None, cancel_event=None):
    try:
        if progress_cb: progress_cb(10, "Acionando a API do FicHub (Bypass de Cloudflare)...", -1)
        
        # Chamamos o servidor secreto que já furou o bloqueio
        api_url = f"https://fichub.net/api/v0/epub?q={url}"
        
        headers = {
            'User-Agent': 'FanficDownloader_QA/1.0'
        }
        
        response = requests.get(api_url, headers=headers, timeout=20)
        response.raise_for_status()
        
        dados = response.json()
        
        if "err" in dados and dados["err"] == 1:
            return False, f"A API não encontrou a história. Erro: {dados.get('msg', 'Desconhecido')}"
            
        if "epub_url" not in dados:
            return False, "A API não retornou o link do livro."
            
        link_download = "https://fichub.net" + dados["epub_url"]
        
        if progress_cb: progress_cb(50, "Baixando o livro completo da API...", -1)
        
        req_epub = requests.get(link_download, headers=headers, timeout=40)
        req_epub.raise_for_status()
        
        if cancel_event and cancel_event.is_set():
            return False, "Download cancelado pelo usuário."
            
        # O FicHub gera um nome amigável na URL. Exemplo: /cache/epub/123/Nome_da_Fic.epub
        nome_arquivo_base = link_download.split('/')[-1].split('?')[0].replace(".epub", "")
        
        if progress_cb: progress_cb(90, "Convertendo e salvando o arquivo...", -1)
        
        # A API sempre entrega a obra completa. Vamos avisar o usuário se ele pediu só um capítulo.
        aviso_extra = ""
        if modo == "Apenas este capítulo":
            aviso_extra = "\n(Nota: A API burlou o sistema e já te entregou a obra completa de brinde!)"
            
        if formato == "EPUB":
            caminho_final = os.path.join(pasta, f"{nome_arquivo_base}.epub")
            with open(caminho_final, 'wb') as f:
                f.write(req_epub.content)
            return True, f"Obra baixada com sucesso!{aviso_extra}\nSalvo em:\n{caminho_final}"
            
        elif formato == "TXT":
            caminho_final = os.path.join(pasta, f"{nome_arquivo_base}.txt")
            texto = extrair_texto_de_epub(req_epub.content)
            with open(caminho_final, 'w', encoding='utf-8') as f:
                f.write(texto)
            return True, f"Obra convertida para TXT com sucesso!{aviso_extra}\nSalvo em:\n{caminho_final}"
            
        elif formato == "PDF":
            # Extraímos o texto do EPUB primeiro e mandamos para o conversor PDF
            texto = extrair_texto_de_epub(req_epub.content)
            caminho_final = salvar_pdf(nome_arquivo_base, texto, pasta)
            return True, f"Obra convertida para PDF com sucesso!{aviso_extra}\nSalvo em:\n{caminho_final}"
            
        else:
            return False, f"Formato {formato} ainda não configurado para o FanFiction.net."
            
    except requests.exceptions.Timeout:
        return False, "O servidor demorou muito para responder. Tente novamente."
    except Exception as e:
        return False, f"Falha na conexão com a API:\n{str(e)}"