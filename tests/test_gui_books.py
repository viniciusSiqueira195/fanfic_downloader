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
            self.assertFalse(dialogo.proxima.IsEnabled())
            dialogo.fonte.buscar_pagina.assert_called_once_with("teste", "epub", 0)
        finally:
            dialogo.Destroy()

    def test_busca_foca_status_enquanto_worker_roda(self):
        import wx
        from gui.books_dialog import BooksDialog
        dialogo = BooksDialog(None, sons=Mock())
        try:
            dialogo.termo.SetValue("dom casmurro")
            dialogo._executar = Mock()
            dialogo.on_pesquisar(None)
            wx.Yield()
            self.assertEqual(
                dialogo.status.GetValue(),
                "Pesquisando em Todas as fontes, página 1...",
            )
            self.assertIs(wx.Window.FindFocus(), dialogo.status)
            dialogo._executar.assert_called_once()
        finally:
            dialogo.Destroy()

    def test_enter_na_lista_abre_menu_de_acoes(self):
        import wx
        from gui.books_dialog import BooksDialog
        from books.models import Livro
        from unittest.mock import patch
        dialogo = BooksDialog(None, sons=Mock())
        try:
            dialogo.livros = [Livro("Teste", "https://visionvox.net/a.epub", "epub")]
            dialogo.resultados.Set(["Teste"])
            dialogo.resultados.SetSelection(0)
            dialogo.on_menu_acoes = Mock()
            evento = Mock()
            evento.GetKeyCode.return_value = wx.WXK_RETURN
            with patch("gui.books_dialog.wx.Window.FindFocus", return_value=dialogo.resultados):
                dialogo.on_tecla(evento)
            dialogo.on_menu_acoes.assert_called_once_with(evento)
        finally:
            dialogo.Destroy()

    def test_campo_de_termo_vem_antes_da_fonte_na_ordem_de_tab(self):
        from gui.books_dialog import BooksDialog
        dialogo = BooksDialog(None, sons=Mock())
        try:
            filhos = dialogo.GetChildren()
            self.assertLess(filhos.index(dialogo.termo), filhos.index(dialogo.fonte_escolha))
        finally:
            dialogo.Destroy()

    def test_pasta_escolhida_e_persistida_somente_quando_necessaria(self):
        import wx
        from gui.books_dialog import BooksDialog
        from unittest.mock import patch
        salvar = Mock()
        dialogo = BooksDialog(None, pasta="", sons=Mock(), ao_escolher_pasta=salvar)
        seletor = Mock()
        seletor.__enter__ = Mock(return_value=seletor)
        seletor.__exit__ = Mock(return_value=False)
        seletor.ShowModal.return_value = wx.ID_OK
        seletor.GetPath.return_value = r"C:\Livros"
        try:
            with patch("gui.books_dialog.wx.DirDialog", return_value=seletor):
                self.assertEqual(dialogo._selecionar_pasta(), r"C:\Livros")
            salvar.assert_called_once_with(r"C:\Livros")
            self.assertEqual(dialogo.pasta_salva, r"C:\Livros")
        finally:
            dialogo.Destroy()
