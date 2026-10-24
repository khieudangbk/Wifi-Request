# Plan chuyển WiFi Request sang Ubuntu 26.04

26/10/2026 · khanh

## Tóm tắt

Phần lõi đăng nhập (requests + BeautifulSoup gọi router và Awing) chạy được trên Linux nguyên vẹn. Thứ chặn là khoảng 8 chỗ gọi API Windows: hiện tại `src_wifi_request.py` sẽ crash ngay dòng `import winreg` trên Ubuntu.

Hướng đề xuất: giữ **một codebase chạy cả hai OS**, tách phần phụ thuộc hệ điều hành ra `platform_win.py` và `platform_linux.py`, chọn theo `sys.platform`. Bản Windows không đổi hành vi. Ước lượng 1–2 buổi code, cộng 1 buổi thử thật trên máy Ubuntu 26.04 ở KTX (bắt buộc, vì captive portal chỉ test được tại chỗ).

Giả định: Ubuntu 26.04 Desktop bản gốc (GNOME, phiên Wayland, Python 3.14 hệ thống). Nếu bạn dùng bản khác (Kubuntu, Xubuntu) thì phần khay hệ thống sẽ dễ hơn.

## Những chỗ phụ thuộc Windows

Mỗi dòng dưới đây là một chỗ trong `src_wifi_request.py` sẽ lỗi hoặc vô tác dụng trên Ubuntu, kèm cách thay.

| Chức năng | Code hiện tại (Windows) | Thay trên Ubuntu |
| --- | --- | --- |
| Chạy một phiên bản | `CreateMutexW` + `MessageBoxW` qua `ctypes.windll` | `fcntl.flock` trên file khóa trong `$XDG_RUNTIME_DIR`; thông báo bằng `tkinter.messagebox` |
| Nạp font JetBrains Mono | `gdi32.AddFontResourceExW` | Ghi TTF vào `~/.local/share/fonts/` rồi chạy `fc-cache -f` trước khi tạo cửa sổ Tk (hoặc dùng gói `tkextrafont`) |
| Ẩn nút thu nhỏ/phóng to | `user32.SetWindowLongW` | Bỏ qua trên Linux; giữ `resizable(False, False)`. Wayland không cho ứng dụng chỉnh viền cửa sổ |
| Icon khay hệ thống | `pystray._win32.Icon` subclass bắt double-click | `pystray.Icon` thường, backend `appindicator`. Double-click không có trên AppIndicator, nên mục "Show" thành mục đầu menu |
| Kiểm tra Internet | `subprocess.run(['curl', ...], creationflags=CREATE_NO_WINDOW)` | `creationflags` gây `AttributeError` trên Linux. Thay bằng `requests.head('http://115.79.4.48/', timeout=1, allow_redirects=False)` và kiểm tra `dst` trong header `Location`; bỏ phụ thuộc curl |
| Lấy gateway | `netifaces.gateways()` | `netifaces` đã ngừng bảo trì từ 2021, không có wheel cho Python 3.14 nên `pip install` phải biên dịch C. Thay bằng hàm đọc `/proc/net/route` (khoảng 10 dòng), Windows giữ netifaces hoặc chuyển sang `netifaces-plus` |
| Tự khởi động cùng máy | Shortcut `.lnk` qua `win32com` vào thư mục Startup | File `~/.config/autostart/wifi-request.desktop` (chuẩn XDG, GNOME tự đọc) |
| Lưu cài đặt | `winreg` (`HKCU\Software\WiFiRequest`) | Hiện chưa được gọi (`load_data` rỗng). Nếu cần: JSON trong `~/.config/wifi-request/` |
| Đóng gói | `wifi_request.spec` dùng `icon\app.png` và file version Windows | Spec riêng cho Linux, không có `icon`/`version`; ra file ELF `dist/wifi_request` |

Ngoài ra có một lỗi sẵn có sẽ lộ rõ hơn trên Linux: luồng nền gọi thẳng `label.configure(...)` thay vì qua `root.after`. Tk trên Linux dễ báo `main thread is not in main loop` hoặc treo hơn Windows, nên nên gom mọi cập nhật giao diện về `root.after(0, ...)`.

## Các bước thực hiện

