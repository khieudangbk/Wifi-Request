"""Windows integration, imported only on Windows."""
import atexit
import base64
import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import winreg
import zlib

_MUTEX = None


def check_single_instance():
    global _MUTEX
    if _MUTEX is not None:
        return True
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateMutexW(None, False, 'Global\\RequestAppMutex')
    error = ctypes.get_last_error()
    if not handle:
        raise ctypes.WinError(error)
    if error == 183:
        kernel.CloseHandle(handle)
        return False
    _MUTEX = handle
    atexit.register(kernel.CloseHandle, handle)
    return True


def load_embedded_font():
    import font_base64
    try:
        directory = Path(tempfile.gettempdir()) / 'WiFiRequestFont'
        directory.mkdir(exist_ok=True)
        path = directory / 'JetBrainsMono-Bold.ttf'
        if not path.exists() or path.stat().st_size == 0:
            path.write_bytes(zlib.decompress(base64.b64decode(font_base64.FONT_JETBRAINS_MONO_BOLD)))
        ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, 0)
    except OSError as exc:
        logging.warning('Could not load embedded font: %s', exc)


def strip_window_buttons(root):
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
    ctypes.windll.user32.SetWindowLongW(hwnd, -16, style & ~0x00020000 & ~0x00010000)
    ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0020 | 0x0004)


def get_router_ip():
    import netifaces
    try:
        default = netifaces.gateways().get('default', {})
        return default.get(netifaces.AF_INET, ('',))[0]
    except (OSError, ValueError):
        return ''


def add_to_startup(app_name='request'):
    from win32com.client import Dispatch
    frozen = getattr(sys, 'frozen', False)
    target = sys.executable
    script = str(Path(__file__).resolve().with_name('src_wifi_request.py'))
    folder = Path(os.environ['APPDATA']) / r'Microsoft\Windows\Start Menu\Programs\Startup'
    folder.mkdir(parents=True, exist_ok=True)
    shortcut = Dispatch('WScript.Shell').CreateShortcut(str(folder / (app_name + '.lnk')))
    shortcut.TargetPath = target
    shortcut.Arguments = '' if frozen else subprocess.list2cmdline([script])
    shortcut.WorkingDirectory = str(Path(target if frozen else script).parent)
    shortcut.Save()


def make_tray_icon(name, image, title, callbacks):
    import pystray
    from pystray import _win32
    from pystray._util import win32

    class DoubleClickWin32Icon(_win32.Icon):
        def _on_notify(self, wparam, lparam):
            if lparam == 0x0203:
                return super()._on_notify(wparam, win32.WM_LBUTTONUP)
            if lparam != win32.WM_LBUTTONUP:
                return super()._on_notify(wparam, lparam)

    menu = pystray.Menu(
        pystray.MenuItem('Toggle window', callbacks['toggle'], default=True, visible=False),
        pystray.MenuItem('Show', callbacks['show']),
        pystray.MenuItem(callbacks['pause_label'], callbacks['pause']),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Exit', callbacks['exit']),
    )
    return DoubleClickWin32Icon(name, image, title, menu)


def save_setting(name, value):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\WiFiRequest') as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ if isinstance(value, str) else winreg.REG_DWORD, value)


def get_setting(name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\WiFiRequest') as key:
            return winreg.QueryValueEx(key, name)[0]
    except FileNotFoundError:
        return None
