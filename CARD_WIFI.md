# Luồng mới: chạm thẻ → ESP32 đọc Wi-Fi → kết nối

## Ai phải nhập gì?

- **Người thiết lập/chủ cửa hàng** ghi thẻ một lần: chọn UID mục tiêu, storeId, SSID và mật khẩu Wi-Fi thật.
- **Người sử dụng** chỉ bật ESP32 và chạm thẻ. Không nhập email, mật khẩu Firebase hoặc chạy Python.
- Website vẫn cần tài khoản chủ cửa hàng để quản lý dữ liệu. Không thay Rules hoặc mở dữ liệu công khai.

Firmware đọc SSID/password/storeId TRỰC TIẾP từ bộ nhớ thẻ, không tra bảng UID hoặc Firebase.
Đây là định dạng riêng P5W1 cho RC522/MIFARE Classic 1K, không phải bản ghi NFC NDEF dùng chung mọi điện thoại.
Log trước đó đã nhận diện thẻ MIFARE 1K; quyền đọc/ghi và khóa mặc định trên từng thẻ vẫn phải thử thực tế.
Chỉ thử thẻ dự phòng thuộc quyền của bạn. Không dùng thẻ ngân hàng, thẻ ra vào hoặc thẻ có dữ liệu cần giữ.

**Giới hạn bảo mật:** MIFARE Classic với Key A mặc định không bảo vệ mật khẩu Wi-Fi cho sản phẩm thật.
CRC chỉ phát hiện dữ liệu lỗi, không chống sao chép/giả mạo. Dùng mạng demo/hotspot có quyền quản lý.
USB khi ghi thẻ không mã hóa. Không đưa password, recordHex, memory dump hoặc log chứa bí mật lên GitHub.

## 1. Cập nhật code — CMD tại repository của bạn

```cmd
cd /d D:\NAM5\PBL5_backend\PBL5_backend_firebase
git status
git pull --ff-only origin firebase-rfid-usb
```

Nếu có thay đổi cục bộ/xung đột, dừng và giữ nguyên file, không reset/clean.

## 2. Nạp chế độ ghi — Terminal ESP-IDF 5.4.4

```cmd
cd /d D:\NAM5\PBL5_backend\PBL5_backend_firebase\RFID\RFID
idf.py -B build_firebase menuconfig
```

Vào **PBL5 RFID transport → Operating mode**, chọn:

```text
Setup only: provision a spare MIFARE 1K card over USB
```

S → Enter lưu, Q thoát. Không nhập SSID/password vào menuconfig.

```cmd
idf.py -B build_firebase build
idf.py -B build_firebase -p COM5 flash monitor
```

Phải thấy `WRITER_READY` trong bản tin PBL5CARD. Thử đặt thẻ để xác nhận UID sẽ chỉ báo NOT_ARMED, KHÔNG tự ghi.
Lấy thẻ ra và nhấn Ctrl+] đóng monitor. COM5 phải được giải phóng trước khi chạy công cụ ghi.
Giữ nguyên GPIO: MISO19, MOSI23, SCK18, SS5, RST22; RC522 dùng 3.3V.

## 3. Chuẩn bị công cụ ghi — CMD thường tại thư mục gốc repository

```cmd
cd /d D:\NAM5\PBL5_backend\PBL5_backend_firebase
```

Nếu chưa có .venv:

```cmd
py -3 -m venv .venv
```

Cài thư viện:

```cmd
.\.venv\Scripts\python.exe -m pip install -r requirements-card.txt
```

Chỉ cần pyserial cho công cụ ghi; công cụ KHÔNG đăng nhập hoặc gọi Firebase.

## 4. Ghi đúng một thẻ

Ví dụ thẻ có UID đã đọc là CD 4B 1E 03:

```cmd
.\.venv\Scripts\python.exe provision_card.py --port COM5 --uid "CD 4B 1E 03"
```

Nhập theo lời nhắc:

1. **storeId:** lấy mã thật của cửa hàng trên website/Firestore, có thể là ID ngẫu nhiên hiện tại. Không tự đổi ID tài liệu.
2. **Wi-Fi SSID thật:** mạng 2.4 GHz trong vùng phủ sóng, đúng chữ hoa/thường và khoảng trắng.
3. **Wi-Fi password:** nhập ẩn; để rỗng chỉ nếu mạng thật là mạng mở.
4. Xác nhận chính xác `WRITE CD 4B 1E 03` (thay bằng UID mục tiêu nếu dùng thẻ khác).
5. Công cụ sẽ yêu cầu nhấn EN/RESET trên ESP32 để nhận WRITER_READY. Chưa đặt thẻ lên RC522.
6. Khi báo ARMED/đã sẵn sàng, đặt đúng thẻ và giữ yên đến `WRITE_VERIFIED`.

Chỉ WRITE_VERIFIED mới xác nhận đã ghi và đọc lại đúng; chưa chứng minh mạng Wi-Fi kết nối được.
Sai UID: TARGET_MISMATCH, không ghi. NOT_ARMED: chưa chuẩn bị hoặc đã hết hạn.
Không có xác nhận WRITE từ người thiết lập thì công cụ chưa gửi dữ liệu.
Trường hợp thoát công cụ sau ARMED: reset ESP32 ngay để hủy; yêu cầu cũng tự hết hạn sau 90s.

