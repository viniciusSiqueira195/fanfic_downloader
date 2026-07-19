"""Downloader do Spirit Fanfics baseado no Camoufox (Firefox anti-detecção).

O Spirit exige login para ler qualquer capítulo e protege o login com
Cloudflare Turnstile, que bloqueia clientes HTTP comuns e navegadores com CDP
(Playwright/Chrome). O Camoufox resolve o Turnstile "managed" sozinho, sem
interação do usuário.

Fluxo:
  1. Se existe uma sessão salva (spirit_session.json), ela é reutilizada.
  2. Sem sessão válida, o login é feito com usuário/senha fornecidos pela GUI;
     apenas os cookies da sessão ficam salvos no computador, nunca a senha.
  3. Quando falta login (sem credenciais, sessão expirada ou senha recusada),
     retorna (False, LOGIN_NECESSARIO + motivo) para a GUI pedir as credenciais.
"""
import glob
import html as html_lib
import os
import re
import sys
import threading
import time
from pathlib import Path

from converters.to_txt import salvar_txt
from converters.to_pdf import salvar_pdf
from converters.to_epub import salvar_epub
from scrapers.chapter_selection import SelecaoCapitulosError, selecionar_capitulos

BASE_URL = "https://www.spiritfanfiction.com"
LOGIN_URL = f"{BASE_URL}/login"

# Relativo ao diretório de trabalho (ao lado do config.json), para funcionar
# junto do executável na máquina de cada usuário.
SESSION_FILE = Path("spirit_session.json")

# Prefixo-sentinela: a GUI detecta e abre o diálogo de login, com o motivo após o prefixo
LOGIN_NECESSARIO = "__SPIRIT_LOGIN_NECESSARIO__"


def tem_sessao_salva():
    return SESSION_FILE.exists()


# ----------------------------------------------------------------------------
# Localização do executável do Camoufox
# ----------------------------------------------------------------------------
_EXE_NAMES = ("camoufox.exe",) if sys.platform == "win32" else ("camoufox", "camoufox-bin")


def _app_base_dirs():
    """Diretórios candidatos onde o binário do Camoufox pode estar empacotado
    junto do app. Cobre execução como script, PyInstaller e Nuitka."""
    dirs = []
    if getattr(sys, "frozen", False):
        dirs.append(Path(sys.executable).resolve().parent)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            dirs.append(Path(meipass))
    if "__compiled__" in globals():
        try:
            dirs.append(Path(sys.argv[0]).resolve().parent)
        except Exception:
            pass
    try:
        # sobe de src/scrapers/ até a raiz do projeto
        raiz = Path(__file__).resolve().parent.parent.parent
        dirs.append(raiz)
        dirs.append(Path(__file__).resolve().parent)
    except Exception:
        pass
    dirs.append(Path.cwd())
    out, seen = [], set()
    for d in dirs:
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _search_dir_for_exe(base):
    for sub in ("", "camoufox", "browser", "camoufox-browser", "bin"):
        d = base / sub if sub else base
        for name in _EXE_NAMES:
            p = d / name
            if p.exists():
                return str(p)
    for sub in ("camoufox", "browser", "camoufox-browser"):
        d = base / sub
        if d.is_dir():
            for name in _EXE_NAMES:
                hits = sorted(d.glob(f"**/{name}"))
                if hits:
                    return str(hits[0])
    return None


def _exe_utilizavel(exe_path):
    """True se o caminho aponta para um Camoufox instalado por COMPLETO.
    Um download/extração interrompido pode deixar o camoufox.exe (798 KB) sem o
    xul.dll (o motor, ~170 MB); nesse caso o navegador não lança. Exigir o
    xul.dll ao lado evita usar uma instalação parcial."""
    exe = Path(exe_path)
    return exe.exists() and (exe.parent / "xul.dll").exists()


