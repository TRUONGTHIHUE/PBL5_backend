# PBL5 — RFID và Wi-Fi cửa hàng

Luồng mới cho người dùng: **chạm thẻ MIFARE 1K → ESP32 đọc storeId/SSID/password trên thẻ → kết nối Wi-Fi**.
Người sử dụng không nhập email/mật khẩu Firebase và không chạy Python. Người thiết lập ghi thẻ một lần bằng USB.

Đọc **[CARD_WIFI.md](CARD_WIFI.md)** để nạp chế độ ghi, chuẩn bị thẻ dự phòng, rồi nạp chế độ người dùng.
Không dùng thẻ ngân hàng/ra vào/thẻ có dữ liệu cần giữ. Chỉ dùng MIFARE 1K có quyền đọc/ghi với Key A mặc định cho demo.
Không ghi block UID hoặc sector trailer. MIFARE Classic với khóa mặc định không bảo vệ mật khẩu cho sản phẩm thật.

Website vẫn ở `firebase/`. Phần sản phẩm, YOLO, TTS và thông báo giọng nói chưa tích hợp trong luồng này.
Quyền người mua truy xuất sản phẩm Firebase sẽ cần thiết kế riêng, không dùng tài khoản chủ cửa hàng trên thiết bị người dùng.

Các chế độ Python–Firebase–USB và Render cũ được giữ trong menu để kiểm tra tương thích; không phải luồng dùng hằng ngày.
Hướng dẫn cũ ở [FIREBASE_RFID.md](FIREBASE_RFID.md), giao thức cũ ở [SERIAL_PROTOCOL.md](SERIAL_PROTOCOL.md).
Kết quả kiểm tra và giới hạn thực tế: [BUILD_VALIDATION.md](BUILD_VALIDATION.md).
