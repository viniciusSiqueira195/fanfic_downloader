import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@unittest.skipUnless(importlib.util.find_spec("wx"), "Requer wxPython")
class SoundsTests(unittest.TestCase):
    def test_sons_desligados_nao_inicializam_audio(self):
        from gui.sounds import FeedbackSonoro
        with patch("gui.sounds.wx.adv.Sound") as som:
            FeedbackSonoro(lambda: False).tocar("navegar")
            som.assert_not_called()

    def test_carrega_arquivos_cc0_empacotados(self):
        from gui.sounds import FeedbackSonoro, caminho_som
        self.assertTrue(caminho_som("navegar").is_file())
        self.assertTrue(caminho_som("confirmar").is_file())
        self.assertTrue(caminho_som("abrir").is_file())
        with patch("gui.sounds.wx.adv.Sound") as classe_som:
            som = classe_som.return_value
            som.IsOk.return_value = True
            FeedbackSonoro().tocar("confirmar")
            self.assertEqual(Path(classe_som.call_args.args[0]).name, "confirm.wav")
            som.Play.assert_called_once()

    def test_setas_repetidas_nao_sobrepoem_confirmacao(self):
        from gui.sounds import FeedbackSonoro
        feedback = FeedbackSonoro()
        navegar, confirmar = Mock(), Mock()
        feedback._sons = {"navegar": navegar, "confirmar": confirmar}
        with \
                patch("gui.sounds.time.monotonic", side_effect=[1, 1.01, 1.02, 1.03, 1.2]):
            for tipo in ("navegar", "navegar", "confirmar", "navegar", "navegar"):
                feedback.tocar(tipo)
        self.assertEqual(navegar.Play.call_count, 2)
        confirmar.Play.assert_called_once()
