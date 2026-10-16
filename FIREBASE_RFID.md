# Demo RFID → Firebase → Terminal Python

Website Firebase từ ZIP đã được tích hợp tại `firebase/` trong repository này.
Các file giao diện được sửa là `firebase/public/products.js` và `firebase/public/product.html`.
Khi deploy, mở PowerShell tại `PBL5_backend/firebase/` (nơi có firebase.json).
Mã firmware và Python vẫn nằm ở các đường dẫn bên dưới. Không cần tải ZIP hoặc tạo lại từng file khi dùng Git.

Luồng mới: RC522 → ESP32 → USB serial → Python đăng nhập Firebase Authentication → Firestore stores.
Render không tham gia luồng RFID này. Đây là demo cần USB, KHÔNG phải ESP32 kết nối trực tiếp Firebase qua Wi-Fi.
PBL5_render_api được giữ để các chức năng PHP/CSV và mã vạch cũ tiếp tục dùng. Chưa chuyển sản phẩm sang Firebase.

## 1. Chuẩn bị dữ liệu trên Firebase Console

Không tạo lại tài liệu hoặc đổi ID ngẫu nhiên. Với mỗi cửa hàng, sửa `rfidId` đúng thẻ:

| Cửa hàng demo | rfidId |
|---|---|
| STORE01 | CD 4B 1E 03 |
| STORE02 | F0 78 0E 04 |
| STORE03 | C7 9A 0C 03 |

Mỗi tài liệu cần các trường string: ownerUid, rfidId, storeId, storeName, wifiSSID.
ownerUid phải bằng UID tài khoản Firebase Authentication sẽ đăng nhập trong Python.
storeId có thể giữ ID ngẫu nhiên hiện tại. Không thay bằng mã STORE001 của firmware.
Tên cửa hàng ở bảng chỉ là tên demo, không phải dữ liệu đọc từ thẻ.
Giữ Rules hiện có, không mở read/write công khai. Không cần service-account key.
Python chỉ truy vấn cửa hàng thuộc tài khoản đăng nhập. UID phải lưu đúng dạng có khoảng trắng và chữ hoa.
Website chặn UID trùng trong tài khoản ở mức form; chưa có ràng buộc duy nhất nguyên tử phía server.

## 2. Nạp firmware — Terminal ESP-IDF 5.4.4

Chép main.c và Kconfig.projbuild trong gói vào PBL5_backend/RFID/RFID/main/.
Giữ nguyên CMakeLists.txt, thư viện RC522 và các file khác.
Mở thư mục PBL5_backend/RFID/RFID trong VS Code với ESP-IDF 5.4.4 đã cấu hình.
Dùng thư mục build mới vì build_http trong repo có đường dẫn từ máy khác:

```powershell
idf.py -B build_firebase menuconfig
```

Trong `PBL5 RFID transport`, bật `Send RFID over USB to the Python Firebase client` (mặc định bật), lưu cấu hình.

```powershell
idf.py -B build_firebase build
idf.py -B build_firebase -p COM5 flash monitor
```

Thay COM5 bằng cổng thật. Thử quét thẻ: cần có dòng `RFID_UID:CD 4B 1E 03` tương ứng thẻ.
Nếu build lỗi, gửi phần lỗi đầu tiên và khoảng 20 dòng xung quanh; chưa coi firmware đã đạt nếu chỉ tải file.
Thoát monitor bằng Ctrl+] trước khi chạy Python: một cổng COM không mở cùng lúc ở hai terminal.
Chân giữ nguyên: MISO19, MOSI23, SCLK18, SS5, RST22. Không cần Wi-Fi ESP32 ở chế độ USB.
Không in hoặc truyền mật khẩu Wi-Fi. Cấu hình Wi-Fi cũ đã bỏ khỏi mã nguồn và chuyển sang menuconfig cho chế độ Render cũ; không commit sdkconfig chứa thông tin thật.

