"""Integração wx sem rede nem reprodução de áudio (Windows)."""
import importlib.util
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@unittest.skipUnless(sys.platform == "win32" and importlib.util.find_spec("wx"), "Requer wxPython no Windows")
class BooksGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import wx
        cls.app = wx.App.Get() or wx.App(False)

    def test_trocar_fonte_limpa_resultados_e_paginacao(self):
        from gui.books_dialog import BooksDialog
        from books.gutenberg import Gutenberg
        from books.models import Livro
        dialogo = BooksDialog(None, sons=Mock())
        try:
            dialogo.livros = [Livro("Antigo", "https://visionvox.net/a.epub", "epub")]
            dialogo.resultados.Set(["Antigo"])
            dialogo.consulta = ("teste", "epub")
            dialogo.pagina = 3
            dialogo.tem_proxima = True
            dialogo.fonte_escolha.SetStringSelection("Project Gutenberg")
            dialogo.on_fonte(None)
            self.assertIsInstance(dialogo.fonte, Gutenberg)
            self.assertEqual(dialogo.resultados.GetCount(), 0)
            self.assertFalse(dialogo.baixar.IsEnabled())
            self.assertFalse(dialogo.proxima.IsEnabled())
            self.assertIsNone(dialogo.consulta)
        finally:
            dialogo.Destroy()

    def test_worker_entrega_resultados_sem_proxima_pagina_fantasma(self):
        import wx
        from gui.books_dialog import BooksDialog
        from books.models import Livro, PaginaLivros
        dialogo = BooksDialog(None, sons=Mock())
        try:
            dialogo.fonte = Mock()
            dialogo.fonte.buscar_pagina.return_value = PaginaLivros(
                [Livro("Teste", "https://visionvox.net/a.epub", "epub")], False)
            dialogo.termo.SetValue("teste")
            dialogo.on_pesquisar(None)
            limite = time.monotonic() + 5
            while dialogo.ocupado and time.monotonic() < limite:
                wx.Yield()
                time.sleep(0.01)
            self.assertFalse(dialogo.ocupado)
            self.assertEqual(dialogo.resultados.GetCount(), 1)
            self.assertTrue(dialogo.baixar.IsEnabled())
            self.assertFalse(dialogo.proxima.IsEnabled())
            dialogo.fonte.buscar_pagina.assert_called_once_with("teste", "epub", 0)
        finally:
            dialogo.Destroy()
