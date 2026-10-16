import unittest
from unittest.mock import patch, Mock

from firebase_rfid import FirebaseClient, normalize_uid, display


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
        self.assertNotIn('wifiPassword', result)
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


if __name__ == '__main__':
    unittest.main()
