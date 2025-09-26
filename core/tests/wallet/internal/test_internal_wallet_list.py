from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.internal.services import Services
from exchange.base.models import Currencies
from exchange.wallet.models import Wallet
from tests.helpers import InternalAPITestMixin, create_internal_token, mock_internal_service_settings


class InternalWalletListTestCase(InternalAPITestMixin, APITestCase):
    URL = '/internal/wallets/list'
    user1: User
    user2: User

    @classmethod
    def setUpTestData(cls):
        cls.user1 = User.objects.get(pk=201)
        cls.user2 = User.objects.get(pk=202)

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ABC.value)}')
        self.user1_credit_btc_wallet = Wallet.get_user_wallet(self.user1, Currencies.btc, tp=Wallet.WALLET_TYPE.credit)
        self.user1_credit_btc_wallet.balance = Decimal('0.1')
        self.user1_credit_btc_wallet.save()
        self.user1_credit_eth_wallet = Wallet.get_user_wallet(self.user1, Currencies.eth, tp=Wallet.WALLET_TYPE.credit)
        self.user1_credit_eth_wallet.balance = Decimal('0.2')
        self.user1_credit_eth_wallet.save()
        self.user2_credit_btc_wallet = Wallet.get_user_wallet(self.user2, Currencies.btc, tp=Wallet.WALLET_TYPE.credit)
        self.user2_credit_btc_wallet.balance = Decimal('0.3')
        self.user2_credit_btc_wallet.save()

    def _request(self, data=None, headers=None):
        return self.client.post(self.URL, data=data or {}, headers=headers or {}, format='json')

    @mock_internal_service_settings
    def test_illegal_arguments(self):
        data = ['invalid input']
        response = self._request(data)
        response_data = response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response_data.get('code') == 'IllegalArgument'
        assert (
            response_data.get('message')
            == "[{'non_field_errors': [ErrorDetail(string='داده نامعتبر. باید دیکشنری ارسال می شد، اما str ارسال شده است.', code='invalid')]}]"
        )

        data = [{'uid': 'illegal uid', 'type': 'credit', 'currency': 'btc'}]
        response = self._request(data=data)
        response_data = response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response_data.get('code') == 'IllegalArgument'
        assert (
            response_data.get('message') == "[{'uid': [ErrorDetail(string='Must be a valid UUID.', code='invalid')]}]"
        )

        data = [{'uid': str(self.user1.uid), 'type': 'invalid_type_value', 'currency': 'invalid_currency_value'}]
        response = self._request(data=data)
        response_data = response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response_data.get('code') == 'IllegalArgument'
        assert (
            response_data.get('message') == "[{'type': [ErrorDetail(string='Invalid choices: \"invalid_type_value\"',"
            " code='invalid')], "
            "'currency': [ErrorDetail(string='Invalid choices: \"invalid_currency_value\"', code='invalid')]}]"
        )

        data = [{"uid": str(self.user1.uid), 'type': 'credit', 'currency': 'btc'} for i in range(101)]
        response = self._request(data=data)
        response_data = response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response_data.get('code') == 'IllegalArgument'
        assert (
            response_data.get('message')
            == "{'non_field_errors': [ErrorDetail(string='Ensure this field has no more than 100 elements.', code='max_length')]}"
        )

    @mock_internal_service_settings
    def test_not_found_wallets(self):
        data = [{'uid': str(self.user1.uid), 'type': 'credit', 'currency': 'ltc'}]
        response = self._request(data=data)
        response_data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert len(response_data.keys()) == 0

    @mock_internal_service_settings
    def test_forbidden_wallets(self):
        data = [{'uid': str(self.user1.uid), 'type': 'spot', 'currency': 'btc'}]
        response = self._request(data=data)
        response_data = response.json()
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response_data.get('code') == 'PermissionDenied'
        assert response_data.get('message') == 'Service ABC does not have access to wallet with type Spot'

    @mock_internal_service_settings
    def test_get_wallets(self):
        data = [
            {"uid": str(self.user1.uid), 'type': 'credit', 'currency': 'btc'},
            {"uid": str(self.user1.uid), 'type': 'credit', 'currency': 'eth'},
            {"uid": str(self.user2.uid), 'type': 'credit', 'currency': 'btc'},
        ]
        response = self._request(data=data)
        response_data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert len(response_data.keys()) == 2
        assert len(response_data.get(str(self.user1.uid))) == 2
        assert len(response_data.get(str(self.user2.uid))) == 1
        assert response_data.get(str(self.user1.uid))[0].get('userId') == str(self.user1.uid)
        assert response_data.get(str(self.user1.uid))[0].get('balance') == '0.1000000000'
        assert response_data.get(str(self.user1.uid))[0].get('type') == 'credit'
        assert response_data.get(str(self.user1.uid))[1].get('userId') == str(self.user1.uid)
        assert response_data.get(str(self.user1.uid))[1].get('balance') == '0.2000000000'
        assert response_data.get(str(self.user1.uid))[1].get('type') == 'credit'
        assert response_data.get(str(self.user2.uid))[0].get('userId') == str(self.user2.uid)
        assert response_data.get(str(self.user2.uid))[0].get('balance') == '0.3000000000'
        assert response_data.get(str(self.user2.uid))[0].get('type') == 'credit'
