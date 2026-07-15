import requests
from bs4 import BeautifulSoup
from converters.to_txt import salvar_txt
from converters.to_pdf import salvar_pdf
from converters.to_epub import salvar_epub
import time

def extrair_texto(url, headers):
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    paragrafos = soup.find_all('p')
    return "\n\n".join([p.get_text().strip() for p in paragrafos if p.get_text().strip()])

def baixar_wattpad(url, modo, formato, pasta, progress_cb=None, cancel_event=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        if progress_cb: progress_cb(5, "Acessando a página principal...", -1)
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        titulo = soup.title.string.strip() if soup.title else "Titulo Desconhecido"
        
        texto_final = ""
        
        if modo == "Apenas este capítulo":
            if cancel_event and cancel_event.is_set():
                return False, "Download cancelado pelo usuário."
            if progress_cb: progress_cb(50, "Extraindo texto do capítulo...", -1)
            texto_final = extrair_texto(url, headers)
        else:
            toc = soup.find(class_="table-of-contents")
            if not toc:
                return False, "Para Obra Completa, cole o link da página inicial da história."
            
            links = toc.find_all('a')
            urls_capitulos = []
            for a in links:
                href = a.get('href')
                if href:
                    if not href.startswith('http'):
                        href = "https://www.wattpad.com" + href
                    urls_capitulos.append(href)
            
            total = len(urls_capitulos)
            if total == 0:
                return False, "Nenhum capítulo encontrado no índice."
            
            textos = []
            inicio_tempo = time.time()
            
            for i, link in enumerate(urls_capitulos):
                if cancel_event and cancel_event.is_set():
                    return False, "Download cancelado pelo usuário."
                    
                txt_cap = extrair_texto(link, headers)
                textos.append(f"--- CAPITULO {i+1} ---\n\n{txt_cap}")
                
                if progress_cb:
                    pct = int(((i + 1) / total) * 100)
                    decorrido = time.time() - inicio_tempo
                    restante = (decorrido / (i + 1)) * (total - (i + 1))
                    msg = f"Baixando capítulo {i+1} de {total}..."
                    progress_cb(pct, msg, restante)
                    
                time.sleep(0.2)
            
            if progress_cb: progress_cb(95, "Juntando os capítulos...", -1)
            texto_final = "\n\n\n".join(textos)
            
        if cancel_event and cancel_event.is_set():
            return False, "Download cancelado pelo usuário."
            
        if progress_cb: progress_cb(98, "Salvando arquivo...", -1)
        
        if formato == "TXT":
            caminho = salvar_txt(titulo, texto_final, pasta)
            return True, f"Download concluído!\nArquivo salvo em:\n{caminho}"
        elif formato == "PDF":
            caminho = salvar_pdf(titulo, texto_final, pasta)
            return True, f"Download concluído!\nArquivo salvo em:\n{caminho}"
        elif formato == "EPUB":
            caminho = salvar_epub(titulo, texto_final, pasta)
            return True, f"Download concluído!\nArquivo salvo em:\n{caminho}"
        else:
            return False, f"O formato {formato} ainda será implementado."
            
    except Exception as e:
        return False, f"Erro:\n{str(e)}"