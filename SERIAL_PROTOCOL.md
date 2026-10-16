# PBL5 Serial JSON v1

UART0 qua USB-UART, 115200 baud, 8N1. Không dùng Serial Monitor cùng Python.
Mỗi bản tin: `PBL5:` + JSON UTF-8 một dòng + LF (`\n`). Tối đa 2048 byte trước LF.
Log ESP-IDF bình thường được bỏ qua. Bộ nhận giữ mảnh dòng qua nhiều lần đọc;
dòng vượt giới hạn bị bỏ đến LF. JSON hỏng/thiếu kết thúc không được dùng để kết nối.
Không paste/log bản tin cấu hình thật: USB không mã hóa.

ESP32 phát khi đọc thẻ (ví dụ UID, không phải credential):

```json
{"v":1,"type":"scan","requestId":"1234abcd-1","uid":"CD 4B 1E 03"}
```

`requestId` gồm nonce khởi động và số thứ tự, để tương quan bản tin, không phải cơ chế xác thực.
ESP32 chỉ chấp nhận cấu hình cùng requestId và uid trong thời hạn tra cứu 60s.
Python query Firestore với `ownerUid == UID_đăng_nhập` AND `rfidId == UID_thẻ`, limit 2 để phát hiện trùng.

Python trả `type=store_config`, v=1, requestId, uid và đủ bốn trường string:
storeId, storeName, wifiSSID, wifiPassword. Không có giá trị thật trong tài liệu này.
Thiếu trường, kiểu sai, ký tự điều khiển, password/SSID vượt giới hạn: INVALID_CONFIG.
SSID 1–32 byte UTF-8, storeId 1–128 byte, storeName 1–600 byte.
Password 8–63 byte hoặc 64 hex; chuỗi rỗng có nghĩa mạng mở; thiếu trường không có nghĩa mạng mở.
Chuỗi chứa NUL không được chấp nhận. Không lấy SSID/password từ bảng demo trong firmware.

Nếu tra cứu lỗi, Python trả type=lookup_error với v/requestId/uid; không gửi token hoặc thông báo Firebase thô.
ESP32 xác nhận bằng status=LOOKUP_FAILED rồi về chờ quét.

ESP32 phát `type=status` với v/requestId/uid và status:

| status | Ý nghĩa |
|---|---|
| CONFIG_RECEIVED | Đã nhận và kiểm tra cấu hình, chưa xác nhận Wi-Fi |
| WIFI_CONNECTING | Bắt đầu một lần thử kết nối |
| WIFI_CONNECTED | Đã nhận địa chỉ IP, storeId sẵn sàng dùng sau |
| WIFI_FAILED / WIFI_TIMEOUT | Không có IP sau tối đa 20s chờ kết nối |
| WIFI_STOP_FAILED | Lỗi dừng kết nối cũ, không báo kết nối mới thành công |
| INVALID_CONFIG | Bản tin tương quan đúng nhưng cấu hình sai |
| LOOKUP_FAILED | Python báo không tra được cấu hình |
| LOOKUP_TIMEOUT | Không có phản hồi tương quan hợp lệ trong 60s |

Status không chứa password/SSID; Python chỉ in SSID từ dữ liệu Firestore đã kiểm tra.
Python chờ ACK 8s sau gửi, sau ACK chờ kết quả 35s (gồm dừng/khởi động Wi-Fi).
Không coi FETCH SUCCESS hay CONFIG_RECEIVED là WIFI_CONNECTED.

Quét lúc đang chờ/kết nối: ESP32 phát type=busy/status=BUSY_RESCAN_AFTER_RESULT.
Yêu cầu đang làm không bị thay thế. Người dùng đợi kết quả, lấy thẻ ra rồi quét lại.
Khi chấp nhận lần quét mới, ESP32 xóa storeId sẵn sàng dùng trước đó; nếu tra cứu lỗi,
không được tiếp tục dùng cửa hàng cũ cho UID mới. Kết nối Wi-Fi cũ có thể còn đến lúc nhận cấu hình mới.
Boot phát type=ready/status=READY; Python hủy yêu cầu cũ khi nhận ready.
Phản hồi status cũ không làm hoàn thành yêu cầu mới. Không gửi lại cấu hình chứa mật khẩu tự động.
Mất Wi-Fi sau thành công không tự reconnect; hàm firebase_bridge_connected_store() không trả storeId khi mất IP.
