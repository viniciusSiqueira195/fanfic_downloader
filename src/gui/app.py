import wx
import threading
from scrapers.spirit import baixar_spirit
from scrapers.wattpad import baixar_wattpad

class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title="Fanfic Downloader", size=(500, 400))
        
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        lbl_url = wx.StaticText(panel, label="Cole a URL da Fanfic:")
        self.txt_url = wx.TextCtrl(panel, name="URL da Fanfic")
        sizer.Add(lbl_url, 0, wx.ALL, 5)
        sizer.Add(self.txt_url, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        opcoes_modo = ["Obra Completa", "Apenas este capítulo"]
        self.radio_modo = wx.RadioBox(panel, label="Modo de Download", choices=opcoes_modo, majorDimension=1, style=wx.RA_SPECIFY_COLS)
        sizer.Add(self.radio_modo, 0, wx.ALL | wx.EXPAND, 5)
        
        lbl_formato = wx.StaticText(panel, label="Selecione o formato de saída:")
        formatos = ["PDF", "EPUB", "TXT"]
        self.combo_formato = wx.Choice(panel, choices=formatos, name="Formato do Arquivo")
        self.combo_formato.SetSelection(0)
        sizer.Add(lbl_formato, 0, wx.ALL, 5)
        sizer.Add(self.combo_formato, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        lbl_pasta = wx.StaticText(panel, label="Pasta para salvar:")
        self.picker_pasta = wx.DirPickerCtrl(panel, message="Escolha onde salvar", name="Pasta de Destino")
        sizer.Add(lbl_pasta, 0, wx.ALL, 5)
        sizer.Add(self.picker_pasta, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        self.btn_baixar = wx.Button(panel, label="Baixar Fanfic")
        self.btn_baixar.Bind(wx.EVT_BUTTON, self.on_baixar)
        sizer.Add(self.btn_baixar, 0, wx.ALL | wx.CENTER, 15)
        
        panel.SetSizer(sizer)
        self.Center()
        
    def on_baixar(self, event):
        url = self.txt_url.GetValue().strip()
        
        if not url:
            wx.MessageBox("A URL da fanfic não pode estar vazia.", "Erro de Validação", wx.OK | wx.ICON_ERROR)
            self.txt_url.SetFocus()
            return
            
        modo = self.radio_modo.GetStringSelection()
        formato = self.combo_formato.GetStringSelection()
        pasta = self.picker_pasta.GetPath()
        
        self.btn_baixar.Disable()
        self.btn_baixar.SetLabel("Baixando...")
        
        thread = threading.Thread(target=self._processar_download, args=(url, modo, formato, pasta))
        thread.daemon = True
        thread.start()
        
    def _processar_download(self, url, modo, formato, pasta):
        if "spiritfanfiction" in url.lower():
            sucesso, mensagem = baixar_spirit(url, modo)
        elif "wattpad" in url.lower():
            sucesso, mensagem = baixar_wattpad(url, modo, formato, pasta)
        else:
            sucesso = False
            mensagem = "No momento, apenas links do Spirit e Wattpad estão suportados."
            
        wx.CallAfter(self._finalizar_download, sucesso, mensagem)
        
    def _finalizar_download(self, sucesso, mensagem):
        self.btn_baixar.Enable()
        self.btn_baixar.SetLabel("Baixar Fanfic")
        
        if sucesso:
            wx.MessageBox(mensagem, "Sucesso", wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox(mensagem, "Erro no Download", wx.OK | wx.ICON_ERROR)