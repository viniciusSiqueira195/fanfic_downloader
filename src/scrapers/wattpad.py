import requests
import json
from bs4 import BeautifulSoup
from converters.to_txt import salvar_txt
from converters.to_pdf import salvar_pdf
from converters.to_epub import salvar_epub
import time
from urllib.parse import urljoin


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


def baixar_capa(url, headers):
    if not url:
        return None
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        if response.headers.get('Content-Type', '').lower().startswith('image/'):
            return response.content
    except requests.exceptions.RequestException:
        pass
    return None

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
        titulo, metadados = extrair_metadados(soup, url)
        
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
            capitulos = []
            urls_encontradas = set()
            for a in links:
                href = a.get('href')
                if href:
                    href = urljoin("https://www.wattpad.com", href)
                    if href in urls_encontradas:
                        continue
                    urls_encontradas.add(href)
                    titulo_capitulo = " ".join(a.get_text(" ", strip=True).split())
                    capitulos.append((href, titulo_capitulo))
            
            total = len(capitulos)
            if total == 0:
                return False, "Nenhum capítulo encontrado no índice."
            
            textos = []
            inicio_tempo = time.time()
            
            for i, (link, titulo_capitulo) in enumerate(capitulos):
                if cancel_event and cancel_event.is_set():
                    return False, "Download cancelado pelo usuário."
                    
                txt_cap = extrair_texto(link, headers)
                titulo_capitulo = titulo_capitulo or f"Capítulo {i+1}"
                textos.append(f"--- CAPITULO {i+1}: {titulo_capitulo} ---\n\n{txt_cap}")
                
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

        capa = baixar_capa(metadados['capa_url'], headers) if formato in ("PDF", "EPUB") else None
        
        if formato == "TXT":
            caminho = salvar_txt(titulo, texto_final, pasta)
            return True, f"Download concluído!\nArquivo salvo em:\n{caminho}"
        elif formato == "PDF":
            caminho = salvar_pdf(titulo, texto_final, pasta, metadados, capa)
            return True, f"Download concluído!\nArquivo salvo em:\n{caminho}"
        elif formato == "EPUB":
            caminho = salvar_epub(titulo, texto_final, pasta, metadados, capa)
            return True, f"Download concluído!\nArquivo salvo em:\n{caminho}"
        else:
            return False, f"O formato {formato} ainda será implementado."
            
    except Exception as e:
        return False, f"Erro:\n{str(e)}"