def find_camoufox_exe():
    """Localiza o binário do Camoufox: variável CAMOUFOX_EXE, pasta do app
    (usuário final recebe o browser empacotado) ou caches de instalação
    (ambiente de desenvolvimento). Só retorna instalações completas."""
    env = os.environ.get("CAMOUFOX_EXE")
    if env and _exe_utilizavel(env):
        return env

    # 1) empacotado junto do app (release) tem prioridade
    for base in _app_base_dirs():
        hit = _search_dir_for_exe(base)
        if hit and _exe_utilizavel(hit):
            return hit

    # 2) mecanismo OFICIAL do pacote camoufox: garante que o que foi baixado
    #    por garantir_camoufox seja encontrado, seja qual for a pasta que o
    #    platformdirs escolher (evita descasamento com os globs abaixo)
    try:
        from camoufox.pkgman import camoufox_path
        p = camoufox_path(download_if_missing=False)
        if p:
            for name in _EXE_NAMES:
                exe = Path(p) / name
                if _exe_utilizavel(exe):
                    return str(exe)
    except Exception:
        pass

    la = os.environ.get("LOCALAPPDATA", "")
    dev_patterns = [
        os.path.join(la, "Packages", "PythonSoftwareFoundation.Python*",
                     "LocalCache", "Local", "camoufox", "**", "camoufox.exe"),
        os.path.join(la, "camoufox", "**", "camoufox.exe"),
        os.path.join(os.path.expanduser("~"), ".cache", "camoufox", "**", "camoufox*"),
    ]
    for pat in dev_patterns:
        for hit in sorted(glob.glob(pat, recursive=True)):
            if _exe_utilizavel(hit):
                return hit
    return None


def camoufox_instalado():
    """True se o navegador Camoufox já está disponível (empacotado ou baixado)."""
    return find_camoufox_exe() is not None


def _dir_instalacao_camoufox():
    """Pasta FÍSICA e gravável onde instalar o Camoufox baixado, ao lado do app.

    Não usamos o cache padrão do camoufox (AppData\\Local\\camoufox): sob o Python
    da Microsoft Store esse caminho é VIRTUALIZADO para dentro de
    Packages\\...\\LocalCache, e o subprocesso do navegador não resolve essa
    virtualização — o launch falha com "executable doesn't exist". A pasta do
    app é um caminho real, que o find_camoufox_exe já procura primeiro."""
    for base in _app_base_dirs():
        try:
            base.mkdir(parents=True, exist_ok=True)
            teste = base / ".cf_write_test"
            teste.write_text("x")
            teste.unlink()
            return base / "camoufox"
        except Exception:
            continue
    return None


def _baixar_camoufox_para(destino, progress_cb, cancel_event):
    """Baixa e extrai a última versão do Camoufox para `destino` (caminho real)."""
    import shutil
    import tempfile
    from camoufox.pkgman import CamoufoxFetcher, webdl, unzip

    fetcher = CamoufoxFetcher()  # fetch_latest no __init__ resolve a URL do release
    url = fetcher.url

    destino = Path(destino)
    if destino.exists():
        shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True, exist_ok=True)

    def _cb(baixado, total):
        if progress_cb and total:
            pct = max(1, min(99, int(baixado / total * 100)))
            progress_cb(pct, f"Baixando o navegador seguro do Spirit... {pct}%", -1)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    try:
        with open(tmp.name, "wb") as f:
            webdl(url, buffer=f, bar=False, progress_callback=_cb)
        if progress_cb:
            progress_cb(-1, "Instalando o navegador seguro (extraindo)...", -1)
        with open(tmp.name, "rb") as f:
            unzip(f, str(destino), bar=False)
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    # Marca a versão instalada (o camoufox exige version.json para reconhecer
    # a instalação) e registra a pasta do app como a instalação ativa.
    _escrever_version_json(destino, fetcher.version, fetcher.build,
                           getattr(fetcher, "is_prerelease", False))
    _registrar_camoufox(destino)


