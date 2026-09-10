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
            dialogo.fonte.buscar_pagina.assert_called_once_with("teste", "epub", 0, "pt")
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
                "Pesquisando em Todas as fontes...",
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
            filhos = dialogo.painel_busca.GetChildren()
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

    def test_ctrl_f_retorna_ao_campo_de_pesquisa(self):
        import wx
        from gui.books_dialog import BooksDialog
        dialogo = BooksDialog(None, sons=Mock())
        evento = Mock()
        evento.GetKeyCode.return_value = ord("F")
        evento.ControlDown.return_value = True
        try:
            dialogo.on_tecla(evento)
            wx.Yield()
            self.assertIs(wx.Window.FindFocus(), dialogo.termo)
        finally:
            dialogo.Destroy()

    def test_pesquisa_esconde_formulario_e_exibe_apenas_resultados(self):
        from gui.books_dialog import BooksDialog
        dialogo = BooksDialog(None, sons=Mock())
        try:
            dialogo.termo.SetValue("dom casmurro")
            dialogo._executar = Mock()
            dialogo.on_pesquisar(None)
            self.assertFalse(dialogo.painel_busca.IsShown())
            self.assertTrue(dialogo.painel_resultados.IsShown())
        finally:
            dialogo.Destroy()

    def test_voltar_da_lista_reexibe_pesquisa_sem_perder_termo(self):
        import wx
        from gui.books_dialog import BooksDialog
        dialogo = BooksDialog(None, sons=Mock())
        try:
            dialogo.termo.SetValue("capitu")
            dialogo._mostrar_tela(True)
            dialogo.on_voltar_pesquisa()
            wx.Yield()
            self.assertTrue(dialogo.painel_busca.IsShown())
            self.assertFalse(dialogo.painel_resultados.IsShown())
            self.assertEqual(dialogo.termo.GetValue(), "capitu")
            self.assertIs(wx.Window.FindFocus(), dialogo.termo)
        finally:
            dialogo.Destroy()

    def test_descobrir_abre_catalogo_baixavel_com_filtros_atuais(self):
        import wx
        from gui.books_dialog import BooksDialog
        from unittest.mock import patch
        dialogo = BooksDialog(None, sons=Mock())
        seletor = Mock()
        seletor.__enter__ = Mock(return_value=seletor)
        seletor.__exit__ = Mock(return_value=False)
        seletor.ShowModal.return_value = wx.ID_OK
        seletor.GetStringSelection.return_value = "Ficção"
        dialogo._buscar_pagina = Mock()
        try:
            with patch("gui.books_dialog.wx.SingleChoiceDialog", return_value=seletor):
                dialogo.on_descobrir(None)
            self.assertTrue(dialogo.explorando)
            self.assertEqual(dialogo.topico_explorar, "fiction")
            self.assertEqual(dialogo.fonte_escolha.GetStringSelection(), "Todas as fontes")
            self.assertEqual(dialogo.consulta, ("", "epub", "pt"))
            dialogo._buscar_pagina.assert_called_once_with(0)
        finally:
            dialogo.Destroy()

    def test_wikisource_remove_txt_dos_formatos_disponiveis(self):
        from gui.books_dialog import BooksDialog
        dialogo = BooksDialog(None, sons=Mock())
        try:
            dialogo.fonte_escolha.SetStringSelection("Wikisource")
            dialogo.on_fonte(None)
            self.assertEqual([dialogo.formato.GetString(i)
                              for i in range(dialogo.formato.GetCount())], ["EPUB", "PDF"])
        finally:
            dialogo.Destroy()

    def test_modo_continuo_carrega_ate_o_limite_sem_tirar_selecao(self):
        import wx
        from books.models import Livro, PaginaLivros
        from gui.books_dialog import BooksDialog
        dialogo = BooksDialog(None, sons=Mock(), modo_carregamento="continuo",
                              limite_resultados=3)
        dialogo.fonte = Mock()
        dialogo.fonte.buscar_pagina.side_effect = [
            PaginaLivros([Livro("A", "https://visionvox.net/a.epub", "epub")], True),
            PaginaLivros([Livro("B", "https://visionvox.net/b.epub", "epub")], True),
            PaginaLivros([Livro("C", "https://visionvox.net/c.epub", "epub")], True),
        ]
        try:
            dialogo.termo.SetValue("livro")
            dialogo.on_pesquisar(None)
            limite = time.monotonic() + 5
            while (dialogo.ocupado or dialogo.carregando_mais) and time.monotonic() < limite:
                wx.Yield(); time.sleep(.01)
            self.assertEqual(dialogo.resultados.GetCount(), 3)
            self.assertEqual(dialogo.resultados.GetSelection(), 0)
            self.assertIn("Limite configurado atingido", dialogo.status.GetValue())
        finally:
            dialogo.Destroy()

    def test_modo_manual_acrescenta_quinze_ao_chegar_no_fim(self):
        import wx
        from books.models import Livro, PaginaLivros
        from gui.books_dialog import BooksDialog
        dialogo = BooksDialog(None, sons=Mock(), modo_carregamento="manual",
                              limite_resultados=200)
        primeira = [Livro(f"Livro {i}", f"https://visionvox.net/{i}.epub", "epub")
                    for i in range(10)]
        segunda = [Livro(f"Livro {i}", f"https://visionvox.net/{i}.epub", "epub")
                   for i in range(10, 30)]
        dialogo.fonte = Mock()
        dialogo.fonte.buscar_pagina.side_effect = [PaginaLivros(primeira, True),
                                                   PaginaLivros(segunda, False)]
        evento = Mock()
        try:
            dialogo.termo.SetValue("livro")
            dialogo.on_pesquisar(None)
            limite = time.monotonic() + 5
            while dialogo.ocupado and time.monotonic() < limite:
                wx.Yield(); time.sleep(.01)
            dialogo.resultados.SetSelection(5)
            dialogo.on_selecao_resultado(evento)
            while dialogo.carregando_mais and time.monotonic() < limite:
                wx.Yield(); time.sleep(.01)
            self.assertEqual(dialogo.resultados.GetCount(), 25)
            self.assertEqual(len(dialogo.resultados_reserva), 5)
            evento.Skip.assert_called()
        finally:
            dialogo.Destroy()
