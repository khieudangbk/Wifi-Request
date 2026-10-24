"""Linux desktop integration. No GTK import until the tray is requested."""
import atexit
import base64
import fcntl
import json
import logging
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import zlib

_LOCK = None


def _xdg(variable, fallback):
    value = os.environ.get(variable)
    return Path(value) if value and Path(value).is_absolute() else Path.home() / fallback


def check_single_instance():
    global _LOCK
    if _LOCK is not None:
        return True
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    directory = Path(runtime) if runtime and Path(runtime).is_absolute() else _xdg('XDG_CACHE_HOME', '.cache') / 'wifi-request'
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = (directory / 'wifi-request.lock').open('a+')
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        return False
    lock.seek(0)
    lock.truncate()
    lock.write(str(os.getpid()))
    lock.flush()
    _LOCK = lock  # Keep the descriptor alive; do not unlink the lock file.
    atexit.register(lock.close)
    return True


def load_embedded_font():
    import font_base64
    directory = _xdg('XDG_DATA_HOME', '.local/share') / 'fonts' / 'wifi-request'
    data = zlib.decompress(base64.b64decode(font_base64.FONT_JETBRAINS_MONO_BOLD))
    destination = directory / 'JetBrainsMono-Bold.ttf'
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or destination.read_bytes() != data:
            destination.write_bytes(data)
            subprocess.run(['fc-cache', '-f', str(directory)], check=True, timeout=20,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except (OSError, subprocess.SubprocessError) as exc:
        logging.warning('Could not register JetBrains Mono; using font fallback: %s', exc)


def strip_window_buttons(root):
    # Window decorations belong to the compositor, especially under Wayland.
    return None


def get_router_ip(route_file='/proc/net/route'):
    routes = []
    try:
        with open(route_file, encoding='ascii') as stream:
            next(stream, None)
            for line in stream:
                fields = line.split()
                if len(fields) < 8 or fields[1] != '00000000' or fields[7] != '00000000':
                    continue
                try:
                    flags, gateway, metric = int(fields[3], 16), int(fields[2], 16), int(fields[6])
                    if flags & 0x3 == 0x3 and gateway:
                        routes.append((metric, socket.inet_ntoa(struct.pack('<I', gateway))))
                except (ValueError, struct.error, OSError):
                    continue
    except OSError:
        return ''
    return min(routes)[1] if routes else ''


def launch_command():
    if getattr(sys, 'frozen', False):
        return [str(Path(sys.executable).absolute())]
    return [sys.executable, str(Path(__file__).resolve().with_name('src_wifi_request.py'))]


def desktop_exec(arguments):
    # Exec is not a shell command. Escape both argument quoting and desktop-key syntax.
    quoted = []
    for arg in arguments:
        if '\n' in arg or '\r' in arg:
            raise ValueError('Newlines are not allowed in desktop command paths')
        arg = arg.replace('%', '%%')
        for old, new in [('\\', '\\\\'), ('"', '\\"'), ('`', '\\`'), ('$', '\\$')]:
            arg = arg.replace(old, new)
        quoted.append('"' + arg + '"')
    return ' '.join(quoted).replace('\\', '\\\\')


def add_to_startup(app_name='request'):
    command = launch_command()
    directory = _xdg('XDG_CONFIG_HOME', '.config') / 'autostart'
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / 'wifi-request.desktop'
    content = ('[Desktop Entry]\nType=Application\nName=WiFi Request\n'
               'Comment=Keep the dormitory Wi-Fi session connected\n'
               f'Exec={desktop_exec(command)}\n'
               'Icon=wifi-request\nTerminal=false\nX-GNOME-Autostart-enabled=true\n')
    if not destination.exists() or destination.read_text() != content:
        destination.write_text(content, encoding='utf-8')
    return destination


def _indicator_host_available():
    try:
        from gi.repository import Gio, GLib
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = connection.call_sync(
            'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
            'NameHasOwner', GLib.Variant('(s)', ('org.kde.StatusNotifierWatcher',)),
            GLib.VariantType.new('(b)'), Gio.DBusCallFlags.NONE, 1000, None)
        return bool(reply.unpack()[0])
    except Exception:
        return False


def make_tray_icon(name, image, title, callbacks):
    if not _indicator_host_available():
        raise RuntimeError('No AppIndicator host. Enable Ubuntu AppIndicators; using taskbar fallback.')
    # Explicitly avoid pystray's menu-less Xorg backend on GNOME/Wayland.
    os.environ.setdefault('PYSTRAY_BACKEND', 'appindicator')
    import pystray
    menu = pystray.Menu(
        pystray.MenuItem('Show', callbacks['show']),
        pystray.MenuItem(callbacks['pause_label'], callbacks['pause']),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Exit', callbacks['exit']),
    )
    return pystray.Icon(name, image, title, menu)


def _settings_file():
    return _xdg('XDG_CONFIG_HOME', '.config') / 'wifi-request' / 'settings.json'


def get_setting(name):
    try:
        data = json.loads(_settings_file().read_text())
        return data.get(name) if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def save_setting(name, value):
    path = _settings_file()
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data[name] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.chmod(temporary, 0o600)
    temporary.replace(path)
