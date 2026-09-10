"""Regressões da integração de preferências; opcionais sem wxPython."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@unittest.skipUnless(importlib.util.find_spec("wx"), "Requer wxPython")
class PreferencesTests(unittest.TestCase):
    def test_sons_desativados_persistem_ao_salvar_outras_preferencias(self):
        from gui import app
        with tempfile.TemporaryDirectory() as pasta:
            with patch.object(app, "CONFIG_FILE", str(Path(pasta) / "config.json")):
                app.salvar_config("EPUB", "", False, sons_navegacao=False)
                app.salvar_config("TXT", "", False)
                self.assertIs(app.carregar_config()["sons_navegacao"], False)

    def test_preferencias_individuais_de_som_persistem(self):
        from gui import app
        with tempfile.TemporaryDirectory() as pasta:
            with patch.object(app, "CONFIG_FILE", str(Path(pasta) / "config.json")):
                sons = {"abrir": True, "navegar": False, "confirmar": True}
                app.salvar_config("EPUB", "", False, sons_individuais=sons)
                app.salvar_config("TXT", "", False)
                self.assertEqual(app.carregar_config()["sons_individuais"], sons)

    def test_pasta_livros_persiste_ao_salvar_preferencias_de_fanfics(self):
        from gui import app
        with tempfile.TemporaryDirectory() as pasta:
            with patch.object(app, "CONFIG_FILE", str(Path(pasta) / "config.json")):
                app.salvar_config("EPUB", "", False, pasta_livros=pasta)
                app.salvar_config("TXT", "outra pasta", False)
                self.assertEqual(app.carregar_config()["pasta_livros"], pasta)

    def test_historico_de_livros_persiste_e_e_limitado(self):
        from gui import app
        with tempfile.TemporaryDirectory() as pasta:
            with patch.object(app, "CONFIG_FILE", str(Path(pasta) / "config.json")):
                historico = [{"titulo": str(i), "caminho": str(i)} for i in range(55)]
                app.salvar_config("EPUB", "", False, historico_livros=historico)
                salvo = app.carregar_config()["historico_livros"]
                self.assertEqual(len(salvo), 50)
                self.assertEqual(salvo[0]["titulo"], "5")

    def test_configuracao_tem_caminho_absoluto(self):
        from gui.app import CONFIG_FILE
        self.assertTrue(Path(CONFIG_FILE).is_absolute())

    def test_modo_e_limite_das_listas_persistem(self):
        import tempfile
        from gui import app
        with tempfile.TemporaryDirectory() as pasta:
            with patch.object(app, "CONFIG_FILE", str(Path(pasta) / "config.json")):
                app.salvar_config("EPUB", "", False, modo_lista_livros="continuo",
                                  limite_resultados_livros=0)
                config = app.carregar_config()
                self.assertEqual(config["modo_lista_livros"], "continuo")
                self.assertEqual(config["limite_resultados_livros"], 0)

    def test_configuracoes_usam_guias_e_controle_unico_de_sons(self):
        import wx
        from gui.app import ConfigFrame
        aplicativo = wx.App.Get() or wx.App(False)
        principal = wx.Frame(None)
        principal.config = {"modo_lista_livros": "manual", "limite_resultados_livros": 200,
                            "sons_navegacao": True, "verificar_atualizacoes": False}
        principal.sons = Mock()
        principal.sons.vincular = Mock()
        principal._salvar_preferencias = Mock()
        janela = ConfigFrame(principal)
        try:
            self.assertEqual([janela.guias.GetPageText(i)
                              for i in range(janela.guias.GetPageCount())],
                             ["Geral", "Livros", "Sons"])
            janela.chk_sons.SetValue(False)
            janela.on_salvar(None)
            self.assertFalse(principal.config["sons_navegacao"])
            self.assertEqual(principal.config["sons_individuais"], {
                "abrir": False, "navegar": False, "confirmar": False})
        finally:
            if janela:
                janela.Destroy()
            principal.Destroy()

    def test_sair_fecha_janela(self):
        from gui.app import MainFrame
        janela = Mock()
        MainFrame.on_menu_principal(janela, "Sair")
        janela.Close.assert_called_once_with()
