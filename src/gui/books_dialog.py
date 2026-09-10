"""Interface nativa de livros; rede e arquivos ficam no pacote books."""
import os
import threading
from pathlib import Path

import wx

from books.download import (DownloadCancelado, ErroPasta, baixar_livro,
                            caminho_destino, validar_pasta)
from books.sources import FONTES, TodasFontes
from gui.sounds import FeedbackSonoro

IDIOMAS = {
    "Todos os idiomas": "",
    "Português": "pt",
    "Inglês": "en",
    "Espanhol": "es",
    "Francês": "fr",
}
TEMAS = {
    "Mais baixados": "",
    "Ficção": "fiction",
    "Romance": "romance",
    "Mistério": "mystery",
    "Ficção científica": "science fiction",
    "Literatura infantil": "children",
    "História": "history",
}


class SinopseDialog(wx.Dialog):
    def __init__(self, parent, livro, texto):
        super().__init__(parent, title=f"Sinopse — {livro.titulo}", size=(620, 480),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        sizer = wx.BoxSizer(wx.VERTICAL)
        detalhes = [f"Título: {livro.titulo}", f"Fonte: {livro.origem}",
                    f"Formato: {livro.formato.upper()}"]
        if livro.autor:
            detalhes.append(f"Autor: {livro.autor}")
        if livro.idioma:
            detalhes.append(f"Idioma: {livro.idioma}")
        conteudo = "\n".join(detalhes) + "\n\nSinopse:\n" + texto
        self.texto = wx.TextCtrl(self, value=conteudo, style=wx.TE_MULTILINE | wx.TE_READONLY,
                                 name=f"Sinopse de {livro.titulo}")
        sizer.Add(self.texto, 1, wx.EXPAND | wx.ALL, 10)
        copiar = wx.Button(self, label="&Copiar detalhes e sinopse")
        fechar = wx.Button(self, wx.ID_OK, label="Fechar")
        sizer.Add(copiar, 0, wx.ALIGN_CENTER | wx.BOTTOM, 6)
        sizer.Add(fechar, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
        self.SetSizer(sizer)
        self.CenterOnParent()
        self.texto.SetFocus()
        copiar.Bind(wx.EVT_BUTTON, self.on_copiar)

    def on_copiar(self, event):
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(self.texto.GetValue()))
            finally:
                wx.TheClipboard.Close()
            wx.MessageBox("Detalhes e sinopse copiados.", "Copiar", parent=self)


class HistoricoDialog(wx.Dialog):
    def __init__(self, parent, historico):
        super().__init__(parent, title="Histórico de livros", size=(620, 420),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.historico = [item for item in reversed(historico)
                          if Path(item.get("caminho", "")).is_file()]
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.lista = wx.ListBox(self, choices=[item.get("titulo", Path(item["caminho"]).name)
                                               for item in self.historico],
                                name="Livros baixados")
        sizer.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)
        botoes = wx.BoxSizer(wx.HORIZONTAL)
        abrir = wx.Button(self, label="Abrir livro")
        pasta = wx.Button(self, label="Abrir pasta")
        fechar = wx.Button(self, wx.ID_OK, label="Fechar")
        for botao in (abrir, pasta, fechar):
            botoes.Add(botao, 0, wx.RIGHT, 8)
        sizer.Add(botoes, 0, wx.ALL, 8)
        self.SetSizer(sizer)
        abrir.Bind(wx.EVT_BUTTON, self.on_abrir)
        pasta.Bind(wx.EVT_BUTTON, self.on_pasta)
        self.lista.Bind(wx.EVT_LISTBOX_DCLICK, self.on_abrir)
        if self.historico:
            self.lista.SetSelection(0)
            self.lista.SetFocus()
        else:
            self.lista.Set(["Nenhum livro baixado ainda."])
            fechar.SetFocus()

    def _caminho(self):
        indice = self.lista.GetSelection()
        return None if indice == wx.NOT_FOUND or indice >= len(self.historico) else Path(
            self.historico[indice]["caminho"])

    def on_abrir(self, event):
        caminho = self._caminho()
        if caminho:
            os.startfile(caminho)

    def on_pasta(self, event):
        caminho = self._caminho()
        if caminho:
            os.startfile(caminho.parent)


class BooksDialog(wx.Dialog):
    def __init__(self, parent, pasta="", sons=None, ao_escolher_pasta=None,
                 historico=None, ao_baixar=None, modo_carregamento="manual",
                 limite_resultados=200):
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
        self.explorando = False
        self.topico_explorar = ""
        self.ultima_pasta = ""
        self.pasta_salva = pasta
        self.ao_escolher_pasta = ao_escolher_pasta
        self.historico = list(historico or [])
        self.ao_baixar = ao_baixar
        self.modo_carregamento = (modo_carregamento
                                  if modo_carregamento in ("continuo", "manual") else "manual")
        self.limite_resultados = max(0, int(limite_resultados))
        self.carregando_mais = False
        self.lote_restante = 0
        self.urls_exibidas = set()
        self.resultados_reserva = []
        self.tem_proxima_remota = False
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.painel_busca = wx.Panel(self, name="Tela de pesquisa de livros")
        busca_sizer = wx.BoxSizer(wx.VERTICAL)
        explicacao = wx.TextCtrl(self.painel_busca, value=(
            "Digite o título ou autor e escolha uma fonte, ou pesquise em todas. O Visionvox é destinado "
            "a pessoas com deficiência visual. O Gutenberg reúne principalmente obras clássicas, "
            "em vários idiomas; alguns formatos podem não estar disponíveis. "
            "O arquivo será preservado no formato original. "
            "EPUB vem selecionado para facilitar a leitura ajustável; a acessibilidade "
            "depende de cada arquivo. Na lista, pressione Enter, Shift+F10 ou a tecla de menu "
            "para baixar ou ler a sinopse. Atalhos: Ctrl+F pesquisa, Ctrl+D baixa, Ctrl+H abre "
            "o histórico e F5 repete a pesquisa. Use Tab para navegar e Escape para fechar ou cancelar."),
            style=wx.TE_MULTILINE | wx.TE_READONLY, name="Como baixar livros")
        busca_sizer.Add(explicacao, 0, wx.EXPAND | wx.ALL, 8)
        busca_sizer.Add(wx.StaticText(self.painel_busca, label="Título ou autor:"), 0, wx.LEFT, 8)
        self.termo = wx.TextCtrl(self.painel_busca, name="Título ou autor", style=wx.TE_PROCESS_ENTER)
        busca_sizer.Add(self.termo, 0, wx.EXPAND | wx.ALL, 8)
        busca_sizer.Add(wx.StaticText(self.painel_busca, label="Fonte da pesquisa:"), 0, wx.LEFT, 8)
        self.fonte_escolha = wx.Choice(self.painel_busca, choices=list(FONTES), name="Fonte da pesquisa de livros")
        self.fonte_escolha.SetSelection(0)
        busca_sizer.Add(self.fonte_escolha, 0, wx.EXPAND | wx.ALL, 8)
        busca_sizer.Add(wx.StaticText(self.painel_busca, label="Formato disponível na fonte:"), 0, wx.LEFT, 8)
        self.formato = wx.Choice(self.painel_busca, choices=["EPUB", "TXT", "PDF"], name="Formato do livro")
        self.formato.SetSelection(0)
        busca_sizer.Add(self.formato, 0, wx.EXPAND | wx.ALL, 8)
        busca_sizer.Add(wx.StaticText(self.painel_busca, label="Idioma:"), 0, wx.LEFT, 8)
        self.idioma = wx.Choice(self.painel_busca, choices=list(IDIOMAS), name="Idioma dos livros")
        self.idioma.SetStringSelection("Português")
        busca_sizer.Add(self.idioma, 0, wx.EXPAND | wx.ALL, 8)
        self.btn_descobrir = wx.Button(self.painel_busca, label="&Descobrir livros para baixar...")
        busca_sizer.Add(self.btn_descobrir, 0, wx.ALL, 8)
        botoes_busca = wx.BoxSizer(wx.HORIZONTAL)
        self.pesquisar = wx.Button(self.painel_busca, label="&Pesquisar")
        self.btn_historico = wx.Button(self.painel_busca, label="&Histórico de downloads")
        self.btn_saude = wx.Button(self.painel_busca, label="&Verificar fontes")
        self.fechar = wx.Button(self.painel_busca, wx.ID_CANCEL, label="Fechar")
        for botao in (self.pesquisar, self.btn_historico, self.btn_saude, self.fechar):
            botoes_busca.Add(botao, 0, wx.RIGHT, 8)
        busca_sizer.Add(botoes_busca, 0, wx.ALL, 8)
        self.painel_busca.SetSizer(busca_sizer)
        sizer.Add(self.painel_busca, 1, wx.EXPAND)

        self.painel_resultados = wx.Panel(self, name="Tela de resultados de livros")
        resultados_sizer = wx.BoxSizer(wx.VERTICAL)
        self.resultados = wx.ListBox(self.painel_resultados, name="Livros encontrados")
        resultados_sizer.Add(self.resultados, 1, wx.EXPAND | wx.ALL, 8)
        paginas = wx.BoxSizer(wx.HORIZONTAL)
        self.anterior = wx.Button(self.painel_resultados, label="Página anterior")
        self.proxima = wx.Button(self.painel_resultados, label="Próxima página")
        paginas.Add(self.anterior, 0, wx.RIGHT, 8)
        paginas.Add(self.proxima)
        resultados_sizer.Add(paginas, 0, wx.ALL, 8)
        self.anterior.Hide()
        self.proxima.Hide()
        self.status = wx.TextCtrl(self.painel_resultados, value="Pronto para pesquisar.",
                                  style=wx.TE_READONLY, name="Status da operação de livros")
        resultados_sizer.Add(self.status, 0, wx.EXPAND | wx.ALL, 8)
        self.progresso = wx.Gauge(self.painel_resultados, range=100, name="Progresso do download do livro")
        self.progresso.Hide()
        resultados_sizer.Add(self.progresso, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        botoes = wx.BoxSizer(wx.HORIZONTAL)
        self.cancelar = wx.Button(self.painel_resultados, label="Cancelar operação")
        self.voltar = wx.Button(self.painel_resultados, label="&Voltar à pesquisa")
        for botao in (self.cancelar, self.voltar):
            botoes.Add(botao, 0, wx.RIGHT, 8)
        resultados_sizer.Add(botoes, 0, wx.ALL, 8)
        self.painel_resultados.SetSizer(resultados_sizer)
        self.painel_resultados.Hide()
        sizer.Add(self.painel_resultados, 1, wx.EXPAND)
        self.SetSizer(sizer)
        self.pesquisar.Bind(wx.EVT_BUTTON, self.on_pesquisar)
        self.btn_descobrir.Bind(wx.EVT_BUTTON, self.on_descobrir)
        self.termo.Bind(wx.EVT_TEXT_ENTER, self.on_pesquisar)
        self.fonte_escolha.Bind(wx.EVT_CHOICE, self.on_fonte)
        self.resultados.Bind(wx.EVT_LISTBOX_DCLICK, self.on_menu_acoes)
        self.resultados.Bind(wx.EVT_LISTBOX, self.on_selecao_resultado)
        self.resultados.Bind(wx.EVT_CONTEXT_MENU, self.on_menu_acoes)
        self.anterior.Bind(wx.EVT_BUTTON, lambda e: self._buscar_pagina(self.pagina - 1))
        self.proxima.Bind(wx.EVT_BUTTON, lambda e: self._buscar_pagina(self.pagina + 1))
        self.cancelar.Bind(wx.EVT_BUTTON, self.on_cancelar)
        self.btn_historico.Bind(wx.EVT_BUTTON, self.on_historico)
        self.btn_saude.Bind(wx.EVT_BUTTON, self.on_verificar_fontes)
        self.voltar.Bind(wx.EVT_BUTTON, self.on_voltar_pesquisa)
        self.fechar.Bind(wx.EVT_BUTTON, self.on_fechar)
        self.Bind(wx.EVT_CLOSE, self.on_fechar)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_tecla)
        self.sons.vincular(self)
        self._atualizar_filtros_fonte()
        self._ocupacao(False)
        self.CenterOnParent()
        self.termo.SetFocus()

    def _mostrar_tela(self, resultados):
        self.painel_busca.Show(not resultados)
        self.painel_resultados.Show(resultados)
        self.Layout()

    def on_voltar_pesquisa(self, event=None):
        if self.ocupado:
            return
        self._mostrar_tela(False)
        self.termo.SetFocus()

    def _ocupacao(self, ocupado):
        self.ocupado = ocupado
        for controle in (self.fonte_escolha, self.termo, self.formato, self.idioma,
                         self.pesquisar, self.btn_descobrir, self.resultados):
            controle.Enable(not ocupado)
        self.anterior.Enable(not ocupado and self.consulta is not None and self.pagina > 0)
        self.proxima.Enable(not ocupado and self.tem_proxima)
        self.cancelar.Enable(ocupado)
        self.voltar.Enable(not ocupado)
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
        self.explorando = False
        self._reiniciar_resultados()
        self.consulta = (self.termo.GetValue().strip(), self.formato.GetStringSelection().lower(),
                         IDIOMAS[self.idioma.GetStringSelection()])
        self._buscar_pagina(0)

    def on_descobrir(self, event):
        if self.ocupado:
            return
        with wx.SingleChoiceDialog(
                self, "Escolha o tema dos livros disponíveis para download.",
                "Descobrir livros", list(TEMAS)) as dialogo:
            dialogo.SetSelection(0)
            if dialogo.ShowModal() != wx.ID_OK:
                self.btn_descobrir.SetFocus()
                return
            self.topico_explorar = TEMAS[dialogo.GetStringSelection()]
        self.explorando = True
        self._reiniciar_resultados()
        self.fonte_escolha.SetStringSelection("Todas as fontes")
        self.fonte = FONTES["Todas as fontes"]()
        self.consulta = ("", self.formato.GetStringSelection().lower(),
                         IDIOMAS[self.idioma.GetStringSelection()])
        self._buscar_pagina(0)

    def on_fonte(self, event):
        self.explorando = False
        self.fonte = FONTES[self.fonte_escolha.GetStringSelection()]()
        self._atualizar_filtros_fonte()
        self.consulta = None
        self.pagina = 0
        self.tem_proxima = False
        self.livros = []
        self.urls_exibidas.clear()
        self.resultados_reserva.clear()
        self.tem_proxima_remota = False
        self.lote_restante = 0
        self.resultados.Clear()
        self.status.SetValue("Fonte alterada. Pressione Pesquisar para consultar o título ou autor informado.")
        self._ocupacao(False)

    def _atualizar_filtros_fonte(self):
        nome = self.fonte_escolha.GetStringSelection() or "Todas as fontes"
        atual_formato = self.formato.GetStringSelection() or "EPUB"
        atual_idioma = self.idioma.GetStringSelection() or "Português"
        if nome == "Todas as fontes":
            capacidades = [getattr(fabrica, "capacidades", None)
                           for fabrica in FONTES.values() if fabrica is not TodasFontes]
            formatos = set().union(*(cap.formatos for cap in capacidades if cap))
            idiomas = set().union(*(cap.idiomas for cap in capacidades if cap))
        else:
            cap = getattr(FONTES[nome], "capacidades", None)
            formatos = set(cap.formatos) if cap else {"epub", "txt", "pdf"}
            idiomas = set(cap.idiomas) if cap else {"pt", "en", "es", "fr"}
        opcoes_formato = [item for item in ("EPUB", "TXT", "PDF") if item.lower() in formatos]
        self.formato.Set(opcoes_formato)
        self.formato.SetStringSelection(atual_formato if atual_formato in opcoes_formato
                                        else opcoes_formato[0])
        opcoes_idioma = [rotulo for rotulo, codigo in IDIOMAS.items()
                         if not codigo or codigo in idiomas]
        self.idioma.Set(opcoes_idioma)
        self.idioma.SetStringSelection(atual_idioma if atual_idioma in opcoes_idioma
                                       else opcoes_idioma[0])

    def _reiniciar_resultados(self):
        self.pagina = 0
        self.tem_proxima = False
        self.livros = []
        self.urls_exibidas.clear()
        self.resultados_reserva.clear()
        self.tem_proxima_remota = False
        self.lote_restante = 0
        self.resultados.Clear()

    def _buscar_pagina(self, pagina):
        incremental = pagina > 0
        if self.ocupado or self.carregando_mais or self.consulta is None:
            return
        self._mostrar_tela(True)
        termo, formato, idioma = self.consulta
        acao = "Explorando livros disponíveis" if self.explorando else "Pesquisando"
        self.status.SetValue(
            f"{acao} em {self.fonte_escolha.GetStringSelection()}..." if not incremental
            else f"Carregando mais resultados; {len(self.livros)} exibidos até agora...")
        parciais = []

        def atualizar_fonte(nome, estado, quantidade, livros):
            if estado == "concluída":
                texto = f"{nome} respondeu com {quantidade} resultados. Aguardando as demais fontes..."
                if not incremental:
                    parciais.extend(livros)
                    rotulos = [self._rotulo_livro(livro) for livro in parciais]
                    wx.CallAfter(self.resultados.Set, rotulos)
            elif estado == "falhou":
                texto = f"{nome} não respondeu. A pesquisa continua nas demais fontes..."
            else:
                return
            wx.CallAfter(self.status.SetValue, texto)

        def buscar():
            if self.explorando:
                livros = self.fonte.explorar_pagina(
                    formato, pagina, idioma, self.topico_explorar)
            elif isinstance(self.fonte, TodasFontes):
                livros = self.fonte.buscar_pagina(
                    termo, formato, pagina, idioma, atualizar_fonte, self.cancel_event)
            else:
                livros = self.fonte.buscar_pagina(termo, formato, pagina, idioma)
            if self.cancel_event.is_set():
                raise DownloadCancelado()
            return livros

        def mostrar(resultado):
            if not incremental:
                self.livros = []
                self.urls_exibidas.clear()
                self.resultados.Clear()
            novos, urls_da_pagina = [], set()
            for livro in resultado.livros:
                chave = livro.url.casefold()
                if chave not in self.urls_exibidas and chave not in urls_da_pagina:
                    urls_da_pagina.add(chave)
                    novos.append(livro)
            self.urls_exibidas.update(urls_da_pagina)
            if incremental and self.modo_carregamento == "manual" and self.lote_restante:
                self.resultados_reserva.extend(novos[self.lote_restante:])
                novos = novos[:self.lote_restante]
            if self.limite_resultados:
                novos = novos[:max(0, self.limite_resultados - len(self.livros))]
            for livro in novos:
                self.livros.append(livro)
                self.resultados.Append(self._rotulo_livro(livro))
            self.tem_proxima_remota = resultado.tem_proxima
            self.tem_proxima = resultado.tem_proxima or bool(self.resultados_reserva)
            self.pagina = pagina
            atingiu_limite = bool(self.limite_resultados and
                                  len(self.livros) >= self.limite_resultados)
            if atingiu_limite:
                self.tem_proxima = False
            self.status.SetValue(
                f"{len(self.livros)} livros carregados."
                f"{' Limite configurado atingido.' if atingiu_limite else ''}{resultado.aviso}"
            )
            if incremental:
                self.carregando_mais = False
                self.cancelar.Disable()
            else:
                self._ocupacao(False)
            if self.livros and not incremental:
                self.resultados.SetSelection(0)
                self.resultados.SetFocus()
            elif not self.livros:
                self.status.SetFocus()
            if self.modo_carregamento == "manual" and self.lote_restante:
                self.lote_restante = max(0, self.lote_restante - len(novos))
            continuar = (self.modo_carregamento == "continuo" or self.lote_restante > 0)
            if continuar and self.tem_proxima and novos:
                wx.CallAfter(self._buscar_pagina, pagina + 1)

        if incremental:
            self.carregando_mais = True
            self.cancelar.Enable()

            def worker_incremental():
                try:
                    resultado, erro = buscar(), None
                except Exception as exc:
                    resultado, erro = None, exc
                wx.CallAfter(self._terminar_incremental, mostrar, resultado, erro)

            threading.Thread(target=worker_incremental, daemon=True).start()
        else:
            self._executar(buscar, mostrar)
        # Leva o leitor de tela à confirmação da busca sem bloquear a janela.
        # _executar dá foco ao botão Cancelar, então esta chamada precisa vir depois.
        if not incremental:
            self.status.SetFocus()

    def _terminar_incremental(self, concluido, resultado, erro):
        self.carregando_mais = False
        self.cancelar.Disable()
        if isinstance(erro, DownloadCancelado) or self.cancel_event.is_set():
            self.tem_proxima = False
            self.status.SetValue("Carregamento de novos resultados cancelado.")
            return
        if erro:
            self.tem_proxima = False
            self.status.SetValue(f"Mais resultados não puderam ser carregados: {erro}")
            return
        concluido(resultado)

    def on_selecao_resultado(self, event):
        if (self.modo_carregamento == "manual" and not self.ocupado
                and not self.carregando_mais and self.tem_proxima):
            indice = self.resultados.GetSelection()
            if indice != wx.NOT_FOUND and indice >= self.resultados.GetCount() - 5:
                self.lote_restante = 15
                quantidade = min(self.lote_restante, len(self.resultados_reserva))
                if self.limite_resultados:
                    quantidade = min(quantidade,
                                     max(0, self.limite_resultados - len(self.livros)))
                for livro in self.resultados_reserva[:quantidade]:
                    self.livros.append(livro)
                    self.resultados.Append(self._rotulo_livro(livro))
                del self.resultados_reserva[:quantidade]
                self.lote_restante -= quantidade
                self.tem_proxima = self.tem_proxima_remota or bool(self.resultados_reserva)
                atingiu_limite = bool(self.limite_resultados and
                                      len(self.livros) >= self.limite_resultados)
                if atingiu_limite:
                    self.tem_proxima = False
                    self.lote_restante = 0
                    self.status.SetValue(
                        f"{len(self.livros)} livros carregados. Limite configurado atingido.")
                elif self.lote_restante and self.tem_proxima_remota:
                    self._buscar_pagina(self.pagina + 1)
                else:
                    self.status.SetValue(f"{len(self.livros)} livros carregados.")
        event.Skip()

    @staticmethod
    def _rotulo_livro(livro):
        detalhes = [livro.origem, livro.formato.upper()]
        if livro.idioma:
            detalhes.append(f"idioma {livro.idioma}")
        return f"{livro.titulo} — " + " — ".join(detalhes)

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
        sinopse = menu.Append(wx.ID_ANY, "Ler detalhes e sinopse")
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
        renomear = False
        existente = caminho_destino(livro, pasta)
        if existente.exists():
            dialogo = wx.MessageDialog(
                self,
                "Este livro já existe. Você pode abrir o arquivo existente ou salvar uma nova cópia com outro nome.",
                "Livro já baixado", wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
            )
            dialogo.SetYesNoCancelLabels("Abrir existente", "Salvar nova cópia", "Cancelar")
            escolha = dialogo.ShowModal()
            dialogo.Destroy()
            if escolha == wx.ID_YES:
                os.startfile(existente)
                self.resultados.SetFocus()
                return
            if escolha != wx.ID_NO:
                self.resultados.SetFocus()
                return
            renomear = True
        self.status.SetValue("Baixando livro. Aguarde ou cancele a operação.")
        self.progresso.SetValue(0)
        self.progresso.Show()
        self.Layout()

        ultimo_anunciado = [-10]

        def atualizar_progresso(recebido, total):
            porcentagem = int(recebido * 100 / total) if total else 0
            wx.CallAfter(self.progresso.SetValue, porcentagem)
            marco = porcentagem // 10 * 10
            if total and marco >= ultimo_anunciado[0] + 10:
                ultimo_anunciado[0] = marco
                wx.CallAfter(self.status.SetValue,
                             f"Baixando {livro.titulo}: {porcentagem}% concluído.")

        def concluido(caminho):
            self.ultima_pasta = str(caminho.parent)
            self.status.SetValue(f"Livro salvo em {caminho}")
            self.progresso.SetValue(100)
            registro = {"titulo": livro.titulo, "caminho": str(caminho),
                        "origem": livro.origem, "formato": livro.formato}
            self.historico = [item for item in self.historico
                              if item.get("caminho") != str(caminho)] + [registro]
            if self.ao_baixar:
                self.ao_baixar(registro)
            wx.MessageBox(f"Livro salvo em:\n{caminho}", "Download concluído", parent=self)
            self.resultados.SetFocus()

        self._executar(lambda: baixar_livro(
            livro, pasta, self.cancel_event, progresso=atualizar_progresso,
            renomear_se_existir=renomear), concluido)

    def on_historico(self, event):
        with HistoricoDialog(self, self.historico) as dialogo:
            dialogo.ShowModal()

    def on_verificar_fontes(self, event):
        if self.ocupado:
            return
        self._mostrar_tela(True)
        self.status.SetValue("Verificando as fontes. Aguarde...")

        def mostrar(estados):
            linhas = [f"{nome}: {'disponível' if ok else 'indisponível'}"
                      for nome, ok, _ in estados]
            texto = ". ".join(linhas) + "."
            self.status.SetValue(texto)
            wx.MessageBox(texto, "Estado das fontes", parent=self)
            self.status.SetFocus()

        self._executar(TodasFontes().verificar_saude, mostrar)
        self.status.SetFocus()

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
        if event.ControlDown() and tecla in (ord("F"), ord("f")):
            self._mostrar_tela(False)
            self.termo.SetFocus()
            self.termo.SelectAll()
            return
        if event.ControlDown() and tecla in (ord("D"), ord("d")):
            self.on_baixar(event)
            return
        if event.ControlDown() and tecla in (ord("H"), ord("h")):
            self.on_historico(event)
            return
        if tecla == wx.WXK_F5:
            if self.explorando:
                self._buscar_pagina(0)
            else:
                self.on_pesquisar(event)
            return
        if tecla in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and foco in (self.termo, self.resultados):
            self.sons.tocar("confirmar")
            if foco is self.resultados:
                self.on_menu_acoes(event)
            else:
                self.on_pesquisar(event)
        elif tecla == wx.WXK_ESCAPE:
            if self.painel_resultados.IsShown() and not self.ocupado:
                self.on_voltar_pesquisa()
            else:
                self.on_fechar(event)
        else:
            event.Skip()

    def on_fechar(self, event):
        if self.ocupado or self.carregando_mais:
            self.on_cancelar(event)
            if isinstance(event, wx.CloseEvent) and event.CanVeto():
                event.Veto()
            return
        self.EndModal(wx.ID_CANCEL)