def garantir_camoufox(progress_cb=None, cancel_event=None):
    """Garante que o navegador Camoufox esteja disponível. Se faltar (ex.: o
    release não empacota os ~900 MB do navegador), baixa uma vez para a pasta do
    app. Retorna (True, None) ou (False, mensagem_de_erro)."""
    if camoufox_instalado():
        return True, None

    # Faz o Python usar os certificados do Windows. Sem isso, antivírus que
    # interceptam o SSL (ex.: Avast) quebram o download do GitHub com
    # "CERTIFICATE_VERIFY_FAILED", embora o navegador em si funcione.
    try:
        import truststore
        truststore.inject_into_ssl()
    except Exception:
        pass

    destino = _dir_instalacao_camoufox()
    if destino is None:
        return False, ("Não há uma pasta gravável para instalar o navegador seguro "
                       "do Spirit. Verifique as permissões da pasta do aplicativo.")

    resultado = {}

    def _baixar():
        import contextlib
        try:
            # Suprime a barra 'rich' do camoufox (Unicode quebra o stdout cp1252)
            with open(os.devnull, "w", encoding="utf-8") as devnull:
                with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                    _baixar_camoufox_para(destino, progress_cb, cancel_event)
            resultado["ok"] = True
        except Exception as e:  # rede, permissão, etc.
            resultado["erro"] = str(e)

    tarefa = threading.Thread(target=_baixar, daemon=True)
    tarefa.start()

    while tarefa.is_alive():
        if _cancelado(cancel_event):
            # o download segue em background (thread daemon), mas paramos de esperar
            return False, "Download cancelado pelo usuário."
        tarefa.join(timeout=0.3)

    if resultado.get("ok") and camoufox_instalado():
        return True, None
    return False, ("Não foi possível baixar o navegador seguro do Spirit. "
                   "Verifique sua conexão com a internet e tente novamente.\n"
                   f"Detalhe técnico: {resultado.get('erro', 'desconhecido')}")


def _novo_navegador(headless=True):
    """Cria o navegador Camoufox.

    headless=False é usado no login: a janela fica visível para o usuário
    resolver a verificação do Cloudflare e entrar na conta manualmente.

    A combinação geoip=True + locale no próprio Camoufox (nunca via
    new_context) é o que mantém a impressão digital consistente e faz o
    Cloudflare Turnstile aprovar. Não usar disable_coop nem os/i_know_what_im_doing:
    esses ajustes deixam o navegador detectável."""
    from camoufox.sync_api import Camoufox

    kwargs = dict(
        headless=headless,
        humanize=True,
        geoip=True,
        locale="pt-BR",
        window=(1280, 900),
    )
    exe = find_camoufox_exe()
    if exe:
        pasta = Path(exe).parent
        # Faz o Camoufox resolver TUDO (binário, fontes, fontconfig) nesta pasta
        # física. Sob o Python da Microsoft Store o cache padrão é virtualizado e
        # o subprocesso do navegador não o resolve — o launch falharia.
        _registrar_camoufox(pasta)
        # Sem a base GeoIP o launch com geoip=True quebra; garantimos que está lá.
        _garantir_geoip()
        kwargs["executable_path"] = exe
    return Camoufox(**kwargs)


def _escrever_version_json(pasta, version, build, prerelease=False):
    """Cria o version.json que o camoufox usa para reconhecer a instalação."""
    import json
    try:
        dados = {"version": str(version), "build": str(build), "prerelease": bool(prerelease)}
        (Path(pasta) / "version.json").write_text(json.dumps(dados), encoding="utf-8")
    except Exception:
        pass


def _registrar_camoufox(pasta):
    """Registra a pasta do app (caminho físico real) como a instalação ativa do
    Camoufox, para que camoufox_path()/get_path()/launch_path() a usem em vez do
    cache virtualizado. Um caminho absoluto em active_version faz o camoufox
    resolver direto para esta pasta."""
    pasta = Path(pasta).resolve()
    # garante o version.json (empacotamento manual pode não trazê-lo)
    if not (pasta / "version.json").exists():
        version, build = "152.0.4", "stable"
        ini = pasta / "application.ini"
        try:
            if ini.exists():
                m = re.search(r"Version=([\d.]+)-?(\S*)", ini.read_text(errors="ignore"))
                if m:
                    version = m.group(1)
                    build = m.group(2) or "stable"
        except Exception:
            pass
        _escrever_version_json(pasta, version, build)
    try:
        from camoufox.multiversion import set_active, COMPAT_FLAG
        set_active(str(pasta))
        COMPAT_FLAG.touch()
    except Exception:
        pass


