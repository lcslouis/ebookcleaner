# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Collect all data/binaries/hidden imports from key packages
ebooklib_datas, ebooklib_bins, ebooklib_hidden = collect_all('ebooklib')
anthropic_datas, anthropic_bins, anthropic_hidden = collect_all('anthropic')
httpx_datas, httpx_bins, httpx_hidden = collect_all('httpx')
httpcore_datas, httpcore_bins, httpcore_hidden = collect_all('httpcore')
certifi_datas, certifi_bins, certifi_hidden = collect_all('certifi')
requests_datas, requests_bins, requests_hidden = collect_all('requests')
bs4_datas, bs4_bins, bs4_hidden = collect_all('bs4')
lxml_datas, lxml_bins, lxml_hidden = collect_all('lxml')

all_datas = (
    ebooklib_datas + anthropic_datas + httpx_datas +
    httpcore_datas + certifi_datas + requests_datas +
    bs4_datas + lxml_datas +
    [('assets/icon.ico', 'assets'), ('assets/icon_preview.png', 'assets')]
)
all_bins = (
    ebooklib_bins + anthropic_bins + httpx_bins + httpcore_bins +
    certifi_bins + requests_bins + bs4_bins + lxml_bins
)
all_hidden = (
    ebooklib_hidden + anthropic_hidden + httpx_hidden +
    httpcore_hidden + certifi_hidden + requests_hidden +
    bs4_hidden + lxml_hidden + [
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'PySide6.QtSvg',
        'PySide6.QtXml',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebChannel',
        'PySide6.QtNetwork',
        'PySide6.QtPositioning',
        'sqlite3',
        '_sqlite3',
        'difflib',
        'html.parser',
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
        'email',
        'email.mime',
        'email.mime.multipart',
        'email.mime.text',
        'urllib',
        'urllib.request',
        'urllib.parse',
        'anyio',
        'anyio._backends._asyncio',
        'sniffio',
        'h11',
    ]
)

a = Analysis(
    ['main.py'],
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
    name='EbookCleaner',
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
    name='EbookCleaner',
)
