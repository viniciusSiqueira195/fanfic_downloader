 
import wx
from gui.app import MainFrame
from updater import limpar_residuos_atualizacao

def main():
    limpar_residuos_atualizacao()
    app = wx.App(False)
    frame = MainFrame()
    frame.Show()
    app.MainLoop()

if __name__ == "__main__":
    main()