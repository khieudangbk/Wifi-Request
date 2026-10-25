# -*- mode: python ; coding: utf-8 -*-
# Build on Linux, not with Windows cross-compilation.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

project = Path(SPECPATH)
a = Analysis(
    [str(project / 'src_wifi_request.py')],
    pathex=[str(project)],
    binaries=[],
    datas=collect_data_files('customtkinter') + [(str(project / 'icon' / 'app.png'), 'icon')],
    hiddenimports=['PIL._tkinter_finder', 'platform_linux', 'pystray._appindicator', 'gi.repository.Gtk',
                   'gi.repository.Gdk', 'gi.repository.Gio', 'gi.repository.GLib', 'gi.repository.AyatanaAppIndicator3'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['platform_win', 'winreg', 'win32com', 'pythoncom', 'pywintypes', 'netifaces'],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='wifi_request', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, upx_exclude=[], runtime_tmpdir=None, console=True,
    disable_windowed_traceback=False,
)
