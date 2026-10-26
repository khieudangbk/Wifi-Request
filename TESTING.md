# Kiểm chứng bản port Ubuntu 26.04

## Phạm vi

Thiết kế dựa trên `plan-ubuntu-26.04.md`. Mục tiêu là một codebase Windows/Linux; build Ubuntu 26.04/Python 3.14 và không khẳng định binary 26.04 tương thích ngược với glibc cũ.

## Các kiểm tra có thể lặp lại

| Yêu cầu | Kiểm chứng |
|---|---|
| Không import Win32 trên Linux | Unit test import main và module nền tảng |
| Một phiên bản, khôi phục sau khi tiến trình thoát | Hai tiến trình tranh flock; tiến trình thứ ba lấy lại khóa |
| Gateway đúng và có fallback khi không có route | Fixture `/proc/net/route`, so sánh `ip -4 route` trên máy thật |
| Tự khởi động source/frozen | Kiểm thử XDG tạm, quote đường dẫn có dấu cách/ký tự đặc biệt, validate desktop entry |
| Settings không dùng registry trên Linux | JSON round trip, tệp hỏng và quyền 0600 |
| Không gọi Tk từ worker/tray thread | Dispatcher owner-thread test và smoke GUI |
| Probe không phụ thuộc curl | HTTP HEAD, redirect `dst`, timeout được mock |
| Luồng router/Awing được giữ | Form giả lập → VerifyUrl → POST auth; kiểm tra Session đóng khi thành công/lỗi |
| Hợp đồng Windows | Mock mutex 64-bit, shortcut source/frozen và double-click tray |
| Tk, font, icon cửa sổ, khay và pause/resume | `tests/smoke_gui.py` dưới Xvfb; smoke binary `--smoke-test` |
| HiDPI | `WIFI_SMOKE_SCALE=2 xvfb-run -a .venv/bin/python tests/smoke_gui.py` và quan sát desktop thật |
| Linux binary không dùng venv để chạy | Chạy ELF với PATH hệ thống và bỏ VIRTUAL_ENV/PYTHONPATH, HOME/XDG mới |

Các kết quả tự động chỉ chứng minh phần được kiểm tra; mock Windows không thay cho chạy Windows thật, Xvfb không chứng minh extension GNOME đang hiển thị icon trên màn hình vật lý.

## Checklist thử thật còn cần xác nhận

- [ ] Ubuntu 26.04 GNOME/Wayland: font/icon rõ, cửa sổ không cắt chữ ở scale 100% và 200%.
- [ ] Icon khay hiện trên thanh GNOME; Show / Pause / Resume / Exit hoạt động bằng chuột.
- [ ] Chạy app lần hai: hiện thông báo đang chạy và không tạo phiên nền thứ hai.
- [ ] Gateway hiển thị khớp `ip -4 route show default` trên mạng KTX.
- [ ] Nối `INET - Free WiFi`, app tự đăng nhập khi phiên khoảng 15 phút hết hạn; chạy liên tục ít nhất 1 giờ không crash.
- [ ] Đăng xuất/đăng nhập desktop hoặc reboot: app tự chạy từ autostart, đúng binary hoặc đúng Python venv.
- [ ] Binary chạy trên máy Ubuntu sạch, không có venv; kiểm tra AppIndicator/XWayland và thư viện desktop.
- [ ] Build và chạy Windows thật: đăng nhập lại, tray double-click, pause/resume, Startup và chỉ một phiên bản vẫn hoạt động.
- [ ] Nếu hỗ trợ Ubuntu 22.04/24.04: build tại đó và kiểm tra riêng, không chỉ copy ELF build từ 26.04.

## Thu thập lỗi

Chạy từ Terminal và lưu stdout/stderr khi gặp lỗi. Không chia sẻ MAC, token hoặc credential từ portal. Source đã bỏ in username/password do portal trả về. Chế độ `--smoke-test` không gọi mạng và không ghi autostart, phù hợp để thử dependency/GUI trước khi đến KTX.