## 3. Chạy Python — PowerShell thường, tại PBL5_backend

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-firebase.txt
$env:FIREBASE_WEB_API_KEY = "API_KEY_WEB_TRONG_public/firebase-config.js"
```

Thay giá trị mẫu bằng apiKey Web của project. Không dùng private key/service-account key.
Kiểm tra truy vấn thật trước, không cần cắm ESP32:

```powershell
.\.venv\Scripts\python.exe firebase_rfid.py --uid "CD 4B 1E 03"
```

Nhập email tài khoản chủ cửa hàng, sau đó mật khẩu ở lời nhắc ẩn. Không đưa mật khẩu vào lệnh hoặc file.
SUCCESS chỉ in sau khi Firestore trả đúng một cửa hàng của tài khoản, có đủ trường.
Nếu thành công, chạy nhận thẻ:

```powershell
.\.venv\Scripts\python.exe firebase_rfid.py --port COM5
```

Nhập lại đăng nhập. Quét từng thẻ và đối chiếu UID, storeId, documentId, storeName, wifiSSID với Firestore Console.
DATA SOURCE = Firebase Firestore; FETCH STATUS = SUCCESS chỉ sau truy vấn thành công. Không in wifiPassword.
Không chuyển Wi-Fi ESP32 và không chứng minh Wi-Fi cửa hàng hoạt động.
Ctrl+C để dừng. Rút/cắm USB có thể reset ESP32, chương trình sẽ chờ dòng RFID_UID tiếp theo.

## 4. Website Firebase — PowerShell tại thư mục Firebase có firebase.json

Thay đúng public/products.js và public/product.html bằng hai file trong gói. Bản sửa kiểm tra UID 4/7/10 byte,
chuẩn hóa chữ hoa/dấu cách, chặn email, kiểm tra thẻ trùng trong tài khoản. Không tự sửa dữ liệu đã lưu.

```powershell
firebase deploy --only hosting --project quanlycuahang-afb59
```

Chạy lệnh này khi muốn xuất bản thay đổi trên website. Không cần đổi Rules nếu Rules trong ZIP đang được áp dụng.
Sau deploy, Ctrl+F5 rồi thử nhập email vào ô RFID: phải báo lỗi và không tạo cửa hàng.
Không tạo thêm cửa hàng dùng UID đã gán. Nếu cần đổi bản ghi cũ, sửa đúng rfidId trong Console trước.

## 5. Chẩn đoán

- NOT_FOUND: kiểm tra rfidId đúng định dạng và ownerUid thuộc tài khoản đăng nhập.
- DUPLICATE_UID: sửa dữ liệu trùng, không tự chọn cửa hàng bất kỳ.
- MISSING_FIELDS: bổ sung trường được nêu trong lỗi trên tài liệu tương ứng.
- HTTP 400 lúc đăng nhập: kiểm tra API key Web, email/password và Email/Password provider.
- HTTP 403 lúc truy vấn: kiểm tra Rules thực tế, quyền ownerUid và cấu hình API/project.
- Mạng: máy chạy Python cần HTTPS tới identitytoolkit.googleapis.com, securetoken.googleapis.com và firestore.googleapis.com.
- Nếu Firebase báo cần index, dùng thông báo Firebase Console để tạo index phù hợp; không mở Rules để né lỗi.
- COM bận: đóng ESP-IDF monitor hoặc phần mềm serial khác. Không thấy UID: xác minh firmware mới đã nạp và đúng COM/baud115200.

Gửi log lỗi Python, dòng RFID_UID và log build/flash liên quan nếu chưa chạy được; che token, mật khẩu và dữ liệu nhạy cảm.

## Trạng thái xác minh

Đã kiểm thử logic Python bằng phản hồi giả lập: chuẩn hóa UID, lọc ownerUid+rfidId, ID ngẫu nhiên,
không in mật khẩu, không tìm thấy, trùng UID, thiếu trường, lỗi quyền. JavaScript đã kiểm tra cú pháp.
Chưa build firmware bằng ESP-IDF, chưa thử phần cứng hoặc đăng nhập Firebase thật trong môi trường hỗ trợ này.
Chưa triển khai trực tiếp ESP32 → Firebase qua Wi-Fi, chưa chuyển API sản phẩm/YOLO/TTS.
