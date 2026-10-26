# WiFi Request

<p align="center"><img src="icon/app.png" alt="WiFi Request" width="96"></p>

Công cụ tự đăng nhập mạng **INET - Free WiFi tại KTX Khu A ĐHQG-HCM**, giữ kết nối khi phiên captive portal Awing hết hạn. Giao diện dùng CustomTkinter; có nút Request và menu khay Show / Pause–Resume / Exit.

![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-blue)
![Linux](https://img.shields.io/badge/Linux-Ubuntu%2026.04-orange)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)

Một bộ mã nguồn dùng cho Windows và Linux. Bản port đã build và kiểm thử trên **Ubuntu 26.04 Desktop, Python 3.14, GNOME/Wayland (Tk qua XWayland)**. Ubuntu cũ hơn có thể chạy từ nguồn hoặc build tại chỗ nếu có các thư viện bên dưới; chưa coi đó là nền tảng đã được kiểm thử chỉ từ kết quả trên 26.04.

## Trạng thái kiểm chứng

Bản **v1.5.7** đã được kiểm tra ngày **26/10/2026** trên Ubuntu 26.04.1 LTS x86-64, Python 3.14.4:

- Build Linux bằng `bash build_linux.sh`: thành công, tạo `dist/wifi_request` dạng ELF x86-64.
- Unit test bằng `.venv/bin/python -m unittest discover -s tests -v`: **13/13 test passed**.
- GUI/binary smoke test: khởi tạo Tk, font nhúng, AppIndicator, show/hide, pause/resume và shutdown hoạt động.

Các kết quả trên xác nhận build và các luồng tự động trên máy phát triển. Kiểm thử hết phiên captive portal trên mạng KTX, Windows thật và các bản Ubuntu cũ hơn vẫn là các phạm vi riêng trong [TESTING.md](TESTING.md).

## Ubuntu: chạy từ mã nguồn

### 1. Cài thư viện hệ thống

```bash
sudo apt update
sudo apt install python3-venv python3-tk python3-gi gir1.2-ayatanaappindicator3-0.1 fontconfig binutils
```

Ubuntu cần bật extension **Ubuntu AppIndicators** để thấy icon khay. Nếu backend khay không hoạt động, ứng dụng giữ cửa sổ truy cập được; nút đóng thu nhỏ xuống thanh tác vụ thay vì ẩn mất cửa sổ. Có thể thoát bằng mục Exit trong khay hoặc nhấn Ctrl+Q khi cửa sổ đang được chọn.

### 2. Tạo môi trường Python riêng

Tại thư mục dự án:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install --ignore-installed --only-binary=:all: Pillow
```

`--system-site-packages` cho venv sử dụng PyGObject (`gi`) từ gói Ubuntu. Wheel Pillow trong venv cung cấp đủ `ImageTk`; Pillow hệ thống Ubuntu có thể tách phần này sang một gói khác. Không dùng `sudo pip`, không cần `--break-system-packages`.

### 3. Chạy

```bash
.venv/bin/python src_wifi_request.py
```

Khi chạy bình thường, ứng dụng tự đăng ký `~/.config/autostart/wifi-request.desktop` (hoặc `$XDG_CONFIG_HOME/autostart/`), trỏ đúng Python trong venv và đường dẫn mã nguồn. Cần giữ nguyên venv và thư mục dự án để tự chạy sau lần đăng nhập desktop kế tiếp.

Để tắt tự khởi động trên Linux, bỏ mục WiFi Request trong Startup Applications hoặc xóa riêng file autostart đó. Nếu tiếp tục chạy app bình thường, app sẽ tạo lại mục tự khởi động theo hành vi hiện có.

## Ubuntu: build file ELF độc lập

Sau khi cài gói hệ thống, chạy:

```bash
bash build_linux.sh
```

Script tạo venv có quyền đọc `gi` của hệ thống, cài các thư viện, kiểm tra Pillow/ImageTk và chạy:

```bash
.venv/bin/python -m PyInstaller --clean --noconfirm wifi_request_linux.spec
```

Kết quả: **`dist/wifi_request`**, file ELF cho kiến trúc máy đang build. Chạy trực tiếp:

```bash
./dist/wifi_request
```

File này đóng gói Python, dữ liệu CustomTkinter, Pillow/ImageTk, Tk và các thành phần GI/AppIndicator mà hook thu thập. Máy đích vẫn cần môi trường desktop/XWayland, thư viện hệ thống tương thích và AppIndicator host để có menu khay. PyInstaller không build Linux từ Windows.

**Tương thích Ubuntu cũ:** binary build trên 26.04 có thể cần glibc mới hơn máy 22.04/24.04. Muốn phân phối cho bản cũ, hãy build trên phiên bản Linux cũ nhất cần hỗ trợ rồi kiểm thử riêng; không đảm bảo chỉ bằng việc copy binary 26.04 sang máy cũ.

### Cài vào menu ứng dụng cho user hiện tại

```bash
bash install_linux.sh
```

Script cài binary vào `$XDG_DATA_HOME/wifi-request/` (mặc định `~/.local/share/wifi-request/`), tạo launcher trong `~/.local/bin/`, cài icon và file `.desktop` vào menu. Không cần sudo và không tự mở app khi cài. Có thể tìm **WiFi Request** trong danh sách ứng dụng. Cài vào vị trí cố định này trước khi chạy giúp autostart không trỏ vào file build tạm.

## Windows

Bản Windows giữ mutex một phiên bản, font nhúng, shortcut Startup, cửa sổ không resize và double-click icon khay để ẩn/hiện.

### Chạy từ nguồn

Cài Python và tạo venv riêng. Python 3.10 là lựa chọn phù hợp với dependency `netifaces` hiện có; các bản Python mới hơn có thể cần công cụ biên dịch cho dependency Windows này.

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src_wifi_request.py
```

`pywin32` và `netifaces` chỉ cài trên Windows nhờ environment marker trong `requirements.txt`.

### Build EXE trên Windows

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm wifi_request.spec
```

Kết quả: `dist/wifi_request.exe`, giữ icon và version metadata Windows. Không dùng spec Linux để build EXE. Bản phát hành Windows trước đây có thể tải tại [Releases](https://github.com/nndai/wifi-request/releases); bản Linux của thay đổi này cần build từ nguồn cho tới khi có release tương ứng.

## Kiểm thử

Kiểm thử tự động không đăng nhập router hoặc gọi Awing thật:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Kiểm tra Tk, font, AppIndicator, ẩn/hiện, pause/resume và thoát trên màn hình ảo:

```bash
sudo apt install xvfb
xvfb-run -a .venv/bin/python tests/smoke_gui.py
WIFI_SMOKE_SCALE=2 xvfb-run -a .venv/bin/python tests/smoke_gui.py
```

Để khay hoạt động, màn hình ảo vẫn cần truy cập session D-Bus có AppIndicator host. Bài smoke chủ động kiểm tra cả khay; nếu môi trường CI không có host, chạy unit test và kiểm tra fallback thay vì coi khay đã được xác minh.

Kiểm tra chính binary sau khi build:

```bash
./dist/wifi_request --smoke-test
```

Chế độ này mở giao diện, kiểm tra font/khay/ẩn-hiện/pause-resume, in kết quả JSON và thoát. Nó **không gọi mạng và không ghi autostart**. Cần chạy trong desktop có khay đang hoạt động. Chạy không có `--smoke-test` mới thực hiện chức năng tự đăng nhập và đăng ký autostart.

Các bước cần thử thật tại KTX và trên Windows được ghi trong [TESTING.md](TESTING.md). Xvfb và mock HTTP không thay cho kiểm thử hết phiên 15 phút trên mạng KTX.

## Cấu trúc mã nguồn

```text
src_wifi_request.py        # UI, điều phối và luồng HTTP router/Awing dùng chung
platform_win.py           # Mutex, font Win32, gateway, registry, Startup, tray double-click
platform_linux.py         # flock, fontconfig, /proc/net/route, XDG, AppIndicator
ui_dispatch.py            # Queue callback; chỉ luồng chính gọi Tcl/Tk
requirements.txt          # Dependency dùng chung, marker Windows
wifi_request.spec         # Build Windows EXE
wifi_request_linux.spec   # Build Linux ELF, không Windows icon/version, UPX tắt
build_linux.sh            # Chuẩn bị venv và build Linux
install_linux.sh          # Cài ELF, icon và launcher cho user hiện tại
wifi-request.desktop      # Mẫu launcher Linux
font_base64.py             # Font JetBrains Mono Bold nhúng
image_base64.py            # Icon nhúng
icon/app.png              # Icon cho desktop launcher
version_wifi_request.txt  # Metadata EXE Windows
tests/                    # Unit test và smoke GUI
```

## Lưu ý vận hành

- Gateway Linux đọc từ `/proc/net/route`, chọn default route đang hoạt động có metric thấp nhất. Windows tiếp tục dùng `netifaces`.
- Kiểm tra kết nối dùng `requests.head` với timeout và không theo redirect, giữ cơ chế phát hiện portal qua tham số `dst` ở `Location`; không còn phụ thuộc `curl` hoặc `CREATE_NO_WINDOW`.
- Font nhúng Linux được đăng ký trước khi tạo cửa sổ Tk trong `$XDG_DATA_HOME/fonts/wifi-request/`. Có thể xem bằng `fc-match 'JetBrains Mono'`.
- App chỉ giữ một phiên bản nhờ khóa file Linux; khóa tự được hệ điều hành giải phóng nếu tiến trình thoát hoặc bị kill. File khóa còn trên đĩa không có nghĩa app còn chạy.
- GNOME có thể tự hiện cửa sổ captive portal; tùy chọn Connectivity Checking thuộc cài đặt hệ thống. App không tự đổi cài đặt NetworkManager hoặc MAC của bạn.
- Wayland giao quyền quản lý viền cửa sổ cho compositor; Linux không gọi Win32 để ẩn nút thu nhỏ/phóng to.
