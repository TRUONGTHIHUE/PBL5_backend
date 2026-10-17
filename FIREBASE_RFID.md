# RFID → Python/Firebase → ESP32 kết nối Wi-Fi

> Đây là chế độ kiểm tra cũ, có đăng nhập chủ cửa hàng. Luồng mới không yêu cầu người dùng đăng nhập:
> xem CARD_WIFI.md (đọc cấu hình trực tiếp từ thẻ) và chọn đúng Operating mode trong menuconfig.

## Phạm vi và giới hạn

Luồng: RC522 → ESP32 đọc UID → USB Serial → Python đăng nhập Firebase → tra Firestore → USB trả cấu hình → ESP32 kết nối Wi-Fi cửa hàng.
Máy tính cần Internet riêng để tra Firebase trước; không phụ thuộc ESP32 đã có Wi-Fi hay chưa.
Bản này có máy tính làm trung gian; không ghi SSID/password vào thẻ và không phải ESP32 tự truy vấn Firebase.
Python dùng Firebase Authentication email/password và Rules hiện có: chỉ tìm cửa hàng thuộc ownerUid của tài khoản đăng nhập.
Không thể dùng một tài khoản khách bất kỳ để tra mọi cửa hàng. Chưa triển khai phân quyền người mua cho sản phẩm thật.
Không dùng Admin key, không mở Rules công khai. Không thay Excel, barcode, YOLO, PHP/Render/CSV hoặc di chuyển dữ liệu.

USB Serial truyền mật khẩu dạng rõ (JSON), KHÔNG mã hóa. Chỉ dùng thiết bị/máy tính tin cậy cho demo.
Bản demo này có chủ đích in wifiPassword từ Firebase trong Terminal Python sau khi tra cứu và kiểm tra dữ liệu thành công.
Không chụp/chia sẻ màn hình chứa mật khẩu, không redirect output ra file hoặc đưa log lên GitHub. Chương trình không tự ghi file log.
Mật khẩu tài khoản Firebase vẫn được nhập ẩn và không in ra. ESP32 dùng WIFI_STORAGE_RAM.
Mạng cần là Wi-Fi 2.4 GHz tương thích ESP32. Chưa hỗ trợ captive portal hoặc WPA Enterprise.
Mạng giả hoặc không trong vùng phủ sóng phải báo thất bại, không báo kết nối giả.
Có thể gán cả ba cửa hàng cùng Wi-Fi thật tại trọ để thử; điều này chỉ chứng minh chọn đúng bản ghi, không chứng minh chuyển ba mạng khác nhau.

## File nguồn

- `RFID/RFID/main/main.c`: giữ GPIO và RC522; gọi bridge khi đọc được UID.
- `RFID/RFID/main/firebase_bridge.c`, `.h`: Serial hai chiều, chống phản hồi cũ và kết nối Wi-Fi.
- `RFID/RFID/main/Kconfig.projbuild`, `CMakeLists.txt`: bật chế độ bridge và biên dịch module.
- `firebase_rfid.py`: đăng nhập/refresh token, query ownerUid+rfidId, gửi cấu hình, chờ trạng thái.
- `test_firebase_rfid.py`: kiểm thử Firebase giả lập và giao thức Python.
- `SERIAL_PROTOCOL.md`: định dạng bản tin và timeout.
- `firebase/`: website từ ZIP trước đó. Không sửa website, Excel hoặc Rules ở bước Serial hai chiều này.

Các file đầy đủ nằm trên nhánh GitHub `firebase-rfid-usb`; không cần ghép các đoạn code trong chat.

## 1. Cập nhật code — PowerShell tại thư mục repository

Nếu đã ở nhánh firebase-rfid-usb và không có thay đổi cục bộ:

```powershell
git status
git pull --ff-only origin firebase-rfid-usb
```

Nếu Git báo xung đột/thay đổi cục bộ, dừng và giữ các file của bạn; không reset/clean để bỏ dữ liệu.
Có thể clone riêng từ thư mục cha nếu chưa có bản mới:

```powershell
git clone --branch firebase-rfid-usb https://github.com/TRUONGTHIHUE/PBL5_backend.git PBL5_backend_firebase
```

## 2. Dữ liệu Firestore

Giữ collection `stores` và các subcollection `products`. Đường dẫn sản phẩm dùng ID TÀI LIỆU: stores/{documentId}/products/..., không suy ra ID đó từ UID hoặc tên cửa hàng.
Mỗi tài liệu cần trường string: ownerUid, rfidId, storeId, storeName, wifiSSID, wifiPassword.
`storeId` giữ ID ngẫu nhiên hiện tại được; Python in cả documentId và storeId, ESP32 giữ storeId để dùng sau.
`ownerUid` đúng UID tài khoản đăng nhập. UID thẻ chuẩn hóa chữ hoa, khoảng trắng:

| Thẻ thử | rfidId |
|---|---|
| 1 | CD 4B 1E 03 |
| 2 | F0 78 0E 04 |
| 3 | C7 9A 0C 03 |

