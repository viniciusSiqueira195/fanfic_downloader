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
        mensagem = f"Não foi possível salvar suas preferências para a próxima vez, mas o download vai continuar normalmente!\n\nDetalhe técnico: {str(e)}"
        wx.MessageBox(mensagem, "Aviso de Configuração", wx.OK | wx.ICON_WARNING)

class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title=f"Fanfic Downloader v{APP_VERSION}", size=(500, 500))
        
        self.config = carregar_config()
        self.cancel_event = threading.Event()
        self._update_busy = False
        
        self.panel_principal = wx.Panel(self)
        self.sizer_principal = wx.BoxSizer(wx.VERTICAL)
        
        # --- PAINEL DE INPUTS (Tela Inicial) ---
        self.panel_inputs = wx.Panel(self.panel_principal)
        sizer_inputs = wx.BoxSizer(wx.VERTICAL)
        
        lbl_url = wx.StaticText(self.panel_inputs, label="Cole a URL da Fanfic:")
        self.txt_url = wx.TextCtrl(self.panel_inputs, name="URL da Fanfic")
        sizer_inputs.Add(lbl_url, 0, wx.ALL, 5)
        sizer_inputs.Add(self.txt_url, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        lbl_busca = wx.StaticText(self.panel_inputs, label="Ou pesquise por termo (opcional):")
        sizer_inputs.Add(lbl_busca, 0, wx.ALL, 5)

        self.combo_site_busca = wx.Choice(self.panel_inputs, choices=["Todas as fontes", "Wattpad", "Spirit", "FanFiction.net", "PlusFiction"], name="Site da Pesquisa")
        self.combo_site_busca.SetSelection(0)
        sizer_inputs.Add(self.combo_site_busca, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        sizer_busca = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_busca = wx.TextCtrl(self.panel_inputs, name="Termo de pesquisa")
        self.btn_pesquisar = wx.Button(self.panel_inputs, label="Pesquisar")
        self.btn_pesquisar.Bind(wx.EVT_BUTTON, self.on_pesquisar)
        sizer_busca.Add(self.txt_busca, 1, wx.EXPAND | wx.RIGHT, 5)
        sizer_busca.Add(self.btn_pesquisar, 0, wx.ALL, 0)
        sizer_inputs.Add(sizer_busca, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
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

        self.chk_verificar_atualizacoes = wx.CheckBox(
            self.panel_inputs,
            label="Verificar atualizações automaticamente ao iniciar",
        )
        self.chk_verificar_atualizacoes.SetValue(bool(self.config.get("verificar_atualizacoes", False)))
        self.chk_verificar_atualizacoes.Bind(wx.EVT_CHECKBOX, self.on_alterar_preferencia_atualizacao)
        sizer_inputs.Add(self.chk_verificar_atualizacoes, 0, wx.ALL, 5)
        
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

        self.btn_atualizar = wx.Button(self.panel_inputs, label="Verificar atualização")
        self.btn_atualizar.Bind(wx.EVT_BUTTON, self.on_verificar_atualizacao)
        sizer_inputs.Add(self.btn_atualizar, 0, wx.ALL | wx.CENTER, 5)
        
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

        if self.chk_verificar_atualizacoes.GetValue():
            wx.CallAfter(self.on_verificar_atualizacao, None)
        
    def on_procurar(self, event):
        dlg = wx.DirDialog(self, "Escolha onde salvar", style=wx.DD_DEFAULT_STYLE)
        
        if self.txt_pasta.GetValue() and os.path.exists(self.txt_pasta.GetValue()):
            dlg.SetPath(self.txt_pasta.GetValue())
            
        if dlg.ShowModal() == wx.ID_OK:
            self.txt_pasta.SetValue(dlg.GetPath())
        dlg.Destroy()

    def _salvar_preferencias(self):
        salvar_config(
            self.combo_formato.GetStringSelection(),
            self.txt_pasta.GetValue().strip(),
            self.chk_verificar_atualizacoes.GetValue(),
        )

    def on_alterar_preferencia_atualizacao(self, event):
        self._salvar_preferencias()
        
    def _mostrar_painel_download(self, status, tempo, porcentagem, botao_cancelar_ativo, texto_botao_cancelar):
        self.gauge.SetValue(0)
        self.txt_status.SetValue(status)
        self.txt_tempo.SetValue(tempo)
        self.txt_porcentagem.SetValue(porcentagem)
        self.btn_cancelar.SetLabel(texto_botao_cancelar)
        if botao_cancelar_ativo:
            self.btn_cancelar.Enable()
        else:
            self.btn_cancelar.Disable()
        self.panel_inputs.Hide()
        self.panel_download.Show()
        self.panel_principal.Layout()
        
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
        
        salvar_config(formato, pasta, self.chk_verificar_atualizacoes.GetValue())
        self.cancel_event.clear()

        self._mostrar_painel_download(
            "Iniciando...",
            "Tempo estimado: calculando...",
            "Progresso: 0%",
            True,
            "Cancelar Download",
        )
        self.btn_cancelar.SetFocus()
        
        thread = threading.Thread(target=self._processar_download, args=(url, modo, formato, pasta))
        thread.daemon = True
        thread.start()

    def on_verificar_atualizacao(self, event):
        if self._update_busy:
            return

        self._update_busy = True
        self.btn_atualizar.Disable()
        self.btn_atualizar.SetLabel("Verificando...")
        self.txt_status.SetValue("Verificando atualização...")

        thread = threading.Thread(target=self._verificar_atualizacao, daemon=True)
        thread.start()

    def _verificar_atualizacao(self):
        try:
            atualizacao = verificar_atualizacao()
            wx.CallAfter(self._processar_verificacao_atualizacao, atualizacao)
        except Exception as e:
            wx.CallAfter(self._falha_verificacao_atualizacao, str(e))

    def _falha_verificacao_atualizacao(self, mensagem):
        self._update_busy = False
        self.btn_atualizar.Enable()
        self.btn_atualizar.SetLabel("Verificar atualização")
        wx.MessageBox(
            f"Não foi possível verificar novas releases.\n\nDetalhe técnico: {mensagem}",
            "Atualização",
            wx.OK | wx.ICON_ERROR,
        )

    def _processar_verificacao_atualizacao(self, atualizacao):
        self._update_busy = False
        self.btn_atualizar.Enable()
        self.btn_atualizar.SetLabel("Verificar atualização")

        if atualizacao is None:
            wx.MessageBox(
                f"Você já está na versão {APP_VERSION}.",
                "Atualização",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        resposta = wx.MessageBox(
            f"Nova versão encontrada: {atualizacao.latest_version}\n\nDeseja baixar e aplicar agora?",
            "Atualização disponível",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if resposta == wx.YES:
            self._iniciar_atualizacao(atualizacao)

    def _iniciar_atualizacao(self, atualizacao):
        self._mostrar_painel_download(
            "Preparando atualização...",
            "Tempo estimado: calculando...",
            "Progresso: 0%",
            False,
            "Atualizando...",
        )

        thread = threading.Thread(target=self._executar_atualizacao, args=(atualizacao,), daemon=True)
        thread.start()

    def _executar_atualizacao(self, atualizacao):
        try:
            restart_command = baixar_e_aplicar_atualizacao(atualizacao, self._atualizar_progresso)
            wx.CallAfter(self._finalizar_atualizacao, restart_command)
        except Exception as e:
            wx.CallAfter(self._finalizar_atualizacao_com_erro, str(e))

    def _finalizar_atualizacao(self, restart_command):
        self.txt_status.SetValue("Atualização concluída")
        self.txt_tempo.SetValue("Tempo estimado: --")
        self.txt_porcentagem.SetValue("Progresso: 100%")
        reiniciar_aplicativo(restart_command)
        self.Close()

    def _finalizar_atualizacao_com_erro(self, mensagem):
        self.panel_download.Hide()
        self.panel_inputs.Show()
        self.panel_principal.Layout()
        self._update_busy = False
        self.btn_atualizar.Enable()
        self.btn_atualizar.SetLabel("Verificar atualização")
        wx.MessageBox(
            f"Não foi possível aplicar a atualização.\n\nDetalhe técnico: {mensagem}",
            "Atualização",
            wx.OK | wx.ICON_ERROR,
        )

    def on_pesquisar(self, event):
        termo = self.txt_busca.GetValue().strip()
        site = self.combo_site_busca.GetStringSelection()
        if not termo:
            wx.MessageBox("Digite um termo para pesquisar.", "Erro de Validação", wx.OK | wx.ICON_ERROR)
            self.txt_busca.SetFocus()
            return

        wx.BeginBusyCursor()
        try:
            if site == "Todas as fontes":
                resultados = buscar_fanfics_todas_fontes(termo)
            elif site == "Wattpad":
                resultados = buscar_fanfics_wattpad(termo)
            elif site == "Spirit":
                resultados = buscar_fanfics_spirit(termo)
            elif site == "FanFiction.net":
                resultados = buscar_fanfics_fanfiction_net(termo)
            elif site == "PlusFiction":
                resultados = buscar_fanfics_plusfiction(termo)
            else:
                raise ValueError("Site de pesquisa inválido.")
        except requests.exceptions.RequestException as e:
            wx.MessageBox(f"Não foi possível consultar a busca agora.\n\nDetalhe técnico: {str(e)}", "Erro na Busca", wx.OK | wx.ICON_ERROR)
            return
        except ValueError as e:
            wx.MessageBox(str(e), "Erro de Validação", wx.OK | wx.ICON_ERROR)
            return
        finally:
            if wx.IsBusy():
                wx.EndBusyCursor()

        if not resultados:
            wx.MessageBox(f"Nenhum resultado encontrado para esse termo em {site}.", "Busca sem resultados", wx.OK | wx.ICON_INFORMATION)
            return

        opcoes = [f"[{item.get('origem', site)}] {item['titulo']} — por {item['autor']}" for item in resultados]
        dlg = wx.SingleChoiceDialog(self, "Selecione uma fanfic para preencher a URL automaticamente:", "Resultados da Busca", opcoes)

        if dlg.ShowModal() == wx.ID_OK:
            selecionada = resultados[dlg.GetSelection()]
            self.txt_url.SetValue(selecionada["url"])
            self.txt_url.SetFocus()

        dlg.Destroy()

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
            elif "plusfiction.com" in url.lower():
                sucesso, mensagem = baixar_plusfiction(url, modo, formato, pasta, self._atualizar_progresso, self.cancel_event)
            else:
                sucesso = False
                mensagem = "No momento, apenas links do Spirit, Wattpad, FanFiction.net e PlusFiction estão suportados."
                
            wx.CallAfter(self._finalizar_download, sucesso, mensagem)
        except Exception as e:
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
            self.txt_busca.Clear()
            self.panel_download.Hide()
            self.panel_inputs.Show()
            self.panel_principal.Layout()
            self.txt_url.SetFocus()
        else:
            self.Close()