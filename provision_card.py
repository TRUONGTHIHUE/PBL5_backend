"""Setup-only writer for a spare MIFARE 1K card. Never used by the end user."""
import argparse
import getpass
import json
import time
import uuid

from card_record import encode_record, normalize_card_uid

PREFIX = b"PBL5CARD:"


class ProvisionDecoder:
    def __init__(self):
        self.buffer = bytearray()
        self.discard = False

    def feed(self, data):
        messages = []
        for byte in data:
            if byte == 10:
                if not self.discard and self.buffer.startswith(PREFIX):
                    try:
                        value = json.loads(self.buffer[len(PREFIX):].decode("utf-8"))
                        if isinstance(value, dict) and type(value.get("v")) is int and value["v"] == 1:
                            messages.append(value)
                    except (ValueError, UnicodeError):
                        pass
                self.buffer.clear()
                self.discard = False
            elif byte == 0 or len(self.buffer) >= 1024:
                self.discard = True
            elif not self.discard:
                self.buffer.append(byte)
        return messages


def wait_messages(device, decoder, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        yield from decoder.feed(device.read(256))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--uid", required=True, help="UID thẻ dự phòng được phép ghi")
    parser.add_argument("--replace", action="store_true", help="Cho phép thay bản ghi P5W1 đã có; vẫn không ghi dữ liệu lạ")
    args = parser.parse_args()
    try:
        uid = normalize_card_uid(args.uid)
        store = input("storeId (giữ đúng mã trong Firestore): ").strip()
        ssid = input("Wi-Fi SSID thật: ")
        password = getpass.getpass("Wi-Fi password (ẩn, để rỗng nếu mạng mở): ")
        record = encode_record(store, ssid, password)
        del password
        print("Chỉ dùng thẻ dự phòng thuộc quyền của bạn. Ghi 192 byte vào sector 1–4.")
        print("Không ghi UID hoặc khóa. MIFARE Classic/khóa mặc định không bảo vệ mật khẩu cho sản phẩm thật.")
        if args.replace:
            print("--replace: bản ghi P5W1 cũ trên đúng thẻ sẽ được thay thế.")
        if input(f"Xác nhận bằng cách gõ WRITE {uid}: ").strip() != f"WRITE {uid}":
            print("Đã hủy; chưa mở cổng hoặc ghi thẻ.")
            return 1
        import serial
        with serial.Serial(args.port, 115200, timeout=0.2, write_timeout=2) as device:
            decoder = ProvisionDecoder()
            print("Nhấn EN/RESET trên ESP32 để công cụ xác nhận chế độ ghi. Chưa đặt thẻ lên đầu đọc.")
            ready = False
            for message in wait_messages(device, decoder, 30):
                if message.get("status") == "WRITER_READY":
                    ready = True
                    break
            if not ready:
                print("Không thấy WRITER_READY; chưa gửi dữ liệu. Kiểm tra firmware chế độ Setup only/COM.")
                return 1
            request_id = uuid.uuid4().hex
            frame = PREFIX + json.dumps({"v": 1, "type": "prepare", "requestId": request_id,
                "uid": uid, "recordHex": record.hex(), "replace": args.replace},
                separators=(",", ":")).encode() + b"\n"
            if device.write(frame) != len(frame):
                raise OSError("Incomplete serial write")
            # No payload/password logging. USB transport itself is not encrypted.
            for message in wait_messages(device, decoder, 100):
                if message.get("requestId") != request_id:
                    continue
                status = message.get("status")
                if status == "ARMED":
                    print(f"Đã sẵn sàng. Đặt đúng thẻ {uid} lên RC522, giữ yên đến kết quả.")
                elif status == "TARGET_MISMATCH":
                    print("Sai thẻ: không ghi. Lấy thẻ ra và đặt đúng thẻ mục tiêu.")
                elif status == "WRITE_VERIFIED":
                    print("WRITE_VERIFIED: đã đọc lại và xác nhận dữ liệu trên thẻ. Chưa xác nhận kết nối Wi-Fi.")
                    return 0
                elif status in {"EXPIRED", "BUSY", "UNSUPPORTED_CARD", "READ_OR_AUTH_FAILED",
                                "UNRECOGNIZED_DATA_NO_WRITE", "ALREADY_PROVISIONED_USE_REPLACE",
                                "WRITE_FAILED_REMOVE_AND_RECHECK"}:
                    print("Ghi chưa thành công: " + status)
                    return 1
            print("Hết thời gian chờ; không xác nhận thành công. Reset ESP32 trước lần thử tiếp theo.")
            return 1
    except KeyboardInterrupt:
        print("Đã dừng. Nếu đã ARMED, reset ESP32 ngay để hủy yêu cầu ghi đang chờ.")
        return 1
    except ValueError as error:
        print("Dữ liệu không hợp lệ: " + str(error))
        return 1
    except OSError:
        print("Lỗi COM/USB; đóng Serial Monitor, kiểm tra cáp và cổng. Reset ESP32 nếu đã ARMED.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
