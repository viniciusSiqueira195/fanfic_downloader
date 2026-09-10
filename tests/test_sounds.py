import importlib.util
import io
import struct
import sys
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@unittest.skipUnless(importlib.util.find_spec("wx"), "Requer wxPython")
class SoundsTests(unittest.TestCase):
    def test_tom_curto_com_volume_limitado(self):
        from gui.sounds import gerar_tom
        with wave.open(io.BytesIO(gerar_tom((560,), 0.035))) as arquivo:
            self.assertLess(arquivo.getnframes() / arquivo.getframerate(), 0.04)
            dados = arquivo.readframes(arquivo.getnframes())
            valores = struct.unpack("<" + "h" * (len(dados) // 2), dados)
            self.assertLessEqual(max(abs(v) for v in valores), 32767 * 0.07)

    def test_sons_desligados_nao_inicializam_audio(self):
        from gui.sounds import FeedbackSonoro
        with patch("gui.sounds.wx.adv.Sound") as som:
            FeedbackSonoro(lambda: False).tocar("navegar")
            som.assert_not_called()

    def test_setas_repetidas_nao_sobrepoem_confirmacao(self):
        from gui.sounds import FeedbackSonoro
        feedback = FeedbackSonoro()
        navegar, confirmar = Mock(), Mock()
        feedback._sons = {"navegar": navegar, "confirmar": confirmar}
        with patch("gui.sounds.time.monotonic", side_effect=[1, 1.01, 1.02, 1.03, 1.2]):
            for tipo in ("navegar", "navegar", "confirmar", "navegar", "navegar"):
                feedback.tocar(tipo)
        self.assertEqual(navegar.Play.call_count, 2)
        confirmar.Play.assert_called_once()
