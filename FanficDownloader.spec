# -*- mode: python ; coding: utf-8 -*-
# Spec do PyInstaller para o Fanfic Downloader (onedir, sem console).
#
# Pontos importantes:
#  - onedir (e não onefile): o onefile se auto-extrai numa pasta temporária
#    nova a cada execução, o que faz antivírus (Avast etc.) re-escanearem o
#    app inteiro em todo launch. No onedir os arquivos ficam fixos em
#    _internal/, o antivírus escaneia uma vez só e o app abre mais rápido.
#  - Metadados de versão no exe (lidos de src/version.py): exe sem recurso
#    de versão é gatilho comum de heurística de antivírus.
#  - collect_all('playwright'): o Camoufox dirige o navegador pelo driver
#    Node.js que vem dentro do pacote playwright; sem ele o download do
#    Spirit não funciona no exe.
#  - Dados do camoufox / browserforge / apify_fingerprint_datapoints /
#    language_tags: JSON/YAML/DB de fingerprint carregados em tempo de
#    execução; o PyInstaller não os detecta sozinho (não há hooks prontos
#    para esses pacotes no pyinstaller-hooks-contrib).
#  - excludes: só o que nada no app usa de verdade. NÃO adicionar numpy
#    (dependência obrigatória do camoufox) nem PIL (o reportlab 5.x importa
#    Pillow incondicionalmente em reportlab/lib/utils.py).

import os
import re

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
)
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

with open(os.path.join(SPECPATH, 'src', 'version.py'), encoding='utf-8') as f:
    APP_VERSION = re.search(r'"([^"]+)"', f.read()).group(1)

_partes = [int(p) for p in APP_VERSION.split('.')]
VERSAO_TUPLA = tuple((_partes + [0, 0, 0, 0])[:4])

versao_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=VERSAO_TUPLA,
        prodvers=VERSAO_TUPLA,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo([
            StringTable('041604B0', [
                StringStruct('ProductName', 'Fanfic Downloader'),
                StringStruct('FileDescription', 'Fanfic Downloader — baixador de fanfics acessível'),
                StringStruct('FileVersion', APP_VERSION),
                StringStruct('ProductVersion', APP_VERSION),
                StringStruct('InternalName', 'FanficDownloader'),
                StringStruct('OriginalFilename', 'FanficDownloader.exe'),
                StringStruct('LegalCopyright', 'Equipe Fanfic Downloader — licença GPL',),
            ]),
        ]),
        VarFileInfo([VarStruct('Translation', [1046, 1200])]),
    ],
)

playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all('playwright')

datas = [
    *playwright_datas,
    *collect_data_files('camoufox'),
    *collect_data_files('browserforge'),
    *collect_data_files('apify_fingerprint_datapoints'),
    *collect_data_files('language_tags'),
]

hiddenimports = [
    *playwright_hiddenimports,
    # Importados dentro de funções em src/scrapers/spirit.py
    'camoufox.sync_api',
    'camoufox.pkgman',
    'camoufox.multiversion',
    'camoufox.geolocation',
    'truststore',
    # O ua_parser (dependência do camoufox) carrega os matchers sob demanda
    *collect_submodules('ua_parser_builtins'),
]

excludes = [
    'tkinter',
    '_tkinter',
    'PySide6',    # extra "gui" do camoufox, não usado pelo app
    'PyQt5',
    'PyQt6',
    'matplotlib',
    'pandas',
    'scipy',
    'IPython',
    'pytest',
]

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=playwright_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FanficDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=versao_info,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FanficDownloader',
)
