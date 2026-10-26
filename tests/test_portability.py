import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock

import platform_linux as linux
from ui_dispatch import UiDispatcher
from src_wifi_request import MyApp, plat


class LinuxTests(unittest.TestCase):
    def test_import_does_not_require_windows_modules(self):
        self.assertEqual(plat.__name__, 'platform_linux')
        self.assertNotIn('platform_win', sys.modules)
        self.assertNotIn('winreg', sys.modules)

    def test_missing_indicator_host_preserves_taskbar_access(self):
        with mock.patch.object(linux, '_indicator_host_available', return_value=False):
            with self.assertRaises(RuntimeError):
                linux.make_tray_icon('test', None, 'test', {})
        app = MyApp.__new__(MyApp)
        app.tray_available = False
        app.root = mock.Mock()
        app.on_closing()
        app.root.iconify.assert_called_once()
        app.root.withdraw.assert_not_called()

    def test_gateway_prefers_active_default_route_with_lowest_metric(self):
        with tempfile.TemporaryDirectory() as tmp:
            route = Path(tmp) / 'route'
            route.write_text('Iface Destination Gateway Flags RefCnt Use Metric Mask\n'
                             'wifi 00000000 0101A8C0 0003 0 0 600 00000000\n'
                             'eth0 00000000 0100000A 0003 0 0 100 00000000\n'
                             'bad0 00000000 0100007F 0000 0 0 0 00000000\n'
                             'wifi 0001A8C0 00000000 0001 0 0 0 00FFFFFF\n'
                             'broken\n')
            self.assertEqual(linux.get_router_ip(route), '10.0.0.1')
            route.write_text('Iface Destination Gateway Flags RefCnt Use Metric Mask\n')
            self.assertEqual(linux.get_router_ip(route), '')
            self.assertEqual(linux.get_router_ip(Path(tmp) / 'missing'), '')

    def test_lock_rejects_second_process_and_releases_on_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, XDG_RUNTIME_DIR=tmp)
            owner = subprocess.Popen([sys.executable, '-c',
                "import platform_linux as p; assert p.check_single_instance(); print('locked',flush=True); input()"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=env)
            try:
                self.assertEqual(owner.stdout.readline().strip(), 'locked')
                probe = [sys.executable, '-c',
                         'import platform_linux as p; raise SystemExit(0 if p.check_single_instance() else 2)']
                self.assertEqual(subprocess.run(probe, env=env, timeout=5).returncode, 2)
                owner.communicate('\n', timeout=5)
                self.assertEqual(subprocess.run(probe, env=env, timeout=5).returncode, 0)
            finally:
                if owner.poll() is None:
                    owner.kill()
                    owner.communicate()

    def test_desktop_command_quoting_and_autostart_source_and_frozen(self):
        from gi.repository import GLib
        arguments = ['/tmp/an app/python', '/tmp/a$USER`literal`\\"percent%/main.py']
        keyfile = GLib.KeyFile()
        data = '[Desktop Entry]\nType=Application\nName=Test\nExec='+linux.desktop_exec(arguments)+'\n'
        keyfile.load_from_data(data, len(data.encode()), GLib.KeyFileFlags.NONE)
        command = keyfile.get_string('Desktop Entry', 'Exec')
        ok, parsed = GLib.shell_parse_argv(command)
        self.assertTrue(ok)
        self.assertEqual([x.replace('%%','%') for x in parsed], arguments)
        with self.assertRaises(ValueError):
            linux.desktop_exec(['file\nExec=malicious'])
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, XDG_CONFIG_HOME=tmp):
            target = linux.add_to_startup()
            self.assertIn(sys.executable, target.read_text())
            self.assertIn('src_wifi_request.py', target.read_text())
            first = target.read_text()
            self.assertEqual(linux.add_to_startup().read_text(), first)
            with mock.patch.object(sys, 'frozen', True, create=True), mock.patch.object(sys, 'executable', '/opt/my app/wifi_request'):
                self.assertEqual(linux.launch_command(), ['/opt/my app/wifi_request'])
                self.assertNotIn('src_wifi_request.py', linux.add_to_startup().read_text())

    def test_settings_round_trip_and_corrupt_file_recovery(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, XDG_CONFIG_HOME=tmp):
            self.assertIsNone(linux.get_setting('interval'))
            linux.save_setting('interval', 2)
            linux.save_setting('label', 'Tiếng Việt')
            self.assertEqual(linux.get_setting('interval'), 2)
            self.assertEqual(linux.get_setting('label'), 'Tiếng Việt')
            linux._settings_file().write_text('not json')
            self.assertIsNone(linux.get_setting('interval'))
            linux.save_setting('interval', 4)
            self.assertEqual(linux.get_setting('interval'), 4)
            self.assertEqual(linux._settings_file().stat().st_mode & 0o777, 0o600)


