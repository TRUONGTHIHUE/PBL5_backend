"""RFID USB bridge: authenticated Firestore lookup and real ESP32 Wi-Fi status."""
import argparse
import getpass
import json
import os
import re
import time

import requests

PREFIX = b"PBL5:"
FRAME_LIMIT = 2048
FINAL_STATUSES = {"WIFI_CONNECTED", "WIFI_FAILED", "WIFI_TIMEOUT", "WIFI_STOP_FAILED",
                  "INVALID_CONFIG", "LOOKUP_FAILED", "LOOKUP_TIMEOUT"}


class FirebaseError(RuntimeError):
    HINTS = {
        "INVALID_LOGIN_CREDENTIALS": "Email hoặc mật khẩu không đúng, hoặc tài khoản không tồn tại trong project này.",
        "EMAIL_NOT_FOUND": "Email chưa có trong Authentication → Users của project này.",
        "INVALID_PASSWORD": "Mật khẩu tài khoản Firebase không đúng; không dùng mật khẩu Wi-Fi.",
        "INVALID_EMAIL": "Định dạng email không hợp lệ.",
        "USER_DISABLED": "Tài khoản đã bị vô hiệu hóa trong Firebase Authentication.",
        "OPERATION_NOT_ALLOWED": "Kiểm tra Authentication → Sign-in method → Email/Password đã bật.",
        "PASSWORD_LOGIN_DISABLED": "Đăng nhập bằng mật khẩu chưa được cho phép.",
        "API_KEY_INVALID": "API key Web không hợp lệ; đối chiếu firebase/public/firebase-config.js.",
        "TOO_MANY_ATTEMPTS_TRY_LATER": "Firebase đang giới hạn đăng nhập; chờ rồi thử lại.",
        "PERMISSION_DENIED": "Không có quyền; kiểm tra Rules, ownerUid và cấu hình API key/project.",
        "UNAUTHENTICATED": "Phiên đăng nhập không hợp lệ; đăng nhập lại.",
        "FAILED_PRECONDITION": "Kiểm tra cấu hình Firestore và index của truy vấn trong Firebase Console.",
    }

    def __init__(self, status, code=None):
        self.status = int(status)
        self.code = code if code in self.HINTS else "UNKNOWN"
        hint = self.HINTS.get(self.code, "Kiểm tra đăng nhập, API key/project, quyền truy cập và mạng.")
        super().__init__(f"Firebase HTTP {self.status} ({self.code}): {hint}")


def text_bytes(value, field, minimum, maximum):
    if not isinstance(value, str) or not minimum <= len(value.encode("utf-8")) <= maximum:
        raise ValueError(f"INVALID_CONFIG: {field} phải dài {minimum}–{maximum} byte UTF-8")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"INVALID_CONFIG: {field} chứa ký tự điều khiển")
    return value


def validate_store(store):
    for field, maximum in (("storeId", 128), ("wifiSSID", 32)):
        text_bytes(store.get(field), field, 1, maximum)
    password = text_bytes(store.get("wifiPassword"), "wifiPassword", 0, 64)
    length = len(password.encode("utf-8"))
    if length and not (8 <= length <= 63 or re.fullmatch(r"[0-9A-Fa-f]{64}", password)):
        raise ValueError("INVALID_CONFIG: mật khẩu Wi-Fi cần 8–63 byte hoặc 64 ký tự hex")
    return store


class LineDecoder:
    """Keep partial packets; drain oversized frames through the next newline."""
    def __init__(self):
        self.buffer = bytearray()
        self.discard = False

    def feed(self, data):
        messages = []
        for byte in data:
            if byte == 10:
                if not self.discard and self.buffer.startswith(PREFIX):
                    try:
                        message = json.loads(self.buffer[len(PREFIX):].decode("utf-8"))
                        if isinstance(message, dict) and type(message.get("v")) is int and message["v"] == 1:
                            messages.append(message)
                    except (ValueError, UnicodeError):
                        pass
                self.buffer.clear()
                self.discard = False
            elif byte == 0 or len(self.buffer) >= FRAME_LIMIT:
                self.discard = True
            elif not self.discard:
                self.buffer.append(byte)
        return messages