def _garantir_geoip():
    """Baixa a base GeoIP (para o geoip=True) se faltar. O download interno do
    camoufox ignora o truststore e falha atrás de antivírus que interceptam SSL;
    baixamos nós mesmos (requests + truststore) da CDN que está no ar."""
    try:
        import requests
        from camoufox.geolocation import get_mmdb_path, load_geoip_config, MMDB_DIR
    except Exception:
        return
    try:
        import truststore
        truststore.inject_into_ssl()
    except Exception:
        pass
    try:
        cfg = load_geoip_config()
    except Exception:
        return
    try:
        MMDB_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        return
    for ip_ver, urls in cfg.get("urls", {}).items():
        try:
            destino = get_mmdb_path(ip_ver)
        except Exception:
            continue
        if destino.exists() and destino.stat().st_size > 1000:
            continue
        if isinstance(urls, str):
            urls = [urls]
        for url in urls:
            try:
                r = requests.get(url, timeout=120)
                r.raise_for_status()
                destino.write_bytes(r.content)
                break
            except Exception:
                continue


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def _cancelado(cancel_event):
    return cancel_event is not None and cancel_event.is_set()


def _clean(txt):
    txt = html_lib.unescape(txt)
    lines = [ln.rstrip() for ln in txt.splitlines()]
    out, blank = [], 0
    for ln in lines:
        if not ln.strip():
            blank += 1
            if blank <= 1:
                out.append("")
        else:
            blank = 0
            out.append(ln.strip())
    return "\n".join(out).strip()


def _limpar_titulo(titulo):
    titulo = html_lib.unescape(titulo or "")
    titulo = re.sub(r"^Fanfic\s*/\s*Fanfiction\s*", "", titulo).strip()
    return titulo


# ----------------------------------------------------------------------------
# Parsing da página da história (lista de capítulos)
# ----------------------------------------------------------------------------
def _parse_story_html(html, story_url):
    """(titulo_historia, [(num, titulo_cap, url), ...]) a partir do HTML da
    página da história. A listagem é pública (não exige login)."""
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    story_title = "Historia"
    if m:
        story_title = re.split(r"\s*-\s*Hist[oó]ria",
                               html_lib.unescape(m.group(1)))[0].strip() or "Historia"
    story_title = _limpar_titulo(story_title)

    slug_m = re.search(r"/historia/([a-z0-9-]+-\d+)", story_url)
    slug = slug_m.group(1) if slug_m else r"[a-z0-9-]+-\d+"

    link_re = re.compile(
        r'href="(https://www\.spiritfanfiction\.com/historia/' + slug
        + r'/capitulos/\d+)"(?:\s+title="([^"]*)")?'
    )
    chapters, seen = [], set()
    for url, raw_title in link_re.findall(html):
        if url in seen:
            continue
        seen.add(url)
        title = _limpar_titulo(raw_title)
        title = re.sub(r"^.*?\s-\s", "", title, count=1) if " - " in title else title
        chapters.append((len(chapters) + 1, title or f"Capitulo {len(chapters)+1}", url))
    return story_title, chapters


