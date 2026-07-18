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

class ConfigFrame(wx.Frame):
    def __init__(self, main_frame):
        super().__init__(parent=main_frame, title="Configurações", size=(460, 220))
        self.main_frame = main_frame

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.chk_verificar_atualizacoes = wx.CheckBox(
            panel,
            label="Verificar atualizações automaticamente ao iniciar",
        )
        self.chk_verificar_atualizacoes.SetValue(bool(main_frame.config.get("verificar_atualizacoes", False)))
        sizer.Add(self.chk_verificar_atualizacoes, 0, wx.ALL, 10)

        sizer_botoes = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_salvar = wx.Button(panel, label="Salvar")
        self.btn_salvar.Bind(wx.EVT_BUTTON, self.on_salvar)
        self.btn_cancelar = wx.Button(panel, label="Cancelar")
        self.btn_cancelar.Bind(wx.EVT_BUTTON, self.on_cancelar)
        sizer_botoes.Add(self.btn_salvar, 0, wx.RIGHT, 5)
        sizer_botoes.Add(self.btn_cancelar, 0)
        sizer.Add(sizer_botoes, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)
        panel.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        self.CenterOnParent()
        self.chk_verificar_atualizacoes.SetFocus()

    def on_char_hook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
            return
        event.Skip()

    def on_close(self, event):
        if self.main_frame:
            self.main_frame.config_frame = None
        event.Skip()

    def on_salvar(self, event):
        self.main_frame.config["verificar_atualizacoes"] = self.chk_verificar_atualizacoes.GetValue()
        self.main_frame._salvar_preferencias()
        self.Close()

    def on_cancelar(self, event):
        self.Close()

