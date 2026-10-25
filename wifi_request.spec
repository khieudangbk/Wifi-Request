# -*- mode: python ; coding: utf-8 -*-
# Windows build: retain EXE version metadata and double-click tray behavior.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

project = Path(SPECPATH)
a = Analysis(
    [str(project / 'src_wifi_request.py')], pathex=[str(project)], binaries=[],
    datas=collect_data_files('customtkinter'),
    hiddenimports=['PIL._tkinter_finder', 'platform_win', 'pystray._win32', 'win32com.client'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['platform_linux'],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='wifi_request', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None, console=False,
    disable_windowed_traceback=False, argv_emulation=False, target_arch=None,
    codesign_identity=None, entitlements_file=None,
    icon=[str(project / 'icon' / 'app.png')],
    version=str(project / 'version_wifi_request.txt'),
)
