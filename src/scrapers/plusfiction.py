import time
import requests
from bs4 import BeautifulSoup
from converters.to_txt import salvar_txt
from converters.to_pdf import salvar_pdf
from converters.to_epub import salvar_epub
from scrapers.chapter_selection import SelecaoCapitulosError, selecionar_capitulos


BASE_URL = "https://plusfiction.com"
ALT_BASE_URL = "https://www.plusfiction.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _normalizar_url(url):
    if url.startswith("/"):
        return BASE_URL + url
    if not url.startswith("http"):
        return BASE_URL + "/" + url.lstrip("/")
    return url


def _headers(referer=None):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def _criar_sessao():
    sessao = requests.Session()
    sessao.headers.update(_headers())
    return sessao


def _url_host_alternativo(url):
    if "://plusfiction.com" in url:
        return url.replace("://plusfiction.com", "://www.plusfiction.com", 1)
    if "://www.plusfiction.com" in url:
        return url.replace("://www.plusfiction.com", "://plusfiction.com", 1)
    return url


def _aquecer_sessao(sessao, url_alvo):
    rotas = [BASE_URL, ALT_BASE_URL, f"{BASE_URL}/search"]
    if "/chapter/" in url_alvo:
        rotas.append(url_alvo.split("/chapter/")[0])

    for rota in rotas:
        try:
            sessao.get(rota, headers=_headers(BASE_URL), timeout=20)
            time.sleep(0.2)
        except requests.exceptions.RequestException:
            continue


def _obter_html_com_retentativas(sessao, url, referer=None):
    ultima_excecao = None
    ultima_http_error = None

    tentativas = [
        (url, referer or BASE_URL, False),
        (url, referer or BASE_URL, True),
        (_url_host_alternativo(url), referer or BASE_URL, True),
    ]

    if "/chapter/" in url:
        url_obra = url.split("/chapter/")[0]
        tentativas.append((url_obra, BASE_URL, True))
        tentativas.append((url, url_obra, True))

    for url_tentativa, referer_tentativa, aquecer in tentativas:
        try:
            if aquecer:
                _aquecer_sessao(sessao, url_tentativa)

            resposta = sessao.get(url_tentativa, headers=_headers(referer_tentativa), timeout=25)
            resposta.raise_for_status()
            return resposta.text
        except requests.exceptions.HTTPError as erro_http:
            ultima_http_error = erro_http
            status = erro_http.response.status_code if erro_http.response is not None else None
            if status != 403:
                raise
            ultima_excecao = erro_http
            continue
        except requests.exceptions.RequestException as erro_req:
            ultima_excecao = erro_req
            continue

    if ultima_http_error is not None:
        raise ultima_http_error
    if ultima_excecao is not None:
        raise ultima_excecao
    raise requests.exceptions.RequestException("Falha inesperada ao acessar o PlusFiction.")


def _obter_soup(url, referer=None, sessao=None):
    sessao_ativa = sessao if sessao is not None else _criar_sessao()
    html = _obter_html_com_retentativas(sessao_ativa, url, referer=referer)
    return BeautifulSoup(html, "html.parser")


def _extrair_dados_obra(url, sessao):
    soup = _obter_soup(url, referer=BASE_URL, sessao=sessao)
    titulo_tag = soup.find("h1", class_="book-title")
    titulo = titulo_tag.get_text(strip=True) if titulo_tag else "Título Desconhecido"

    capitulos = []
    for link in soup.select("ul.chapter-list a.chapter-link"):
        href = link.get("href", "").strip()
        if "/chapter/" not in href:
            continue

        numero_tag = link.find("span", class_="chapter-number")
        numero = numero_tag.get_text(strip=True) if numero_tag else ""
        texto_link = link.get_text(" ", strip=True)
        if numero:
            nome = texto_link.replace(numero, "", 1).strip()
        else:
            nome = texto_link

        capitulos.append(
            {
                "titulo": nome or "Capítulo",
                "url": _normalizar_url(href),
            }
        )

    return titulo, capitulos


def _extrair_texto_capitulo(url, sessao):
    soup = _obter_soup(url, referer=BASE_URL, sessao=sessao)
    titulo_tag = soup.find("h1", class_="chapter-title")
    titulo_capitulo = titulo_tag.get_text(" ", strip=True) if titulo_tag else "Capítulo"

    container = soup.find("div", id="chapter-text")
    if not container:
        return titulo_capitulo, ""

    for bloco in container.select("div.chapter-options, div.ad, script, style"):
        bloco.decompose()

    notas_iniciais = []
    notas_finais = []
    for alerta in container.select("div.alert"):
        cabecalho = alerta.find("h5")
        texto = alerta.find("div", class_="pre")
        if not cabecalho or not texto:
            continue

        titulo_nota = cabecalho.get_text(" ", strip=True).lower()
        conteudo_nota = texto.get_text("\n", strip=True)
        if not conteudo_nota:
            continue

        if "iniciais" in titulo_nota:
            notas_iniciais.append(conteudo_nota)
        elif "finais" in titulo_nota:
            notas_finais.append(conteudo_nota)

    paragrafos = [p.get_text(" ", strip=True) for p in container.find_all("p") if p.get_text(" ", strip=True)]

    partes = []
    if notas_iniciais:
        partes.append("Notas iniciais:\n" + "\n\n".join(notas_iniciais))
    if paragrafos:
        partes.append("\n\n".join(paragrafos))
    if notas_finais:
        partes.append("Notas finais:\n" + "\n\n".join(notas_finais))

    return titulo_capitulo, "\n\n".join(partes).strip()


