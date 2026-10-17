import ctypes
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zlib

from card_record import DATA_BLOCKS, decode_record, encode_record, normalize_card_uid
from provision_card import ProvisionDecoder


class RecordTests(unittest.TestCase):
    def test_roundtrip(self):
        record = encode_record('firestore-doc-id', 'Wi-Fi thử', 'test-only-password')
        self.assertEqual(len(record), 192)
        self.assertEqual(decode_record(record), {'storeId': 'firestore-doc-id',
            'wifiSSID': 'Wi-Fi thử', 'wifiPassword': 'test-only-password'})

    def test_no_manufacturer_or_trailer_blocks(self):
        self.assertEqual(DATA_BLOCKS, (4, 5, 6, 8, 9, 10, 12, 13, 14, 16, 17, 18))
        self.assertEqual(len(set(DATA_BLOCKS)), 12)
        self.assertTrue(all(block != 0 and block % 4 != 3 for block in DATA_BLOCKS))

    def test_corruption_and_blank_never_decode(self):
        for record in (bytes(192), bytes([255]) * 192):
            with self.assertRaises(ValueError):
                decode_record(record)
        record = encode_record('store', 'ssid', 'test-only-password')
        for i in range(192):
            changed = bytearray(record)
            changed[i] ^= 1
            with self.subTest(byte=i), self.assertRaises(ValueError):
                decode_record(changed)

    def test_lengths_password_and_control_chars(self):
        for values in [('', 'ssid', '12345678'), ('s' * 65, 'ssid', '12345678'),
                       ('store', 'ệ' * 11, '12345678'), ('store', 'ssid', 'short'),
                       ('store', 'ssid', 'z' * 64), ('store', 'ssid', 'abc\x00defgh')]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                encode_record(*values)
        self.assertEqual(decode_record(encode_record('store', 'open', ''))['wifiPassword'], '')

    def test_uid_canonicalization(self):
        self.assertEqual(normalize_card_uid('cd:4b:1e:03'), 'CD 4B 1E 03')
        with self.assertRaises(ValueError):
            normalize_card_uid('email@example.com')

    def test_provision_serial_partial_and_noise(self):
        packet = {'v': 1, 'type': 'provision_status', 'status': 'WRITE_VERIFIED'}
        stream = b'boot\nPBL5CARD:' + json.dumps(packet).encode() + b'\n'
        decoder = ProvisionDecoder()
        messages = []
        for byte in stream:
            messages.extend(decoder.feed(bytes([byte])))
        self.assertEqual(messages, [packet])

    def test_provision_serial_oversized_then_valid(self):
        decoder = ProvisionDecoder()
        self.assertEqual(decoder.feed(b'PBL5CARD:' + b'x' * 1100 + b'\n'), [])
        self.assertEqual(decoder.feed(b'PBL5CARD:{"v":1,"status":"ARMED"}\n'),
                         [{'v': 1, 'status': 'ARMED'}])


class Config(ctypes.Structure):
    _fields_ = [('store_id', ctypes.c_char * 65), ('ssid', ctypes.c_char * 33),
                ('password', ctypes.c_char * 65)]


