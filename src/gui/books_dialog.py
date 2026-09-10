"""Interface nativa de livros; rede e arquivos ficam no pacote books."""
import threading

import wx

from books.download import DownloadCancelado, ErroPasta, baixar_livro, validar_pasta
from books.sources import FONTES
from gui.sounds import FeedbackSonoro


class SinopseDialog(wx.Dialog):
    def __init__(self, parent, livro, texto):
        super().__init__(parent, title=f"Sinopse — {livro.titulo}", size=(620, 480),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.texto = wx.TextCtrl(self, value=texto, style=wx.TE_MULTILINE | wx.TE_READONLY,
                                 name=f"Sinopse de {livro.titulo}")
        sizer.Add(self.texto, 1, wx.EXPAND | wx.ALL, 10)
        fechar = wx.Button(self, wx.ID_OK, label="Fechar")
        sizer.Add(fechar, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
        self.SetSizer(sizer)
        self.CenterOnParent()
        self.texto.SetFocus()


class BooksDialog(wx.Dialog):
    def __init__(self, parent, pasta="", sons=None, ao_escolher_pasta=None):
        super().__init__(parent, title="Baixar livros", size=(650, 720),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.sons = sons or FeedbackSonoro()
        self.fonte = FONTES["Todas as fontes"]()
        self.tem_proxima = False
        self.cancel_event = threading.Event()
        self.ocupado = False
        self.livros = []
        self.pagina = 0
        self.consulta = None
        self.ultima_pasta = ""
        self.pasta_salva = pasta
        self.ao_escolher_pasta = ao_escolher_pasta
        sizer = wx.BoxSizer(wx.VERTICAL)
        explicacao = wx.TextCtrl(self, value=(
            "Digite o título ou autor e escolha uma fonte, ou pesquise em todas. O Visionvox é destinado "
            "a pessoas com deficiência visual. O Gutenberg reúne principalmente obras clássicas, "
            "em vários idiomas; alguns formatos podem não estar disponíveis. "
            "O arquivo será preservado no formato original. "
            "EPUB vem selecionado para facilitar a leitura ajustável; a acessibilidade "
            "depende de cada arquivo. Na lista, pressione Enter, Shift+F10 ou a tecla de menu "
            "para baixar ou ler a sinopse. Use Tab para navegar e Escape para fechar ou cancelar."),
            style=wx.TE_MULTILINE | wx.TE_READONLY, name="Como baixar livros")
        sizer.Add(explicacao, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(wx.StaticText(self, label="Título ou autor:"), 0, wx.LEFT, 8)
        self.termo = wx.TextCtrl(self, name="Título ou autor", style=wx.TE_PROCESS_ENTER)
        sizer.Add(self.termo, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(wx.StaticText(self, label="Fonte da pesquisa:"), 0, wx.LEFT, 8)
        self.fonte_escolha = wx.Choice(self, choices=list(FONTES), name="Fonte da pesquisa de livros")
        self.fonte_escolha.SetSelection(0)
        sizer.Add(self.fonte_escolha, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(wx.StaticText(self, label="Formato disponível na fonte:"), 0, wx.LEFT, 8)
        self.formato = wx.Choice(self, choices=["EPUB", "TXT", "PDF"], name="Formato do livro")
        self.formato.SetSelection(0)
        sizer.Add(self.formato, 0, wx.EXPAND | wx.ALL, 8)
        self.pesquisar = wx.Button(self, label="&Pesquisar")
        sizer.Add(self.pesquisar, 0, wx.ALL, 8)
        self.resultados = wx.ListBox(self, name="Livros encontrados")
        sizer.Add(self.resultados, 1, wx.EXPAND | wx.ALL, 8)
        paginas = wx.BoxSizer(wx.HORIZONTAL)
        self.anterior = wx.Button(self, label="Página anterior")
        self.proxima = wx.Button(self, label="Próxima página")
        paginas.Add(self.anterior, 0, wx.RIGHT, 8)
        paginas.Add(self.proxima)
        sizer.Add(paginas, 0, wx.ALL, 8)
        self.status = wx.TextCtrl(self, value="Pronto para pesquisar.",
                                  style=wx.TE_READONLY, name="Status da operação de livros")
        sizer.Add(self.status, 0, wx.EXPAND | wx.ALL, 8)
        botoes = wx.BoxSizer(wx.HORIZONTAL)
        self.cancelar = wx.Button(self, label="Cancelar operação")
        self.fechar = wx.Button(self, wx.ID_CANCEL, label="Fechar")
        for botao in (self.cancelar, self.fechar):
            botoes.Add(botao, 0, wx.RIGHT, 8)
        sizer.Add(botoes, 0, wx.ALL, 8)
        self.SetSizer(sizer)
        self.pesquisar.Bind(wx.EVT_BUTTON, self.on_pesquisar)
        self.termo.Bind(wx.EVT_TEXT_ENTER, self.on_pesquisar)
        self.fonte_escolha.Bind(wx.EVT_CHOICE, self.on_fonte)
        self.resultados.Bind(wx.EVT_LISTBOX_DCLICK, self.on_menu_acoes)
        self.resultados.Bind(wx.EVT_CONTEXT_MENU, self.on_menu_acoes)
        self.anterior.Bind(wx.EVT_BUTTON, lambda e: self._buscar_pagina(self.pagina - 1))
        self.proxima.Bind(wx.EVT_BUTTON, lambda e: self._buscar_pagina(self.pagina + 1))
        self.cancelar.Bind(wx.EVT_BUTTON, self.on_cancelar)
        self.fechar.Bind(wx.EVT_BUTTON, self.on_fechar)
        self.Bind(wx.EVT_CLOSE, self.on_fechar)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_tecla)
        self.sons.vincular(self)
        self._ocupacao(False)
        self.CenterOnParent()
        self.termo.SetFocus()

    def _ocupacao(self, ocupado):
        self.ocupado = ocupado
        for controle in (self.fonte_escolha, self.termo, self.formato, self.pesquisar, self.resultados):
            controle.Enable(not ocupado)
        self.anterior.Enable(not ocupado and self.consulta is not None and self.pagina > 0)
        self.proxima.Enable(not ocupado and self.tem_proxima)
        self.cancelar.Enable(ocupado)
        if ocupado:
            self.cancelar.SetFocus()

    def _executar(self, funcao, concluido):
        if self.ocupado:
            return
        self.cancel_event.clear()
        self._ocupacao(True)

        def worker():
            try:
                resultado = funcao()
                erro = None
            except Exception as exc:
                resultado, erro = None, exc
            wx.CallAfter(self._terminar, concluido, resultado, erro)

        threading.Thread(target=worker, daemon=True).start()

    def _terminar(self, concluido, resultado, erro):
        self._ocupacao(False)
        if isinstance(erro, DownloadCancelado) or (self.cancel_event.is_set() and resultado is None):
            self.status.SetValue("Operação cancelada.")
            self.status.SetFocus()
        elif erro:
            self.status.SetValue("Não foi possível concluir a operação.")
            wx.MessageBox(str(erro), "Livros", wx.OK | wx.ICON_ERROR, parent=self)
            self.status.SetFocus()
        else:
            concluido(resultado)

    def on_pesquisar(self, event):
        if self.ocupado:
            return
        if not self.termo.GetValue().strip():
            wx.MessageBox("Digite o título ou autor do livro.", "Pesquisa", parent=self)
            self.termo.SetFocus()
            return
        self.consulta = (self.termo.GetValue().strip(), self.formato.GetStringSelection().lower())
        self._buscar_pagina(0)

    def on_fonte(self, event):
        self.fonte = FONTES[self.fonte_escolha.GetStringSelection()]()
        self.consulta = None
        self.pagina = 0
        self.tem_proxima = False
        self.livros = []
        self.resultados.Clear()
        self.status.SetValue("Fonte alterada. Pressione Pesquisar para consultar o título ou autor informado.")
        self._ocupacao(False)

    def _buscar_pagina(self, pagina):
        if self.ocupado or self.consulta is None:
            return
        termo, formato = self.consulta
        self.status.SetValue(f"Pesquisando em {self.fonte_escolha.GetStringSelection()}, página {pagina + 1}...")

        def buscar():
            livros = self.fonte.buscar_pagina(termo, formato, pagina)
            if self.cancel_event.is_set():
                raise DownloadCancelado()
            return livros

        def mostrar(resultado):
            livros = resultado.livros
            self.tem_proxima = resultado.tem_proxima
            self.pagina = pagina
            self.livros = livros
            self.resultados.Set([f"{livro.titulo} — {livro.origem}" for livro in livros])
            self.status.SetValue(
                f"Página {pagina + 1}: {len(livros)} livros encontrados.{resultado.aviso}"
            )
            self._ocupacao(False)
            if livros:
                self.resultados.SetSelection(0)
                self.resultados.SetFocus()
            else:
                self.status.SetFocus()

        self._executar(buscar, mostrar)

    def _selecionar_pasta(self):
        pasta_inicial = self.pasta_salva if self.pasta_salva and wx.DirExists(self.pasta_salva) else ""
        with wx.DirDialog(self, "Escolha a pasta para salvar os livros",
                          defaultPath=pasta_inicial) as dialogo:
            if dialogo.ShowModal() == wx.ID_OK:
                self.pasta_salva = dialogo.GetPath()
                self.ultima_pasta = self.pasta_salva
                if self.ao_escolher_pasta:
                    self.ao_escolher_pasta(self.pasta_salva)
                return self.pasta_salva
        return None

    def _livro_selecionado(self):
        indice = self.resultados.GetSelection()
        return None if indice == wx.NOT_FOUND else self.livros[indice]

    def on_menu_acoes(self, event):
        if self.ocupado or self._livro_selecionado() is None:
            return
        menu = wx.Menu()
        baixar = menu.Append(wx.ID_ANY, "Baixar")
        sinopse = menu.Append(wx.ID_ANY, "Ler sinopse")
        alterar = menu.Append(wx.ID_ANY, "Escolher outra pasta para downloads...")
        menu.Bind(wx.EVT_MENU, self.on_baixar, baixar)
        menu.Bind(wx.EVT_MENU, self.on_sinopse, sinopse)
        menu.Bind(wx.EVT_MENU, lambda evt: self._selecionar_pasta(), alterar)
        self.PopupMenu(menu)
        menu.Destroy()
        if not self.ocupado:
            self.resultados.SetFocus()

    def on_baixar(self, event):
        livro = self._livro_selecionado()
        if self.ocupado or livro is None:
            return
        try:
            pasta = validar_pasta(self.pasta_salva)
        except ErroPasta:
            pasta = self._selecionar_pasta()
            if pasta is None:
                self.status.SetValue("Download não iniciado: nenhuma pasta foi escolhida.")
                self.resultados.SetFocus()
                return
        self.status.SetValue("Baixando livro. Aguarde ou cancele a operação.")

        def concluido(caminho):
            self.ultima_pasta = str(caminho.parent)
            self.status.SetValue(f"Livro salvo em {caminho}")
            wx.MessageBox(f"Livro salvo em:\n{caminho}", "Download concluído", parent=self)
            self.resultados.SetFocus()

        self._executar(lambda: baixar_livro(livro, pasta, self.cancel_event), concluido)

    def on_sinopse(self, event):
        livro = self._livro_selecionado()
        if self.ocupado or livro is None:
            return
        self.status.SetValue(f"Procurando a sinopse de {livro.titulo}...")

        def mostrar(texto):
            if not texto:
                wx.MessageBox("Esta fonte não possui uma sinopse disponível para este livro.",
                              "Sinopse não encontrada", wx.OK | wx.ICON_INFORMATION, parent=self)
                self.resultados.SetFocus()
                return
            with SinopseDialog(self, livro, texto) as dialogo:
                dialogo.ShowModal()
            self.status.SetValue("Sinopse exibida.")
            self.resultados.SetFocus()

        if livro.sinopse:
            mostrar(livro.sinopse)
        else:
            self._executar(lambda: self.fonte.obter_sinopse(livro), mostrar)

    def on_cancelar(self, event):
        self.cancel_event.set()
        self.status.SetValue("Cancelando. Aguardando a requisição em andamento terminar.")
        self.cancelar.Disable()
        self.status.SetFocus()

    def on_tecla(self, event):
        tecla = event.GetKeyCode()
        foco = wx.Window.FindFocus()
        if tecla in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and foco in (self.termo, self.resultados):
            self.sons.tocar("confirmar")
            if foco is self.resultados:
                self.on_menu_acoes(event)
            else:
                self.on_pesquisar(event)
        elif tecla == wx.WXK_ESCAPE:
            self.on_fechar(event)
        else:
            event.Skip()

    def on_fechar(self, event):
        if self.ocupado:
            self.on_cancelar(event)
            if isinstance(event, wx.CloseEvent) and event.CanVeto():
                event.Veto()
            return
        self.EndModal(wx.ID_CANCEL)