**Dữ liệu thẻ:** chỉ 12 block dữ liệu 4,5,6,8,9,10,12,13,14,16,17,18 (sector 1–4).
Không ghi block 0, không ghi sector trailer, không đổi UID/Key A/Key B/access bits.
Dùng Key A mặc định FF FF FF FF FF FF; nếu khóa khác hoặc không có quyền, báo lỗi và không tìm cách vượt quyền.
Giới hạn: storeId 1–64 byte UTF-8, SSID 1–32 byte, password 8–63 byte hoặc 64 hex; rỗng = mạng mở.

- Nếu vùng đã có dữ liệu lạ: UNRECOGNIZED_DATA_NO_WRITE, không xóa tự động; dùng thẻ dự phòng khác.
- Nếu đã có bản ghi P5W1 hợp lệ: mặc định từ chối. Chỉ khi muốn thay, chạy cùng lệnh có `--replace` và xác nhận lại.
- Ghi bị gián đoạn/lỗi: không báo thành công; có thể mất cấu hình cũ trong vùng này. Không tự sửa/xóa dữ liệu lạ.
- Sau khi sửa SSID/password/storeId trên website, thẻ KHÔNG tự đồng bộ: người thiết lập phải ghi lại thẻ.

Muốn ba cửa hàng: lặp lại cho ba UID thật, nhập ba storeId tương ứng. Có thể dùng cùng Wi-Fi thật cho cả ba bản ghi khi thử tại trọ.
Điều đó chỉ chứng minh gán đúng cửa hàng, không chứng minh kết nối ba mạng khác nhau.

## 5. Nạp chế độ người dùng sau khi ghi xong

Đóng công cụ ghi. Trong Terminal ESP-IDF, tại RFID\RFID:

```cmd
idf.py -B build_firebase menuconfig
```

PBL5 RFID transport → Operating mode → chọn:

```text
User: read store Wi-Fi from MIFARE 1K (no Firebase login)
```

Lưu, thoát rồi:

```cmd
idf.py -B build_firebase build
idf.py -B build_firebase -p COM5 flash monitor
```

KHÔNG chạy firebase_rfid.py ở chế độ này. Không nhập tài khoản Firebase hoặc API key.
Chạm thẻ đã ghi. Mong đợi:

```text
DATA SOURCE: CARD_MEMORY; Store ID: ...; Wi-Fi SSID: ...; Password: [HIDDEN]
PBL5: ... CONFIG_RECEIVED ...
PBL5: ... WIFI_CONNECTING ...
PBL5: ... WIFI_CONNECTED ...
```

Giá trị hiển thị phải đúng dữ liệu đã ghi, không lấy từ bảng ba thẻ demo cũ. Password không in trong chế độ người dùng.
WIFI_CONNECTED chỉ khi có IP. Thử tối đa 20s; mạng sai/không có: WIFI_FAILED hoặc WIFI_TIMEOUT, không giả vờ thành công.
Thẻ chưa ghi/CRC sai: CARD_NOT_PROVISIONED_OR_CORRUPT, không kết nối. Khóa/quyền sai: CARD_READ_OR_AUTH_FAILED.
Thẻ khác lúc đang kết nối: BUSY, chờ kết quả rồi lấy ra và quét lại.

Sau nạp chế độ User, USB chỉ cần cấp nguồn; máy tính/monitor không tham gia xử lý. Có thể cấp nguồn bằng cáp USB từ nguồn phù hợp.
**Chưa có thông báo giọng nói:** log dành cho người thiết lập xác minh, chưa phải giao diện sử dụng hoàn chỉnh cho người khiếm thị.
Chưa có loa/buzzer/nút được xác nhận để tự ý gán GPIO. Không coi thiết bị đã hoàn thiện hỗ trợ tiếp cận ở bước này.

## Firebase và sản phẩm nằm ở đâu?

Website/Firestore hiện tại được giữ nguyên. Không cần Firebase để lấy Wi-Fi ban đầu vì dữ liệu đã trên thẻ.
Sau khi kết nối, firmware giữ storeId bằng `firebase_bridge_connected_store()` để bước sau lấy sản phẩm.
**Chưa gửi request sản phẩm và chưa giải quyết quyền người mua đọc sản phẩm Firebase.** Không mở Rules hoặc nhúng tài khoản chủ cửa hàng để né quyền.
Mã Python Firebase trước đây vẫn có cho việc kiểm tra/quản trị, không phải chương trình người dùng phải chạy nữa.

## Kiểm thử thật cần làm lần lượt

1. Writer không ARMED → quét không ghi; sai UID → không ghi.
2. Thẻ dự phòng đúng UID → WRITE_VERIFIED; thử quyền/khóa sai phải báo lỗi.
3. Chuyển User → đọc lại đúng storeId/SSID, có WIFI_CONNECTED với mạng thật.
4. Thẻ trống/CRC sai/mạng không tồn tại/password sai → báo lỗi đúng, không thành công giả.
5. Ba thẻ → ba storeId đúng; không dùng Firebase login ở chế độ người dùng.
6. Reset/mất nguồn → vẫn đọc cấu hình từ thẻ, không phụ thuộc chương trình máy tính.

Kiểm thử tự động có trong test_card_record.py; đối chiếu C/Python không thay thế thao tác ghi thẻ thật.
Kết quả cross-build/kiểm thử được ghi ở BUILD_VALIDATION.md. Chưa có log xác nhận ghi/đọc/kết nối trên thẻ thật của bạn.
