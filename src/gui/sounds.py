"""Tons originais curtos, sem arquivos externos nem reprodução bloqueante."""
import io
import math
import struct
import time
import wave

import wx
import wx.adv


def gerar_tom(frequencias, duracao):
    taxa = 22050
    amostras = int(taxa * duracao)
    pcm = bytearray()
    for i in range(amostras):
        t = i / taxa
        # Envelope suave evita estalos; pico de 7% da escala digital.
        envelope = math.sin(math.pi * i / amostras) ** 2
        valor = sum(math.sin(2 * math.pi * f * t) for f in frequencias) / len(frequencias)
        pcm.extend(struct.pack("<h", int(32767 * 0.07 * envelope * valor)))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(taxa)
        arquivo.writeframes(pcm)
    return buffer.getvalue()


class FeedbackSonoro:
    def __init__(self, habilitado=lambda: True):
        self.habilitado = habilitado
        self._sons = {}
        self._proxima_navegacao = 0.0

    def tocar(self, tipo):
        if not self.habilitado():
            return
        agora = time.monotonic()
        if tipo == "navegar" and agora < self._proxima_navegacao:
            return
        self._proxima_navegacao = agora + (0.12 if tipo == "confirmar" else 0.065)
        try:
            if tipo not in self._sons:
                frequencias, duracao = ((560,), 0.035) if tipo == "navegar" else ((660, 880), 0.09)
                som = wx.adv.Sound()
                if not som.CreateFromData(gerar_tom(frequencias, duracao)):
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
