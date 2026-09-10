import sys


def _autoteste_pacote():
    import camoufox.sync_api  # noqa: F401 - confirma dependência empacotada do Spirit
    import playwright.sync_api  # noqa: F401 - confirma o driver empacotado
    from books.sources import FONTES
    from gui.sounds import caminho_som
    esperadas = {"Todas as fontes", "Visionvox", "Project Gutenberg", "Wikisource",
                 "Internet Archive"}
    if not esperadas.issubset(FONTES) or not all(caminho_som(tipo).is_file()
                                                 for tipo in ("abrir", "navegar", "confirmar")):
        raise RuntimeError("O pacote não contém todos os módulos ou recursos esperados.")

def main():
    if "--self-test" in sys.argv:
        _autoteste_pacote()
        return
    import wx
    from gui.app import MainFrame
    from updater import limpar_residuos_atualizacao
    limpar_residuos_atualizacao()
    app = wx.App(False)
    frame = MainFrame()
    frame.Show()
    frame.sons.tocar("abrir")
    app.MainLoop()

if __name__ == "__main__":
    main()