Đây là UID thử từ firmware cũ; đối chiếu lại UID của thẻ thật, không mặc định thẻ bạn đang cầm có UID này.
Không lưu email vào rfidId. Không dùng một UID cho nhiều cửa hàng trong cùng tài khoản.
SSID 1–32 byte UTF-8; password 8–63 byte, hoặc 64 ký tự hex. wifiPassword chuỗi rỗng chỉ dùng khi mạng thật là mạng mở.
Thiếu trường password khác với chuỗi rỗng; thiếu phải báo MISSING_FIELDS. Không đưa giá trị thật lên GitHub hoặc ảnh log.

## 3. Build/nạp — Terminal ESP-IDF 5.4.4

Từ thư mục gốc repository:

```powershell
cd RFID\RFID
idf.py -B build_firebase menuconfig
```

PBL5 RFID transport → bật `RFID USB bridge: Firebase lookup and store Wi-Fi connection`.
Giữ console mặc định UART0, 115200 baud trên board ESP32 thường có USB-UART; bản này không hỗ trợ console USB-JTAG/custom UART.
Hai mục Wi-Fi legacy để trống. SSID/password thật sẽ lấy từ Firestore, không nhập vào firmware.
Lưu, thoát:

```powershell
idf.py -B build_firebase build
idf.py -B build_firebase -p COM5 flash monitor
```

Thay COM5 bằng cổng thật. Không dùng build_http cũ. GPIO giữ nguyên MISO19, MOSI23, SCK18, SS5, RST22; nguồn RC522 3.3V.
Quét thẻ và thấy bản tin `PBL5:` JSON có type=scan, uid thật và requestId. Firmware cũ chỉ in RFID_UID không tương thích bản này.
Không chạy Python khi monitor còn mở. Ctrl+] để thoát monitor.
Nếu đã thử quét khi chưa chạy Python, reset ESP32 rồi quét lại sau khi Python đăng nhập; mỗi yêu cầu tra cứu hết hạn sau 60 giây.

