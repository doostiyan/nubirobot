from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.db import DatabaseError
from rest_framework import status

from exchange.accounts.models import User
from exchange.base.internal import idempotency
from exchange.base.internal.services import Services
from exchange.base.models import Currencies
from exchange.base.serializers import serialize
from exchange.wallet.models import Wallet
from tests.helpers import (
    APITestCaseWithIdempotency,
    InternalAPITestMixin,
    create_internal_token,
    mock_internal_service_settings,
)


class InternalBatchTransactionTest(InternalAPITestMixin, APITestCaseWithIdempotency):
    URL = '/internal/transactions/batch-create'
    user1: User
    user2: User

    @classmethod
    def setUpTestData(cls):
        cls.user1 = User.objects.get(pk=201)
        cls.user2 = User.objects.get(pk=202)

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ABC.value)}')

        self.user1_credit_usdt_wallet = Wallet.get_user_wallet(
            self.user1, Currencies.usdt, tp=Wallet.WALLET_TYPE.credit
        )
        self.user1_credit_usdt_wallet.balance = 100
        self.user1_credit_usdt_wallet.save()

        self.user2_spot_usdt_wallet = Wallet.get_user_wallet(self.user2, Currencies.usdt, tp=Wallet.WALLET_TYPE.spot)

        self.ok_data = [
            dict(
                uid=self.user2.uid,
                currency='usdt',
                wallet_type='spot',
                amount='75.00',
                description='Test Transaction 1',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
            dict(
                uid=self.user1.uid,
                currency='usdt',
                wallet_type='credit',
                amount='-75.00',
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=2,
            ),
        ]

    def _request(self, data=None, headers=None):
        return self.client.post(self.URL, data=data or {}, headers=headers or {}, format='json')

    def _assert_failed(self):
        self.user1_credit_usdt_wallet.refresh_from_db()
        self.user2_spot_usdt_wallet.refresh_from_db()

        assert self.user1_credit_usdt_wallet.balance == 100
        assert self.user2_spot_usdt_wallet.balance == 0

        assert self.user1_credit_usdt_wallet.transactions.count() == 0
        assert self.user2_spot_usdt_wallet.transactions.count() == 0

    def assert_failed_422(self, response, error_index, error, total_fail):
        assert response.status_code == 422
        self._assert_failed()

        response_data = response.json()
        assert len(response_data) == 2

        assert response_data[error_index]['error'] == error
        assert response_data[error_index]['tx'] is None

        other_tx_index = (error_index + 1) % 2
        assert response_data[other_tx_index]['error'] is None
        assert (
            response_data[other_tx_index]['tx'] is None
            if total_fail
            else response_data[other_tx_index]['tx'] is not None
        )

    @mock_internal_service_settings
    def test_batch_transaction(self):
        response = self._request(data=self.ok_data)
        self.assert_ok(response)

    @mock_internal_service_settings
    def test_batch_transaction_insufficient_balance(self):
        data = [
            dict(
                uid=self.user2.uid,
                currency='usdt',
                wallet_type='spot',
                amount='1000.00',
                description='Test Transaction 1',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
            dict(
                uid=self.user1.uid,
                currency='usdt',
                wallet_type='credit',
                amount='-1000.00',
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=2,
            ),
        ]

        response = self._request(data=data)
        self.assert_failed_422(response, error_index=1, error='InsufficientBalance', total_fail=True)

    @mock_internal_service_settings
    def test_batch_transaction_disallowed_tx_type(self):
        data = [
            dict(
                uid=self.user2.uid,
                currency='usdt',
                wallet_type='spot',
                amount='100.00',
                description='Test Transaction 1',
                tp='withdraw',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
            dict(
                uid=self.user1.uid,
                currency='usdt',
                wallet_type='credit',
                amount='-100.00',
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=2,
            ),
        ]

        response = self._request(data=data)
        self.assert_failed_422(response, error_index=0, error='InvalidTransactionType', total_fail=False)

    @mock_internal_service_settings
    def test_batch_transaction_user_not_found(self):
        invalid_uuid = uuid4()
        data = [
            dict(
                uid=invalid_uuid,
                currency='usdt',
                wallet_type='spot',
                amount='100.00',
                description='Test Transaction 1',
                tp='withdraw',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
            dict(
                uid=self.user1.uid,
                currency='usdt',
                wallet_type='credit',
                amount='-100.00',
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=2,
            ),
        ]

        response = self._request(data=data)
        assert response.status_code == 404
        self._assert_failed()

        response_data = response.json()
        assert response_data == {
            'code': 'UserNotFound',
            'message': f"Users with id of {{'{invalid_uuid!s}'}} are not found",
            'status': 'failed',
        }

    @mock_internal_service_settings
    def test_batch_transaction_non_zero_sum(self):
        data = [
            *self.ok_data,
            dict(
                uid=self.user2.uid,
                currency='usdt',
                wallet_type='spot',
                amount='75.00',
                description='Test Transaction 1',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
        ]

        response = self._request(data=data)
        assert response.status_code == 412
        self._assert_failed()

        response_data = response.json()
        assert response_data == {
            'code': 'NonZeroSumAmount',
            'message': 'Sum of transaction amounts should be zero',
            'status': 'failed',
        }

    @mock_internal_service_settings
    @patch('exchange.wallet.internal.views.create_batch_service_transaction')
    def test_batch_transaction_non_wallet_locked(self, mock_create_batch_service_transaction):
        mock_create_batch_service_transaction.side_effect = DatabaseError()
        response = self._request(data=self.ok_data)
        assert response.status_code == 423
        self._assert_failed()

        response_data = response.json()
        assert response_data == {
            'code': 'LockedWallet',
            'message': 'Some wallets are locked, try again',
            'status': 'failed',
        }

    @mock_internal_service_settings
    def test_internal_batch_transaction_idempotency(self):
        idempotency_key = str(uuid4())

        response = self._request(
            data=self.ok_data,
            headers={
                idempotency.IDEMPOTENCY_HEADER: idempotency_key,
            },
        )
        self.assert_ok(response)

        response = self._request(
            data=self.ok_data,
            headers={
                idempotency.IDEMPOTENCY_HEADER: idempotency_key,
            },
        )
        self.assert_ok(response)

    def assert_ok(self, response):
        response_data = response.json()
        assert response.status_code == 200
        assert len(response_data) == 2
        self.user1_credit_usdt_wallet.refresh_from_db()
        self.user2_spot_usdt_wallet.refresh_from_db()

        assert self.user1_credit_usdt_wallet.balance == 25
        assert self.user2_spot_usdt_wallet.balance == 75

        assert self.user1_credit_usdt_wallet.transactions.count() == 1
        assert self.user2_spot_usdt_wallet.transactions.count() == 1

        tx1 = self.user1_credit_usdt_wallet.transactions.first()
        tx2 = self.user2_spot_usdt_wallet.transactions.first()
        assert response_data == [
            {
                'tx': {
                    'id': tx2.pk,
                    'amount': '75.0000000000',
                    'currency': 'usdt',
                    'description': 'Test Transaction 1',
                    'createdAt': tx2.created_at.isoformat(),
                    'balance': '75.0000000000',
                    'refId': 1,
                    'refModule': 'AssetBackedCreditUserSettlement',
                    'type': 'asset_backed_credit',
                },
                'error': None,
            },
            {
                'tx': {
                    'id': tx1.pk,
                    'amount': '-75.0000000000',
                    'currency': 'usdt',
                    'description': 'Test Transaction 2',
                    'createdAt': tx1.created_at.isoformat(),
                    'balance': '25.0000000000',
                    'refId': 2,
                    'refModule': 'AssetBackedCreditUserSettlement',
                    'type': 'asset_backed_credit',
                },
                'error': None,
            },
        ]
        assert tx1.service == Services.ABC
        assert tx2.service == Services.ABC

    @mock_internal_service_settings
    def test_parse_error(self):
        data = ['invalid input']
        response = self._request(data)
        response_data = response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response_data.get('code') == 'ParseError'
        assert response_data.get('message') == 'Input should be a valid dictionary or instance of TransactionInput'

        data = [{'uid': 'illegal uid', 'type': 'credit', 'currency': 'btc'}]
        response = self._request(data=data)
        response_data = response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response_data.get('code') == 'ParseError'
        assert (
            response_data.get('message')
            == 'Input should be a valid UUID, invalid character: expected an optional prefix of `urn:uuid:` followed by [0-9a-fA-F-], found `i` at 1'
        )

        data = [
            dict(
                uid=self.user1.uid,
                currency='invalid_currency',
                wallet_type='spot',
                amount=Decimal('100.00'),
                description='Test Transaction 1',
                tp='withdraw',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
        ]
        response = self._request(data=data)
        response_data = response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response_data.get('code') == 'ParseError'
        assert response_data.get('message') == 'Value error, Invalid currency: invalid_currency'

        data = [
            dict(
                uid=self.user1.uid,
                currency='usdt',
                wallet_type='spot',
                amount=Decimal('100.00'),
                description='Test Transaction 1',
                tp='invalid_tp',
            ),
        ]
        response = self._request(data=data)
        response_data = response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response_data.get('code') == 'ParseError'
        assert response_data.get('message') == 'Value error, Invalid tp: invalid_tp'

        data = [
            dict(
                uid=self.user1.uid,
                currency='usdt',
                wallet_type='spot',
                amount=Decimal('100.00'),
                description='Test Transaction 1',
                tp='withdraw',
                ref_module='invalid_ref_module',
            ),
        ]
        response = self._request(data=data)
        response_data = response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response_data.get('code') == 'ParseError'
        assert response_data.get('message') == 'Value error, Invalid ref_module: invalid_ref_module'

        response = self._request(
            data=[
                *(self.ok_data * 5),
                dict(
                    uid=self.user1.uid,
                    currency='usdt',
                    wallet_type='spot',
                    amount=Decimal('100.00'),
                    description='Test Transaction 1',
                    tp='withdraw',
                    ref_module='AssetBackedCreditUserSettlement',
                    ref_id=1,
                ),
            ],
        )
        response_data = response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response_data.get('code') == 'ParseError'
        assert response_data.get('message') == 'List is too long, max len is 10'
