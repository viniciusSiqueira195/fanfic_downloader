import requests
from bs4 import BeautifulSoup
from converters.to_txt import salvar_txt
import time

def extrair_texto(url, headers):
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    paragrafos = soup.find_all('p')
    return "\n\n".join([p.get_text().strip() for p in paragrafos if p.get_text().strip()])

def baixar_wattpad(url, modo, formato, pasta):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        titulo = soup.title.string.strip() if soup.title else "Titulo Desconhecido"
        
        texto_final = ""
        
        if modo == "Apenas este capítulo":
            texto_final = extrair_texto(url, headers)
        else:
            toc = soup.find(class_="table-of-contents")
            if not toc:
                return False, "Para Obra Completa, cole o link da página inicial da história (que contém o índice)."
            
            links = toc.find_all('a')
            urls_capitulos = []
            for a in links:
                href = a.get('href')
                if href:
                    if not href.startswith('http'):
                        href = "https://www.wattpad.com" + href
                    urls_capitulos.append(href)
            
            if not urls_capitulos:
                return False, "Nenhum capítulo encontrado no índice."
            
            textos = []
            for i, link in enumerate(urls_capitulos):
                txt_cap = extrair_texto(link, headers)
                textos.append(f"--- CAPITULO {i+1} ---\n\n{txt_cap}")
                time.sleep(0.2)
            
            texto_final = "\n\n\n".join(textos)
            
        if formato == "TXT":
            caminho = salvar_txt(titulo, texto_final, pasta)
            return True, f"Download concluído!\nArquivo salvo em:\n{caminho}"
        else:
            return False, f"O formato {formato} ainda será implementado."
            
    except Exception as e:
        return False, f"Erro:\n{str(e)}"