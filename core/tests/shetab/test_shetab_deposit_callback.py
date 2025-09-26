from rest_framework.test import APITestCase


class ShetabDepositCallbackTest(APITestCase):
    URL = '/users/wallets/deposit/shetab-callback'

    @staticmethod
    def _assert_missing_word(response):
        assert response.status_code == 400
        assert response.json()['message'] == 'Missing word value'
        assert response.json()['code'] == 'ParseError'

    @staticmethod
    def _assert_missing_body(response):
        assert response.status_code == 404
        assert response.json()['message'] == 'Not found'
        assert response.json()['code'] == 'NotFound'

    @staticmethod
    def _assert_invalid_word(response):
        assert response.status_code == 400
        assert response.json()['message'] == 'Invalid word, it should only contain chars, digits and hyphen'
        assert response.json()['code'] == 'ParseError'

    def test_shetab_callback_inputs(self):
        response = self.client.post(self.URL, data={'id': 'http://', 'order_id': 1})
        self._assert_invalid_word(response)

        response = self.client.post(self.URL, data={'id': '1', 'order_id': 'https://'})
        self._assert_invalid_word(response)

        response = self.client.post(self.URL, data={'id': '1', 'order_id': '/'})
        self._assert_invalid_word(response)

        response = self.client.post(self.URL, data={'id': '123-123', 'order_id': '123-123'})
        assert response.status_code == 200

        response = self.client.get(f'{self.URL}?gateway=vandar')
        assert response.status_code == 400
        assert response.json()['message'] == 'Missing word value'
        assert response.json()['code'] == 'ParseError'

        response = self.client.post(f'{self.URL}?gateway=jibit&refnum=http://')
        self._assert_missing_body(response)

        response = self.client.post(f'{self.URL}?gateway=jibit_v2', data={'purchaseId': 'https://'})
        self._assert_invalid_word(response)

        response = self.client.post(f'{self.URL}?gateway=toman', data={'uuid': 'https://'})
        self._assert_invalid_word(response)

        response = self.client.post(f'{self.URL}?token=https://')
        self._assert_missing_body(response)

        response = self.client.post(f'{self.URL}?clientrefid=https://')
        self._assert_missing_body(response)
