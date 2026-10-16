import unittest
import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch, Mock

import requests
from firebase_rfid import (FirebaseClient, normalize_uid, display, SerialBridge,
                           LineDecoder, validate_store, FRAME_LIMIT)


def response(data, status=200):
    return Mock(ok=status == 200, status_code=status, json=lambda: data)


class FirebaseTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(normalize_uid('cd:4b:1e:03'), 'CD 4B 1E 03')
        with self.assertRaises(ValueError):
            normalize_uid('person@example.com')

    def client(self, rows):
        fake = patch('firebase_rfid.requests.post', side_effect=[
            response({'localId': 'owner', 'idToken': 'token', 'refreshToken': 'refresh', 'expiresIn': '3600'}),
            response(rows)])
        request = fake.start()
        self.addCleanup(fake.stop)
        return FirebaseClient('web-key', 'project', 'email', 'password'), request

    def document(self):
        return {'document': {'name': 'projects/project/databases/(default)/documents/stores/random-id',
            'fields': {k: {'stringValue': v} for k, v in {
                'storeId': 'random-id', 'storeName': 'Store', 'wifiSSID': 'demo',
                'rfidId': 'CD 4B 1E 03', 'wifiPassword': 'never-print'}.items()}}}

    def test_owner_scoped_lookup(self):
        client, request = self.client([self.document()])
        result = client.lookup('CD 4B 1E 03')
        self.assertEqual(result['storeId'], 'random-id')
        self.assertEqual(result['wifiPassword'], 'never-print')
        filters = request.call_args.kwargs['json']['structuredQuery']['where']['compositeFilter']['filters']
        self.assertEqual(filters[0]['fieldFilter']['value'], {'stringValue': 'owner'})
        self.assertEqual(filters[1]['fieldFilter']['value'], {'stringValue': 'CD 4B 1E 03'})

    def test_not_found(self):
        client, _ = self.client([{'readTime': 'now'}])
        with self.assertRaisesRegex(ValueError, 'NOT_FOUND'):
            client.lookup('CD 4B 1E 03')

    def test_duplicate(self):
        client, _ = self.client([self.document(), self.document()])
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_UID'):
            client.lookup('CD 4B 1E 03')

    def test_missing_fields(self):
        doc = self.document()
        del doc['document']['fields']['wifiSSID']
        client, _ = self.client([doc])
        with self.assertRaisesRegex(ValueError, 'MISSING_FIELDS'):
            client.lookup('CD 4B 1E 03')

    def test_permission_denied_does_not_expose_body(self):
        with patch('firebase_rfid.requests.post', return_value=response({'secret': 'hidden'}, 403)):
            with self.assertRaisesRegex(RuntimeError, 'HTTP 403'):
                FirebaseClient('key', 'project', 'email', 'password')

    def test_token_refresh(self):
        client, request = self.client([])
        client.expires = 0
        request.side_effect = [response({'id_token': 'new', 'refresh_token': 'new-refresh', 'expires_in': '3600'}),
                               response([self.document()])]
        client.lookup('CD 4B 1E 03')
        self.assertEqual(request.call_args.kwargs['headers']['Authorization'], 'Bearer new')


