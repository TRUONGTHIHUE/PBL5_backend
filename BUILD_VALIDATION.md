# Kết quả kiểm tra

## Yêu cầu hiện tại: UID → Python/Firebase → ESP32 Wi-Fi

- 49 bài `python -m unittest -v test_firebase_rfid test_card_record`: PASS trên máy hỗ trợ Linux/GCC.
- Đã kiểm tra chế độ hằng ngày không gọi prompt email/mật khẩu, khởi tạo bằng refresh token đã lưu,
  xoay refresh token và lưu qua giao diện kho credentials của hệ điều hành.
- Python gửi đúng ba trường cấu hình: storeId, wifiSSID, wifiPassword; storeName không bắt buộc.
- Đã kiểm tra thiếu dữ liệu, không tìm thấy, UID trùng, lỗi Firebase, timeout, phản hồi cũ và sai storeId phản hồi.
- Cross-build với ESP-IDF 5.4.4, RC522 4.0.1, ESP32, UART0 mặc định: PASS.
- Cấu hình tạo mới không override mode đã tự chọn `CONFIG_PBL5_FIREBASE_USB=y`; hai mode card-memory không bật.
- Source của build khớp repository. RFID.bin 830560 byte; còn 21% phân vùng ứng dụng.
- Chưa xác minh vòng tra Firebase → USB → Wi-Fi thật bằng tài khoản/thẻ/ESP32 của người dùng.
- Website, Rules, Excel, chân RC522 và repository PBL5_render_api không thay đổi trong lần xác thực tự động này.
- Mode card-memory trước đó được giữ và ẩn sau tùy chọn thử nghiệm; không dùng cho yêu cầu hiện tại.

## Lịch sử thử nghiệm: đọc Wi-Fi trực tiếp từ thẻ

- 41 kiểm thử `python -m unittest -v test_card_record test_firebase_rfid`: PASS, không có bài bị skip trong môi trường Linux có GCC này.
- Bộ mã hóa Python được đối chiếu với file C thực tế `card_record.c` biên dịch bằng GCC (`-Wall -Wextra -Werror`).
- File `card_storage.c` thực tế được kiểm tra với driver thẻ giả lập: giới hạn block ghi,
  header commit cuối cùng, đọc lại, lỗi giữa chừng và kết thúc phiên crypto sau các thao tác.
- Build **User / PBL5_CARD_WIFI=y**: PASS với ESP-IDF 5.4.4, RC522 4.0.1, target ESP32.
  Image 816640 byte, còn 22% phân vùng ứng dụng.
- Build **Setup only / PBL5_CARD_WRITER=y**: PASS cùng toolchain và thư viện.
  Image 289184 byte, còn 72% phân vùng ứng dụng.
- Các file nguồn C/header/CMake/Kconfig của hai lần build cuối đã được đối chiếu với repository.
- Website, Rules, Excel và PBL5_render_api không thay đổi trong lần chuyển kiến trúc này.
- **Chưa có thiết bị/thẻ thật tại máy hỗ trợ**: chưa xác minh quyền Key A, khả năng ghi thẻ,
  WRITE_VERIFIED trên phần cứng, hoặc kết nối Wi-Fi thật. Không coi build/giả lập là bằng chứng đã ghi thẻ thành công.
- Chế độ USB Firebase cũ được giữ; 28 kiểm thử Python cũ vẫn đạt. Chưa build lại chế độ firmware cũ trong lần này.
- Phần sản phẩm, quyền người mua đọc Firebase và giọng nói chưa triển khai. Xem CARD_WIFI.md để thử từng bước.

## Lịch sử: bản Serial hai chiều trước khi thêm chế độ thẻ

### Đã chạy trên bản cũ

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

## Điều kiện build của máy hỗ trợ (dùng cho cả hai phiên bản)

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