class UiTests(unittest.TestCase):
    def test_workers_never_call_tk_or_widgets(self):
        owner = threading.get_ident()
        root = mock.Mock()
        root.after.side_effect = lambda *args: self.assertEqual(threading.get_ident(), owner) or 'timer'
        ui = UiDispatcher(root)
        seen = []
        def callback(value):
            self.assertEqual(threading.get_ident(), owner)
            seen.append(value)
        worker = threading.Thread(target=lambda: ui.post(callback, 'from worker'))
        worker.start(); worker.join()
        self.assertEqual(seen, [])
        ui.drain()
        self.assertEqual(seen, ['from worker'])
        ui.close()
        ui.post(callback, 'after shutdown')
        self.assertEqual(seen, ['from worker'])

    def test_tray_callbacks_enqueue_ui_actions(self):
        app = MyApp.__new__(MyApp)
        app.ui = mock.Mock()
        app.on_tray_show(None, None)
        app.ui.post.assert_called_with(app.show_window)
        app.on_tray_toggle_pause(None, None)
        app.ui.post.assert_called_with(app.toggle_pause)
        app.on_tray_exit(None, None)
        app.ui.post.assert_called_with(app.end_app)


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.app = MyApp.__new__(MyApp)

    def test_head_probe_and_captive_redirect(self):
        for headers, expected in [({}, True), ({'Location': 'http://router/login?dst=example'}, False),
                                  ({'Location': 'http://router/?DST=example'}, False)]:
            response = mock.MagicMock()
            response.__enter__.return_value = response
            response.headers = headers
            with mock.patch('src_wifi_request.requests.head', return_value=response) as head:
                self.assertEqual(self.app.check_internet(), expected)
                head.assert_called_once_with('http://115.79.4.48/', timeout=1, allow_redirects=False)
                response.__exit__.assert_called_once()
        import requests
        with mock.patch('src_wifi_request.requests.head', side_effect=requests.Timeout):
            self.assertFalse(self.app.check_internet())

    def test_portal_form_flow_and_session_closes(self):
        self.app.display_ip = lambda: '192.168.1.1'
        self.app.login_lock = threading.Lock()
        self.app.closing = False
        html = '<form id="authForm"><input id="client_ip" value="192.168.1.20"><input id="client_mac" value="test-mac"></form>'
        auth = '<form action="http://router/login"><input name="username" value="test-user"><input name="password" value="test-password"></form>'
        session = mock.MagicMock()
        session.get.return_value.text = html
        session.post.side_effect = [mock.Mock(json=lambda: {'captiveContext': {'contentAuthenForm': auth}}),
                                    mock.Mock(status_code=302)]
        context = mock.MagicMock()
        context.__enter__.return_value = session
        with mock.patch('src_wifi_request.requests.Session', return_value=context):
            self.assertTrue(self.app.login(False))
        context.__exit__.assert_called_once()
        self.assertEqual(session.post.call_args.kwargs['data']['username'], 'test-user')
        self.assertEqual(session.post.call_args.kwargs['data']['password'], 'test-password')
        with mock.patch('src_wifi_request.requests.Session', return_value=context):
            session.get.side_effect = OSError('offline')
            self.assertFalse(self.app.login(False))
        self.assertEqual(context.__exit__.call_count, 2)


class WindowsContractTests(unittest.TestCase):
    def load_windows_module(self):
        spec = importlib.util.spec_from_file_location('windows_under_test', Path(__file__).resolve().parents[1] / 'platform_win.py')
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, winreg=mock.Mock()):
            spec.loader.exec_module(module)
        return module

    def test_windows_mutex_keeps_64bit_handle_and_rejects_duplicate(self):
        import ctypes
        win = self.load_windows_module()
        kernel = mock.Mock()
        kernel.CreateMutexW.return_value = 0x100000001
        with mock.patch.object(ctypes, 'WinDLL', return_value=kernel, create=True), \
             mock.patch.object(ctypes, 'get_last_error', return_value=183, create=True), \
             mock.patch.object(win.atexit, 'register'):
            self.assertFalse(win.check_single_instance())
            kernel.CloseHandle.assert_called_with(0x100000001)
        with mock.patch.object(ctypes, 'WinDLL', return_value=kernel, create=True), \
             mock.patch.object(ctypes, 'get_last_error', return_value=0, create=True), \
             mock.patch.object(win.atexit, 'register') as register:
            self.assertTrue(win.check_single_instance())
            self.assertEqual(win._MUTEX, 0x100000001)
            register.assert_called_once_with(kernel.CloseHandle, 0x100000001)

    def test_windows_shortcut_uses_python_for_source_and_exe_for_frozen(self):
        win = self.load_windows_module()
        dispatch = mock.Mock()
        shell = dispatch.return_value
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, APPDATA=tmp), \
             mock.patch.dict(sys.modules, {'win32com': types.ModuleType('win32com'),
                                         'win32com.client': types.SimpleNamespace(Dispatch=dispatch)}):
            win.add_to_startup()
            shortcut = shell.CreateShortcut.return_value
            self.assertEqual(shortcut.TargetPath, sys.executable)
            self.assertIn('src_wifi_request.py', shortcut.Arguments)
            with mock.patch.object(sys, 'frozen', True, create=True), mock.patch.object(sys, 'executable', r'C:\Apps\wifi_request.exe'):
                win.add_to_startup()
                self.assertEqual(shortcut.TargetPath, r'C:\Apps\wifi_request.exe')
                self.assertEqual(shortcut.Arguments, '')

    def test_windows_tray_retains_double_click_behavior(self):
        win = self.load_windows_module()
        class Icon:
            def __init__(self, *args):
                self.messages = []
            def _on_notify(self, wparam, lparam):
                self.messages.append(lparam)
        fake = types.SimpleNamespace(Menu=mock.Mock(), MenuItem=mock.Mock(), _win32=types.SimpleNamespace(Icon=Icon))
        fake.Menu.SEPARATOR = None
        callbacks = {k: mock.Mock() for k in ['toggle','show','pause','pause_label','exit']}
        modules = {'pystray': fake, 'pystray._util': types.SimpleNamespace(win32=types.SimpleNamespace(WM_LBUTTONUP=0x0202))}
        with mock.patch.dict(sys.modules, modules):
            icon = win.make_tray_icon('test', None, 'test', callbacks)
            icon._on_notify(0, 0x0202)
            self.assertEqual(icon.messages, [])
            icon._on_notify(0, 0x0203)
            self.assertEqual(icon.messages, [0x0202])
            icon._on_notify(0, 999)
            self.assertEqual(icon.messages, [0x0202,999])


if __name__ == '__main__':
    unittest.main()
