from unittest import TestCase
from uuid import uuid4

import pytest
import responses
from responses import matchers
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import FeatureUnavailable, InternalAPIError
from exchange.asset_backed_credit.externals.transaction import BatchTransactionCreateAPI, ExchangeTransactionRequest
from exchange.base.models import Settings


class BatchTransactionCreateInternalAPITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.get(id=201)

        self.success_request_data = [
            dict(
                uid=str(self.user.uid),
                currency='usdt',
                wallet_type='credit',
                amount='100.00',
                description='Test Transaction 1',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
            dict(
                uid=str(self.user.uid),
                currency='usdt',
                wallet_type='credit',
                amount='10.00',
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=2,
            ),
        ]

        self.success_response_data = [
            {
                "error": None,
                "tx": {
                    "amount": "75.0000000000",
                    "balance": "75.0000000000",
                    "createdAt": "2024-12-01T14:50:04.778235 00:00",
                    "currency": "usdt",
                    "description": "Test Transaction 1",
                    "id": 2,
                    "refId": 1,
                    "refModule": "AssetBackedCreditUserSettlement",
                    "type": "asset_backed_credit",
                },
            },
            {
                "error": None,
                "tx": {
                    "amount": "-75.0000000000",
                    "balance": "25.0000000000",
                    "createdAt": "2024-12-01T14:50:04.768940 00:00",
                    "currency": "usdt",
                    "description": "Test Transaction 2",
                    "id": 1,
                    "refId": 2,
                    "refModule": "AssetBackedCreditUserSettlement",
                    "type": "asset_backed_credit",
                },
            },
        ]

        self.success_request_parsed_data = [ExchangeTransactionRequest(**d) for d in self.success_request_data]

        self.fail_422_response = [
            {"error": "InvalidTransactionType", "tx": None},
            {
                "error": None,
                "tx": {
                    "amount": "-100",
                    "balance": "0",
                    "created_at": "2024-11-23T07:37:49.474177 00:00",
                    "currency": "usdt",
                    "description": "Test Transaction 2",
                    "id": 86,
                },
            },
        ]

    @responses.activate
    def test_batch_transaction_create_success(self):
        Settings.set('abc_use_transaction_batch_create_internal_api', 'yes')
        responses.post(
            url=BatchTransactionCreateAPI.url,
            json=self.success_response_data,
            status=status.HTTP_200_OK,
            match=[matchers.json_params_matcher(self.success_request_data)],
        )

        transaction_schema = BatchTransactionCreateAPI().request(
            self.success_request_parsed_data, idempotency=str(uuid4())
        )
        assert transaction_schema

    def test_when_feature_is_not_enabled_then_feature_not_available_error_is_raised(self):
        Settings.set('abc_use_transaction_batch_create_internal_api', 'no')

        with pytest.raises(FeatureUnavailable):
            BatchTransactionCreateAPI().request(self.success_request_parsed_data, idempotency=str(uuid4()))

    @responses.activate
    def test_when_internal_api_raises_error_then_internal_api_errr_is_raised(self):
        Settings.set('abc_use_transaction_batch_create_internal_api', 'yes')
        responses.post(
            url=BatchTransactionCreateAPI.url,
            json=self.fail_422_response,
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

        with pytest.raises(InternalAPIError):
            BatchTransactionCreateAPI().request(self.success_request_parsed_data, idempotency=str(uuid4()))
