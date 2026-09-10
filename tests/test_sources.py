import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from books.gutenberg import Gutenberg
from books.internet_archive import InternetArchive
from books.models import Livro, PaginaLivros
from books.sources import TodasFontes
from books.urls import validar_url_download
from books.visionvox import Visionvox
from books.wikisource import Wikisource


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
        self.assertEqual(pagina.livros[0].autor, "Machado de Assis")
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

    def test_gutenberg_filtra_idioma_no_catalogo(self):
        self.resposta.json.return_value = {"results": [], "next": None}
        Gutenberg(self.http).buscar_pagina("amor", "epub", 0, "pt")
        self.assertEqual(self.http.get.call_args.kwargs["params"]["languages"], "pt")

    def test_gutenberg_explora_apenas_formato_baixavel_por_popularidade(self):
        self.resposta.json.return_value = {"results": [], "next": None}
        Gutenberg(self.http).explorar_pagina("epub", 1, "pt", "fiction")
        self.assertEqual(self.http.get.call_args.kwargs["params"], {
            "mime_type": "application/epub+zip", "page": 2, "sort": "popular",
            "languages": "pt", "topic": "fiction",
        })

    def test_gutenberg_usa_opds_oficial_quando_gutendex_expira(self):
        import requests
        lista = Mock()
        lista.content = b'''<feed xmlns="http://www.w3.org/2005/Atom">
          <entry><link rel="subsection" href="/ebooks/1.opds"/></entry>
        </feed>'''
        detalhe = Mock()
        detalhe.content = b'''<feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:dcterms="http://purl.org/dc/terms/">
          <entry><title>Livro livre</title><author><name>Autora</name></author>
          <dcterms:language>pt</dcterms:language>
          <content>Summary: Uma sinopse. Author: Autora</content>
          <link rel="http://opds-spec.org/acquisition" type="application/epub+zip"
          href="https://www.gutenberg.org/ebooks/1.epub.noimages"/></entry>
        </feed>'''
        self.http.get.side_effect = [requests.ReadTimeout("lento"), lista, detalhe]
        pagina = Gutenberg(self.http).buscar_pagina("livro", "epub", 0, "pt")
        self.assertEqual(pagina.livros[0].titulo, "Livro livre — Autora")
        self.assertEqual(pagina.livros[0].idioma, "pt")
        self.assertIn("catálogo alternativo", pagina.aviso)

    def test_visionvox_nao_e_consultado_para_outro_idioma(self):
        pagina = Visionvox(self.http).buscar_pagina("love", "epub", 0, "en")
        self.assertEqual(pagina.livros, [])
        self.http.get.assert_not_called()

    def test_visionvox_descobre_livros_recentes_reais(self):
        self.resposta.content = b'''<a href="https://visionvox.net/biblioteca/r/recente.epub">
            Livro recente.epub</a>
            <a href="recente.php?num_page=50&amp;total_pagina=2">2</a>'''
        fonte = Visionvox(self.http)
        pagina = fonte.explorar_pagina("epub", 0, "pt", "visionvox:recentes")
        self.assertEqual([livro.titulo for livro in pagina.livros], ["Livro recente.epub"])
        self.assertTrue(pagina.tem_proxima)
        parametros = self.http.get.call_args.kwargs["params"]
        self.assertEqual(parametros, {"estante": "recente", "formato": "epub",
                                      "pagina": "Nao", "num_page": 0})
        ultima = fonte.explorar_pagina("epub", 1, "pt", "visionvox:recentes")
        self.assertFalse(ultima.tem_proxima)
        self.assertEqual(self.http.get.call_args.kwargs["params"]["total_pagina"], 2)

    def test_wikisource_cria_download_oficial_e_ignora_capitulos(self):
        self.resposta.json.return_value = {
            "continue": {"sroffset": 20},
            "query": {"search": [{"title": "Dom Casmurro"},
                                   {"title": "Dom Casmurro/Capítulo I"}]},
        }
        pagina = Wikisource(self.http).buscar_pagina("Dom Casmurro", "epub", 0, "pt")
        self.assertEqual(len(pagina.livros), 1)
        self.assertEqual(pagina.livros[0].origem, "Wikisource")
        self.assertIn("ws-export.wmcloud.org", pagina.livros[0].url)
        self.assertIn("format=epub-3", pagina.livros[0].url)
        self.assertTrue(pagina.tem_proxima)

    def test_wikisource_informa_formato_txt_indisponivel_sem_consultar(self):
        pagina = Wikisource(self.http).buscar_pagina("Dom Casmurro", "txt")
        self.assertEqual(pagina.livros, [])
        self.assertIn("EPUB e PDF", pagina.aviso)
        self.http.get.assert_not_called()

    def test_consulta_identica_usa_cache_curto(self):
        self.resposta.json.return_value = {"query": {"search": [{"title": "Dom Casmurro"}]}}
        fonte = Wikisource(self.http)
        fonte.buscar_pagina("Dom Casmurro", "epub", 0, "pt")
        fonte.buscar_pagina("Dom Casmurro", "epub", 0, "pt")
        self.assertEqual(self.http.get.call_count, 1)

    def test_internet_archive_retorna_apenas_arquivo_publico_no_formato(self):
        busca = Mock()
        busca.json.return_value = {"response": {"numFound": 1, "docs": [{
            "identifier": "dom-casmurro", "title": "Dom Casmurro",
            "creator": "Machado de Assis", "language": "por",
            "description": "Romance brasileiro", "licenseurl": "public-domain",
        }]}}
        metadados = Mock()
        metadados.json.return_value = {"metadata": {"access-restricted-item": "false",
                                                     "licenseurl": "public-domain"},
                                       "files": [{"name": "Dom Casmurro.epub",
                                                  "format": "EPUB"}]}
        self.http.get.side_effect = [busca, metadados]
        pagina = InternetArchive(self.http).buscar_pagina("Dom Casmurro", "epub", 0, "pt")
        self.assertEqual(len(pagina.livros), 1)
        self.assertEqual(pagina.livros[0].origem, "Internet Archive")
        self.assertIn("archive.org/download/dom-casmurro/Dom%20Casmurro.epub",
                      pagina.livros[0].url)
        self.assertFalse(pagina.tem_proxima)

    def test_internet_archive_descarta_item_com_acesso_restrito(self):
        self.resposta.json.return_value = {
            "metadata": {"access-restricted-item": "true"},
            "files": [{"name": "livro.pdf", "format": "Text PDF"}],
        }
        item = {"identifier": "livro", "title": "Livro"}
        self.assertIsNone(InternetArchive(self.http)._obter_livro(item, "pdf"))

    def test_descoberta_internet_archive_ordena_por_downloads(self):
        self.resposta.json.return_value = {"response": {"numFound": 0, "docs": []}}
        InternetArchive(self.http).explorar_pagina("epub", 0, "pt", "fiction")
        parametros = self.http.get.call_args.kwargs["params"]
        self.assertEqual(parametros["sort[]"], "downloads desc")
        self.assertIn("language:por", parametros["q"])

    def test_descoberta_fantasia_filtra_assuntos_e_nao_titulos(self):
        self.resposta.json.return_value = {"response": {"numFound": 0, "docs": []}}
        InternetArchive(self.http).explorar_pagina("epub", 0, "pt", "fantasy")
        consulta = self.http.get.call_args.kwargs["params"]["q"]
        self.assertIn('subject:"fantasy"', consulta)
        self.assertIn('subject:"fantasy fiction"', consulta)
        self.assertNotIn("title:", consulta)

    def test_descoberta_combina_fontes_capazes_e_ignora_as_demais(self):
        primeira, segunda, sem_descoberta = Mock(), Mock(), Mock()
        for fonte, nome in ((primeira, "Primeira"), (segunda, "Segunda")):
            fonte.nome = nome
            fonte.capacidades = Mock(descoberta=True, formatos={"epub"}, idiomas={"pt"})
        sem_descoberta.nome = "Busca apenas"
        sem_descoberta.capacidades = Mock(descoberta=False, formatos={"epub"}, idiomas={"pt"})
        primeira.explorar_pagina.return_value = PaginaLivros([
            Livro("A", "https://visionvox.net/a.epub", "epub", "Primeira")], False)
        segunda.explorar_pagina.return_value = PaginaLivros([
            Livro("B", "https://www.gutenberg.org/b.epub", "epub", "Segunda")], False)
        pagina = TodasFontes([primeira, segunda, sem_descoberta]).explorar_pagina("epub", 0, "pt")
        self.assertEqual([livro.origem for livro in pagina.livros], ["Primeira", "Segunda"])
        sem_descoberta.explorar_pagina.assert_not_called()

    def test_descoberta_anuncia_resultados_de_cada_fonte(self):
        fonte = Mock()
        fonte.nome = "Catálogo"
        fonte.capacidades = Mock(descoberta=True, formatos={"epub"}, idiomas={"pt"})
        livros = [Livro("Fantasia", "https://visionvox.net/f.epub", "epub")]
        fonte.explorar_pagina.return_value = PaginaLivros(livros, False)
        progresso = Mock()
        TodasFontes([fonte]).explorar_pagina("epub", 0, "pt", "fantasy", progresso)
        progresso.assert_any_call("Catálogo", "consultando", 0, [])
        progresso.assert_any_call("Catálogo", "concluída", 1, livros)

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
                            ("https://www.gutenberg.org.evil.test/a.epub", "Project Gutenberg"),
                            ("https://archive.org.evil.test/a.epub", "Internet Archive"),
                            ("https://ws-export.wmcloud.org.evil.test/a.epub", "Wikisource")]:
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

    def test_todas_as_fontes_ordenam_e_removem_duplicata_bibliografica(self):
        visionvox, gutenberg = Mock(), Mock()
        visionvox.nome, gutenberg.nome = "Visionvox", "Project Gutenberg"
        visionvox.buscar_pagina.return_value = PaginaLivros([
            Livro("Outro livro.epub", "https://visionvox.net/o.epub", "epub"),
            Livro("Dom Casmurro Machado de Assis.epub", "https://visionvox.net/d.epub", "epub"),
        ], False)
        gutenberg.buscar_pagina.return_value = PaginaLivros([
            Livro("Dom Casmurro — Machado de Assis", "https://www.gutenberg.org/d.epub", "epub",
                  "Project Gutenberg"),
        ], False)
        pagina = TodasFontes([visionvox, gutenberg]).buscar_pagina("Dom Casmurro")
        self.assertEqual(len(pagina.livros), 2)
        self.assertIn("Dom Casmurro", pagina.livros[0].titulo)

    def test_todas_as_fontes_emitem_progresso_individual(self):
        fonte = Mock()
        fonte.nome = "Catálogo"
        fonte.buscar_pagina.return_value = PaginaLivros([], False)
        progresso = Mock()
        TodasFontes([fonte]).buscar_pagina("livro", progresso=progresso)
        progresso.assert_any_call("Catálogo", "consultando", 0, [])
        progresso.assert_any_call("Catálogo", "concluída", 0, [])

    def test_varios_resultados_nao_esperam_catalogo_lento(self):
        rapido, lento = Mock(), Mock()
        rapido.nome, lento.nome = "Rápido", "Lento"
        rapido.buscar_pagina.return_value = PaginaLivros([
            Livro(f"Livro {i}", f"https://visionvox.net/{i}.epub", "epub")
            for i in range(5)
        ], True)
        liberar = threading.Event()

        def demorar(*args):
            liberar.wait(2)
            return PaginaLivros([], False)

        lento.buscar_pagina.side_effect = demorar
        inicio = time.monotonic()
        try:
            pagina = TodasFontes([rapido, lento]).buscar_pagina("livro")
            self.assertLess(time.monotonic() - inicio, .5)
            self.assertEqual(len(pagina.livros), 5)
            self.assertIn("demorando", pagina.aviso)
        finally:
            liberar.set()
