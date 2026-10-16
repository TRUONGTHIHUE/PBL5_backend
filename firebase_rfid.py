"""Read ESP32 serial events and query owner-scoped Firestore (no Render)."""
import argparse
import getpass
import os
import re
import time

import requests


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
            raise RuntimeError(f"Firebase HTTP {response.status_code}; kiểm tra đăng nhập, Rules và mạng")
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
        result = {k: fields.get(k, {}).get("stringValue", "")
                  for k in ("storeId", "storeName", "wifiSSID", "rfidId")}
        if any(not result[k].strip() for k in ("storeId", "storeName", "wifiSSID")):
            raise ValueError("MISSING_FIELDS: thiếu storeId, storeName hoặc wifiSSID")
        result["documentId"] = docs[0]["name"].rsplit("/", 1)[-1]
        return result


def display(client, uid):
    try:
        uid = normalize_uid(uid)
        store = client.lookup(uid)
        print("\n========== RFID DETECTED ==========", flush=True)
        for label, value in (("RFID UID", uid), ("STORE ID", store["storeId"]),
                             ("DOCUMENT ID", store["documentId"]), ("STORE NAME", store["storeName"]),
                             ("WIFI SSID", store["wifiSSID"]), ("DATA SOURCE", "Firebase Firestore"),
                             ("FETCH STATUS", "SUCCESS")):
            print(f"{label:13}: {value}")
        print("===================================", flush=True)
    except (ValueError, RuntimeError, requests.RequestException) as error:
        # requests exceptions can contain URLs; never print tokens or raw responses.
        detail = str(error) if isinstance(error, (ValueError, RuntimeError)) else "NETWORK_ERROR: không kết nối được Firebase"
        print(f"RFID UID: {uid}\nFETCH STATUS: FAILED\n{detail}", flush=True)
        return False
    return True


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
        if args.uid:
            return 0 if display(client, args.uid) else 1
        import serial
        with serial.Serial(args.port, args.baud, timeout=1) as device:
            print("Đã đăng nhập. Đang chờ quét thẻ...", flush=True)
            while True:
                line = device.readline().decode("utf-8", errors="replace").strip()
                if line.startswith("RFID_UID:"):
                    display(client, line.removeprefix("RFID_UID:"))
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, requests.RequestException):
        print("Không đăng nhập được Firebase. Kiểm tra tài khoản, API key và kết nối.")
        return 1
    except OSError:
        print("Không mở/đọc được cổng USB. Kiểm tra COM và đóng ESP-IDF monitor.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
