import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
import responses
from django.test import TestCase, override_settings
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import FeatureUnavailable
from exchange.asset_backed_credit.externals.wallet import (
    InternalWalletType,

    WalletTransferAPI,
    WalletTransferData,
    WalletTransferItem,
    WalletTransferRequest,
)
from exchange.base.models import Currencies, Settings, get_currency_codename
from tests.asset_backed_credit.helper import INTERNAL_TEST_JWT_TOKEN


class WalletTransferInternalAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.get(id=201)

        self.request_data = WalletTransferRequest(
            userId=self.user.uid,
            data=WalletTransferData(
                srcType=InternalWalletType.SPOT,
                dstType=InternalWalletType.CREDIT,
                transfers=[
                    WalletTransferItem(currency=get_currency_codename(Currencies.btc), amount=Decimal('12.1230')),
                    WalletTransferItem(currency=get_currency_codename(Currencies.usdt), amount=Decimal('30.50')),
                ],
            ),
        )

        self.internal_api_response = {'id': 2}

    @override_settings(
        ABC_AUTHENTICATION_INTERNAL_USER_ENABLED=True,
        ABC_INTERNAL_API_JWT_TOKEN=INTERNAL_TEST_JWT_TOKEN,
    )
    @responses.activate
    @patch('rest_framework.authentication.TokenAuthentication.authenticate')
    def test_transfer_from_spot_to_credit_successfully(self, mock_authenticate):
        Settings.set('abc_use_wallet_transfer_internal_api', 'yes')

        mock_authenticate.return_value = (self.user, None)
        responses.post(
            url=WalletTransferAPI.url,
            json=self.internal_api_response,
            status=status.HTTP_200_OK,
        )

        result = WalletTransferAPI().request(self.request_data, uuid.uuid4())

        actual = result.model_dump(mode='json')
        assert actual.pop('createdAt') != None
        expected = {
            'dstType': 'credit',
            'id': self.internal_api_response['id'],
            'rejectionReason': '',
            'srcType': 'spot',
            'status': 'new',
            'transfers': [{'amount': '12.1230', 'currency': 'btc'}, {'amount': '30.50', 'currency': 'usdt'}],
        }
        assert actual == expected

    def test_transfer_raises_exception_when_internal_api_is_not_enable(self):
        with pytest.raises(FeatureUnavailable) as _:
            WalletTransferAPI().request(self.request_data, uuid.uuid4())

    def test_prepare_request_data_nests_some_keys_according_to_internal_api_need(self):
        actual = WalletTransferAPI()._prepare_request_data(self.request_data)

        expected = {
            'userId': str(self.user.uid),
            'data': {
                'dstType': 'credit',
                'srcType': 'spot',
                'transfers': [{'amount': '12.1230', 'currency': 'btc'}, {'amount': '30.50', 'currency': 'usdt'}],
            },
        }
        assert actual == expected

    def test_prepare_response_data_formats_data_correctly(self):
        actual = WalletTransferAPI()._prepare_response_data(
            request_data=self.request_data.model_dump(mode='json'), response_data=self.internal_api_response
        )
        actual = actual.model_dump(mode='json')

        assert actual.pop('createdAt') != None
        expected = {
            'dstType': 'credit',
            'id': self.internal_api_response['id'],
            'rejectionReason': '',
            'srcType': 'spot',
            'status': 'new',
            'transfers': [{'amount': '12.1230', 'currency': 'btc'}, {'amount': '30.50', 'currency': 'usdt'}],
        }
        assert actual == expected
