from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.internal.services import Services
from exchange.base.models import Currencies
from exchange.wallet.internal.exceptions import InsufficientBalance, NonZeroAmountSum, UserNotFound
from exchange.wallet.internal.permissions import ALLOWED_DST_TYPES
from exchange.wallet.internal.service_transaction import create_batch_service_transaction
from exchange.wallet.internal.types import TransactionInput
from exchange.wallet.models import Transaction, Wallet


class TestBatchServiceTransaction(TestCase):
    truncate_models = (Wallet, Transaction)

    def setUp(self):
        self.service = Services.ABC
        self.user1, _ = User.objects.get_or_create(username='user1@TestBatchServiceTransaction')
        self.user2, _ = User.objects.get_or_create(username='user2@TestBatchServiceTransaction')

        self.wallet1 = Wallet.objects.create(
            user=self.user1, balance=Decimal('100.00'), currency=Currencies.usdt, type=Wallet.WALLET_TYPE.spot
        )
        self.wallet2 = Wallet.objects.create(
            user=self.user2, balance=Decimal('200.00'), currency=Currencies.usdt, type=Wallet.WALLET_TYPE.credit
        )

    def assert_rollback(self):
        self.wallet1.refresh_from_db()
        self.wallet2.refresh_from_db()
        assert self.wallet1.balance == Decimal('100.00')
        assert self.wallet2.balance == Decimal('200.00')

    def test_create_batch_service_transaction(self):
        batch_transaction_data = [
            TransactionInput(
                uid=self.user1.uid,
                currency='usdt',
                wallet_type='spot',
                amount=Decimal('75.00'),
                description='Test Transaction 1',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
            TransactionInput(
                uid=self.user2.uid,
                currency='usdt',
                wallet_type='credit',
                amount=Decimal('-75.00'),
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditProviderSettlement',
                ref_id=2,
            ),
        ]

        results, has_error = create_batch_service_transaction(self.service, batch_transaction_data)

        assert not has_error
        assert len(results) == 2
        assert results[0].tx is not None
        assert results[0].tx.amount == Decimal('75')
        assert results[0].tx.wallet_id == self.wallet1.pk
        assert results[0].error is None

        assert results[1].tx is not None
        assert results[1].tx.amount == Decimal('-75')
        assert results[1].tx.wallet_id == self.wallet2.pk
        assert results[1].error is None

        self.wallet1.refresh_from_db()
        self.wallet2.refresh_from_db()
        assert self.wallet1.balance == Decimal('175.00')  # user1: 100 + 75
        assert self.wallet2.balance == Decimal('125.00')  # user2: 200 - 75

    def test_create_batch_service_transaction_wallet_created(self):
        Wallet.objects.create(
            user=self.user2,
            balance=Decimal('100.00'),
            currency=Currencies.btc,
            type=Wallet.WALLET_TYPE.credit,
        )

        batch_transaction_data = [
            TransactionInput(
                uid=self.user1.uid,
                currency='btc',
                wallet_type='spot',
                amount=Decimal('100.00'),
                description='Test Transaction 1',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
            TransactionInput(
                uid=self.user2.uid,
                currency='btc',
                wallet_type='credit',
                amount=Decimal('-100.00'),
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditProviderSettlement',
                ref_id=2,
            ),
        ]

        results, has_error = create_batch_service_transaction(self.service, batch_transaction_data)

        assert not has_error
        assert len(results) == 2
        assert results[0].tx is not None
        assert results[0].error is None

        assert results[1].tx is not None
        assert results[1].error is None

        results[0].tx.wallet.refresh_from_db()
        assert results[0].tx.wallet.balance == 100
        assert results[0].tx.wallet.currency == Currencies.btc
        assert results[0].tx.wallet.type == Wallet.WALLET_TYPE.spot

    def test_create_batch_service_transaction_with_insufficient_balance(self):
        batch_transaction_data = [
            TransactionInput(
                uid=self.user1.uid,
                currency='usdt',
                wallet_type='spot',
                amount=Decimal('300.00'),
                description='Test Transaction 1',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
            TransactionInput(
                uid=self.user2.uid,
                currency='usdt',
                wallet_type='credit',
                amount=Decimal('-300.00'),
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditProviderSettlement',
                ref_id=2,
            ),
        ]

        results, has_error = create_batch_service_transaction(self.service, batch_transaction_data)

        assert has_error
        assert len(results) == 2

        # tx 0 should not be executed
        assert results[0].tx is None
        assert results[0].error is None

        assert results[1].tx is None
        assert results[1].error is not None
        assert isinstance(results[1].error, InsufficientBalance)

        self.assert_rollback()

    def test_create_batch_service_transaction_ordering_fail(self):
        batch_transaction_data = [
            TransactionInput(
                uid=self.user1.uid,
                currency='usdt',
                wallet_type='credit',
                amount=Decimal('1000.00'),
                description='Test Transaction 1',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
            TransactionInput(
                uid=self.user1.uid,
                currency='usdt',
                wallet_type='credit',
                amount=Decimal('-3000.00'),
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditProviderSettlement',
                ref_id=2,
            ),
            TransactionInput(
                uid=self.user2.uid,
                currency='usdt',
                wallet_type='credit',
                amount=Decimal('2000.00'),
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditProviderSettlement',
                ref_id=3,
            ),
        ]

        with patch.dict(
            ALLOWED_DST_TYPES,
            {Services.ABC: [Wallet.WALLET_TYPE.credit]},
        ):
            results, has_error = create_batch_service_transaction(self.service, batch_transaction_data)

        assert has_error
        assert results[0].tx is not None
        assert results[0].error is None
        assert results[1].tx is None
        assert isinstance(results[1].error, InsufficientBalance)
        assert results[2].tx is None
        assert results[2].error is None

        self.assert_rollback()

    def test_create_batch_service_transaction_ordering_success(self):
        batch_transaction_data = [
            TransactionInput(
                uid=self.user1.uid,
                currency='usdt',
                wallet_type='credit',
                amount=Decimal('-2900.00'),
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditProviderSettlement',
                ref_id=2,
            ),
            TransactionInput(
                uid=self.user2.uid,
                currency='usdt',
                wallet_type='credit',
                amount=Decimal('-100.00'),
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditProviderSettlement',
                ref_id=3,
            ),
            TransactionInput(
                uid=self.user1.uid,
                currency='usdt',
                wallet_type='credit',
                amount=Decimal('3000.00'),
                description='Test Transaction 1',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
        ]

        with patch.dict(
            ALLOWED_DST_TYPES,
            {Services.ABC: [Wallet.WALLET_TYPE.credit]},
        ):
            results, has_error = create_batch_service_transaction(self.service, batch_transaction_data)

        assert has_error is False
        assert results[0].tx.amount == -2900
        assert results[0].error is None
        assert results[1].tx.amount == -100
        assert results[1].error is None
        assert results[2].tx.amount == 3000
        assert results[2].error is None

        assert results[1].tx.created_at > results[0].tx.created_at > results[2].tx.created_at

    def test_create_batch_service_transaction_with_non_zero_sum_error(self):
        batch_transaction_data = [
            TransactionInput(
                uid=self.user1.uid,
                currency='usdt',
                wallet_type='spot',
                amount=Decimal('70.00'),
                description='Test Transaction 1',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
            TransactionInput(
                uid=self.user1.uid,
                currency='btc',
                wallet_type='spot',
                amount=Decimal('30.00'),
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=2,
            ),
        ]

        with pytest.raises(NonZeroAmountSum) as ex:
            create_batch_service_transaction(self.service, batch_transaction_data)

        assert ex.value.currency == 'usdt'

        self.wallet1.refresh_from_db()
        self.wallet2.refresh_from_db()
        assert self.wallet1.balance == Decimal('100.00')
        assert self.wallet2.balance == Decimal('200.00')

    def test_create_batch_service_transaction_missing_users(self):
        invalid_user_uid1 = uuid4()
        invalid_user_uid2 = uuid4()
        batch_transaction_data = [
            TransactionInput(
                uid=invalid_user_uid1,
                currency='btc',
                wallet_type='spot',
                amount=Decimal('100.00'),
                description='Test Transaction 1',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=1,
            ),
            TransactionInput(
                uid=invalid_user_uid2,
                currency='btc',
                wallet_type='credit',
                amount=Decimal('-100.00'),
                description='Test Transaction 2',
                tp='asset_backed_credit',
                ref_module='AssetBackedCreditProviderSettlement',
                ref_id=2,
            ),
        ]

        with pytest.raises(UserNotFound) as ex:
            create_batch_service_transaction(self.service, batch_transaction_data)

        assert ex.value.args[0] == {str(invalid_user_uid1), str(invalid_user_uid2)}
