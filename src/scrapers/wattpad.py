import requests
from bs4 import BeautifulSoup
from converters.to_txt import salvar_txt
from converters.to_pdf import salvar_pdf
from converters.to_epub import salvar_epub
import time
import re

def extrair_texto(url, headers):
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    paragrafos = soup.find_all('p')
    return "\n\n".join([p.get_text().strip() for p in paragrafos if p.get_text().strip()])


def _extrair_story_id(url, html):
    match_story = re.search(r'/story/(\d+)', url)
    if match_story:
        return match_story.group(1)

    match_html = re.search(r'https://www\.wattpad\.com/story/(\d+)', html)
    if match_html:
        return match_html.group(1)

    return None


def _urls_capitulos_por_api(story_id, headers):
    api_url = f"https://www.wattpad.com/api/v3/stories/{story_id}"
    response = requests.get(api_url, headers=headers, timeout=20)
    response.raise_for_status()
    dados = response.json()

    urls = []
    for parte in dados.get("parts", []):
        link = parte.get("url")
        if link:
            urls.append(link)
    return urls

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
            urls_capitulos = []

            story_id = _extrair_story_id(url, response.text)
            if story_id:
                urls_capitulos = _urls_capitulos_por_api(story_id, headers)

            if not urls_capitulos:
                toc = soup.find(class_="table-of-contents")
                if toc:
                    links = toc.find_all('a')
                    for a in links:
                        href = a.get('href')
                        if href:
                            if not href.startswith('http'):
                                href = "https://www.wattpad.com" + href
                            urls_capitulos.append(href)
            
            total = len(urls_capitulos)
            if total == 0:
                return False, "Não foi possível localizar os capítulos dessa história para Obra Completa."
            
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