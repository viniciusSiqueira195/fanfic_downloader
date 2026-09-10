"""Feedback de interface com sons CC0 curtos da Kenney."""
import sys
import time
from pathlib import Path

import wx
import wx.adv


ARQUIVOS = {
    "abrir": "startup.wav",
    "navegar": "navigate.wav",
    "confirmar": "confirm.wav",
}


def caminho_som(tipo):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / "assets" / "sounds" / ARQUIVOS[tipo]


class FeedbackSonoro:
    def __init__(self, habilitado=lambda: True):
        self.habilitado = habilitado
        self._sons = {}
        self._proxima_navegacao = 0.0

    def tocar(self, tipo):
        try:
            habilitado = self.habilitado(tipo)
        except TypeError:
            habilitado = self.habilitado()
        if not habilitado:
            return
        agora = time.monotonic()
        if tipo == "navegar" and agora < self._proxima_navegacao:
            return
        self._proxima_navegacao = agora + (0.12 if tipo == "confirmar" else 0.065)
        try:
            if tipo not in self._sons:
                som = wx.adv.Sound(str(caminho_som(tipo)))
                if not som.IsOk():
                    return
                self._sons[tipo] = som
            self._sons[tipo].Play(wx.adv.SOUND_ASYNC)
        except (RuntimeError, OSError):
            # Uma falha de áudio não deve impedir navegação ou ativação.
            return

    def vincular(self, janela):
        def navegar(event):
            self.tocar("navegar")
            event.Skip()

        def confirmar(event):
            self.tocar("confirmar")
            event.Skip()

        janela.Bind(wx.EVT_CHILD_FOCUS, navegar)

        def controles(pai):
            for controle in pai.GetChildren():
                if isinstance(controle, wx.ListBox):
                    controle.Bind(wx.EVT_LISTBOX, navegar)
                elif isinstance(controle, wx.Choice):
                    controle.Bind(wx.EVT_CHOICE, navegar)
                elif isinstance(controle, wx.Button):
                    controle.Bind(wx.EVT_BUTTON, confirmar)
                elif isinstance(controle, wx.CheckBox):
                    controle.Bind(wx.EVT_CHECKBOX, confirmar)
                controles(controle)

        controles(janela)
