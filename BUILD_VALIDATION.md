# Kết quả kiểm tra bản Serial hai chiều

## Đã chạy

- 28 bài `python -m unittest -v test_firebase_rfid`: PASS. Dùng phản hồi Firebase và Serial giả lập,
  bao gồm hiển thị password demo từ bản ghi trả về, chặn hiển thị/gửi credentials khi tra cứu lỗi hoặc dữ liệu thiếu.
- Các bản cập nhật hiển thị password và chẩn đoán đăng nhập chỉ đổi Python, kiểm thử và tài liệu; firmware giữ nguyên bản cross-build bên dưới.
- Cross-build firmware ESP32 với ESP-IDF tag `v5.4.4`:
  `296b6eab9445fd720e71aecab961e2d3fbca9944`.
- RC522 từ repository chính thức `abobija/esp-idf-rc522`, tag `4.0.1`, commit
  `a44b3e774b838ac33841213eead4f66491ee84f5`.
- Cấu hình: ESP32, UART0 mặc định, `CONFIG_PBL5_FIREBASE_USB=y`.
- `idf.py reconfigure` rồi `ninja -j4`: PASS, 1012 bước build, exit 0.
- Đã đối chiếu nội dung main.c, firebase_bridge.c/.h, CMakeLists.txt và Kconfig.projbuild
  của bản build với repository: giống nhau.
- RFID.bin: 830592 byte; phân vùng ứng dụng 1048576 byte, còn 21%.
- SHA-256 RFID.bin của lần build này:
  `0b1388d3fed9d1c983f2acef0656c84d9c5c64551d578ad315f0a3212221fb94`.
- `git diff --check`: PASS. Website, Rules, Excel và repository PBL5_render_api không sửa trong lần này.

## Điều kiện build của máy hỗ trợ

Image Docker ESP-IDF đầy đủ không giải nén được do giới hạn đĩa; đã chuyển sang SDK/toolchain cài tối thiểu cho ESP32.
Kho component Espressif bị proxy chặn. Bản sao dùng để build lấy RC522 từ GitHub chính thức theo tag/commit nêu trên,
và dùng override_path cục bộ; không sửa manifest hoặc lockfile của repository người dùng.
URL constraints cho công cụ Python của SDK cũng bị chặn. Môi trường build dùng lựa chọn chính thức
`idf_tools.py install-python-env --no-constraints --extra-wheels-url https://pypi.org/simple`.
Điều này bỏ giới hạn phiên bản bổ sung của các gói Python công cụ, không bỏ TLS hoặc kiểm tra checksum toolchain.
SDK requirements vẫn được kiểm tra trước khi build. esptool phiên bản 5.6.0 phát cảnh báo option cũ nhưng tạo image thành công.
Người dùng nên giữ cài đặt ESP-IDF 5.4.4 chuẩn trên máy của mình; không cần áp dụng các workaround mạng này.

## Chưa chạy — cần thiết bị/tài khoản thật

- Nạp và chạy firmware trên ESP32, đọc ba thẻ RC522.
- Đăng nhập Firebase thật, xác minh Rules đã deploy, tra đúng dữ liệu người dùng.
- Truyền qua cổng USB vật lý và nhận ACK từ board.
- Kết nối Wi-Fi thật, password sai, SSID không tồn tại, ngắt mạng thật.
- Website/Excel trên Hosting thật. Không có thay đổi code ở các phần này, nhưng điều đó không thay thế kiểm thử bài 7.

Build thành công không chứng minh toàn bộ hệ thống đã hoạt động. Làm lần lượt 7 bài trong FIREBASE_RFID.md.
