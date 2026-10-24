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
        if not self.running:
            return

        if self.run_thread is not None and self.run_thread.is_alive():
            return

        self.run_thread = Thread(target=self.run_background, daemon=True)
        self.run_thread.start()

    def login(self, is_logout=True):
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
        
        #time.sleep(0.5)
        
        session = requests.Session()
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
            
            print(f"User: {real_user}")
            print(f"Pass: {real_pass}")
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

    # def check_internet(self):
    #     try:
    #         result = subprocess.run(['ping', '-n', '1', '-l', '1', '203.162.4.191'],timeout = 1, 
    #                                 stdout = subprocess.PIPE,
    #                                 stderr = subprocess.PIPE, 
    #                                 creationflags = subprocess.CREATE_NO_WINDOW).stdout.decode('utf-8')
    #     except subprocess.TimeoutExpired:
    #         print("Ping Timeout")
    #         return False
        
    #     if 'time' in result:
    #         return True
    #     return False
    
    def check_internet(self):
        try:
            result = subprocess.run(['curl', '-I', 'http://115.79.4.48/'],timeout = 1, 
                                    stdout = subprocess.PIPE,
                                    stderr = subprocess.PIPE, 
                                    creationflags = subprocess.CREATE_NO_WINDOW).stdout.decode('utf-8')
        except subprocess.TimeoutExpired:
            print("Curl Timeout")
            return False
        
        #print(result)
        
        if result == "":
            return False
    
        if 'dst' in result:
            return False
        return True
    
    def display_ip(self):
        ip = self.get_router_ip()
        if ip == '':
            self.ip_label.configure(text = '0.0.0.0')
            return ''
        
        self.ip_label.configure(text = ip)
        return ip

    def get_router_ip(self):
        router_ip = ''
        gateways = netifaces.gateways()
        default_gateway = gateways.get('default')
        if default_gateway and netifaces.AF_INET in default_gateway:
            router_ip = default_gateway[netifaces.AF_INET][0]
        return router_ip

    def create_tray_icon(self):
        tray_image = self.get_pil_image_from_base64(image_base64.APP_ICON_BASE64)
        if tray_image is None:
            return

        menu = pystray.Menu(
            pystray.MenuItem('Toggle window', self.on_tray_toggle_window, default=True, visible=False),
            pystray.MenuItem('Show', self.on_tray_show),
            pystray.MenuItem(self.get_pause_menu_label, self.on_tray_toggle_pause),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Exit', self.on_tray_exit)
        )

        self.tray_icon = DoubleClickWin32Icon("wifi_request", tray_image, f"WiFi Request {self.version}", menu)
        self.tray_icon.run()

    def on_tray_show(self, icon, item):
        self.root.after(0, self.show_window)

    def on_tray_toggle_window(self, icon, item):
        self.root.after(0, self.toggle_window_visibility)

    def toggle_window_visibility(self):
        if self.root.winfo_viewable():
            self.on_closing()
        else:
            self.show_window()

    def on_tray_toggle_pause(self, icon, item):
        if self.running:
            self.pause_app()
        else:
            self.resume_app()

        self.refresh_tray_menu()

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
        self.end_app()

    def pause_app(self):
        self.running = False
        self.wait = 0

        if self.run_thread is not None and self.run_thread.is_alive() and self.run_thread != current_thread():
            self.run_thread.join(timeout=3)

        self.refresh_tray_menu()
        self.root.after(0, lambda: self.status_label.configure(text="Status: Pause", text_color="yellow"))
        self.root.after(0, lambda: self.info_label.configure(text=f"TimePause: {time.strftime('%H:%M')}"))
        self.update_internet_status(None)

    def resume_app(self):
        self.running = True
        self.time_login = None
        self.current_times_error = 0
        self.wait = 0
        self.start_run_thread()
        self.refresh_tray_menu()
        self.update_internet_status(None)
        self.root.after(0, lambda: self.status_label.configure(text="Status: Running", text_color="green"))
        self.root.after(0, lambda: self.info_label.configure(text="Resuming..."))

    def remove_minimize_maximize(self):
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
        style = style & ~0x00020000  # WS_MINIMIZEBOX
        style = style & ~0x00010000  # WS_MAXIMIZEBOX
        ctypes.windll.user32.SetWindowLongW(hwnd, -16, style)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0020 | 0x0004)

    def show_window(self):
        self.root.deiconify()
    def on_closing(self):
        self.root.withdraw()
    def end_app(self):
        self.running = False

        try:
            self.root.after(0, self.on_closing)
        except Exception:
            pass

        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

        if self.run_thread is not None and self.run_thread.is_alive() and self.run_thread != current_thread():
            self.run_thread.join(timeout=2)

        try:
            self.root.after(0, self.root.quit)
        except Exception:
            pass
        

    def load_data(self):
        # Mặc định: internet_check_interval = 2s, login_retry_duration = never_time (nv)
        pass

    def save_winreg_variables(self, name, value):
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\WiFiRequest")
        if type(value) is str:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        else:
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)

    def get_winreg_variables(self, name):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\WiFiRequest")
            value = winreg.QueryValueEx(key, name)[0]
            winreg.CloseKey(key)
            return value
        except FileNotFoundError:
            return None
    
    
    def get_pil_image_from_base64(self, data_base64):
        try:
            image_data = base64.b64decode(data_base64)
            return Image.open(BytesIO(image_data)).convert("RGBA")
        except Exception:
            return None
        

