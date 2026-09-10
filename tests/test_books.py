import io
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from books.download import baixar_livro, DownloadCancelado, ErroPasta
from books.visionvox import Livro, Visionvox, extrair_livros, validar_url


class Resposta:
    def __init__(self, dados=b"Texto de teste", status=200, headers=None, callback=None):
        self.content = dados
        self.status_code = status
        self.headers = headers or {}
        self.callback = callback

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError("Falha HTTP")

    def iter_content(self, tamanho):
        yield self.content[:5]
        if self.callback:
            self.callback()
        yield self.content[5:]


class BuscaTests(unittest.TestCase):
    def test_parser_filtra_links_e_duplicatas(self):
        html = '''<a href="https://visionvox.net/biblioteca/a.epub">Ação &amp; voz.epub</a>
        <a href="https://visionvox.net/biblioteca/a.epub">Duplicado</a>
        <a href="/biblioteca/b.TXT">B</a><a href="/busca.php">Próxima</a>
        <a href="https://visionvox.net.evil.test/a.pdf">Falso</a>'''
        livros = extrair_livros(html)
        self.assertEqual(len(livros), 2)
        self.assertEqual(livros[0].titulo, "Ação & voz.epub")
        self.assertEqual(livros[1].formato, "txt")

    def test_url_nao_confunde_dominio_com_texto(self):
        for url in ("https://evil.test/?visionvox.net", "http://visionvox.net/a.txt",
                    "https://visionvox.net.evil.test/a.txt", "https://x@visionvox.net/a.txt",
                    "file:///a.txt", "https://visionvox.net:444/a.txt"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validar_url(url)

    def test_busca_parametros_paginacao_acentos(self):
        http = Mock()
        http.get.return_value = Resposta('<a href="https://visionvox.net/a.epub">Ação</a>'.encode())
        livros = Visionvox(http).buscar(" ação ", "epub", 2)
        self.assertEqual(livros[0].titulo, "Ação")
        self.assertEqual(http.get.call_args.kwargs["params"],
                         {"busca": "ação", "ext": "epub", "pagina": "sim", "num_page": 2})

    def test_entrada_invalida_nao_acessa_rede(self):
        http = Mock()
        for termo, formato, pagina in [(" ", "epub", 0), ("x", "exe", 0), ("x", "txt", -1)]:
            with self.assertRaises(ValueError):
                Visionvox(http).buscar(termo, formato, pagina)
        http.get.assert_not_called()

    def test_bloqueio_nao_parece_busca_vazia(self):
        http = Mock()
        http.get.return_value = Resposta(b"<html>Verifique que voce e humano</html>")
        with self.assertRaises(ValueError):
            Visionvox(http).buscar("teste")

    def test_busca_vazia(self):
        http = Mock()
        http.get.return_value = Resposta(b'<input name="busca"><h2>Encontramos 0 resultados</h2>')
        self.assertEqual(Visionvox(http).buscar("teste"), [])


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        self.livro = Livro("Ação.txt", "https://visionvox.net/a.txt", "txt")
        self.http = Mock()
        self.http.get.return_value = Resposta()

    def baixar(self, **kwargs):
        return baixar_livro(self.livro, self.pasta, http=self.http, **kwargs)

    def test_salva_bytes_originais(self):
        progresso = Mock()
        caminho = self.baixar(progresso=progresso)
        self.assertEqual(caminho.read_bytes(), b"Texto de teste")
        self.assertEqual(caminho.name, "Ação.txt")
        self.assertFalse(list(self.pasta.glob("*.part")))
        progresso.assert_called()

    def test_nao_sobrescreve(self):
        existente = self.pasta / "Ação.txt"
        existente.write_text("original")
        with self.assertRaises(ValueError):
            self.baixar()
        self.assertEqual(existente.read_text(), "original")
        self.assertEqual(list(self.pasta.iterdir()), [existente])

    def test_pode_salvar_nova_copia_com_nome_numerado(self):
        existente = self.pasta / "Ação.txt"
        existente.write_text("original")
        copia = self.baixar(renomear_se_existir=True)
        self.assertEqual(copia.name, "Ação (2).txt")
        self.assertEqual(existente.read_text(), "original")

    def test_pasta_vazia_ou_relativa_nao_usa_diretorio_de_execucao(self):
        for pasta in ("", "   ", ".", "livros"):
            with self.subTest(pasta=pasta), self.assertRaises(ErroPasta):
                baixar_livro(self.livro, pasta, http=self.http)
        self.http.get.assert_not_called()

    def test_permissao_negada_orienta_escolher_pasta(self):
        with patch("books.download.tempfile.NamedTemporaryFile", side_effect=PermissionError("negado")):
            with self.assertRaisesRegex(ErroPasta, "Escolha outra pasta"):
                self.baixar()
        self.assertEqual(list(self.pasta.iterdir()), [])

    def test_dois_downloads_seguidos_na_mesma_pasta(self):
        primeiro = self.baixar()
        self.livro = Livro("Segundo.txt", "https://visionvox.net/b.txt", "txt")
        segundo = self.baixar()
        self.assertEqual(primeiro.parent, segundo.parent)
        self.assertTrue(primeiro.exists() and segundo.exists())
        self.assertFalse(list(self.pasta.glob("*.part")))

    def test_cancelamento_antes_da_rede(self):
        evento = threading.Event()
        evento.set()
        with self.assertRaises(DownloadCancelado):
            self.baixar(cancel_event=evento)
        self.http.get.assert_not_called()

    def test_cancelamento_remove_temporario(self):
        evento = threading.Event()
        self.http.get.return_value = Resposta(callback=evento.set)
        with self.assertRaises(DownloadCancelado):
            self.baixar(cancel_event=evento)
        self.assertEqual(list(self.pasta.iterdir()), [])

    def test_limite_sem_content_length(self):
        with self.assertRaises(ValueError):
            self.baixar(limite_bytes=6)
        self.assertEqual(list(self.pasta.iterdir()), [])

    def test_limite_declarado(self):
        self.http.get.return_value = Resposta(headers={"Content-Length": "200"})
        with self.assertRaises(ValueError):
            self.baixar(limite_bytes=100)
        self.assertEqual(list(self.pasta.iterdir()), [])

    def test_rejeita_html_vazio_ou_truncado(self):
        for resposta in (Resposta(b"<html>Erro</html>"), Resposta(b""),
                         Resposta(headers={"Content-Type": "text/html"}),
                         Resposta(headers={"Content-Length": "200"})):
            with self.subTest(resposta=resposta):
                self.http.get.return_value = resposta
                with self.assertRaises(ValueError):
                    self.baixar()
                self.assertEqual(list(self.pasta.iterdir()), [])

    def test_redirecionamento_externo_nao_e_seguido(self):
        self.http.get.return_value = Resposta(status=302, headers={"Location": "https://evil.test/a.txt"})
        with self.assertRaises(ValueError):
            self.baixar()
        self.http.get.assert_called_once()

    def test_redirecionamento_interno(self):
        self.http.get.side_effect = [Resposta(status=302, headers={"Location": "/b.txt"}), Resposta()]
        self.assertTrue(self.baixar().exists())
        self.assertEqual(self.http.get.call_args.args[0], "https://visionvox.net/b.txt")

    def test_falha_http(self):
        import requests
        self.http.get.return_value = Resposta(status=404)
        with self.assertRaises(requests.HTTPError):
            self.baixar()
        self.assertEqual(list(self.pasta.iterdir()), [])

    def test_validacao_epub(self):
        self.livro = Livro("Livro", "https://visionvox.net/a.epub", "epub")
        self.http.get.return_value = Resposta(b"nao e epub")
        with self.assertRaises(ValueError):
            self.baixar()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as arquivo:
            arquivo.writestr("mimetype", b"application/epub+zip")
        self.http.get.return_value = Resposta(buffer.getvalue())
        self.assertEqual(self.baixar().suffix, ".epub")

    def test_validacao_pdf(self):
        self.livro = Livro("Livro", "https://visionvox.net/a.pdf", "pdf")
        with self.assertRaises(ValueError):
            self.baixar()
        self.http.get.return_value = Resposta(b"%PDF-1.7\nfixture")
        self.assertEqual(self.baixar().suffix, ".pdf")