class ProtocolTests(unittest.TestCase):
    uid = 'CD 4B 1E 03'
    request_id = '1234abcd-1'

    def setUp(self):
        self.store = {'storeId': 'random', 'documentId': 'random', 'storeName': 'Cửa hàng',
                      'wifiSSID': 'A real SSID', 'wifiPassword': 'secret-test-password'}
        self.device = Mock()
        self.device.write.side_effect = lambda frame: len(frame)
        self.client = Mock()
        self.client.lookup.return_value = self.store
        self.now = 0
        self.bridge = SerialBridge(self.client, self.device, lambda: self.now)
        self.scan = {'v': 1, 'type': 'scan', 'requestId': self.request_id, 'uid': self.uid}
        self.output = io.StringIO()
        self.capture = redirect_stdout(self.output)
        self.capture.__enter__()
        self.addCleanup(self.capture.__exit__, None, None, None)

    def status(self, status, request_id=None):
        self.bridge.handle({'v': 1, 'type': 'status', 'requestId': request_id or self.request_id,
                            'uid': self.uid, 'status': status})

    def test_partial_serial_and_noise(self):
        decoder = LineDecoder()
        frame = b'boot log\r\nPBL5:' + json.dumps(self.scan).encode() + b'\r\n'
        messages = []
        for byte in frame:
            messages += decoder.feed(bytes([byte]))
        self.assertEqual(messages, [self.scan])

    def test_oversized_frame_drained_and_next_frame_survives(self):
        decoder = LineDecoder()
        frame = b'PBL5:' + b'x' * FRAME_LIMIT + b'\nPBL5:' + json.dumps(self.scan).encode() + b'\n'
        self.assertEqual(decoder.feed(frame), [self.scan])

    def test_truncated_invalid_and_wrong_version_do_not_create_scan(self):
        decoder = LineDecoder()
        self.assertEqual(decoder.feed(b'PBL5:{"v":1'), [])
        self.assertEqual(decoder.feed(b'\nPBL5:{"v":2}\nPBL5:null\n'), [])

    def test_roundtrip_needs_real_connected_status(self):
        self.bridge.handle(self.scan)
        sent = self.device.write.call_args.args[0]
        packet = json.loads(sent[5:])
        self.assertEqual(packet['type'], 'store_config')
        self.assertEqual(packet['wifiPassword'], self.store['wifiPassword'])
        self.assertTrue(sent.endswith(b'\n'))
        self.assertNotIn('WIFI_CONNECTED', self.output.getvalue())
        self.assertIn('Wi-Fi Password : ' + self.store['wifiPassword'], self.output.getvalue())
        self.status('CONFIG_RECEIVED')
        self.assertTrue(self.bridge.pending['acked'])
        self.status('WIFI_CONNECTED')
        self.assertIsNone(self.bridge.pending)
        self.assertIn('WIFI_CONNECTED', self.output.getvalue())

    def test_stale_response_cannot_complete_new_request(self):
        self.bridge.handle(self.scan)
        self.status('WIFI_CONNECTED', 'old-session')
        self.assertIsNotNone(self.bridge.pending)
        self.assertNotIn('WIFI_CONNECTED', self.output.getvalue())

    def test_duplicate_scan_is_not_queried_twice(self):
        self.bridge.handle(self.scan)
        self.bridge.handle(self.scan)
        self.client.lookup.assert_called_once_with(self.uid)

    def test_timeout_without_ack(self):
        self.bridge.handle(self.scan)
        self.now = 9
        self.bridge.tick()
        self.assertIn('ESP32_ACK_TIMEOUT', self.output.getvalue())
        self.assertIsNone(self.bridge.pending)

    def test_timeout_after_ack(self):
        self.bridge.handle(self.scan)
        self.status('CONFIG_RECEIVED')
        self.now = 36
        self.bridge.tick()
        self.assertIn('ESP32_RESULT_TIMEOUT', self.output.getvalue())

    def test_no_wifi_success_on_failure(self):
        self.bridge.handle(self.scan)
        self.status('WIFI_FAILED')
        self.assertIsNone(self.bridge.pending)
        self.assertNotIn('WIFI_CONNECTED', self.output.getvalue())

    def test_network_error_replied_without_leaking_exception(self):
        self.client.lookup.side_effect = requests.ConnectionError('secret-exception')
        self.bridge.handle(self.scan)
        packet = json.loads(self.device.write.call_args.args[0][5:])
        self.assertEqual(packet['type'], 'lookup_error')
        self.assertNotIn('secret-exception', self.output.getvalue())

    def test_missing_password_and_ssid_byte_limit(self):
        for field, value in [('wifiPassword', None), ('wifiSSID', 'a' * 33),
                             ('wifiPassword', 'short'), ('wifiPassword', 'z' * 64)]:
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    validate_store({**self.store, field: value})
        self.assertEqual(validate_store({**self.store, 'wifiPassword': ''})['wifiPassword'], '')

    def test_unicode_ssid_limit_is_bytes_not_characters(self):
        with self.assertRaises(ValueError):
            validate_store({**self.store, 'wifiSSID': 'ệ' * 11})

    def test_short_write_is_an_error(self):
        self.device.write.side_effect = lambda frame: len(frame) - 1
        with self.assertRaises(OSError):
            self.bridge.handle(self.scan)

    def test_reset_cancels_pending_request(self):
        self.bridge.handle(self.scan)
        self.bridge.handle({'v': 1, 'type': 'ready'})
        self.assertIsNone(self.bridge.pending)

    def test_three_cards_keep_separate_store_configs(self):
        cards = ['CD 4B 1E 03', 'F0 78 0E 04', 'C7 9A 0C 03']
        records = {uid: {**self.store, 'storeId': f'store-{i}', 'wifiSSID': f'network-{i}'}
                   for i, uid in enumerate(cards)}
        self.client.lookup.side_effect = records.__getitem__
        for i, uid in enumerate(cards):
            request_id = f'1234abcd-{i + 1}'
            self.bridge.handle({**self.scan, 'uid': uid, 'requestId': request_id})
            packet = json.loads(self.device.write.call_args.args[0][5:])
            self.assertEqual(packet['uid'], uid)
            self.assertEqual(packet['storeId'], records[uid]['storeId'])
            self.assertEqual(packet['wifiSSID'], records[uid]['wifiSSID'])
            self.bridge.handle({'v': 1, 'type': 'status', 'uid': uid,
                                'requestId': request_id, 'status': 'WIFI_CONNECTED'})
        self.assertIn('Wi-Fi Password : ' + self.store['wifiPassword'], self.output.getvalue())

    def test_missing_fields_does_not_print_or_send_credentials(self):
        self.client.lookup.return_value = {**self.store, 'wifiSSID': None}
        self.bridge.handle(self.scan)
        output = self.output.getvalue()
        self.assertIn('FETCH STATUS: FAILED (INVALID_CONFIG)', output)
        self.assertNotIn('THONG TIN CUA HANG', output)
        self.assertNotIn(self.store['wifiPassword'], output)
        packet = json.loads(self.device.write.call_args.args[0][5:])
        self.assertEqual(packet['type'], 'lookup_error')
        self.assertNotIn('wifiPassword', packet)

    def test_not_found_does_not_print_or_send_credentials(self):
        self.client.lookup.side_effect = ValueError('NOT_FOUND: no matching store')
        self.bridge.handle(self.scan)
        output = self.output.getvalue()
        self.assertIn('Không tìm thấy thẻ', output)
        self.assertNotIn('THONG TIN CUA HANG', output)
        packet = json.loads(self.device.write.call_args.args[0][5:])
        self.assertEqual(packet['type'], 'lookup_error')
        self.assertNotIn('wifiPassword', packet)

    def test_display_uses_values_from_lookup(self):
        self.client.lookup.return_value = {**self.store, 'storeId': 'another-store',
                                          'wifiSSID': 'different-network',
                                          'wifiPassword': 'different-demo-password'}
        self.assertTrue(display(self.client, self.uid))
        output = self.output.getvalue()
        self.assertIn('Store ID       : another-store', output)
        self.assertIn('Wi-Fi SSID     : different-network', output)
        self.assertIn('Wi-Fi Password : different-demo-password', output)
        self.assertNotIn(self.store['wifiPassword'], output)


if __name__ == '__main__':
    unittest.main()