# ----------------------------------------------------------------------------
# Extração do texto do capítulo
# ----------------------------------------------------------------------------
def _extrair_texto_capitulo(page):
    """Extrai o texto do capítulo. Tenta seletores conhecidos e cai para uma
    heurística de densidade de <p> (o corpo da fic é uma sequência de
    parágrafos), ignorando menus/rodapé/comentários."""
    candidates = [
        "#historia-capitulo", ".historia-capitulo",
        ".historia-texto", ".texto-capitulo", ".capitulo-texto",
        "#texto", "#conteudo-capitulo", "div.text-justify",
    ]
    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                txt = loc.inner_text(timeout=3000)
                if txt and len(txt.strip()) > 200:
                    return _clean(txt)
        except Exception:
            continue

    js = r"""
    () => {
        const bad = 'nav, footer, header, .navbar, .comentario, .comentarios, #comentarios, aside, form, script, style';
        const nodes = Array.from(document.querySelectorAll('div, article, section'));
        let best = null, bestLen = 0;
        for (const n of nodes) {
            if (n.closest(bad)) continue;
            const ps = n.querySelectorAll(':scope > p, :scope > div > p');
            if (ps.length < 2) continue;
            let len = 0;
            ps.forEach(p => len += (p.innerText || '').length);
            if (len > bestLen) { bestLen = len; best = n; }
        }
        if (best) {
            return Array.from(best.querySelectorAll('p'))
                        .map(p => p.innerText.trim()).filter(Boolean).join('\n\n');
        }
        return '';
    }
    """
    txt = page.evaluate(js)
    if txt and len(txt.strip()) > 200:
        return _clean(txt)

    js2 = r"""
    () => {
        const nodes = Array.from(document.querySelectorAll('div, article, section'));
        let best = '', bestLen = 0;
        for (const n of nodes) {
            if (n.closest('nav, footer, header, .navbar')) continue;
            const t = n.innerText || '';
            if (t.length > bestLen) { bestLen = t.length; best = t; }
        }
        return best;
    }
    """
    return _clean(page.evaluate(js2) or "")


# ----------------------------------------------------------------------------
# Login e sessão
# ----------------------------------------------------------------------------
def _fechar_banner_cookies(page):
    """O banner de cookies cobre o widget do Turnstile; fecha se aparecer."""
    for sel in ('button:has-text("Prosseguir")', 'text=Prosseguir'):
        try:
            page.locator(sel).first.click(timeout=2500)
            return
        except Exception:
            continue


def _contexto_sessao_salva(browser):
    """Abre um contexto com a sessão salva, se existir e ainda for válida."""
    if not SESSION_FILE.exists():
        return None
    try:
        # locale já vem do Camoufox; não sobrepor aqui (quebra a fingerprint)
        ctx = browser.new_context(storage_state=str(SESSION_FILE))
        page = ctx.new_page()
        page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        if "/login" in page.url:
            ctx.close()
            return None
        page.close()
        return ctx
    except Exception:
        return None


TIMEOUT_LOGIN_MANUAL = 300  # segundos que o usuário tem para completar o login