1. **Chuẩn bị máy Ubuntu 26.04.** Cài gói hệ thống:
    - `sudo apt install python3-venv python3-tk python3-gi gir1.2-ayatanaappindicator3-0.1 fontconfig`
    - Kiểm tra extension "Ubuntu AppIndicators" đang bật (mặc định có trên Ubuntu), nếu không icon khay sẽ không hiện.
2. **Tạo venv.** Ubuntu chặn `pip install` vào Python hệ thống (PEP 668), nên dùng `python3 -m venv --system-site-packages .venv` để venv thấy được `python3-gi` mà pystray cần.
3. **Tách requirements.** Dùng environment marker để một file dùng chung: `pywin32; sys_platform == "win32"`, `netifaces; sys_platform == "win32"`. Trên Linux chỉ còn `beautifulsoup4 customtkinter Pillow pystray requests`.
4. **Tách lớp nền tảng.** Tạo `platform_win.py` (chuyển nguyên code hiện tại sang) và `platform_linux.py`, cùng các hàm: `check_single_instance()`, `load_embedded_font()`, `add_to_startup()`, `get_router_ip()`, `strip_window_buttons(root)`, `make_tray_icon(...)`. File chính chỉ còn `import platform_win as plat` hoặc `platform_linux` theo `sys.platform`, và bỏ các import `winreg`, `ctypes.windll`, `win32com`, `pystray._win32` ở đầu file.
5. **Viết phần Linux** theo bảng ở trên: khóa file, font vào `~/.local/share/fonts`, file autostart `.desktop`, đọc `/proc/net/route`, tray qua pystray mặc định.
6. **Sửa `check_internet` dùng chung** bằng `requests.head` cho cả hai OS, bỏ curl và `creationflags`.
7. **Gom cập nhật giao diện về luồng chính**: mọi `status_label/info_label/ip_label.configure` từ luồng nền đi qua `root.after(0, ...)`.
8. **Đóng gói Linux.** Thêm `wifi_request_linux.spec` (không `icon`, không `version`, `upx=False`), build bằng `python -m PyInstaller wifi_request_linux.spec` ngay trên Ubuntu 26.04 (PyInstaller không build chéo từ Windows). Kèm file `wifi-request.desktop` và `icon/app.png` để hiện trong menu ứng dụng.
9. **Cập nhật README**: thêm badge Linux, mục cài đặt Ubuntu (lệnh apt, venv, chạy, build), bảng cấu trúc thư mục mới.

## Kiểm thử và rủi ro

Kiểm thử trên máy Ubuntu 26.04 thật, nối `INET - Free WiFi` tại KTX:

- [ ] App mở được, font JetBrains Mono hiển thị đúng, icon cửa sổ đúng
- [ ] Icon khay hiện trên thanh GNOME; menu Show / Pause-Resume / Exit hoạt động
- [ ] Mở lần hai thì báo đang chạy và thoát
- [ ] IP gateway hiện đúng (so với `ip route`)
- [ ] Tự đăng nhập khi phiên 15 phút hết hạn, chạy liên tục ít nhất 1 giờ không crash
- [ ] Khởi động lại máy thì app tự chạy
- [ ] Bản build PyInstaller chạy được trên máy Ubuntu sạch (không có venv)
- [ ] Bản Windows vẫn chạy như cũ sau khi tách code

Rủi ro cần biết:

- **Khay hệ thống trên GNOME** phụ thuộc extension AppIndicator. Nếu pystray lỗi khi chạy chung với Tk, phương án dự phòng là bỏ tray trên Linux và cho nút đóng cửa sổ thu nhỏ xuống taskbar.
- **GNOME tự mở trang captive portal**: NetworkManager kiểm tra kết nối và có thể bật cửa sổ đăng nhập mỗi 15 phút. Có thể tắt trong Settings → Privacy → Connectivity Checking.
- **MAC ngẫu nhiên**: nếu bật MAC ngẫu nhiên cho mạng Wi-Fi này, portal có thể coi mỗi lần nối là máy mới. Nên đặt "Permanent" trong cài đặt Wi-Fi.
- **Wayland**: Tk chạy qua XWayland nên ổn, nhưng trên màn hình HiDPI cửa sổ 372x146 có thể bị nhỏ hoặc cắt chữ; cần thử scale 100% và 200%.