def add_to_startup_folder(app_name="request"):
    try:
        file_path = os.path.abspath(sys.argv[0])
        file_path = file_path[0].upper() + file_path[1:]
        startup_folder = os.path.join(
            os.getenv('APPDATA'),
            r"Microsoft\Windows\Start Menu\Programs\Startup"
        )

        shortcut_path = os.path.join(startup_folder, f"{app_name}.lnk")
        shell = Dispatch('WScript.Shell')

        if os.path.exists(shortcut_path):
            shortcut = shell.CreateShortcut(shortcut_path)
            if shortcut.TargetPath != file_path:
                print(shortcut.TargetPath)
                print(file_path)
                shortcut.TargetPath = file_path
                shortcut.WorkingDirectory = os.path.dirname(file_path)
                shortcut.Save()

        else:
            shortcut = shell.CreateShortcut(shortcut_path)
            shortcut.TargetPath = file_path
            shortcut.WorkingDirectory = os.path.dirname(file_path)
            shortcut.Save()

    except Exception as e:
        pass

def load_embedded_font():
    try:
        temp_dir = os.path.join(tempfile.gettempdir(), "WiFiRequestFont")
        os.makedirs(temp_dir, exist_ok=True)
        font_path = os.path.join(temp_dir, "JetBrainsMono-Bold.ttf")

        if not os.path.exists(font_path) or os.path.getsize(font_path) == 0:
            font_data = zlib.decompress(base64.b64decode(font_base64.FONT_JETBRAINS_MONO_BOLD))
            with open(font_path, "wb") as f:
                f.write(font_data)

        # 0x10 = FR_PRIVATE: Nạp font riêng cho tiến trình này, tự giải phóng khi tắt app
        ctypes.windll.gdi32.AddFontResourceExW(font_path, 0x10, 0)
    except Exception as e:
        print(f"Font loading error: {e}")


def check_single_instance():
    ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\RequestAppMutex")
    if ctypes.GetLastError() == 183:
        # MB_OK (0x0) | MB_ICONINFORMATION (0x40) | MB_TOPMOST (0x40000)
        ctypes.windll.user32.MessageBoxW(
            None,
            "Ứng dụng đang chạy nền. Vui lòng nhấp vào icon ở khay hệ thống để mở lại.",
            "WiFi Request",
            0x00000040 | 0x00040000
        )
        sys.exit(0)


if __name__ == "__main__":
    check_single_instance()
    load_embedded_font()
    
    root = ctk.CTk()
    app = MyApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    add_to_startup_folder()
    root.mainloop()