@unittest.skipUnless(shutil.which('gcc'), 'C codec cross-check requires gcc on the test host')
class CCodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        source = Path(__file__).parent / 'RFID/RFID/main/card_record.c'
        library = Path(cls.temp.name) / 'codec.so'
        subprocess.run(['gcc', '-std=gnu11', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                        str(source), '-o', str(library)], check=True)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.card_record_encode.argtypes = [ctypes.POINTER(Config), ctypes.c_void_p]
        cls.lib.card_record_encode.restype = ctypes.c_bool
        cls.lib.card_record_decode.argtypes = [ctypes.c_void_p, ctypes.POINTER(Config)]
        cls.lib.card_record_decode.restype = ctypes.c_bool
        cls.lib.card_data_block.argtypes = [ctypes.c_uint]
        cls.lib.card_data_block.restype = ctypes.c_uint8
        # Compile the real storage code against a tiny in-memory card driver.
        # This checks write boundaries, commit order, read-back and crypto-session lifetime.
        stub = Path(cls.temp.name)
        (stub / 'picc').mkdir()
        (stub / 'rc522.h').write_text('''#pragma once
#include <stdint.h>
typedef void *rc522_handle_t;
typedef int esp_err_t;
typedef struct { int type; } rc522_picc_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_NOT_SUPPORTED -2
#define ESP_ERR_INVALID_ARG -3
#define RC522_PICC_TYPE_MIFARE_1K 1
''')
        (stub / 'rc522_picc.h').write_text('#pragma once\n#include "rc522.h"\n')
        (stub / 'picc/rc522_mifare.h').write_text('''#pragma once
#include "rc522.h"
#define RC522_MIFARE_KEY_A 0
#define RC522_MIFARE_KEY_VALUE_DEFAULT 255,255,255,255,255,255
typedef struct { int type; uint8_t value[6]; } rc522_mifare_key_t;
esp_err_t rc522_mifare_auth(rc522_handle_t,const rc522_picc_t*,uint8_t,const rc522_mifare_key_t*);
esp_err_t rc522_mifare_read(rc522_handle_t,const rc522_picc_t*,uint8_t,uint8_t*);
esp_err_t rc522_mifare_write(rc522_handle_t,const rc522_picc_t*,uint8_t,const uint8_t*);
esp_err_t rc522_mifare_deauth(rc522_handle_t,const rc522_picc_t*);
''')
        (stub / 'fake.c').write_text('''#include <string.h>
#include "picc/rc522_mifare.h"
static uint8_t memory[64][16], addresses[32];
static int writes, sector, finished, fail_at;
void fake_reset(void) { memset(memory,0,sizeof(memory));
 for(int i=0;i<64;i++) if(i==0||i%4==3) memset(memory[i],0x5a,16);
 writes=0;sector=-1;finished=0;fail_at=-1; }
void fake_fail_at(int n) { fail_at=n; }
int fake_writes(void) { return writes; }
int fake_finished(void) { return finished; }
int fake_address(int i) { return addresses[i]; }
int fake_byte(int b,int n) { return memory[b][n]; }
esp_err_t rc522_mifare_auth(rc522_handle_t h,const rc522_picc_t*p,uint8_t b,const rc522_mifare_key_t*k)
 { (void)h;(void)p;(void)k;sector=b/4;return 0; }
esp_err_t rc522_mifare_read(rc522_handle_t h,const rc522_picc_t*p,uint8_t b,uint8_t*d)
 { (void)h;(void)p;if(b>=64||sector!=b/4)return -1;memcpy(d,memory[b],16);return 0; }
esp_err_t rc522_mifare_write(rc522_handle_t h,const rc522_picc_t*p,uint8_t b,const uint8_t*d)
 { (void)h;(void)p;if(b==0||b>=64||b%4==3||sector!=b/4)return -1;
 if(writes==fail_at) { return -1; }
 addresses[writes++]=b;memcpy(memory[b],d,16);return 0; }
esp_err_t rc522_mifare_deauth(rc522_handle_t h,const rc522_picc_t*p)
 { (void)h;(void)p;sector=-1;finished++;return 0; }
''')
        storage_library = stub / 'storage.so'
        subprocess.run(['gcc', '-std=gnu11', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                        '-I', str(stub), str(source), str(source.parent / 'card_storage.c'), str(stub / 'fake.c'),
                        '-o', str(storage_library)], check=True)
        cls.storage = ctypes.CDLL(str(storage_library))
        for name in ('card_storage_read', 'card_storage_write'):
            function = getattr(cls.storage, name)
            function.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
            function.restype = ctypes.c_int
        cls.storage.card_storage_finish.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_python_and_firmware_use_identical_layout_and_crc(self):
        for fields in [('store', 'ssid', 'test-only-password'), ('s' * 64, 'n' * 32, 'a' * 64),
                       ('store', 'Wi-Fi thử', ''), ('STORE03', 'same-network', 'another-test-password')]:
            expected = encode_record(*fields)
            config = Config(*(field.encode('utf-8') for field in fields))
            encoded = ctypes.create_string_buffer(192)
            self.assertTrue(self.lib.card_record_encode(ctypes.byref(config), encoded))
            self.assertEqual(encoded.raw, expected)
            decoded = Config()
            self.assertTrue(self.lib.card_record_decode(encoded, ctypes.byref(decoded)))
            self.assertEqual([bytes(getattr(decoded, key)).decode() for key in ('store_id', 'ssid', 'password')], list(fields))

    def test_firmware_rejects_corruption_and_embedded_nul(self):
        record = bytearray(encode_record('store', 'ssid', 'test-only-password'))
        record[16] = 0
        record[8:12] = zlib.crc32(record[:8] + record[12:]).to_bytes(4, 'little')
        self.assertFalse(self.lib.card_record_decode(ctypes.create_string_buffer(bytes(record)), ctypes.byref(Config())))
        for i in range(192):
            changed = bytearray(encode_record('store', 'ssid', 'test-only-password'))
            changed[i] ^= 1
            self.assertFalse(self.lib.card_record_decode(ctypes.create_string_buffer(bytes(changed)), ctypes.byref(Config())))

    def test_firmware_mapping_matches_safe_python_blocks(self):
        self.assertEqual(tuple(self.lib.card_data_block(i) for i in range(12)), DATA_BLOCKS)
        self.assertEqual(self.lib.card_data_block(12), 255)

    def test_write_commits_header_last_and_never_touches_keys(self):
        self.storage.fake_reset()
        picc = ctypes.c_int(1)
        record = encode_record('store', 'ssid', 'test-only-password')
        self.assertEqual(self.storage.card_storage_write(1, ctypes.byref(picc), ctypes.create_string_buffer(record)), 0)
        writes = [self.storage.fake_address(i) for i in range(self.storage.fake_writes())]
        self.assertEqual(writes, [4, *DATA_BLOCKS[1:], 4])
        self.assertEqual(self.storage.fake_finished(), 0)
        self.storage.card_storage_finish(1, ctypes.byref(picc))
        self.assertEqual(self.storage.fake_finished(), 1)
        for block in (0, *range(3, 64, 4)):
            self.assertTrue(all(self.storage.fake_byte(block, i) == 0x5a for i in range(16)))

    def test_failed_write_leaves_record_invalid(self):
        self.storage.fake_reset()
        self.storage.fake_fail_at(5)
        picc = ctypes.c_int(1)
        record = encode_record('store', 'ssid', 'test-only-password')
        self.assertNotEqual(self.storage.card_storage_write(1, ctypes.byref(picc), ctypes.create_string_buffer(record)), 0)
        actual = ctypes.create_string_buffer(192)
        self.assertEqual(self.storage.card_storage_read(1, ctypes.byref(picc), actual), 0)
        with self.assertRaises(ValueError):
            decode_record(actual.raw)
        self.storage.card_storage_finish(1, ctypes.byref(picc))

    def test_wrong_card_type_never_writes(self):
        self.storage.fake_reset()
        picc = ctypes.c_int(99)
        self.assertNotEqual(self.storage.card_storage_write(1, ctypes.byref(picc), ctypes.create_string_buffer(192)), 0)
        self.assertEqual(self.storage.fake_writes(), 0)


if __name__ == '__main__':
    unittest.main()
