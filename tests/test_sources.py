import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from books.gutenberg import Gutenberg
from books.models import Livro, PaginaLivros
from books.sources import TodasFontes
from books.urls import validar_url_download
from books.visionvox import Visionvox


class SourcesTests(unittest.TestCase):
    def setUp(self):
        self.http = Mock()
        self.resposta = self.http.get.return_value

    def test_gutenberg_busca_paginada_por_titulo_autor_e_formato(self):
        self.resposta.json.return_value = {"results": [{
            "title": "Dom Casmurro", "authors": [{"name": "Machado de Assis"}],
            "formats": {"application/epub+zip": "https://www.gutenberg.org/ebooks/55752.epub3.images"},
            "summaries": ["Bentinho conta sua história e suas dúvidas sobre Capitu."]
        }], "next": "https://gutendex.com/books/?page=3"}
        pagina = Gutenberg(self.http).buscar_pagina(" Machado ", "epub", 1)
        self.assertTrue(pagina.tem_proxima)
        self.assertEqual(pagina.livros[0].origem, "Project Gutenberg")
        self.assertIn("Machado de Assis", pagina.livros[0].titulo)
        self.assertIn("Capitu", pagina.livros[0].sinopse)
        self.assertEqual(self.http.get.call_args.kwargs["params"],
                         {"search": "Machado", "mime_type": "application/epub+zip", "page": 2})

    def test_gutenberg_prefere_txt_utf8(self):
        self.resposta.json.return_value = {"results": [{"title": "Ação", "formats": {
            "text/plain; charset=us-ascii": "https://www.gutenberg.org/a.txt",
            "text/plain; charset=utf-8": "https://www.gutenberg.org/a-8.txt",
        }}], "next": None}
        pagina = Gutenberg(self.http).buscar_pagina("ação", "txt")
        self.assertEqual(pagina.livros[0].url, "https://www.gutenberg.org/a-8.txt")
        self.assertFalse(pagina.tem_proxima)

    def test_formato_indisponivel_e_link_externo_nao_viram_download(self):
        self.resposta.json.return_value = {"results": [
            {"title": "HTML", "formats": {"text/html": "https://www.gutenberg.org/a.html"}},
            {"title": "Externo", "formats": {"application/epub+zip": "https://evil.test/a.epub"}},
        ], "next": None}
        self.assertEqual(Gutenberg(self.http).buscar("teste"), [])

    def test_resposta_invalida_nao_parece_busca_vazia(self):
        self.resposta.json.return_value = {"erro": "indisponivel"}
        with self.assertRaises(ValueError):
            Gutenberg(self.http).buscar("teste")

    def test_entrada_invalida_nao_consulta_api(self):
        for termo, formato, pagina in [("", "epub", 0), ("x", "exe", 0), ("x", "txt", -1)]:
            with self.assertRaises(ValueError):
                Gutenberg(self.http).buscar(termo, formato, pagina)
        self.http.get.assert_not_called()

    def test_hosts_de_uma_fonte_nao_sao_aceitos_na_outra(self):
        for url, origem in [("https://www.gutenberg.org/a.epub", "Visionvox"),
                            ("https://visionvox.net/a.epub", "Project Gutenberg"),
                            ("https://www.gutenberg.org.evil.test/a.epub", "Project Gutenberg")]:
            with self.subTest(origem=origem), self.assertRaises(ValueError):
                validar_url_download(url, origem)

    def test_visionvox_detecta_proxima_pagina_real(self):
        self.resposta.content = b'<input name="busca"><a href="busca.php?num_page=1">2</a>'
        self.assertTrue(Visionvox(self.http).buscar_pagina("teste").tem_proxima)
        self.assertFalse(Visionvox(self.http).buscar_pagina("teste", pagina=1).tem_proxima)

    def test_visionvox_busca_sinopse_sob_demanda(self):
        busca_vazia = Mock()
        busca_vazia.content = b'<p>Nenhuma sinopse</p>'
        busca = Mock()
        busca.content = '<a href="Sinopse.php?sinopse=602">Machado de Assis - Dom Casmurro</a>'.encode()
        detalhe = Mock()
        detalhe.content = '<p>Autor:</p><p>Machado</p><p>Sinopse:</p><p>Capitu tem olhos de ressaca.</p><p>Copiar sinopse</p>'.encode()
        self.http.get.side_effect = [busca_vazia, busca, detalhe]
        livro = Livro("Machado de Assis Dom Casmurro.epub", "https://visionvox.net/a.epub", "epub")
        self.assertEqual(Visionvox(self.http).obter_sinopse(livro), "Capitu tem olhos de ressaca.")
        self.assertEqual(self.http.get.call_count, 3)

    def test_todas_as_fontes_unem_resultados_e_preservam_origem(self):
        visionvox, gutenberg = Mock(), Mock()
        visionvox.buscar_pagina.return_value = PaginaLivros(
            [Livro("Livro A", "https://visionvox.net/a.epub", "epub")], False)
        gutenberg.buscar_pagina.return_value = PaginaLivros(
            [Livro("Livro B", "https://www.gutenberg.org/b.epub", "epub", "Project Gutenberg")], True)
        pagina = TodasFontes([visionvox, gutenberg]).buscar_pagina("livro")
        self.assertEqual([l.origem for l in pagina.livros], ["Visionvox", "Project Gutenberg"])
        self.assertTrue(pagina.tem_proxima)
