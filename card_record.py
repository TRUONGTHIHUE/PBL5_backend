"""P5W1 custom MIFARE 1K record; no Firebase or network access."""
import re
import zlib

RECORD_SIZE = 192
DATA_BLOCKS = tuple(4 + (i // 3) * 4 + i % 3 for i in range(12))


def normalize_card_uid(uid):
    compact = re.sub(r"[\s:-]", "", uid).upper()
    if len(compact) not in (8, 14, 20) or not re.fullmatch(r"[0-9A-F]+", compact):
        raise ValueError("UID cần 4, 7 hoặc 10 byte hex")
    return " ".join(compact[i:i + 2] for i in range(0, len(compact), 2))


def encode_record(store_id, ssid, password):
    values = (store_id, ssid, password)
    limits = ((1, 64), (1, 32), (0, 64))
    encoded = []
    for value, (minimum, maximum), field in zip(values, limits, ("storeId", "SSID", "password")):
        if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError(f"{field}: kiểu dữ liệu hoặc ký tự không hợp lệ")
        data = value.encode("utf-8")
        if not minimum <= len(data) <= maximum:
            raise ValueError(f"{field}: cần {minimum}–{maximum} byte UTF-8")
        encoded.append(data)
    length = len(encoded[2])
    if length and not (8 <= length <= 63 or re.fullmatch(r"[0-9A-Fa-f]{64}", password)):
        raise ValueError("Password: cần 8–63 byte hoặc 64 hex; rỗng chỉ dùng cho mạng mở")
    record = bytearray(RECORD_SIZE)
    record[:8] = b"P5W1\x01" + bytes(map(len, encoded))
    payload = b"".join(encoded)
    record[16:16 + len(payload)] = payload
    record[8:12] = zlib.crc32(record[:8] + record[12:]).to_bytes(4, "little")
    return bytes(record)


def decode_record(record):
    if len(record) != RECORD_SIZE or record[:5] != b"P5W1\x01":
        raise ValueError("Invalid P5W1 record")
    if int.from_bytes(record[8:12], "little") != zlib.crc32(record[:8] + record[12:]):
        raise ValueError("CRC mismatch")
    lengths = record[5:8]
    if not 1 <= lengths[0] <= 64 or not 1 <= lengths[1] <= 32 or lengths[2] > 64:
        raise ValueError("Invalid field lengths")
    offset = 16
    fields = []
    for length in lengths:
        fields.append(record[offset:offset + length].decode("utf-8"))
        offset += length
    # Reuse validation; no data is returned if any field is malformed.
    encode_record(*fields)
    return dict(zip(("storeId", "wifiSSID", "wifiPassword"), fields))
