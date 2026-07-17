import requests
import json
import time
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from converters.to_txt import salvar_txt
from converters.to_pdf import salvar_pdf
from converters.to_epub import salvar_epub

def _conteudo_meta(soup, **atributos):
    elemento = soup.find('meta', attrs=atributos)
    return elemento.get('content', '').strip() if elemento else ''

def _dados_estruturados(soup):
    for elemento in soup.find_all('script', type='application/ld+json'):
        try:
            dados = json.loads(elemento.string or '')
        except (TypeError, json.JSONDecodeError):
            continue

        itens = dados if isinstance(dados, list) else [dados]
        for item in itens:
            if isinstance(item, dict):
                yield item

def extrair_metadados(soup, url):
    titulo = _conteudo_meta(soup, property='og:title')
    descricao = _conteudo_meta(soup, property='og:description') or _conteudo_meta(soup, name='description')
    autor = (
        _conteudo_meta(soup, name='author')
        or _conteudo_meta(soup, property='books:author')
        or _conteudo_meta(soup, name='twitter:creator')
    )
    capa_url = _conteudo_meta(soup, property='og:image') or _conteudo_meta(soup, name='twitter:image')

    for dados in _dados_estruturados(soup):
        titulo = titulo or str(dados.get('name', '')).strip()
        descricao = descricao or str(dados.get('description', '')).strip()
        capa_url = capa_url or str(dados.get('image', '')).strip()
        dados_autor = dados.get('author')
        if not autor and isinstance(dados_autor, dict):
            autor = str(dados_autor.get('name', '')).strip()

    if not titulo:
        titulo = soup.title.string.strip() if soup.title and soup.title.string else "Titulo Desconhecido"

    return titulo, {
        'autor': autor,
        'descricao': descricao,
        'origem': url,
        'capa_url': capa_url,
    }

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
            urls_capitulos = []
            
            # SOLUÇÃO DEFINITIVA: Bypass do HTML sujo usando a API do Wattpad
            if "/story/" in url:
                if progress_cb: progress_cb(10, "Extraindo lista de capítulos limpa via API...", -1)
                match = re.search(r'/story/(\d+)', url)
                if match:
                    story_id = match.group(1)
                    # A API entrega os dados puros, ignorando tags e layout visual
                    api_url = f"https://www.wattpad.com/api/v3/stories/{story_id}"
                    res_api = requests.get(api_url, headers=headers)
                    if res_api.status_code == 200:
                        dados = res_api.json()
                        for part in dados.get("parts", []):
                            if "id" in part:
                                urls_capitulos.append(f"https://www.wattpad.com/{part['id']}")
            
            # Se a URL não tiver /story/ (se for link de capítulo), usa o método HTML antigo
            if not urls_capitulos:
                toc = soup.find(class_="table-of-contents")
                if not toc:
                    return False, "Para Obra Completa, cole o link da página inicial da história ou de um capítulo."
                
                links = toc.find_all('a')
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