from unittest.mock import MagicMock, patch

import pytest
import responses
from django.test import TestCase

from exchange.base.models import Settings
from exchange.corporate_banking.exceptions import ThirdPartyClientUnavailable, ThirdPartyDataParsingException
from exchange.corporate_banking.integrations.jibit.cards_list import CardDTO, CobankJibitCardsList
from exchange.corporate_banking.models import CoBankAccount


class TestCobankJibitCardsList(TestCase):
    def setUp(self):
        self.account = CoBankAccount(iban='IR12345678901234567890')
        self.jibit_cards_client = CobankJibitCardsList(bank_account=self.account)
        self.base_url = f'https://napi.jibit.ir/cobank/v1/accounts/{self.account.iban}/cards'

        self.default_access_token = 'some_access_token'
        Settings.set('cobank_jibit_access_token', self.default_access_token)

        self.sample_response = [
            {
                'id': 12345,
                'cardNumber': '5022291012345678',
                'iban': self.account.iban,
                'active': True,
            }
        ]

    @responses.activate
    def test_get_cards_success(self):
        responses.add(
            responses.GET,
            self.base_url,
            json=self.sample_response,
            status=200,
        )

        result = self.jibit_cards_client.get_cards()
        assert isinstance(result, list)
        assert len(result) == 1
        card = result[0]
        assert isinstance(card, CardDTO)
        assert card.id == 12345
        assert card.cardNumber == '5022291012345678'
        assert card.iban == self.account.iban
        assert card.active is True

    @responses.activate
    def test_get_cards_invalid_data(self):
        invalid_response = [{'id': 123, 'invalid_field': 'oops'}]  # missing required fields
        responses.add(
            responses.GET,
            self.base_url,
            json=invalid_response,
            status=200,
        )

        with pytest.raises(ThirdPartyDataParsingException):
            self.jibit_cards_client.get_cards()

    @responses.activate
    def test_get_cards_server_error(self):
        responses.add(
            responses.GET,
            self.base_url,
            json={},
            status=500,
        )

        with pytest.raises(ThirdPartyClientUnavailable):
            self.jibit_cards_client.get_cards()

    @responses.activate
    @patch('exchange.corporate_banking.integrations.jibit.authenticator.CobankJibitAuthenticator.get_auth_token')
    def test_get_cards_fetch_new_token_on_missing_token(self, mock_get_auth_token: MagicMock):
        Settings.set('cobank_jibit_access_token', '')
        mock_get_auth_token.return_value = 'new_token'

        responses.add(
            responses.GET,
            self.base_url,
            json=self.sample_response,
            status=200,
        )

        result = self.jibit_cards_client.get_cards()
        assert len(result) == 1
        mock_get_auth_token.assert_called()
