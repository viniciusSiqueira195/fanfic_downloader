import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, unquote


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _normalizar_url(url, dominio):
    if url.startswith("/"):
        return dominio + url
    if not url.startswith("http"):
        return dominio + "/" + url.lstrip("/")
    return url


def _extrair_link_duckduckgo(href):
    href_limpo = href.strip()
    if "uddg=" in href_limpo:
        return unquote(href_limpo.split("uddg=", 1)[1].split("&", 1)[0])
    if href_limpo.startswith("//duckduckgo.com/l/?uddg="):
        return unquote(href_limpo.split("uddg=", 1)[1].split("&", 1)[0])
    return href_limpo


def buscar_fanfics_wattpad(termo, limite=10):
    termo_limpo = termo.strip()
    if not termo_limpo:
        raise ValueError("O termo de busca não pode estar vazio.")

    headers = {"User-Agent": USER_AGENT}
    params = {
        "query": termo_limpo,
        "limit": limite,
        "offset": 0,
    }

    response = requests.get("https://www.wattpad.com/api/v3/stories", headers=headers, params=params, timeout=20)
    response.raise_for_status()
    dados = response.json()

    resultados = []
    for historia in dados.get("stories", []):
        url = historia.get("url", "")
        if not url:
            continue

        # CORREÇÃO DEFINITIVA: O scanner (re.search) procura os números do ID na URL.
        # Se achar, ele monta a URL contendo EXATAMENTE só o ID, igual o seu baixador precisa.
        match_id = re.search(r'/(\d+)', url)
        if match_id:
            url = f"https://www.wattpad.com/{match_id.group(1)}"
        else:
            url = _normalizar_url(url, "https://www.wattpad.com")

        resultados.append(
            {
                "titulo": historia.get("title", "Título Desconhecido"),
                "autor": historia.get("user", {}).get("name", "Autor Desconhecido"),
                "url": url,
                "origem": "Wattpad",
            }
        )

    return resultados


def buscar_fanfics_spirit(termo, limite=10):
    termo_limpo = termo.strip()
    if not termo_limpo:
        raise ValueError("O termo de busca não pode estar vazio.")

    headers = {"User-Agent": USER_AGENT}
    params = {"query": termo_limpo}

    response = requests.get("https://www.spiritfanfiction.com/busca", headers=headers, params=params, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    resultados = []
    links_vistos = set()

    for artigo in soup.find_all("article"):
        titulo_link = artigo.find("h2")
        if not titulo_link:
            continue

        titulo_link = titulo_link.find("a")
        if not titulo_link:
            continue

        href = titulo_link.get("href", "").strip()
        if "/historia/" not in href:
            continue

        url = _normalizar_url(href, "https://www.spiritfanfiction.com")
        if url in links_vistos:
            continue
        links_vistos.add(url)

        autor_tag = artigo.find("a", class_="usuario")
        autor = "Autor Desconhecido"
        if autor_tag and autor_tag.get_text():
            autor = autor_tag.get_text().strip()

        resultados.append(
            {
                "titulo": titulo_link.get_text(strip=True) or "Título Desconhecido",
                "autor": autor,
                "url": url,
                "origem": "Spirit",
            }
        )

        if len(resultados) >= limite:
            break

    return resultados


def buscar_fanfics_fanfiction_net(termo, limite=10):
    termo_limpo = termo.strip()
    if not termo_limpo:
        raise ValueError("O termo de busca não pode estar vazio.")

    headers = {"User-Agent": USER_AGENT}
    params = {"q": f"site:fanfiction.net/s/ {termo_limpo}"}

    response = requests.get("https://duckduckgo.com/html/", headers=headers, params=params, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    resultados = []
    links_vistos = set()

    for link in soup.find_all("a", class_="result__a"):
        href = _extrair_link_duckduckgo(link.get("href", ""))

        if "fanfiction.net/s/" not in href:
            continue
        if href in links_vistos:
            continue
        links_vistos.add(href)

        titulo = link.get_text(strip=True) or "Título Desconhecido"
        resultados.append(
            {
                "titulo": titulo,
                "autor": "Autor não informado na busca",
                "url": href,
                "origem": "FanFiction.net",
            }
        )

        if len(resultados) >= limite:
            break

    return resultados


def _buscar_fanfics_plusfiction_direto(termo_limpo, limite):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://plusfiction.com/",
    }

    url_busca = f"https://plusfiction.com/search/{quote_plus(termo_limpo)}"
    response = requests.get(url_busca, headers=headers, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    resultados = []
    links_vistos = set()

    for link in soup.find_all("a", href=True):
        href = link.get("href", "").strip()
        if "/book/" not in href:
            continue

        url = _normalizar_url(href, "https://plusfiction.com")
        if url in links_vistos:
            continue
        links_vistos.add(url)

        titulo = link.get_text(strip=True) or link.get("title", "").strip() or "Título Desconhecido"
        resultados.append(
            {
                "titulo": titulo,
                "autor": "Autor não informado na busca",
                "url": url,
                "origem": "PlusFiction",
            }
        )

        if len(resultados) >= limite:
            break

    return resultados


def _buscar_fanfics_plusfiction_via_duckduckgo(termo_limpo, limite):
    headers = {"User-Agent": USER_AGENT}
    params = {"q": f"site:plusfiction.com/book {termo_limpo}"}

    response = requests.get("https://duckduckgo.com/html/", headers=headers, params=params, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    resultados = []
    links_vistos = set()

    for link in soup.find_all("a", class_="result__a"):
        href = _extrair_link_duckduckgo(link.get("href", ""))
        if "plusfiction.com/book/" not in href:
            continue
        if href in links_vistos:
            continue
        links_vistos.add(href)

        titulo = link.get_text(strip=True) or "Título Desconhecido"
        resultados.append(
            {
                "titulo": titulo,
                "autor": "Autor não informado na busca",
                "url": href,
                "origem": "PlusFiction",
            }
        )

        if len(resultados) >= limite:
            break

    return resultados


def buscar_fanfics_plusfiction(termo, limite=10):
    termo_limpo = termo.strip()
    if not termo_limpo:
        raise ValueError("O termo de busca não pode estar vazio.")

    try:
        return _buscar_fanfics_plusfiction_direto(termo_limpo, limite)
    except requests.exceptions.HTTPError as erro:
        if erro.response is not None and erro.response.status_code == 403:
            return _buscar_fanfics_plusfiction_via_duckduckgo(termo_limpo, limite)
        raise


def buscar_fanfics_todas_fontes(termo, limite_por_fonte=5):
    termo_limpo = termo.strip()
    if not termo_limpo:
        raise ValueError("O termo de busca não pode estar vazio.")

    funcoes = [
        buscar_fanfics_wattpad,
        buscar_fanfics_spirit,
        buscar_fanfics_fanfiction_net,
        buscar_fanfics_plusfiction,
    ]

    resultados = []
    urls_vistas = set()
    erros = []

    for funcao in funcoes:
        try:
            encontrados = funcao(termo_limpo, limite=limite_por_fonte)
            for item in encontrados:
                url = item.get("url", "").strip()
                if not url or url in urls_vistas:
                    continue
                urls_vistas.add(url)
                resultados.append(item)
        except requests.exceptions.RequestException as erro:
            erros.append(str(erro))

    if not resultados and erros:
        raise requests.exceptions.RequestException("Falha ao buscar nas fontes configuradas.")

    return resultados