def baixar_plusfiction(url, modo, formato, pasta, progress_cb=None, cancel_event=None, selecao_capitulos=""):
    try:
        url_limpa = url.strip()
        if not url_limpa:
            return False, "A URL do PlusFiction está vazia."

        sessao = _criar_sessao()

        if progress_cb:
            progress_cb(5, "Acessando PlusFiction...", -1)

        is_url_capitulo = "/chapter/" in url_limpa
        url_obra = url_limpa.split("/chapter/")[0] if is_url_capitulo else url_limpa
        url_obra = _normalizar_url(url_obra)

        titulo_obra, capitulos = _extrair_dados_obra(url_obra, sessao)

        if cancel_event and cancel_event.is_set():
            return False, "Download cancelado pelo usuário."

        if modo == "Apenas este capítulo":
            aviso = ""
            if is_url_capitulo:
                alvo = _normalizar_url(url_limpa)
            else:
                if not capitulos:
                    return False, "Não foi possível encontrar capítulos nessa obra."
                alvo = capitulos[0]["url"]
                aviso = "\n(Nota: você colou a URL da obra; foi baixado o primeiro capítulo.)"

            if progress_cb:
                progress_cb(70, "Extraindo texto do capítulo...", -1)

            titulo_capitulo, texto = _extrair_texto_capitulo(alvo, sessao)
            if not texto:
                return False, "Não foi possível extrair o texto do capítulo."

            texto_final = f"--- {titulo_capitulo} ---\n\n{texto}"
        else:
            if is_url_capitulo and not capitulos:
                return False, "Para obra completa, use o link da página principal da história."
            if not capitulos:
                return False, "Nenhum capítulo encontrado no índice da obra."

            textos = []
            inicio = time.time()
            capitulos_para_baixar = list(enumerate(capitulos, start=1))
            if modo == "Selecionar capítulos":
                try:
                    capitulos_para_baixar = selecionar_capitulos(capitulos, selecao_capitulos)
                except SelecaoCapitulosError as e:
                    return False, str(e)

            total = len(capitulos_para_baixar)
            aviso = ""

            for i, (numero_capitulo, cap) in enumerate(capitulos_para_baixar):
                if cancel_event and cancel_event.is_set():
                    return False, "Download cancelado pelo usuário."

                titulo_capitulo, texto_capitulo = _extrair_texto_capitulo(cap["url"], sessao)
                if not texto_capitulo:
                    continue

                textos.append(f"--- CAPITULO {numero_capitulo}: {titulo_capitulo} ---\n\n{texto_capitulo}")

                if progress_cb:
                    pct = int(((i + 1) / total) * 95)
                    decorrido = time.time() - inicio
                    restante = (decorrido / (i + 1)) * (total - (i + 1))
                    progress_cb(pct, f"Baixando capítulo {i + 1} de {total}...", restante)

                time.sleep(0.1)

            if not textos:
                return False, "Não foi possível extrair o texto dos capítulos."

            texto_final = "\n\n\n".join(textos)

        if cancel_event and cancel_event.is_set():
            return False, "Download cancelado pelo usuário."

        if progress_cb:
            progress_cb(98, "Salvando arquivo...", -1)

        if formato == "TXT":
            caminho = salvar_txt(titulo_obra, texto_final, pasta)
        elif formato == "PDF":
            caminho = salvar_pdf(titulo_obra, texto_final, pasta)
        elif formato == "EPUB":
            caminho = salvar_epub(titulo_obra, texto_final, pasta)
        else:
            return False, f"O formato {formato} ainda não está disponível para PlusFiction."

        return True, f"Download concluído!{aviso}\nArquivo salvo em:\n{caminho}"
    except requests.exceptions.Timeout:
        return False, "O PlusFiction demorou muito para responder. Tente novamente."
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "desconhecido"
        if status == 403:
            return False, "O PlusFiction bloqueou o acesso automatizado (HTTP 403) mesmo após retentativas com sessão aquecida."
        return False, f"Falha ao acessar o PlusFiction (HTTP {status})."
    except Exception as e:
        return False, f"Erro no download do PlusFiction:\n{str(e)}"
