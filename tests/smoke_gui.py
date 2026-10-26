"""Run under xvfb-run: real Tk and AppIndicator, mocked network, no autostart."""
import os
from pathlib import Path
import sys
import threading
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import customtkinter as ctk
import tkinter.font
from src_wifi_request import MyApp, plat

plat.load_embedded_font()
scale = float(os.environ.get('WIFI_SMOKE_SCALE', '1'))
ctk.set_widget_scaling(scale)
ctk.set_window_scaling(scale)
root = ctk.CTk()
failures = []
root.report_callback_exception = lambda *args: failures.append(args)
# No traffic to a live router or captive portal during this smoke test.
with mock.patch.object(MyApp, 'check_internet', return_value=True):
    app = MyApp(root)
    root.protocol('WM_DELETE_WINDOW', app.on_closing)
    def pause_resume():
        app.pause_app()
        root.after(200, app.resume_app)
    def check():
        try:
            assert 'JetBrains Mono' in tkinter.font.families(root), 'Embedded font not available'
            assert root.winfo_exists()
            for widget in [app.button, app.status_label, app.info_label, app.internet_label, app.ip_label]:
                assert widget.winfo_rootx() >= root.winfo_rootx()
                assert widget.winfo_rooty() >= root.winfo_rooty()
                assert widget.winfo_rootx()+widget.winfo_width() <= root.winfo_rootx()+root.winfo_width(), 'Widget clipped horizontally'
                assert widget.winfo_rooty()+widget.winfo_height() <= root.winfo_rooty()+root.winfo_height(), 'Widget clipped vertically'
            assert app.tray_available, 'AppIndicator tray failed'
            assert app.run_thread and app.run_thread.is_alive()
            assert app.ip_label.cget('text') == (plat.get_router_ip() or '0.0.0.0')
            app.on_closing()
            assert root.state() == 'withdrawn'
            app.show_window()
            assert root.state() == 'normal'
            app.on_tray_toggle_pause(None, None)
            assert not app.running
            app.on_tray_toggle_pause(None, None)
            assert app.running
        except BaseException as exc:
            failures.append(exc)
        finally:
            def capture_and_exit():
                if os.environ.get('WIFI_SMOKE_CAPTURE'):
                    from PIL import ImageGrab
                    x,y=root.winfo_rootx(),root.winfo_rooty()
                    ImageGrab.grab((x,y,x+root.winfo_width(),y+root.winfo_height())).save(os.environ['WIFI_SMOKE_CAPTURE'])
                app.end_app()
            root.after(600, capture_and_exit)
    root.after(500, pause_resume)
    root.after(1800, check)
    root.mainloop()
assert not failures, failures
print('GUI smoke passed: Tk, embedded font, AppIndicator, show/hide, pause/resume, shutdown.')
