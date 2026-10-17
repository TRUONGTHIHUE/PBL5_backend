# PBL5 — RFID → Python/Firebase → ESP32 Wi-Fi

Luồng sử dụng theo yêu cầu hiện tại:

```text
RC522 đọc UID → ESP32 gửi USB/UART → Python tra Firestore
→ trả storeId + wifiSSID + wifiPassword → ESP32 cấu hình Wi-Fi
→ nhận IP → xác nhận WIFI_CONNECTED và giữ đúng storeId
```

Thẻ chỉ nhận diện cửa hàng. Không ghi dữ liệu Wi-Fi vào thẻ ở luồng này.
Python tra dữ liệu; chỉ ESP32 thực hiện kết nối mạng Wi-Fi cửa hàng.
Máy tính cần Internet sẵn để tra Firebase.

- **Cách chạy COM5, cấu hình Firestore và lỗi:** [FIREBASE_RFID.md](FIREBASE_RFID.md).
- **JSON hai chiều, timeout và đối chiếu storeId:** [SERIAL_PROTOCOL.md](SERIAL_PROTOCOL.md).
- **Kết quả build/kiểm thử thực tế và các bước chưa xác minh:** [BUILD_VALIDATION.md](BUILD_VALIDATION.md).

File chính: `RFID/RFID/main/main.c`, `firebase_bridge.c`, `Kconfig.projbuild`, `firebase_rfid.py`.
Chọn Operating mode **RFID USB bridge: Firebase lookup and store Wi-Fi connection** trong menuconfig;
đây cũng là mặc định của cấu hình mới. Không chạy Serial Monitor cùng Python trên COM5.

Website trong `firebase/`, Rules, Excel và API PHP/Render/CSV được giữ nguyên.
Các chế độ card-memory thử nghiệm được giữ để không xóa mã cũ nhưng ẩn sau tùy chọn riêng, không dùng cho yêu cầu này.
Không chạy provision_card.py, không cần ghi thẻ, không thay chân RC522.
Firebase vẫn yêu cầu xác thực: bản demo dùng tài khoản có ownerUid phù hợp. Không nhúng tài khoản chủ cửa hàng lên ESP32.
