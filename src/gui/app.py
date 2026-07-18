import wx
import threading
import json
import os
import requests
from scrapers.spirit import baixar_spirit
from scrapers.wattpad import baixar_wattpad
from scrapers.fanfiction_net import baixar_fanfiction_net
from scrapers.plusfiction import baixar_plusfiction
from scrapers.search import buscar_fanfics_wattpad, buscar_fanfics_spirit, buscar_fanfics_fanfiction_net, buscar_fanfics_plusfiction, buscar_fanfics_todas_fontes
from updater import baixar_e_aplicar_atualizacao, reiniciar_aplicativo, verificar_atualizacao
from version import APP_VERSION

CONFIG_FILE = "config.json"

def carregar_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if "verificar_atualizacoes" not in config:
                    config["verificar_atualizacoes"] = False
                return config
        except:
            pass
    return {"formato": "PDF", "pasta": "", "verificar_atualizacoes": False}

def salvar_config(formato, pasta, verificar_atualizacoes):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(
                {"formato": formato, "pasta": pasta, "verificar_atualizacoes": verificar_atualizacoes},
                f,
            )
    except Exception as e:
        wx.MessageBox(f"Erro ao salvar configurações: {str(e)}", "Aviso", wx.OK | wx.ICON_WARNING)

class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title=f"Fanfic Downloader v{APP_VERSION}", size=(500, 500))
        self.config = carregar_config()
        self.cancel_event = threading.Event()
        self._update_busy = False
        
        self.panel_principal = wx.Panel(self)
        self.sizer_principal = wx.BoxSizer(wx.VERTICAL)
        
        # --- PAINEL DE INPUTS ---
        self.panel_inputs = wx.Panel(self.panel_principal)
        sizer_inputs = wx.BoxSizer(wx.VERTICAL)
        
        self.txt_url = wx.TextCtrl(self.panel_inputs, name="URL da Fanfic")
        sizer_inputs.Add(wx.StaticText(self.panel_inputs, label="Cole a URL da Fanfic:"), 0, wx.ALL, 5)
        sizer_inputs.Add(self.txt_url, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        self.combo_site_busca = wx.Choice(self.panel_inputs, choices=["Todas as fontes", "Wattpad", "Spirit", "FanFiction.net", "PlusFiction"])
        self.combo_site_busca.SetSelection(0)
        sizer_inputs.Add(wx.StaticText(self.panel_inputs, label="Pesquisar termo:"), 0, wx.ALL, 5)
        sizer_inputs.Add(self.combo_site_busca, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        sizer_busca = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_busca = wx.TextCtrl(self.panel_inputs)
        self.btn_pesquisar = wx.Button(self.panel_inputs, label="Pesquisar")
        self.btn_pesquisar.Bind(wx.EVT_BUTTON, self.on_pesquisar)
        sizer_busca.Add(self.txt_busca, 1, wx.EXPAND | wx.RIGHT, 5)
        sizer_busca.Add(self.btn_pesquisar, 0)
        sizer_inputs.Add(sizer_busca, 0, wx.EXPAND | wx.ALL, 5)
        
        self.radio_modo = wx.RadioBox(self.panel_inputs, label="Modo", choices=["Obra Completa", "Apenas este capítulo"])
        sizer_inputs.Add(self.radio_modo, 0, wx.ALL | wx.EXPAND, 5)
        
        self.combo_formato = wx.Choice(self.panel_inputs, choices=["PDF", "EPUB", "TXT"])
        self.combo_formato.SetStringSelection(self.config.get("formato", "PDF"))
        sizer_inputs.Add(wx.StaticText(self.panel_inputs, label="Formato:"), 0, wx.ALL, 5)
        sizer_inputs.Add(self.combo_formato, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        self.chk_verificar_atualizacoes = wx.CheckBox(self.panel_inputs, label="Verificar atualizações automaticamente")
        self.chk_verificar_atualizacoes.SetValue(bool(self.config.get("verificar_atualizacoes", False)))
        sizer_inputs.Add(self.chk_verificar_atualizacoes, 0, wx.ALL, 5)
        
        self.txt_pasta = wx.TextCtrl(self.panel_inputs)
        self.txt_pasta.SetValue(self.config.get("pasta", ""))
        self.btn_procurar = wx.Button(self.panel_inputs, label="Procurar pasta...")
        self.btn_procurar.Bind(wx.EVT_BUTTON, self.on_procurar)
        sizer_pasta = wx.BoxSizer(wx.HORIZONTAL)
        sizer_pasta.Add(self.txt_pasta, 1, wx.EXPAND | wx.RIGHT, 5)
        sizer_pasta.Add(self.btn_procurar, 0)
        sizer_inputs.Add(wx.StaticText(self.panel_inputs, label="Pasta para salvar:"), 0, wx.ALL, 5)
        sizer_inputs.Add(sizer_pasta, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        
        self.btn_baixar = wx.Button(self.panel_inputs, label="Baixar Fanfic")
        self.btn_baixar.Bind(wx.EVT_BUTTON, self.on_baixar)
        sizer_inputs.Add(self.btn_baixar, 0, wx.ALL | wx.CENTER, 15)

        self.btn_atualizar = wx.Button(self.panel_inputs, label="Verificar atualização")
        self.btn_atualizar.Bind(wx.EVT_BUTTON, self.on_verificar_atualizacao)
        sizer_inputs.Add(self.btn_atualizar, 0, wx.ALL | wx.CENTER, 5)
        
        self.panel_inputs.SetSizer(sizer_inputs)
        self.sizer_principal.Add(self.panel_inputs, 1, wx.EXPAND)
        
        # --- PAINEL DE DOWNLOAD ---
        self.panel_download = wx.Panel(self.panel_principal)
        sizer_download = wx.BoxSizer(wx.VERTICAL)
        self.btn_cancelar = wx.Button(self.panel_download, label="Cancelar Download")
        self.btn_cancelar.Bind(wx.EVT_BUTTON, self.on_cancelar)
        self.gauge = wx.Gauge(self.panel_download, range=100)
        self.txt_status = wx.TextCtrl(self.panel_download, style=wx.TE_READONLY | wx.BORDER_NONE)
        self.txt_tempo = wx.TextCtrl(self.panel_download, style=wx.TE_READONLY | wx.BORDER_NONE)
        self.txt_porcentagem = wx.TextCtrl(self.panel_download, style=wx.TE_READONLY | wx.BORDER_NONE)
        
        for item in [self.btn_cancelar, self.gauge, self.txt_status, self.txt_tempo, self.txt_porcentagem]:
            sizer_download.Add(item, 0, wx.EXPAND | wx.ALL, 5)
        self.panel_download.SetSizer(sizer_download)
        self.sizer_principal.Add(self.panel_download, 1, wx.EXPAND)
        self.panel_download.Hide()
        
        self.panel_principal.SetSizer(self.sizer_principal)
        self.Center()
        if self.chk_verificar_atualizacoes.GetValue():
            wx.CallAfter(self.on_verificar_atualizacao, None)

    def on_procurar(self, event):
        dlg = wx.DirDialog(self, "Escolha onde salvar")
        if dlg.ShowModal() == wx.ID_OK: self.txt_pasta.SetValue(dlg.GetPath())
        dlg.Destroy()

    def on_baixar(self, event):
        url, pasta = self.txt_url.GetValue().strip(), self.txt_pasta.GetValue().strip()
        if not url or not pasta:
            wx.MessageBox("URL ou Pasta vazia!", "Erro", wx.OK | wx.ICON_ERROR)
            return
        salvar_config(self.combo_formato.GetStringSelection(), pasta, self.chk_verificar_atualizacoes.GetValue())
        self.cancel_event.clear()
        self._mostrar_painel_download("Iniciando...", "Calculando...", "0%", True, "Cancelar")
        threading.Thread(target=self._processar_download, args=(url, self.radio_modo.GetStringSelection(), self.combo_formato.GetStringSelection(), pasta), daemon=True).start()

    def _mostrar_painel_download(self, status, tempo, progresso, cancelar, label_cancel):
        self.txt_status.SetValue(status)
        self.txt_tempo.SetValue(tempo)
        self.txt_porcentagem.SetValue(progresso)
        self.btn_cancelar.Enable(cancelar)
        self.panel_inputs.Hide()
        self.panel_download.Show()
        self.panel_principal.Layout()

    def on_pesquisar(self, event):
        termo = self.txt_busca.GetValue().strip()
        if not termo: return
        try:
            resultados = buscar_fanfics_todas_fontes(termo)
            opcoes = [f"[{i['origem']}] {i['titulo']}" for i in resultados]
            dlg = wx.SingleChoiceDialog(self, "Selecione a fanfic:", "Resultados", opcoes)
            if dlg.ShowModal() == wx.ID_OK: self.txt_url.SetValue(resultados[dlg.GetSelection()]["url"])
            dlg.Destroy()
        except Exception as e:
            wx.MessageBox(str(e), "Erro", wx.OK | wx.ICON_ERROR)

    def on_cancelar(self, event):
        self.cancel_event.set()
        self.btn_cancelar.Disable()
        self.txt_status.SetValue("Cancelando...")

    def _atualizar_progresso(self, porcentagem, mensagem, tempo):
        wx.CallAfter(self.gauge.SetValue, porcentagem)
        wx.CallAfter(self.txt_status.SetValue, mensagem)
        wx.CallAfter(self.txt_porcentagem.SetValue, f"Progresso: {porcentagem}%")

    def _processar_download(self, url, modo, formato, pasta):
        try:
            if "wattpad" in url: sucesso, msg = baixar_wattpad(url, modo, formato, pasta, self._atualizar_progresso, self.cancel_event)
            # NOTA: AQUI ESTÁ A CORREÇÃO QUE EXIGE OS 6 PARÂMETROS DO SPIRIT
            elif "spirit" in url: sucesso, msg = baixar_spirit(url, modo, formato, pasta, self._atualizar_progresso, self.cancel_event)
            elif "fanfiction.net" in url: sucesso, msg = baixar_fanfiction_net(url, modo, formato, pasta, self._atualizar_progresso, self.cancel_event)
            elif "plusfiction" in url: sucesso, msg = baixar_plusfiction(url, modo, formato, pasta, self._atualizar_progresso, self.cancel_event)
            else: sucesso, msg = False, "Site não suportado"
            wx.CallAfter(self._finalizar_download, sucesso, msg)
        except Exception as e:
            wx.CallAfter(self._finalizar_download, False, str(e))

    def _finalizar_download(self, sucesso, mensagem):
        self.panel_download.Hide()
        self.panel_inputs.Show()
        self.panel_principal.Layout()
        wx.MessageBox(mensagem, "Download", wx.OK | (wx.ICON_INFORMATION if sucesso else wx.ICON_ERROR))

    def on_verificar_atualizacao(self, event):
        self.btn_atualizar.Disable()
        threading.Thread(target=self._executar_atualizacao_check, daemon=True).start()

    def _executar_atualizacao_check(self):
        try:
            res = verificar_atualizacao()
            wx.CallAfter(self._resultado_atualizacao, res)
        except:
            wx.CallAfter(self.btn_atualizar.Enable)

    def _resultado_atualizacao(self, atualizacao):
        self.btn_atualizar.Enable()
        if atualizacao:
            if wx.MessageBox("Nova versão! Atualizar?", "Update", wx.YES_NO) == wx.YES:
                self._iniciar_atualizacao(atualizacao)
        else:
            wx.MessageBox("Você está na versão atual.", "Info", wx.OK | wx.ICON_INFORMATION)

    def _iniciar_atualizacao(self, atualizacao):
        self._mostrar_painel_download("Atualizando...", "...", "0%", False, "Atualizando")
        threading.Thread(target=self._executar_update_process, args=(atualizacao,), daemon=True).start()

    def _executar_update_process(self, atualizacao):
        try:
            cmd = baixar_e_aplicar_atualizacao(atualizacao, self._atualizar_progresso)
            reiniciar_aplicativo(cmd)
            wx.CallAfter(self.Close)
        except Exception as e:
            wx.CallAfter(self._finalizar_download, False, str(e))