def normalize_uid(value):
    compact = re.sub(r"[\s:-]", "", value).upper()
    if len(compact) not in (8, 14, 20) or not re.fullmatch(r"[0-9A-F]+", compact):
        raise ValueError("UID phải gồm 4, 7 hoặc 10 byte hex; ví dụ CD 4B 1E 03")
    return " ".join(compact[i:i + 2] for i in range(0, len(compact), 2))


class FirebaseClient:
    def __init__(self, api_key, project, email, password):
        self.api_key, self.project = api_key, project
        data = self._post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
            json={"email": email, "password": password, "returnSecureToken": True})
        self.owner = data["localId"]
        self._tokens(data["idToken"], data["refreshToken"], data["expiresIn"])

    @staticmethod
    def _post(url, **kwargs):
        response = requests.post(url, timeout=20, **kwargs)
        if not response.ok:
            # Do not expose request bodies, tokens, passwords or response documents.
            code = None
            try:
                payload = response.json()
                error = payload.get("error") if isinstance(payload, dict) else None
                if isinstance(error, dict):
                    for candidate in (error.get("message"), error.get("status")):
                        if isinstance(candidate, str) and candidate in FirebaseError.HINTS:
                            code = candidate
                            break
            except ValueError:
                pass
            raise FirebaseError(response.status_code, code)
        return response.json()

    def _tokens(self, token, refresh, seconds):
        self.token, self.refresh = token, refresh
        self.expires = time.monotonic() + int(seconds) - 60

    def lookup(self, uid):
        uid = normalize_uid(uid)
        if time.monotonic() >= self.expires:
            data = self._post(
                f"https://securetoken.googleapis.com/v1/token?key={self.api_key}",
                data={"grant_type": "refresh_token", "refresh_token": self.refresh})
            self._tokens(data["id_token"], data["refresh_token"], data["expires_in"])
        filters = [{"fieldFilter": {"field": {"fieldPath": field}, "op": "EQUAL",
                    "value": {"stringValue": value}}}
                   for field, value in (("ownerUid", self.owner), ("rfidId", uid))]
        rows = self._post(
            f"https://firestore.googleapis.com/v1/projects/{self.project}/databases/(default)/documents:runQuery",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"structuredQuery": {"from": [{"collectionId": "stores"}],
                  "where": {"compositeFilter": {"op": "AND", "filters": filters}}, "limit": 2}})
        docs = [row["document"] for row in rows if "document" in row]
        if not docs:
            raise ValueError("NOT_FOUND: tài khoản này chưa có cửa hàng gắn với UID này")
        if len(docs) != 1:
            raise ValueError("DUPLICATE_UID: có nhiều cửa hàng cùng UID; cần sửa dữ liệu")
        fields = docs[0].get("fields", {})
        result = {k: fields.get(k, {}).get("stringValue")
                  for k in ("storeId", "storeName", "wifiSSID", "rfidId", "wifiPassword")}
        if any(not isinstance(result[k], str) or not result[k].strip()
               for k in ("storeId", "wifiSSID")) or not isinstance(result["wifiPassword"], str):
            raise ValueError("MISSING_FIELDS: thiếu storeId, wifiSSID hoặc wifiPassword")
        result["documentId"] = docs[0]["name"].rsplit("/", 1)[-1]
        return validate_store(result)


def show_store(uid, store):
    # Intentional demo output. Never save/share this terminal output publicly.
    print("\n========== THONG TIN CUA HANG ==========", flush=True)
    for label, field in (("Store ID", "storeId"), ("Wi-Fi SSID", "wifiSSID"),
                         ("Wi-Fi Password", "wifiPassword")):
        print(f"{label:15}: {store[field]}")
    print("========================================", flush=True)
    print(f"RFID UID     : {uid}")
    if store.get('documentId'):
        print(f"DOCUMENT ID  : {store['documentId']}")
    print("DATA SOURCE  : Firebase Firestore\nFETCH STATUS : SUCCESS", flush=True)


