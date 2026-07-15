import wx
import threading
import json
import os
from scrapers.spirit import baixar_spirit
from scrapers.wattpad import baixar_wattpad
from scrapers.fanfiction_net import baixar_fanfiction_net

CONFIG_FILE = "config.json"

def carregar_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"formato": "PDF", "pasta": ""}

def salvar_config(formato, pasta):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"formato": formato, "pasta": pasta}, f)
    except Exception as e:
        # Vacina: Se der erro de permissão no arquivo, apenas avisa no terminal e NÃO trava o download
        print(f"Aviso: Não foi possível salvar as preferências no config.json: {e}")

class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title="Fanfic Downloader", size=(500, 450))
        
        self.config = carregar_config()
        self.cancel_event = threading.Event()
        
        self.panel_principal = wx.Panel(self)
        self.sizer_principal = wx.BoxSizer(wx.VERTICAL)
        
        # --- PAINEL DE INPUTS (Tela Inicial) ---
        self.panel_inputs = wx.Panel(self.panel_principal)
        sizer_inputs = wx.BoxSizer(wx.VERTICAL)
        
        lbl_url = wx.StaticText(self.panel_inputs, label="Cole a URL da Fanfic:")
        self.txt_url = wx.TextCtrl(self.panel_inputs, name="URL da Fanfic")
        sizer_inputs.Add(lbl_url, 0, wx.ALL, 5)
        sizer_inputs.Add(self.txt_url, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        opcoes_modo = ["Obra Completa", "Apenas este capítulo"]
        self.radio_modo = wx.RadioBox(self.panel_inputs, label="Modo de Download", choices=opcoes_modo, majorDimension=1, style=wx.RA_SPECIFY_COLS)
        sizer_inputs.Add(self.radio_modo, 0, wx.ALL | wx.EXPAND, 5)
        
        lbl_formato = wx.StaticText(self.panel_inputs, label="Selecione o formato de saída:")
        formatos = ["PDF", "EPUB", "TXT"]
        self.combo_formato = wx.Choice(self.panel_inputs, choices=formatos, name="Formato do Arquivo")
        
        if self.config["formato"] in formatos:
            self.combo_formato.SetStringSelection(self.config["formato"])
        else:
            self.combo_formato.SetSelection(0)
            
        sizer_inputs.Add(lbl_formato, 0, wx.ALL, 5)
        sizer_inputs.Add(self.combo_formato, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        # --- COMPONENTE DE PASTA CUSTOMIZADO E ACESSÍVEL ---
        lbl_pasta = wx.StaticText(self.panel_inputs, label="Pasta para salvar:")
        sizer_inputs.Add(lbl_pasta, 0, wx.ALL, 5)
        
        sizer_pasta = wx.BoxSizer(wx.HORIZONTAL)
        
        self.txt_pasta = wx.TextCtrl(self.panel_inputs, name="Se preferir, cole o caminho da pasta aqui")
        if self.config["pasta"] and os.path.exists(self.config["pasta"]):
            self.txt_pasta.SetValue(self.config["pasta"])
            
        self.btn_procurar = wx.Button(self.panel_inputs, label="Procurar...")
        self.btn_procurar.Bind(wx.EVT_BUTTON, self.on_procurar)
        
        sizer_pasta.Add(self.txt_pasta, 1, wx.EXPAND | wx.RIGHT, 5)
        sizer_pasta.Add(self.btn_procurar, 0, wx.ALL, 0)
        
        sizer_inputs.Add(sizer_pasta, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        # ----------------------------------------------------
        
        self.btn_baixar = wx.Button(self.panel_inputs, label="Baixar Fanfic")
        self.btn_baixar.Bind(wx.EVT_BUTTON, self.on_baixar)
        sizer_inputs.Add(self.btn_baixar, 0, wx.ALL | wx.CENTER, 15)
        
        self.panel_inputs.SetSizer(sizer_inputs)
        self.sizer_principal.Add(self.panel_inputs, 1, wx.EXPAND | wx.ALL, 0)
        
        # --- PAINEL DE DOWNLOAD (Tela de Progresso) ---
        self.panel_download = wx.Panel(self.panel_principal)
        sizer_download = wx.BoxSizer(wx.VERTICAL)
        
        self.btn_cancelar = wx.Button(self.panel_download, label="Cancelar Download")
        self.btn_cancelar.Bind(wx.EVT_BUTTON, self.on_cancelar)
        sizer_download.Add(self.btn_cancelar, 0, wx.ALL | wx.CENTER, 15)
        
        self.gauge = wx.Gauge(self.panel_download, range=100, name="Barra de Progresso Visual")
        sizer_download.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 10)
        
        self.txt_status = wx.TextCtrl(self.panel_download, value="Iniciando...", style=wx.TE_READONLY | wx.BORDER_NONE | wx.TE_CENTRE, name="Status")
        sizer_download.Add(self.txt_status, 0, wx.EXPAND | wx.ALL, 5)
        
        self.txt_tempo = wx.TextCtrl(self.panel_download, value="Tempo estimado: calculando...", style=wx.TE_READONLY | wx.BORDER_NONE | wx.TE_CENTRE, name="Tempo Estimado")
        sizer_download.Add(self.txt_tempo, 0, wx.EXPAND | wx.ALL, 5)
        
        self.txt_porcentagem = wx.TextCtrl(self.panel_download, value="Progresso: 0%", style=wx.TE_READONLY | wx.BORDER_NONE | wx.TE_CENTRE, name="Porcentagem")
        sizer_download.Add(self.txt_porcentagem, 0, wx.EXPAND | wx.ALL, 5)
        
        self.panel_download.SetSizer(sizer_download)
        self.sizer_principal.Add(self.panel_download, 1, wx.EXPAND | wx.ALL, 0)
        
        self.panel_download.Hide()
        
        self.panel_principal.SetSizer(self.sizer_principal)
        self.Center()
        
    def on_procurar(self, event):
        dlg = wx.DirDialog(self, "Escolha onde salvar", style=wx.DD_DEFAULT_STYLE)
        
        if self.txt_pasta.GetValue() and os.path.exists(self.txt_pasta.GetValue()):
            dlg.SetPath(self.txt_pasta.GetValue())
            
        if dlg.ShowModal() == wx.ID_OK:
            self.txt_pasta.SetValue(dlg.GetPath())
        dlg.Destroy()
        
    def on_baixar(self, event):
        url = self.txt_url.GetValue().strip()
        pasta = self.txt_pasta.GetValue().strip()
        
        if not url:
            wx.MessageBox("A URL da fanfic não pode estar vazia.", "Erro de Validação", wx.OK | wx.ICON_ERROR)
            self.txt_url.SetFocus()
            return
            
        if not pasta:
            wx.MessageBox("Por favor, selecione ou digite uma pasta de destino.", "Erro de Validação", wx.OK | wx.ICON_ERROR)
            self.txt_pasta.SetFocus()
            return
            
        modo = self.radio_modo.GetStringSelection()
        formato = self.combo_formato.GetStringSelection()
        
        salvar_config(formato, pasta)
        self.cancel_event.clear()
        
        self.gauge.SetValue(0)
        self.txt_status.SetValue("Iniciando...")
        self.txt_tempo.SetValue("Tempo estimado: calculando...")
        self.txt_porcentagem.SetValue("Progresso: 0%")
        
        self.panel_inputs.Hide()
        self.panel_download.Show()
        self.panel_principal.Layout()
        
        self.btn_cancelar.Enable()
        self.btn_cancelar.SetFocus()
        
        thread = threading.Thread(target=self._processar_download, args=(url, modo, formato, pasta))
        thread.daemon = True
        thread.start()
        
    def on_cancelar(self, event):
        self.cancel_event.set()
        self.btn_cancelar.Disable()
        self.txt_status.SetValue("Cancelando... aguarde.")
        
    def _atualizar_progresso(self, porcentagem, mensagem, tempo_restante):
        wx.CallAfter(self.gauge.SetValue, porcentagem)
        wx.CallAfter(self.txt_status.SetValue, mensagem)
        wx.CallAfter(self.txt_porcentagem.SetValue, f"Progresso: {porcentagem}%")
        if tempo_restante >= 0:
            minutos = int(tempo_restante // 60)
            segundos = int(tempo_restante % 60)
            wx.CallAfter(self.txt_tempo.SetValue, f"Tempo estimado: {minutos}m {segundos}s")
        
    def _processar_download(self, url, modo, formato, pasta):
        try:
            if "spiritfanfiction" in url.lower():
                sucesso, mensagem = baixar_spirit(url, modo)
            elif "wattpad" in url.lower():
                sucesso, mensagem = baixar_wattpad(url, modo, formato, pasta, self._atualizar_progresso, self.cancel_event)
            elif "fanfiction.net" in url.lower():
                sucesso, mensagem = baixar_fanfiction_net(url, modo, formato, pasta, self._atualizar_progresso, self.cancel_event)
            else:
                sucesso = False
                mensagem = "No momento, apenas links do Spirit, Wattpad e FanFiction.net estão suportados."
                
            wx.CallAfter(self._finalizar_download, sucesso, mensagem)
        except Exception as e:
            # Rede de segurança absoluta
            wx.CallAfter(self._finalizar_download, False, f"Erro Crítico na Thread:\n{str(e)}")
            
    def _finalizar_download(self, sucesso, mensagem):
        self.gauge.SetValue(100 if sucesso else 0)
        self.txt_status.SetValue("Concluído!" if sucesso else "Erro/Cancelado")
        self.txt_tempo.SetValue("Tempo estimado: --")
        
        estilo = wx.OK | wx.ICON_INFORMATION if sucesso else wx.OK | wx.ICON_ERROR
        wx.MessageBox(mensagem, "Resultado do Download", estilo)
        
        resp = wx.MessageBox("Deseja baixar outra fanfic?", "Continuar?", wx.YES_NO | wx.ICON_QUESTION)
        if resp == wx.YES:
            self.txt_url.Clear()
            self.panel_download.Hide()
            self.panel_inputs.Show()
            self.panel_principal.Layout()
            self.txt_url.SetFocus()
        else:
            self.Close()