import pytest
import responses
from django.test import TestCase
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import FeatureUnavailable, InternalAPIError
from exchange.asset_backed_credit.externals.wallet import WalletListAPI, WalletRequestItem
from exchange.base.models import Settings


class WalletListInternalAPITest(TestCase):
    def setUp(self):
        self.user_1 = User.objects.get(id=201)
        self.user_2 = User.objects.get(id=203)

        self.request_data = [
            WalletRequestItem(currency="btc", type="credit", uid=str(self.user_1.uid)),
            WalletRequestItem(currency="eth", type="credit", uid=str(self.user_1.uid)),
            WalletRequestItem(currency="btc", type="credit", uid=str(self.user_2.uid)),
        ]

        self.internal_api_response = {
            str(self.user_1.uid): [
                {
                    "activeBalance": "0.1000000000",
                    "balance": "0.1000000000",
                    "blockedBalance": "0E-10",
                    "currency": "btc",
                    "type": "credit",
                    "userId": str(self.user_1.uid)
                },
                {
                    "activeBalance": "0.2000000000",
                    "balance": "0.2000000000",
                    "blockedBalance": "0E-10",
                    "currency": "eth",
                    "type": "credit",
                    "userId": str(self.user_1.uid)
                }
            ],
            str(self.user_2.uid): [
                {
                    "activeBalance": "0.3000000000",
                    "balance": "0.3000000000",
                    "blockedBalance": "0E-10",
                    "currency": "btc",
                    "type": "credit",
                    "userId": str(self.user_2.uid)
                }
            ]
        }

        Settings.set('abc_use_wallet_list_internal_api', 'yes')

    @responses.activate
    def test_wallet_list_success(self):
        responses.post(
            url=WalletListAPI.url,
            json=self.internal_api_response,
            status=status.HTTP_200_OK,
        )

        wallet_list_schema = WalletListAPI().request(self.request_data)
        assert wallet_list_schema
        assert wallet_list_schema[self.user_1.uid]
        assert wallet_list_schema[self.user_2.uid]

    def test_wallet_list_with_feature_not_being_enabled(self):
        Settings.set('abc_use_wallet_list_internal_api', 'no')

        with pytest.raises(FeatureUnavailable):
            WalletListAPI().request(self.request_data)

    @responses.activate
    def test_with_internal_api_raises_error(self):
        responses.post(
            url=WalletListAPI.url,
            json={},
            status=status.HTTP_400_BAD_REQUEST,
        )

        with pytest.raises(InternalAPIError):
            WalletListAPI().request(self.request_data)