def display(client, uid):
    try:
        uid = normalize_uid(uid)
        store = validate_store(client.lookup(uid))
        show_store(uid, store)
    except (ValueError, RuntimeError, requests.RequestException) as error:
        # requests exceptions can contain URLs; never print tokens or raw responses.
        detail = str(error) if isinstance(error, (ValueError, RuntimeError)) else "NETWORK_ERROR: không kết nối được Firebase"
        print(f"RFID UID: {uid}\nFETCH STATUS: FAILED\n{detail}", flush=True)
        return False
    return True


class SerialBridge:
    def __init__(self, client, device, clock=time.monotonic):
        self.client, self.device, self.clock = client, device, clock
        self.pending = None

    def send(self, message):
        frame = PREFIX + json.dumps({"v": 1, **message}, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8") + b"\n"
        if len(frame) - 1 > FRAME_LIMIT:
            raise ValueError("FRAME_TOO_LARGE: bản tin vượt giới hạn Serial")
        if self.device.write(frame) != len(frame):
            raise OSError("Serial short write")

    def handle(self, message):
        kind = message.get("type")
        if kind == "ready":
            self.pending = None
            print("ESP32 READY; nếu đang xử lý, yêu cầu trước đã hủy do reset.", flush=True)
            return
        if kind == "busy":
            print("ESP32 đang xử lý thẻ trước. Chờ kết quả, lấy thẻ ra rồi quét lại.", flush=True)
            return
        if kind == "scan":
            request_id, uid = message.get("requestId"), message.get("uid")
            if not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{8}-[0-9]{1,10}", request_id):
                return
            try:
                canonical = normalize_uid(uid) if isinstance(uid, str) else None
                if canonical != uid:
                    raise ValueError("INVALID_UID")
            except ValueError:
                print("Bỏ qua bản tin UID không hợp lệ.", flush=True)
                return
            if self.pending:
                print("Bỏ qua scan mới khi chưa có kết quả; hãy chờ hoặc reset ESP32.", flush=True)
                return
            base = {"requestId": request_id, "uid": uid}
            self.pending = {**base, "acked": False, "deadline": self.clock() + 55,
                            "state": "LOOKUP"}
            try:
                store = validate_store(self.client.lookup(uid))
            except (ValueError, RuntimeError, requests.RequestException) as error:
                # No exception bodies, document contents, credentials or raw serial are logged.
                code = str(error).split(":", 1)[0] if isinstance(error, ValueError) else "FIREBASE_ERROR"
                allowed = {"NOT_FOUND", "DUPLICATE_UID", "MISSING_FIELDS", "INVALID_CONFIG"}
                code = code if code in allowed else "NETWORK_OR_FIREBASE_ERROR"
                if isinstance(error, FirebaseError):
                    code = f"FIREBASE_HTTP_{error.status}"
                hint = {
                    "NOT_FOUND": "Không tìm thấy thẻ trong các cửa hàng tài khoản được phép đọc.",
                    "DUPLICATE_UID": "Có nhiều cửa hàng gắn cùng UID; cần sửa dữ liệu trùng.",
                    "MISSING_FIELDS": "Bản ghi thiếu thông tin cửa hàng hoặc Wi-Fi.",
                    "INVALID_CONFIG": "Thông tin cửa hàng hoặc SSID/mật khẩu Wi-Fi không hợp lệ.",
                }.get(code, "Kiểm tra kết nối Internet, đăng nhập và quyền Firebase.")
                print(f"RFID UID: {uid}\nFETCH STATUS: FAILED ({code})\n{hint}", flush=True)
                self.send({**base, "type": "lookup_error"})
                self.pending.update(deadline=self.clock() + 8, state="ERROR_REPLY")
                return
            show_store(uid, store)
            self.send({**base, "type": "store_config", **{
                field: store[field] for field in ("storeId", "wifiSSID", "wifiPassword")}})
            self.pending.update(deadline=self.clock() + 8, state="WAIT_ACK", storeId=store['storeId'])
            print("Đã gửi cấu hình qua USB. Chưa xác nhận ESP32 nhận hoặc kết nối Wi-Fi.", flush=True)
            return
        if kind != "status" or not self.pending:
            return
        if any(message.get(key) != self.pending[key] for key in ("requestId", "uid")):
            return  # A previous scan/session must not change the current result.
        status = message.get("status")
        if status not in FINAL_STATUSES | {"CONFIG_RECEIVED", "WIFI_CONNECTING"}:
            return
        if status in {"CONFIG_RECEIVED", "WIFI_CONNECTING", "WIFI_CONNECTED"} and (
                message.get("storeId") != self.pending.get("storeId") or "storeId" not in self.pending):
            print("ESP32_STORE_MISMATCH: phản hồi không khớp storeId đã gửi; chưa xác nhận thành công.", flush=True)
            return
        print("ESP32 STATUS : " + status, flush=True)
        if status == "WIFI_CONNECTED":
            print("CURRENT STORE: " + self.pending['storeId'], flush=True)
        if status in FINAL_STATUSES:
            self.pending = None
        elif status == "CONFIG_RECEIVED":
            self.pending.update(acked=True, deadline=self.clock() + 35, state="WAIT_WIFI")

    def tick(self):
        if self.pending and self.clock() >= self.pending["deadline"]:
            status = "ESP32_RESULT_TIMEOUT" if self.pending["acked"] else "ESP32_ACK_TIMEOUT"
            print(status + ": chưa xác nhận thành công; kiểm tra firmware/COM rồi quét lại.", flush=True)
            self.pending = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Cổng ESP32, ví dụ COM5")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--uid", help="Thử truy vấn Firebase bằng UID thật, không cần ESP32")
    parser.add_argument("--email", default=os.getenv("FIREBASE_EMAIL"))
    parser.add_argument("--project", default="quanlycuahang-afb59")
    args = parser.parse_args()
    if not args.uid and not args.port:
        parser.error("Cần --port COMx hoặc --uid 'CD 4B 1E 03'")
    key = os.getenv("FIREBASE_WEB_API_KEY")
    if not key:
        parser.error("Đặt FIREBASE_WEB_API_KEY bằng apiKey trong public/firebase-config.js")
    email = args.email or input("Email Firebase: ").strip()
    password = getpass.getpass("Mật khẩu Firebase (không hiển thị): ")
    try:
        client = FirebaseClient(key, args.project, email, password)
        del password
        print(f"Đã đăng nhập Firebase. User UID: {client.owner}", flush=True)
        if args.uid:
            return 0 if display(client, args.uid) else 1
        import serial
        with serial.Serial(args.port, args.baud, timeout=0.2, write_timeout=2) as device:
            print("Đã đăng nhập. Đang chờ quét thẻ...", flush=True)
            decoder = LineDecoder()
            bridge = SerialBridge(client, device)
            while True:
                for message in decoder.feed(device.read(256)):
                    bridge.handle(message)
                bridge.tick()
    except KeyboardInterrupt:
        return 0
    except FirebaseError as error:
        print(str(error))
        return 1
    except requests.exceptions.SSLError:
        print("FIREBASE_TLS_ERROR: kiểm tra chứng chỉ HTTPS, ngày giờ Windows hoặc proxy; không tắt xác minh TLS.")
        return 1
    except requests.exceptions.Timeout:
        print("FIREBASE_TIMEOUT: Firebase không phản hồi trong thời gian chờ; kiểm tra Internet.")
        return 1
    except requests.exceptions.ConnectionError:
        print("FIREBASE_NETWORK_ERROR: không kết nối được Firebase; kiểm tra Internet, proxy hoặc tường lửa.")
        return 1
    except (RuntimeError, ValueError, requests.RequestException):
        print("Lỗi Firebase/dữ liệu. Kiểm tra tài khoản, API key, trường dữ liệu và kết nối.")
        return 1
    except OSError:
        print("Không mở/đọc được cổng USB. Kiểm tra COM và đóng ESP-IDF monitor.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
