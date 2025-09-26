from unittest.mock import MagicMock, patch

import pytest
import requests
import responses
from django.test import TestCase

from exchange.base.settings import Settings
from exchange.corporate_banking.exceptions import ThirdPartyAuthenticationException, ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.toman.accounts_list import CobankTomanAccountsList


class TestCobankTomanAccountsList(TestCase):
    def setUp(self):
        self.base_url = 'https://dbank-staging.qcluster.org/api/v1/account/?page=1&page_size=2'
        self.client = CobankTomanAccountsList()
        self.default_access_token = 'some_access_token'
        Settings.set('cobank_toman_access_token', self.default_access_token)

    @responses.activate
    def test_get_bank_accounts_success(self):
        responses.add(
            responses.GET,
            self.base_url,
            json={
                'results': [
                    {
                        'id': 3,
                        'bank_id': 2,
                        'iban': 'IR460170000000111111130003',
                        'account_number': '0111111130003',
                        'account_owner': 'elecom 3',
                        'active': True,
                        'last_update_balance_at': '2022-10-04',
                        'balance': 200000,
                        'credential': [1, 2],
                        'opening_date': '2024-08-07',
                        'unexpected_field': 'Should not be a problem',
                    },
                    {
                        'id': 4,
                        'bank_id': 3,
                        'iban': 'IR460170000000111111130004',
                        'account_number': '0111111130004',
                        'account_owner': 'elecom 4',
                        'active': True,
                        'last_update_balance_at': '2022-10-05',
                        'pinned': False,
                        'balance': 300000,
                        'credential': [1, 2],
                        'opening_date': '2024-08-08',
                    },
                ],
                'count': 2,
                'next': None,
                'previous': None,
            },
            status=200,
        )

        result = self.client.get_bank_accounts(page=1, page_size=2)

        assert result.count == 2
        assert len(result.results) == 2
        assert result.results[0].account_number == '0111111130003'
        assert result.results[1].account_number == '0111111130004'
        assert responses.calls[0].request.headers['Authorization'] == f'Bearer {self.default_access_token}'

    @responses.activate
    def test_get_bank_accounts_failure(self):
        responses.add(
            responses.GET,
            self.base_url,
            json={},
            status=500,
        )

        with pytest.raises(ThirdPartyClientUnavailable):
            self.client.get_bank_accounts(page=1, page_size=2)

    @responses.activate
    def test_get_bank_accounts_invalid_json(self):
        responses.add(
            responses.GET,
            self.base_url,
            json={
                'invalid_key': 'invalid_value',
            },
            status=200,
        )

        result = self.client.get_bank_accounts(page=1, page_size=2)

        assert result.count == 0
        assert len(result.results) == 0
        assert result.next is None
        assert result.previous is None

    @responses.activate
    @patch('exchange.corporate_banking.integrations.toman.base.CobankTomanAuthenticator.get_auth_token')
    def test_get_bank_accounts_fetch_new_token(self, mock_get_access_token: MagicMock):
        Settings.set('cobank_toman_access_token', '')

        mock_get_access_token.return_value = 'new_access_token'

        responses.add(
            responses.GET,
            self.base_url,
            json={
                'results': [
                    {
                        'id': 3,
                        'bank_id': 2,
                        'iban': 'IR460170000000111111130003',
                        'account_number': '0111111130003',
                        'account_owner': 'elecom 3',
                        'active': True,
                        'last_update_balance_at': '2022-10-04',
                        'pinned': False,
                        'balance': 200000,
                        'credential': [1, 2],
                        'opening_date': '2024-08-07',
                    },
                ],
                'count': 1,
                'next': None,
                'previous': None,
            },
            status=200,
        )

        result = self.client.get_bank_accounts(page=1, page_size=2)

        assert result.count == 1
        assert len(result.results) == 1
        assert result.results[0].account_number == '0111111130003'
        mock_get_access_token.assert_called()
        assert responses.calls[0].request.headers['Authorization'] == 'Bearer new_access_token'

    @responses.activate
    @patch('exchange.corporate_banking.integrations.toman.base.CobankTomanAuthenticator.get_auth_token')
    def test_get_bank_accounts_authenticator_error_by_thirdparty(self, mock_get_access_token):
        Settings.set('cobank_toman_access_token', '')

        mock_get_access_token.side_effect = ThirdPartyAuthenticationException('invalid_grant', 'you have not access')

        with pytest.raises(ThirdPartyAuthenticationException):
            self.client.get_bank_accounts(page=1, page_size=2)

    @responses.activate
    @patch('exchange.corporate_banking.integrations.toman.base.CobankTomanAuthenticator.get_auth_token')
    def test_get_bank_accounts_authenticator_error_by_network(self, mock_get_access_token):
        Settings.set('cobank_toman_access_token', '')

        mock_get_access_token.side_effect = requests.ConnectionError()

        with pytest.raises(ThirdPartyClientUnavailable):
            self.client.get_bank_accounts(page=1, page_size=2)
