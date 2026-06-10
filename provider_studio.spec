# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

block_cipher = None

requests_datas, requests_bins, requests_hidden = collect_all('requests')
bs4_datas,      bs4_bins,      bs4_hidden      = collect_all('bs4')
lxml_datas,     lxml_bins,     lxml_hidden     = collect_all('lxml')
certifi_datas,  certifi_bins,  certifi_hidden  = collect_all('certifi')

all_datas = (
    requests_datas + bs4_datas + lxml_datas + certifi_datas +
    [('assets/icon.ico', 'assets')]
)
all_bins = requests_bins + bs4_bins + lxml_bins + certifi_bins

all_hidden = (
    requests_hidden + bs4_hidden + lxml_hidden + certifi_hidden + [
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'PySide6.QtSvg',
        'PySide6.QtXml',
        'PySide6.QtNetwork',
        'lxml',
        'lxml.etree',
        'lxml._elementpath',
        'lxml.html',
        'bs4',
        'bs4.builder._lxml',
        'bs4.builder._htmlparser',
        'requests',
        'urllib3',
        'charset_normalizer',
        'idna',
        'urllib',
        'urllib.request',
        'urllib.parse',
    ]
)

a = Analysis(
    ['provider_studio/main.py'],
    pathex=['.'],
    binaries=all_bins,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'pandas',
        'scipy', 'PIL', 'cv2', 'IPython', 'jupyter',
        'PyQt5', 'PyQt6', 'wx',
        'anthropic', 'httpx', 'httpcore', 'ebooklib',
        'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineCore',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ProviderStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='assets/icon.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'python*.dll', 'Qt*.dll'],
    name='ProviderStudio',
)