class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title=f"Fanfic Downloader v{APP_VERSION}", size=(500, 500))

        self.config = carregar_config()
        self.cancel_event = threading.Event()
        self._update_busy = False
        self.config_frame = None

        self.panel_principal = wx.Panel(self)
        self.sizer_principal = wx.BoxSizer(wx.VERTICAL)

        # --- MENU PRINCIPAL ---
        self.panel_menu_principal, self.listbox_principal = self._criar_painel_menu(
            "Menu principal",
            ["Baixar fanfics", "Baixar livros", "Configurações", "Verificar atualização", "Ver créditos"],
            self.on_menu_principal,
        )

        # --- SUBMENU BAIXAR FANFICS ---
        self.panel_menu_fanfics, self.listbox_fanfics = self._criar_painel_menu(
            "Baixar fanfics",
            ["Pesquisar", "Baixar direto por URL"],
            self.on_menu_fanfics,
        )

        # --- PAINEL DE PESQUISA ---
        self.panel_pesquisa = wx.Panel(self.panel_principal)
        sizer_pesquisa = wx.BoxSizer(wx.VERTICAL)

        lbl_busca = wx.StaticText(self.panel_pesquisa, label="Pesquise por termo:")
        sizer_pesquisa.Add(lbl_busca, 0, wx.ALL, 5)

        self.combo_site_busca = wx.Choice(self.panel_pesquisa, choices=["Todas as fontes", "Wattpad", "Spirit", "FanFiction.net", "PlusFiction"], name="Site da Pesquisa")
        self.combo_site_busca.SetSelection(0)
        sizer_pesquisa.Add(self.combo_site_busca, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        sizer_busca = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_busca = wx.TextCtrl(self.panel_pesquisa, name="Termo de pesquisa")
        self.btn_pesquisar = wx.Button(self.panel_pesquisa, label="Pesquisar")
        self.btn_pesquisar.Bind(wx.EVT_BUTTON, self.on_pesquisar)
        sizer_busca.Add(self.txt_busca, 1, wx.EXPAND | wx.RIGHT, 5)
        sizer_busca.Add(self.btn_pesquisar, 0, wx.ALL, 0)
        sizer_pesquisa.Add(sizer_busca, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        self.panel_pesquisa.SetSizer(sizer_pesquisa)

        # --- PAINEL DE DOWNLOAD POR URL ---
        self.panel_url = wx.Panel(self.panel_principal)
        sizer_url = wx.BoxSizer(wx.VERTICAL)

        lbl_url = wx.StaticText(self.panel_url, label="Cole a URL da Fanfic:")
        self.txt_url = wx.TextCtrl(self.panel_url, name="URL da Fanfic")
        sizer_url.Add(lbl_url, 0, wx.ALL, 5)
        sizer_url.Add(self.txt_url, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        opcoes_modo = ["Obra Completa", "Apenas este capítulo"]
        self.radio_modo = wx.RadioBox(self.panel_url, label="Modo de Download", choices=opcoes_modo, majorDimension=1, style=wx.RA_SPECIFY_COLS)
        sizer_url.Add(self.radio_modo, 0, wx.ALL | wx.EXPAND, 5)

        lbl_formato = wx.StaticText(self.panel_url, label="Selecione o formato de saída:")
        formatos = ["PDF", "EPUB", "TXT"]
        self.combo_formato = wx.Choice(self.panel_url, choices=formatos, name="Formato do Arquivo")

        if self.config["formato"] in formatos:
            self.combo_formato.SetStringSelection(self.config["formato"])
        else:
            self.combo_formato.SetSelection(0)

        sizer_url.Add(lbl_formato, 0, wx.ALL, 5)
        sizer_url.Add(self.combo_formato, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # --- COMPONENTE DE PASTA CUSTOMIZADO E ACESSÍVEL ---
        lbl_pasta = wx.StaticText(self.panel_url, label="Pasta para salvar:")
        sizer_url.Add(lbl_pasta, 0, wx.ALL, 5)

        sizer_pasta = wx.BoxSizer(wx.HORIZONTAL)

        self.txt_pasta = wx.TextCtrl(self.panel_url, name="Se preferir, cole o caminho da pasta aqui")
        if self.config["pasta"] and os.path.exists(self.config["pasta"]):
            self.txt_pasta.SetValue(self.config["pasta"])

        self.btn_procurar = wx.Button(self.panel_url, label="Procurar...")
        self.btn_procurar.Bind(wx.EVT_BUTTON, self.on_procurar)

        sizer_pasta.Add(self.txt_pasta, 1, wx.EXPAND | wx.RIGHT, 5)
        sizer_pasta.Add(self.btn_procurar, 0, wx.ALL, 0)

        sizer_url.Add(sizer_pasta, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        # ----------------------------------------------------

        self.btn_baixar = wx.Button(self.panel_url, label="Baixar Fanfic")
        self.btn_baixar.Bind(wx.EVT_BUTTON, self.on_baixar)
        sizer_url.Add(self.btn_baixar, 0, wx.ALL | wx.CENTER, 15)

        self.panel_url.SetSizer(sizer_url)

        # --- PAINEL DE CRÉDITOS ---
        self.panel_creditos = wx.Panel(self.panel_principal)
        sizer_creditos = wx.BoxSizer(wx.VERTICAL)

        lbl_creditos = wx.StaticText(self.panel_creditos, label="Créditos")
        sizer_creditos.Add(lbl_creditos, 0, wx.ALL, 10)

        texto_creditos = (
            f"Fanfic Downloader v{APP_VERSION}\n"
            "\n"
            "Desenvolvido por:\n"
            "\n"
            "- Vinicius Siqueira (GitHub: viniciusSiqueira195)\n"
            "- Gustavo Almeida Barrios (GitHub: gustavo-barrios2006)\n"
            "- Paulo Santesso (GitHub: paulosantesso1)\n"
            "- Eduardo Ferreira (GitHub: Ed-Fe)\n"
            "\n"
            "Obrigado por usar o Fanfic Downloader!"
        )
        self.txt_creditos = wx.TextCtrl(
            self.panel_creditos,
            value=texto_creditos,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            name="Créditos",
        )
        sizer_creditos.Add(self.txt_creditos, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.panel_creditos.SetSizer(sizer_creditos)

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

        # --- NAVEGAÇÃO ENTRE PAINÉIS ---
        self.paineis = [
            self.panel_menu_principal,
            self.panel_menu_fanfics,
            self.panel_pesquisa,
            self.panel_url,
            self.panel_creditos,
            self.panel_download,
        ]
        for painel in self.paineis:
            self.sizer_principal.Add(painel, 1, wx.EXPAND | wx.ALL, 0)

        # Esc leva ao painel parente; painéis fora do dicionário não respondem ao Esc
        self.parentes = {
            self.panel_menu_fanfics: self.panel_menu_principal,
            self.panel_pesquisa: self.panel_menu_fanfics,
            self.panel_url: self.panel_menu_fanfics,
            self.panel_creditos: self.panel_menu_principal,
        }

        self.foco_padrao = {
            self.panel_menu_principal: self.listbox_principal,
            self.panel_menu_fanfics: self.listbox_fanfics,
            self.panel_pesquisa: self.txt_busca,
            self.panel_url: self.txt_url,
            self.panel_creditos: self.txt_creditos,
        }

        # Enter é tratado no EVT_CHAR_HOOK do frame porque o ListBox nativo
        # do Windows não recebe EVT_KEY_DOWN para essa tecla
        self.acoes_menu = {
            self.listbox_principal: self.on_menu_principal,
            self.listbox_fanfics: self.on_menu_fanfics,
        }

        self.painel_atual = None
        self._mostrar_painel(self.panel_menu_principal)

        self.panel_principal.SetSizer(self.sizer_principal)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.Center()

        if self.config.get("verificar_atualizacoes", False):
            wx.CallAfter(self.on_menu_verificar_atualizacao)

    def _criar_painel_menu(self, titulo, opcoes, ao_ativar):
        painel = wx.Panel(self.panel_principal)
        sizer = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(painel, label=titulo)
        sizer.Add(lbl, 0, wx.ALL, 10)

        listbox = wx.ListBox(painel, choices=opcoes, name=titulo)
        listbox.SetSelection(0)
        listbox.Bind(wx.EVT_LISTBOX_DCLICK, lambda event: self._ativar_opcao_menu(listbox, ao_ativar))
        sizer.Add(listbox, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        painel.SetSizer(sizer)
        return painel, listbox

    def _ativar_opcao_menu(self, listbox, ao_ativar):
        opcao = listbox.GetStringSelection()
        if opcao:
            ao_ativar(opcao)

    def _mostrar_painel(self, painel):
        for outro in self.paineis:
            if outro is not painel:
                outro.Hide()
        painel.Show()
        self.painel_atual = painel
        self.panel_principal.Layout()
        foco = self.foco_padrao.get(painel)
        if foco:
            foco.SetFocus()

    def on_char_hook(self, event):
        keycode = event.GetKeyCode()

        if keycode == wx.WXK_ESCAPE:
            parente = self.parentes.get(self.painel_atual)
            if parente is not None:
                self._mostrar_painel(parente)
                return

        if keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            foco = wx.Window.FindFocus()
            ao_ativar = self.acoes_menu.get(foco)
            if ao_ativar:
                self._ativar_opcao_menu(foco, ao_ativar)
                return

        event.Skip()

    def on_menu_principal(self, opcao):
        if opcao == "Baixar fanfics":
            self._mostrar_painel(self.panel_menu_fanfics)
        elif opcao == "Baixar livros":
            wx.MessageBox("Função em desenvolvimento.", "Baixar livros", wx.OK | wx.ICON_INFORMATION)
        elif opcao == "Configurações":
            self.abrir_configuracoes()
        elif opcao == "Verificar atualização":
            self.on_menu_verificar_atualizacao()
        elif opcao == "Ver créditos":
            self._mostrar_painel(self.panel_creditos)

    def on_menu_fanfics(self, opcao):
        if opcao == "Pesquisar":
            self._mostrar_painel(self.panel_pesquisa)
        elif opcao == "Baixar direto por URL":
            self._mostrar_painel(self.panel_url)

    def on_menu_verificar_atualizacao(self):
        if self._update_busy:
            return
        indice = self.listbox_principal.FindString("Verificar atualização")
        if indice != wx.NOT_FOUND:
            self.listbox_principal.SetString(indice, "Verificando...")
        self.iniciar_verificacao_atualizacao(self._restaurar_item_verificar_atualizacao)

    def _restaurar_item_verificar_atualizacao(self):
        indice = self.listbox_principal.FindString("Verificando...")
        if indice != wx.NOT_FOUND:
            self.listbox_principal.SetString(indice, "Verificar atualização")

    def abrir_configuracoes(self):
        if self.config_frame:
            self.config_frame.Raise()
            return
        self.config_frame = ConfigFrame(self)
        self.config_frame.Show()

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
            bool(self.config.get("verificar_atualizacoes", False)),
        )

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
        self._mostrar_painel(self.panel_download)

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

        salvar_config(formato, pasta, bool(self.config.get("verificar_atualizacoes", False)))
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

    def iniciar_verificacao_atualizacao(self, ao_finalizar=None):
        if self._update_busy:
            if ao_finalizar:
                ao_finalizar()
            return

        self._update_busy = True

        thread = threading.Thread(target=self._verificar_atualizacao, args=(ao_finalizar,), daemon=True)
        thread.start()

    def _verificar_atualizacao(self, ao_finalizar):
        try:
            atualizacao = verificar_atualizacao()
            wx.CallAfter(self._processar_verificacao_atualizacao, atualizacao, ao_finalizar)
        except Exception as e:
            wx.CallAfter(self._falha_verificacao_atualizacao, str(e), ao_finalizar)

    def _falha_verificacao_atualizacao(self, mensagem, ao_finalizar):
        self._update_busy = False
        if ao_finalizar:
            ao_finalizar()
        wx.MessageBox(
            f"Não foi possível verificar novas releases.\n\nDetalhe técnico: {mensagem}",
            "Atualização",
            wx.OK | wx.ICON_ERROR,
        )

    def _processar_verificacao_atualizacao(self, atualizacao, ao_finalizar):
        self._update_busy = False
        if ao_finalizar:
            ao_finalizar()

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
            if self.config_frame:
                self.config_frame.Close()
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
        self._mostrar_painel(self.panel_menu_principal)
        self._update_busy = False
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
            self._mostrar_painel(self.panel_url)

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
                sucesso, mensagem = baixar_spirit(url, modo, formato, pasta, self._atualizar_progresso, self.cancel_event)
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
            self._mostrar_painel(self.panel_menu_fanfics)
        else:
            self.Close()