def _login_manual(browser, usuario, senha, progress_cb, cancel_event):
    """Abre a página de login numa janela VISÍVEL para o usuário entrar na
    conta (incluindo resolver o Cloudflare Turnstile). Não tenta automatizar o
    captcha: apenas aguarda o login ser concluído, detectado quando a página
    sai de /login, e então salva a sessão. Retorna (contexto, None) ou
    (None, mensagem_de_erro)."""
    ctx = browser.new_context()  # locale já vem do Camoufox
    page = ctx.new_page()
    try:
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        _fechar_banner_cookies(page)

        # já autenticado por algum motivo (cookies do navegador)
        if "/login" not in page.url:
            try:
                ctx.storage_state(path=str(SESSION_FILE))
            except Exception:
                pass
            return ctx, None

        # pré-preenche as credenciais para o usuário só resolver a verificação
        if usuario:
            try:
                page.fill("#Usuario", usuario)
            except Exception:
                pass
        if senha:
            try:
                page.fill("#Senha", senha)
            except Exception:
                pass
    except Exception:
        # janela fechada/erro antes mesmo de começar
        try:
            ctx.close()
        except Exception:
            pass
        return None, LOGIN_NECESSARIO + "Não foi possível abrir a tela de login do Spirit. Tente novamente."

    if progress_cb:
        progress_cb(10, "Faça login na janela do Spirit que abriu (resolva a verificação e clique em Entrar)...", -1)

    # aguarda o usuário concluir o login manualmente
    inicio = time.time()
    while time.time() - inicio < TIMEOUT_LOGIN_MANUAL:
        if _cancelado(cancel_event):
            try:
                ctx.close()
            except Exception:
                pass
            return None, "Download cancelado pelo usuário."

        # IMPORTANTE: page.wait_for_timeout é uma chamada ao Playwright e
        # processa os eventos de navegação, mantendo page.url atualizado. Um
        # time.sleep() comum NÃO faz isso: numa thread secundária (a da GUI) o
        # page.url ficaria congelado na URL de login e o login nunca seria
        # detectado.
        try:
            page.wait_for_timeout(1000)
            url_atual = page.url
        except Exception:
            # o usuário fechou a janela antes de concluir
            return None, LOGIN_NECESSARIO + "A janela de login foi fechada antes de concluir. Tente novamente."

        if url_atual and "/login" not in url_atual:
            # login concluído: salva a sessão para os próximos downloads
            try:
                ctx.storage_state(path=str(SESSION_FILE))
            except Exception:
                pass
            if progress_cb:
                progress_cb(16, "Login concluído! Retomando o download...", -1)
            return ctx, None

    try:
        ctx.close()
    except Exception:
        pass
    return None, LOGIN_NECESSARIO + ("Tempo esgotado para o login. Clique em baixar novamente "
                                     "e conclua o login na janela do Spirit.")


def _abrir_contexto_autenticado(browser, usuario, senha, progress_cb, cancel_event, precisa_login):
    """Devolve (contexto_autenticado, None) ou (None, mensagem_de_erro).

    Com sessão salva válida, reutiliza-a (modo silencioso/headless). Sem sessão
    válida, faz o login manual na janela visível."""
    if not precisa_login:
        if progress_cb:
            progress_cb(5, "Verificando sessão salva do Spirit...", -1)
        ctx = _contexto_sessao_salva(browser)
        if ctx is not None:
            return ctx, None
        # sessão salva expirou: remove e pede novo login (a GUI reabre visível)
        try:
            SESSION_FILE.unlink()
        except Exception:
            pass
        return None, LOGIN_NECESSARIO + "Sua sessão do Spirit expirou. Faça login novamente."

    return _login_manual(browser, usuario, senha, progress_cb, cancel_event)


# ----------------------------------------------------------------------------
# Download
# ----------------------------------------------------------------------------
def _url_da_historia(url):
    """Se a URL for de um capítulo, devolve a URL da página da história."""
    return re.sub(r"/capitulos/\d+.*$", "", url)


def _listar_capitulos(page, url, modo):
    if modo == "Apenas este capítulo":
        if "/capitulos/" not in url:
            return None, None, ("Para baixar apenas um capítulo, cole o link do capítulo "
                                "(ele contém /capitulos/ no endereço). Para a obra inteira, "
                                "use o modo Obra Completa.")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        if "/login" in page.url:
            return None, None, LOGIN_NECESSARIO + "Sua sessão do Spirit expirou. Entre novamente para continuar."
        titulo_pagina = _limpar_titulo(page.title())
        titulo = re.split(r"\s*-\s*Hist[oó]ria", titulo_pagina)[0].strip() or "Fanfic_Spirit"
        return titulo, [(1, titulo_pagina or "Capitulo 1", url)], None

    page.goto(_url_da_historia(url), wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1500)
    titulo, capitulos = _parse_story_html(page.content(), url)
    if not capitulos:
        return None, None, ("Nenhum capítulo encontrado. Verifique se a URL é de uma "
                            "história do Spirit Fanfics.")
    return titulo, capitulos, None


