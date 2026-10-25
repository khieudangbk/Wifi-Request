import os
import logging
import argparse
import json
import re
import sys
import time
import base64
import requests
import datetime
import image_base64
import urllib.parse
from io import BytesIO
from PIL import Image, ImageTk
import customtkinter as ctk
from threading import Thread, Lock, Event
from bs4 import BeautifulSoup


from ui_dispatch import UiDispatcher

if sys.platform == 'win32':
    import platform_win as plat
elif sys.platform.startswith('linux'):
    import platform_linux as plat
else:
    raise RuntimeError('WiFi Request supports Windows and Linux desktops.')


class MyApp:
    def __init__(self, root, *, start_network=True):

        self.version = '1.5.7'

        self.root = root
        self.ui = UiDispatcher(root)
        self.network_enabled = start_network
        self.closing = False
        self.worker_stop = Event()
        self.login_lock = Lock()
        self.tray_available = False

        self.internet_check_interval = 2        #(second), the time between two internet checks or login attempts
        self.login_interval = 600               #(second), time between two logins
        self.never_time = 60 * 60 * 24 * 7      #~1week, never pause relogin
        self.login_retry_duration = self.never_time      #(second), default 'nv'

        self.button_default_text = "Request"
        self.button_spinner_frames = ["Request |", "Request /", "Request -", "Request \\"]
        self.button_spinner_index = 0
        self.button_is_spinning = False
        self.button_spin_job = None

        self.is_internet_connected = False
        self.current_times_error = 0
        self.time_login = None
        self.wait = 0.0

        self.key_internet_check_interval = "internet_check_interval"
        self.key_login_retry_duration = "login_retry_duration"

        self.tray_icon = None
        self.running = True
        self.run_thread = None

        self.load_data()
        self.init_window()
        self.root.bind('<Control-q>', lambda event: self.end_app())


        self.tray_thread = Thread(target=self.create_tray_icon, daemon=True)
        self.tray_thread.start()

        self.start_run_thread()



    def init_window(self):
        self.root.title("WiFi Request " + self.version)
        self.root.geometry("372x146")

        ctk.set_default_color_theme("blue")
        self.root.resizable(False, False)

        self.remove_minimize_maximize()
        self.root._iconbitmap_method_called = True  # Prevents the icon from being overwritten by the default icon
        self.window_icon = ImageTk.PhotoImage(data=base64.b64decode(image_base64.APP_ICON_BASE64))
        self.root.tk.call("wm", "iconphoto", self.root._w, self.window_icon)
        # self.root.attributes("-topmost", True)
        # self.on_closing()

        self.info_frame = ctk.CTkFrame(self.root, border_color="blue",width=250,height=100)
        self.info_frame.place(x=15,y=15)

        self.status_label = ctk.CTkLabel(
            self.info_frame,
            width=150, height=10,
            font=("JetBrains Mono", 14, "bold"),
            justify="left",
            anchor="nw", text="",
            wraplength=380
        )
        self.status_label.grid(row=0, column=0, padx=10, pady=(10, 2), sticky="w")

        self.info_label = ctk.CTkLabel(
            self.info_frame,
            width=150, height=89,
            font=("JetBrains Mono", 14, "bold"),
            justify="left",
            anchor="nw", text="",
            wraplength=380
        )
        self.info_label.grid(row=1, column=0, padx=10, pady=0, sticky="w")



        self.control_frame = ctk.CTkFrame(self.root,width=300,height=50)
        self.control_frame.place(x=200,y=15)

        self.ip_frame = ctk.CTkFrame(self.control_frame, width=300,height=10, fg_color = "#2d7cbb",)
        self.ip_frame.grid(row=0, column=0, padx=7,pady=7, sticky="w")
        self.ip_label = ctk.CTkLabel(
            self.ip_frame,
            width=131, height=13,
            font=("JetBrains Mono", 14, "bold"),
            anchor="center",
            text="0.0.0.0",
            text_color="#dce4e4"
        )
        self.ip_label.grid(row=0, column=0, padx=7,pady=5, sticky="w")


        self.internet_frame = ctk.CTkFrame(self.control_frame, width=300, height=10, fg_color = "#2d7cbb")
        self.internet_frame.grid(row=1, column=0, padx=7, pady=4, sticky="w")
        self.internet_label = ctk.CTkLabel(
            self.internet_frame,
            width=131, height=13,
            font=("JetBrains Mono", 14, "bold"),
            anchor="center",
            text="Internet: ...",
            text_color="#ffffff"
        )
        self.internet_label.grid(row=0, column=0, padx=7, pady=5, sticky="w")


        self.button = ctk.CTkButton(
            self.control_frame,
            width = 146,
            text=self.button_default_text,
            command=self.login_by_button,
            font=("JetBrains Mono", 14, "bold"),
            fg_color = "#2d7cbb"
        )
        self.button.grid(row=2, column=0, padx=7,pady=7, sticky="w")



    def login_by_button(self):
        self.configure_widget(self.status_label, text="Logging in......", text_color = "white")
        self.configure_widget(self.info_label, text="")
        self.update_internet_status(None)
        self.start_button_spinner()
        Thread(target=self.login_by_button_worker, daemon=True).start()
        self.current_times_error = 0
        self.time_login = None
        self.wait = 1.0
        self.running = True
        self.start_run_thread()
        self.refresh_tray_menu()

    def configure_widget(self, widget, **options):
        self.ui.post(widget.configure, **options)

    def login_by_button_worker(self):
        try:
            self.login(is_logout=False)
        finally:
            self.ui.post(self.stop_button_spinner)

    def spin_button(self):
        if not self.button_is_spinning:
            return

        self.configure_widget(self.button, text=self.button_spinner_frames[self.button_spinner_index])
        self.button_spinner_index = (self.button_spinner_index + 1) % len(self.button_spinner_frames)
        self.button_spin_job = self.root.after(120, self.spin_button)

    def start_button_spinner(self):
        if self.button_is_spinning:
            return

        self.button_is_spinning = True
        self.button_spinner_index = 0
        self.configure_widget(self.button, state="disabled")
        self.spin_button()

    def stop_button_spinner(self):
        self.button_is_spinning = False
        if self.button_spin_job is not None:
            self.root.after_cancel(self.button_spin_job)
            self.button_spin_job = None

        self.configure_widget(self.button, text=self.button_default_text, state="normal")


    def display_login_info(self):
        if self.time_login == None:
            return
        self.configure_widget(self.status_label, text="Status: Running", text_color = "green")
        elapsed = int((datetime.datetime.now() - self.time_login).total_seconds())
        self.configure_widget(self.info_label, text = f"TimeLogin: {self.time_login.strftime('%H:%M')}\n"f"TimeUsage: {elapsed//60:02d}:{elapsed%60:02d}")

    def update_internet_status(self, is_connected):
        def _update():
            if is_connected is True:
                self.configure_widget(self.internet_label, text="Internet: YES", text_color="#00ff88")
            elif is_connected is False:
                self.configure_widget(self.internet_label, text="Internet: NO", text_color="#ff6b6b")
            else:
                self.configure_widget(self.internet_label, text="Internet: ...", text_color="#dce4e4")

        try:
            self.ui.post(_update)
        except Exception:
            pass

    def error_login_handle(self):
        self.is_internet_connected = False
        self.update_internet_status(False)
        if self.current_times_error >= int(self.login_retry_duration/self.internet_check_interval):
            self.running = False
            self.configure_widget(self.status_label, text="Status: Pause", text_color = "yellow")
            self.configure_widget(self.info_label, text=f"TimePause: {time.strftime('%H:%M')}")
            self.refresh_tray_menu()
            print("\n-----App paused.-----\n")
            return

        # handle error
        self.current_times_error += 1
        self.configure_widget(self.status_label, text="Status: Error", text_color = "red")
        if self.login_retry_duration == self.never_time:
            self.configure_widget(self.info_label, text=f"Attempt: {self.current_times_error}")
        else:
            self.configure_widget(self.info_label, text=f"Attempt: {self.current_times_error}/{int(self.login_retry_duration/self.internet_check_interval)}")

        self.wait = self.internet_check_interval


    def login_success_but_no_internet_handle(self, is_login_success):
        if is_login_success:
            self.configure_widget(self.status_label, text="Status: Error", text_color = "red")
            self.configure_widget(self.info_label, text="Login success but\nno internet!\nChecking...")
            self.worker_stop.wait(3)

            # check internet again
            attempt = 0
            max_attempts = 15
            while not self.worker_stop.is_set() and attempt < max_attempts and not self.check_internet():
                self.configure_widget(self.info_label, text="Login success but\nno internet!\nChecking...\nAttempt: " + str(attempt + 1) + "/" + str(max_attempts))
                self.worker_stop.wait(0.2)
                attempt += 1

            if self.check_internet():
                self.is_internet_connected = True
                self.update_internet_status(True)
                self.wait = self.internet_check_interval
                return

            self.is_internet_connected = False
            self.update_internet_status(False)
            self.configure_widget(self.status_label, text="Status: Error", text_color = "red")
            self.configure_widget(self.info_label, text="Login success but\nno internet!\nRe-login")

        self.time_login = None

    def run_have_logout(self):
        while self.running and not self.worker_stop.is_set():

            if self.wait > 0:
                if self.is_internet_connected:
                    self.display_login_info()
                self.wait -= 0.5
                self.worker_stop.wait(0.5)
                continue


            is_login_success = False
            if self.time_login == None or (datetime.datetime.now() - self.time_login).total_seconds() >= self.login_interval:
                self.is_internet_connected = False

                if self.login():
                    # successful login
                    is_login_success = True
                    self.time_login = datetime.datetime.now()
                    self.current_times_error = 0

                else:
                    # pause
                    self.error_login_handle()
                    continue

            # check internet
            if not self.check_internet():
                self.is_internet_connected = False
                self.update_internet_status(False)
                self.login_success_but_no_internet_handle(is_login_success)
                continue

            self.is_internet_connected = True
            self.update_internet_status(True)

            self.wait = self.internet_check_interval

    def run_no_logout(self):
        self.display_ip()

        while self.running and not self.worker_stop.is_set():
            if self.wait > 0:
                if self.is_internet_connected:
                    self.display_login_info()
                self.wait -= 0.5
                self.worker_stop.wait(0.5)
                continue

            is_login_success = False
            if not self.check_internet():
                self.is_internet_connected = False
                self.update_internet_status(False)

                if self.login(False):
                    # successful login
                    is_login_success = True
                    self.time_login = datetime.datetime.now()
                    self.current_times_error = 0

                else:
                    # pause
                    self.error_login_handle()
                    continue

                # check internet after login
                if not self.check_internet():
                    self.is_internet_connected = False
                    self.update_internet_status(False)
                    self.login_success_but_no_internet_handle(is_login_success)
                    continue

                self.current_times_error = 0

            self.is_internet_connected = True
            self.update_internet_status(True)
            if self.time_login is None:
                self.time_login = datetime.datetime.now()

            self.wait = self.internet_check_interval

    def run_background(self):
        self.current_times_error = 0
        self.time_login = None
        self.wait = 0.0
        self.is_internet_connected = False

        self.run_no_logout()
        #self.run_have_logout()

    def start_run_thread(self):
        if self.closing or not self.running or not self.network_enabled:
            return
        if self.run_thread is not None and self.run_thread.is_alive():
            if self.worker_stop.is_set():
                self.root.after(100, self.start_run_thread)
            return
        self.worker_stop = Event()
        self.run_thread = Thread(target=self.run_background, daemon=True)
        self.run_thread.start()

    def login(self, is_logout=True):
        # The automatic loop and Request button must not race portal sessions.
        with self.login_lock:
            if self.closing:
                return False
            return self._login(is_logout)

    def _login(self, is_logout=True):
        try:
            ip = self.display_ip()
            if ip == '':
                return False

            if is_logout:
                req = requests.get(f'http://{ip}/logout?', timeout = 2, allow_redirects=False)
                print("Logout: " + str(req.status_code))

        except requests.RequestException as e:
            print(f"Logout Request Exception: {e}")
            return False
        except Exception as e:
            print(f"Logout Exception: {e}")
            return False

        #self.worker_stop.wait(0.5)

        with requests.Session() as session:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            gateway_url = f"http://{ip}/login?r=1" # this ip address doesn't seem to be fixed

            try:
                resp_dummy = session.get(gateway_url, headers=headers, timeout = 2)

                redirect_url = self.process_interstitial_html(resp_dummy.text)
                if not redirect_url:
                    print('\n' + resp_dummy.text)
                    print("---> Không tìm thấy URL Redirect.")
                    return False

                print(redirect_url)

            except Exception as e:
                print(f"[-] Lỗi kết nối Router: {e}")
                return False

            verify_url = "http://v1.awingconnect.vn/Home/VerifyUrl"

            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': redirect_url,
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json'
            })

            try:
                resp_verify = session.post(verify_url, timeout = 2)

                data = None
                try:
                    data = resp_verify.json()
                except Exception as e:
                    print('\n' + resp_verify.text)
                    print(f"JSON Decode Exception: {e}")
                    return False

                html_form = data['captiveContext']['contentAuthenForm']
                real_action_url = re.search(r'action="([^"]+)"', html_form).group(1)
                real_user = re.search(r'name="username" value="([^"]+)"', html_form).group(1)
                real_pass = re.search(r'name="password" value="([^"]+)"', html_form).group(1)

                print(f"Action: {real_action_url}")

                final_payload = {
                    'username': real_user,
                    'password': real_pass,
                    'dst': 'http://v1.awingconnect.vn/Success',
                    'popup': 'false'
                }

                session.headers.update({'Content-Type': 'application/x-www-form-urlencoded'})
                final_resp = session.post(real_action_url, data=final_payload, timeout = 2)

                if final_resp.status_code == 200 or final_resp.status_code == 302:
                    print("[SUCCESS] Đã đăng nhập thành công!: " + str(final_resp.status_code) + "\n")
                    return True

                print('\n' + final_resp.text)
                print(f"[FAIL] Server phản hồi: {final_resp.status_code}\n")
                return False

            except Exception as e:
                print(f"Login Exception: {e}\n")
                return False


    def process_interstitial_html(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        form = soup.find('form', id='authForm')

        if not form:
            print("Lỗi: Không tìm thấy form authForm trong HTML")
            return None

        id_mapping = {
            'serial': 'serial',
            'client_mac': 'client_mac',
            'client_ip': 'client_ip',
            'userurl': 'userurl',
            'login_url': 'login_url',
            'chap-id': 'chap_id',
            'chap-challenge': 'chap_challenge'
        }

        params = {}
        for html_id, url_param_name in id_mapping.items():
            input_tag = form.find('input', id=html_id)
            if input_tag:
                value = input_tag.get('value', '')
                params[url_param_name] = value

        base_url = "http://v1.awingconnect.vn/login"

        query_string = urllib.parse.urlencode(params)
        final_url = f"{base_url}?{query_string}"

        return final_url

    def check_internet(self):
        try:
            with requests.head('http://115.79.4.48/', timeout=1, allow_redirects=False) as response:
                location = response.headers.get('Location', '')
                if 'dst' in location.lower():
                    return False
                # Preserve the original header-based probe on both platforms.
                # A portal response redirects with a dst parameter.
                return 'dst' not in location.lower()
        except requests.RequestException:
            return False

    def display_ip(self):
        ip = self.get_router_ip()
        if ip == '':
            self.configure_widget(self.ip_label, text = '0.0.0.0')
            return ''

        self.configure_widget(self.ip_label, text = ip)
        return ip

    def get_router_ip(self):
        return plat.get_router_ip()

    def create_tray_icon(self):
        try:
            image = self.get_pil_image_from_base64(image_base64.APP_ICON_BASE64)
            if image is None:
                raise RuntimeError('Invalid embedded tray icon')
            self.tray_icon = plat.make_tray_icon(
                'wifi_request', image, f'WiFi Request {self.version}',
                {'show': self.on_tray_show, 'toggle': self.on_tray_toggle_window,
                 'pause': self.on_tray_toggle_pause, 'pause_label': self.get_pause_menu_label,
                 'exit': self.on_tray_exit})
            self.tray_available = True
            if self.closing:
                return
            self.tray_icon.run()
        except Exception:
            logging.exception('Tray unavailable; keep the application accessible in the taskbar')
            self.tray_available = False
            self.ui.post(self.show_window)

    def on_tray_show(self, icon, item):
        self.ui.post(self.show_window)

    def on_tray_toggle_window(self, icon, item):
        self.ui.post(self.toggle_window_visibility)

    def toggle_window_visibility(self):
        if self.root.winfo_viewable():
            self.on_closing()
        else:
            self.show_window()

    def on_tray_toggle_pause(self, icon, item):
        self.ui.post(self.toggle_pause)

    def toggle_pause(self):
        if self.running:
            self.pause_app()
        else:
            self.resume_app()

    def get_pause_menu_label(self, item):
        if self.running:
            return 'Pause'
        return 'Resume'

    def refresh_tray_menu(self):
        if self.tray_icon is not None:
            try:
                self.tray_icon.update_menu()
            except Exception:
                pass

    def on_tray_exit(self, icon, item):
        self.ui.post(self.end_app)

    def pause_app(self):
        self.running = False
        self.wait = 0

        self.worker_stop.set()

        self.refresh_tray_menu()
        self.ui.post(lambda: self.configure_widget(self.status_label, text="Status: Pause", text_color="yellow"))
        self.ui.post(lambda: self.configure_widget(self.info_label, text=f"TimePause: {time.strftime('%H:%M')}"))
        self.update_internet_status(None)

    def resume_app(self):
        self.running = True
        self.time_login = None
        self.current_times_error = 0
        self.wait = 0
        self.start_run_thread()
        self.refresh_tray_menu()
        self.update_internet_status(None)
        self.ui.post(lambda: self.configure_widget(self.status_label, text="Status: Running", text_color="green"))
        self.ui.post(lambda: self.configure_widget(self.info_label, text="Resuming..."))

    def remove_minimize_maximize(self):
        plat.strip_window_buttons(self.root)

    def show_window(self):
        if not self.closing:
            self.root.deiconify()
            self.root.lift()

    def on_closing(self):
        if self.tray_available:
            self.root.withdraw()
        else:
            self.root.iconify()

    def end_app(self):
        if self.closing:
            return
        self.closing = True
        self.running = False
        self.worker_stop.set()
        self.stop_button_spinner()
        self.ui.close()
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                logging.exception('Could not stop tray icon')
        self.root.destroy()

    def load_data(self):
        # Mặc định: internet_check_interval = 2s, login_retry_duration = never_time (nv)
        pass

    def save_winreg_variables(self, name, value):
        # Kept as compatibility wrappers; Linux delegates to XDG JSON settings.
        plat.save_setting(name, value)

    def get_winreg_variables(self, name):
        return plat.get_setting(name)

    def get_pil_image_from_base64(self, data_base64):
        try:
            image_data = base64.b64decode(data_base64)
            return Image.open(BytesIO(image_data)).convert("RGBA")
        except Exception:
            return None


def main():
    parser = argparse.ArgumentParser(description='WiFi Request for Windows and Linux desktops')
    parser.add_argument('--smoke-test', action='store_true',
                        help='Check GUI/font/tray and exit; no network or autostart changes')
    args = parser.parse_args()
    if not plat.check_single_instance():
        from tkinter import messagebox
        try:
            messagebox.showinfo('WiFi Request', 'Ứng dụng đang chạy. Mở lại từ khay hệ thống hoặc thanh tác vụ.')
        except Exception:
            print('WiFi Request is already running.', file=sys.stderr)
        return 0
    plat.load_embedded_font()
    root = ctk.CTk(className='WiFiRequest')
    app = MyApp(root, start_network=not args.smoke_test)
    root.protocol('WM_DELETE_WINDOW', app.on_closing)
    result = {'ok': True}
    if args.smoke_test:
        def finish_smoke():
            import tkinter.font
            try:
                checks = {
                    'font': 'JetBrains Mono' in tkinter.font.families(root),
                    'tray': app.tray_available and bool(app.tray_icon.visible),
                    'window': root.winfo_exists() == 1,
                    'network_disabled': not app.network_enabled,
                }
                app.on_closing()
                checks['hide_to_tray'] = root.state() == 'withdrawn'
                app.show_window()
                checks['show'] = root.state() == 'normal'
                app.pause_app()
                checks['pause'] = not app.running
                app.resume_app()
                checks['resume'] = app.running
                result['ok'] = all(checks.values())
                print(json.dumps({'ok': result['ok'], 'checks': checks}), flush=True)
            except Exception:
                result['ok'] = False
                logging.exception('Desktop smoke test failed')
            finally:
                app.end_app()
        root.after(2000, finish_smoke)
    else:
        try:
            plat.add_to_startup()
        except Exception:
            logging.exception('Could not register autostart; app will continue for this session')
    root.mainloop()
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