## 4. Python — PowerShell tại thư mục gốc repository

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-firebase.txt
$env:FIREBASE_WEB_API_KEY = "API_KEY_WEB_LAY_TU_firebase/public/firebase-config.js"
```

Thay chữ mẫu bằng giá trị apiKey Web của project. Không dùng private key/service-account key.
Kiểm tra Firestore riêng, không kết nối Wi-Fi ESP32:

```powershell
.\.venv\Scripts\python.exe firebase_rfid.py --uid "CD 4B 1E 03"
```

Nhập tài khoản chủ cửa hàng trên website, không phải tài khoản Google Console hay mật khẩu Wi-Fi. Mật khẩu đăng nhập được nhập ẩn.
Không ghi email/mật khẩu vào source. Email phải có trong Firebase Console → Authentication → Users,
và Email/Password provider phải bật. Đăng nhập thành công in User UID để đối chiếu với ownerUid của tài liệu cửa hàng.
UID tài khoản Authentication khác UID thẻ RFID: tài khoản cấp quyền đọc, UID thẻ chọn cửa hàng.
Nếu lỗi trước thông báo đăng nhập thành công, chương trình chưa mở COM hoặc tra thẻ; sửa đăng nhập/mạng trước.
INVALID_LOGIN_CREDENTIALS: kiểm tra tài khoản project này và mật khẩu; API_KEY_INVALID: kiểm tra API key Web;
OPERATION_NOT_ALLOWED: bật Email/Password. Không chia sẻ mật khẩu, token hay log Wi-Fi để chẩn đoán đăng nhập.
FETCH STATUS SUCCESS chỉ chứng minh truy vấn Firebase đúng; không chứng minh ESP32 đã nhận hoặc kết nối.
Sau đó chạy nhận thẻ:

```powershell
.\.venv\Scripts\python.exe firebase_rfid.py --port COM5
```

Đăng nhập, quét thẻ. Chương trình mở COM một lần. Không mở Serial Monitor song song. Ctrl+C để dừng.
Thông tin cửa hàng từ Firebase được in, bao gồm wifiPassword thật trong bản demo theo yêu cầu.
Các dòng dưới là định dạng, không phải dữ liệu đã được xác minh hoặc giá trị cần hardcode:

```text
========== THONG TIN CUA HANG ==========
Store ID       : <storeId lấy từ Firebase>
Wi-Fi SSID     : <wifiSSID lấy từ Firebase>
Wi-Fi Password : <wifiPassword lấy từ Firebase>
========================================
```

Python tiếp tục gửi cùng cấu hình về ESP32 sau khi in. Không tìm thấy/thông tin thiếu hoặc không hợp lệ:
chỉ báo lỗi và gửi lookup_error, không in khối thông tin thành công hoặc gửi cấu hình Wi-Fi.
Trạng thái mong đợi theo thứ tự:

```text
FETCH STATUS : SUCCESS
ESP32 STATUS : CONFIG_RECEIVED
ESP32 STATUS : WIFI_CONNECTING
ESP32 STATUS : WIFI_CONNECTED
```

WIFI_CONNECTED chỉ phát khi ESP32 nhận IP. Có cấu hình nhưng chưa có IP thì chưa thành công.
Khi đang xử lý, thẻ khác báo BUSY_RESCAN_AFTER_RESULT: chờ kết quả, lấy thẻ ra rồi quét lại. Không tự động chuyển thẻ giữa chừng.
Khi đổi cửa hàng, ESP32 dừng kết nối cũ và thử cấu hình mới một lần; không tự quay lại Wi-Fi cũ hoặc retry vô hạn.
Nếu mất mạng sau khi đã kết nối, ESP32 xóa mã cửa hàng đang có kết nối; cần quét lại để thử kết nối mới.
Hàm firmware firebase_bridge_connected_store() chỉ trả storeId khi kết nối còn IP; chưa gửi request sản phẩm trong giai đoạn này.

## 5. Bảy bài kiểm thử trên máy bạn

| Bài | Thao tác | Kết quả cần kiểm chứng |
|---|---|---|
| 1 | flash monitor, quét thẻ | UID JSON đúng với UID thẻ; thoát monitor sau kiểm tra |
| 2 | --uid UID_THAT | Tìm đúng documentId/storeId/tên/SSID/password; xem tại máy, không chia sẻ log |
| 3 | --port COMx, quét thẻ | CONFIG_RECEIVED từ ESP32; không coi lệnh Python gửi thành công là đã nhận |
| 4 | SSID/password hợp lệ của mạng thật | WIFI_CONNECTED sau khi có IP |
| 5 | Quét lần lượt ba thẻ, chờ xong mỗi lần | Ba bản ghi đúng; kiểm tra SSID từng bản ghi, không dựa vào bảng firmware |
| 6 | Thẻ chưa đăng ký, thiếu trường, sai password, ngắt Internet máy tính | NOT_FOUND/MISSING_FIELDS/INVALID_CONFIG hoặc lỗi mạng; ESP32 LOOKUP_FAILED hay WIFI_FAILED/TIMEOUT; không báo thành công |
| 7 | Website đăng nhập, chọn cửa hàng, upload Excel thử trên cửa hàng demo | Sản phẩm tải lại đúng; nhớ upload Excel thay danh sách cũ, không thử trên dữ liệu thật cần giữ |

Bài test timeout: tắt Python, reset ESP32, quét thẻ, chờ 60s: LOOKUP_TIMEOUT.
Bài test phản hồi cũ/cắt dòng được kiểm tra giả lập phía Python; muốn xác minh toàn bộ firmware phải thử trên board.
Mỗi lần quét xem requestId để tránh nhầm lần thử trước. Không paste bản tin store_config vì chứa mật khẩu.
Mạng máy tính cần truy cập identitytoolkit.googleapis.com, securetoken.googleapis.com, firestore.googleapis.com qua HTTPS.
Quyền sai tài khoản và UID không tồn tại đều có thể hiện NOT_FOUND: không dò dữ liệu tài khoản khác.

## 6. Lỗi và giới hạn

- ESP32_ACK_TIMEOUT: Python đã gửi nhưng chưa thấy CONFIG_RECEIVED trong 8s; kiểm tra firmware mới, console UART0/115200, COM rồi reset/quét lại.
- ESP32_RESULT_TIMEOUT: có ACK nhưng chưa có kết quả Wi-Fi trong 35s. Chưa được kết luận kết nối thành công.
- LOOKUP_TIMEOUT: ESP32 chờ 60s chưa có cấu hình đúng requestId/uid. Kiểm tra Python/mạng.
- WIFI_FAILED/WIFI_TIMEOUT: kiểm tra mạng 2.4 GHz có thật trong vùng phủ sóng, password và router. Không retry vô hạn.
- WIFI_STOP_FAILED: không dừng được kết nối cũ; reset và gửi log đã che bí mật.
- NOT_FOUND: kiểm tra UID chuẩn hóa và ownerUid thuộc tài khoản.
- DUPLICATE_UID: sửa bản ghi trùng, chương trình không chọn tùy ý.
- MISSING_FIELDS/INVALID_CONFIG: sửa dữ liệu trong Firestore, không giả lập thành công.
- Cổng bận: đóng ESP-IDF monitor/phần mềm serial khác. Mất USB: chương trình báo lỗi COM và kết thúc.
- API Firebase trả lỗi: kiểm tra Email/Password provider, API key/project, Rules thực tế; không mở quyền công khai để né lỗi.
- Nếu Console báo cần index, tạo index theo truy vấn ownerUid+rfidId bằng công cụ Firebase.
- Nội dung thẻ không phải credentials: chỉ UID được đọc. UID không phải bằng chứng xác thực an toàn chống sao chép.

## 7. Xác minh trong môi trường hỗ trợ

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_firebase_rfid
```

Kiểm thử tự động dùng phản hồi Firebase và Serial giả lập. Không thay thế kiểm thử Wi-Fi, tài khoản thật hoặc website thật.
Kết quả build firmware trong phiên triển khai được ghi riêng ở BUILD_VALIDATION.md; xem file đó để phân biệt build với nạp/chạy trên board.
Chưa xác minh 7 bài thử phần cứng/Firebase/website trên máy bạn. Không tuyên bố hệ thống hoàn thành trước khi có log thật.