def baixar_spirit(url, modo, formato, pasta, progress_cb=None, cancel_event=None,
                  selecao_capitulos="", usuario="", senha=""):
    try:
        from camoufox.sync_api import Camoufox  # noqa: F401
    except ImportError:
        return False, ("O componente de navegação segura (Camoufox) não está instalado.\n"
                       "Reinstale o aplicativo ou execute: pip install camoufox[geoip]")

    # Garante o navegador Camoufox (baixa na primeira vez, se o release não o empacotar)
    if progress_cb:
        progress_cb(1, "Verificando o navegador seguro do Spirit...", -1)
    ok, erro = garantir_camoufox(progress_cb, cancel_event)
    if not ok:
        return False, erro

    try:
        url = url.strip()
        # Sem sessão salva é preciso login manual → janela visível.
        # Com sessão salva, o download roda silencioso (headless).
        precisa_login = not SESSION_FILE.exists()

        if progress_cb:
            progress_cb(2, "Preparando navegador seguro (Camoufox)...", -1)

        with _novo_navegador(headless=not precisa_login) as browser:
            if _cancelado(cancel_event):
                return False, "Download cancelado pelo usuário."

            ctx, erro = _abrir_contexto_autenticado(browser, usuario, senha,
                                                    progress_cb, cancel_event,
                                                    precisa_login)
            if ctx is None:
                return False, erro

            page = ctx.new_page()
            if progress_cb:
                progress_cb(18, "Mapeando capítulos da história...", -1)
            titulo, capitulos, erro = _listar_capitulos(page, url, modo)
            if erro:
                return False, erro

            capitulos_para_baixar = capitulos
            if modo == "Selecionar capítulos":
                try:
                    selecionados = selecionar_capitulos(capitulos, selecao_capitulos)
                except SelecaoCapitulosError as e:
                    return False, str(e)
                capitulos_para_baixar = [cap for _, cap in selecionados]

            total = len(capitulos_para_baixar)
            textos = []
            inicio = time.time()

            for i, (numero, titulo_cap, link) in enumerate(capitulos_para_baixar):
                if _cancelado(cancel_event):
                    return False, "Download cancelado pelo usuário."

                texto = ""
                for tentativa in (1, 2):
                    try:
                        page.goto(link, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(1500)
                        if "/login" in page.url:
                            return False, (LOGIN_NECESSARIO
                                           + "Sua sessão do Spirit expirou durante o download. "
                                             "Entre novamente para continuar.")
                        texto = _extrair_texto_capitulo(page)
                        if not texto or len(texto) < 100:
                            raise RuntimeError("texto vazio ou curto demais")
                        break
                    except Exception:
                        if tentativa == 2:
                            texto = "[Não foi possível extrair o texto deste capítulo.]"
                        else:
                            page.wait_for_timeout(2500)

                textos.append(f"--- CAPITULO {numero}: {titulo_cap} ---\n\n{texto}")

                if progress_cb:
                    pct = 20 + int(((i + 1) / total) * 70)
                    decorrido = time.time() - inicio
                    restante = (decorrido / (i + 1)) * (total - (i + 1))
                    progress_cb(pct, f"Baixando capítulo {i + 1} de {total}...", restante)

                if i + 1 < total:
                    time.sleep(1.0)  # gentil com o servidor

        if _cancelado(cancel_event):
            return False, "Download cancelado pelo usuário."

        texto_final = "\n\n\n".join(textos)

        if progress_cb:
            progress_cb(95, f"Preparando conversão para {formato}...", -1)

        if formato == "TXT":
            caminho = salvar_txt(titulo, texto_final, pasta)
        elif formato == "PDF":
            caminho = salvar_pdf(titulo, texto_final, pasta)
        elif formato == "EPUB":
            caminho = salvar_epub(titulo, texto_final, pasta)
        else:
            return False, f"O formato {formato} ainda será implementado."

        if progress_cb:
            progress_cb(100, "Concluído!", 0)
        return True, f"Download concluído!\nArquivo salvo em:\n{caminho}"

    except Exception as e:
        return False, f"Erro inesperado ao baixar do Spirit:\n{str(e)}"
