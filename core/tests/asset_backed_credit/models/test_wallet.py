import uuid
from datetime import datetime
from decimal import Decimal

import fakeredis
import pytest
from django.db import transaction
from django.test import TestCase

from exchange.asset_backed_credit.exceptions import TransactionInsufficientBalanceError, TransactionInvalidError
from exchange.asset_backed_credit.externals.wallet import WalletType
from exchange.asset_backed_credit.models import InternalUser, Transaction, Wallet
from exchange.asset_backed_credit.models.wallet import WalletCache, WalletCacheManager
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from tests.asset_backed_credit.helper import ABCMixins


class InternalTransactionCommitTests(TestCase, ABCMixins):
    def setUp(self):
        """
        Create a user and wallet. Set up a default valid transaction object.
        """
        self.user = self.create_user()
        self.internal_user = InternalUser.objects.create(uid=self.user.uid, user_type=self.user.user_type)
        self.wallet = Wallet.objects.create(
            user=self.user,
            internal_user=self.internal_user,
            currency=Currencies.usdt,
            type=Wallet.WalletType.COLLATERAL,
            balance=Decimal('100'),
            blocked_balance=Decimal('0'),
            is_active=True,
        )
        self.transaction = Transaction(
            wallet=self.wallet,
            type=Transaction.Type.TRANSFER,
            amount=Decimal('10'),
            balance=None,
            created_at=datetime.now(),
            description='Test commit transaction',
        )

    def test_commit_successful(self):
        """
        Test committing a valid transaction updates the wallet balance
        and saves the transaction record with the updated balance.
        """
        initial_balance = self.wallet.balance

        self.transaction.commit()

        self.wallet.refresh_from_db()
        self.transaction.refresh_from_db()

        expected_balance = initial_balance + Decimal('10')
        assert (
            self.wallet.balance == expected_balance
        ), f'Expected wallet balance to be {expected_balance}, got {self.wallet.balance}'
        assert (
            self.transaction.balance == expected_balance
        ), 'Transaction balance should match the updated wallet balance after commit.'

    def test_commit_negative_balance_not_allowed(self):
        """
        Test that committing a transaction that results in a negative balance
        raises ValueError if allow_negative_balance=False.
        """
        self.transaction.amount = Decimal('-200')

        with transaction.atomic():
            with pytest.raises(TransactionInsufficientBalanceError, match='Balance Error In Commiting Transaction'):
                self.transaction.commit(allow_negative_balance=False)

        # Ensure the balance was not changed
        self.wallet.refresh_from_db()
        assert self.wallet.balance == Decimal('100'), 'Wallet balance should remain 100 after a failed transaction.'

    def test_commit_negative_balance_allowed(self):
        """
        Test that if allow_negative_balance=True, we can commit a transaction
        that would make the wallet balance negative.
        """
        self.transaction.amount = Decimal('-200')
        self.transaction.commit(allow_negative_balance=True)

        self.wallet.refresh_from_db()
        assert self.wallet.balance == Decimal('-100'), f'Expected wallet balance to be -100, got {self.wallet.balance}'

    def test_commit_inactive_wallet(self):
        """
        Test that committing a transaction on an inactive wallet raises ValueError.
        """
        self.wallet.is_active = False
        self.wallet.save()

        with pytest.raises(TransactionInvalidError):
            self.transaction.commit()

        # Check that balance has not changed
        self.wallet.refresh_from_db()
        assert self.wallet.balance == Decimal(
            '100'
        ), 'Wallet balance should remain the same after a failed transaction.'

    def test_commit_check_transaction_fails(self):
        """
        If check_transaction() fails (e.g., amount=None), commit should raise ValueError.
        """
        self.transaction.amount = None  # Make the transaction invalid

        with pytest.raises(TransactionInvalidError):
            self.transaction.commit()

        self.wallet.refresh_from_db()
        assert self.wallet.balance == Decimal('100'), 'Wallet balance remains unchanged after invalid transaction.'

    def test_commit_with_ref(self):
        """
        Test that passing a Ref object to commit sets the ref_module and ref_id.
        """
        ref = Transaction.Ref(ref_module=2, ref_id=999)
        initial_balance = self.wallet.balance

        self.transaction.commit(ref=ref)

        self.transaction.refresh_from_db()
        self.wallet.refresh_from_db()

        assert (
            self.transaction.ref_module == 2
        ), f'Expected transaction.ref_module to be 2, got {self.transaction.ref_module}'
        assert self.transaction.ref_id == 999, f'Expected transaction.ref_id to be 999, got {self.transaction.ref_id}'

        expected_balance = initial_balance + Decimal('10')
        assert (
            self.wallet.balance == expected_balance
        ), f'Expected wallet balance to be {expected_balance}, got {self.wallet.balance}'


class TestWalletCacheManager(TestCase):
    def setUp(self):
        self.redis = fakeredis.FakeStrictRedis()
        self.redis.flushall()
        self.manager = WalletCacheManager(client=self.redis)

    def test_get_missing_returns_none(self):
        assert self.manager.get(uuid.uuid4(), WalletType.spot, Currencies.usdt) is None

    def test_set_and_get_roundtrip(self):
        user_id = uuid.uuid4()
        wallet = WalletCache(
            id=1,
            balance=50,
            blocked_balance=0,
            currency=Currencies.usdt,
            type=WalletType.credit,
            updated_at=ir_now().timestamp(),
        )
        self.manager.set(user_id=user_id, wallet=wallet)

        result = self.manager.get(user_id, WalletType.credit, Currencies.usdt)
        assert result == wallet

        # verify the raw JSON in Redis matches
        raw = self.redis.hget(self.manager._user_wallets_key(user_id), f'{WalletType.credit}:{Currencies.usdt}')
        assert raw.decode() == wallet.json()

    def test_get_by_user_and_get_by_type(self):
        user_id = uuid.uuid4()
        wallet_1 = WalletCache(
            id=1,
            balance=10,
            blocked_balance=0,
            currency=Currencies.usdt,
            type=WalletType.credit,
            updated_at=ir_now().timestamp(),
        )
        wallet_2 = WalletCache(
            id=2,
            balance=20,
            blocked_balance=0,
            currency=Currencies.btc,
            type=WalletType.credit,
            updated_at=ir_now().timestamp(),
        )
        wallet_3 = WalletCache(
            balance=30,
            blocked_balance=0,
            currency=Currencies.eth,
            type=WalletType.debit,
            updated_at=ir_now().timestamp(),
        )

        self.manager.set(user_id, wallet_1)
        self.manager.set(user_id, wallet_2)
        self.manager.set(user_id, wallet_3)

        all_wallets = self.manager.get_by_user(user_id)
        assert all_wallets == [wallet_1, wallet_2, wallet_3]

        credit = self.manager.get_by_type(user_id, WalletType.credit)
        assert credit == [wallet_1, wallet_2]

        debit = self.manager.get_by_type(user_id, WalletType.debit)
        assert debit == [wallet_3]

    def test_set_bulk(self):
        user_id = uuid.uuid4()
        wallets = [
            WalletCache(
                id=1,
                balance=5,
                blocked_balance=0,
                currency=Currencies.usdt,
                type=WalletType.credit,
                updated_at=ir_now().timestamp(),
            ),
            WalletCache(
                id=2,
                balance=6,
                blocked_balance=0,
                currency=Currencies.btc,
                type=WalletType.credit,
                updated_at=ir_now().timestamp(),
            ),
            WalletCache(
                id=3,
                balance=7,
                blocked_balance=0,
                currency=Currencies.eth,
                type=WalletType.debit,
                updated_at=ir_now().timestamp(),
            ),
        ]
        self.manager.bulk_set(user_id=user_id, wallets=wallets)

        result = self.manager.get_by_user(user_id)
        assert result == wallets

    def test_overwrite_same_field(self):
        user_id = uuid.uuid4()
        w1 = WalletCache(
            id=1,
            balance=1,
            blocked_balance=0,
            currency=Currencies.usdt,
            type=WalletType.spot,
            updated_at=ir_now().timestamp(),
        )
        w2 = WalletCache(
            id=2,
            balance=2,
            blocked_balance=0,
            currency=Currencies.usdt,
            type=WalletType.spot,
            updated_at=ir_now().timestamp(),
        )
        self.manager.set(user_id, w1)
        self.manager.set(user_id, w2)

        wallet = self.manager.get(user_id, WalletType.spot, Currencies.usdt)
        assert wallet == w2

    def test_get_by_user_raise_value_error(self):
        user_id = uuid.uuid4()
        key = self.manager._user_wallets_key(user_id)
        # corrupt one entry
        self.redis.hset(key, f'{WalletType.debit}:{Currencies.usdt}', b'not-json')
        # valid entry
        good = WalletCache(
            id=1,
            balance=42,
            blocked_balance=0,
            currency=Currencies.eth,
            type=WalletType.debit,
            updated_at=ir_now().timestamp(),
        )
        self.redis.hset(key, f'{WalletType.debit}:{Currencies.eth}', good.json())

        with pytest.raises(ValueError):
            self.manager.get_by_user(user_id)

    def test_get_by_users_empty(self):
        user_id_1 = uuid.uuid4()
        user_id_2 = uuid.uuid4()
        user_ids = [user_id_1, user_id_2]
        all_wallets = self.manager.get_by_users(user_ids)
        assert all_wallets == {user_id_1: [], user_id_2: []}

    def test_get_by_users_single_user_multiple_wallets(self):
        user_id_1 = uuid.uuid4()
        w1 = WalletCache(
            id=1,
            balance=100,
            blocked_balance=0,
            currency=Currencies.btc,
            type=WalletType.spot,
            updated_at=ir_now().timestamp(),
        )
        w2 = WalletCache(
            id=2,
            balance=200,
            blocked_balance=0,
            currency=Currencies.eth,
            type=WalletType.margin,
            updated_at=ir_now().timestamp(),
        )

        self.manager.set(user_id=user_id_1, wallet=w1)
        self.manager.set(user_id=user_id_1, wallet=w2)

        result = self.manager.get_by_users([user_id_1])
        assert user_id_1 in result
        assert result[user_id_1][0] == w1
        assert result[user_id_1][1] == w2

    def test_get_by_users_multiple_users(self):
        user_id_1 = uuid.uuid4()
        user_id_2 = uuid.uuid4()
        user_id_3 = uuid.uuid4()
        w1 = WalletCache(
            id=1,
            balance=100,
            blocked_balance=0,
            currency=Currencies.btc,
            type=WalletType.spot,
            updated_at=ir_now().timestamp(),
        )
        w2 = WalletCache(
            id=2,
            balance=200,
            blocked_balance=0,
            currency=Currencies.usdt,
            type=WalletType.debit,
            updated_at=ir_now().timestamp(),
        )

        self.manager.set(user_id=user_id_1, wallet=w1)
        self.manager.set(user_id=user_id_2, wallet=w2)

        result = self.manager.get_by_users([user_id_1, user_id_2, user_id_3])
        assert result[user_id_1][0] == w1
        assert result[user_id_2][0] == w2
        assert result[user_id_3] == []

    def test_get_by_users_and_type_empty(self):
        user_id_1 = uuid.uuid4()
        user_id_2 = uuid.uuid4()
        result = self.manager.get_by_users_and_type([user_id_1, user_id_2], WalletType.spot)
        assert result == {user_id_1: [], user_id_2: []}

    def test_get_by_users_and_type_single_user(self):
        user_id_1 = uuid.uuid4()
        user_id_2 = uuid.uuid4()
        wallet_spot = WalletCache(
            id=1,
            balance=100,
            blocked_balance=0,
            currency=Currencies.btc,
            type=WalletType.spot,
            updated_at=ir_now().timestamp(),
        )
        wallet_margin = WalletCache(
            id=2,
            balance=200,
            blocked_balance=0,
            currency=Currencies.eth,
            type=WalletType.margin,
            updated_at=ir_now().timestamp(),
        )

        self.manager.set(user_id=user_id_1, wallet=wallet_spot)
        self.manager.set(user_id=user_id_2, wallet=wallet_margin)

        result = self.manager.get_by_users_and_type([user_id_1], WalletType.spot)
        assert set(result.keys()) == {user_id_1}
        assert result[user_id_1][0] == wallet_spot

    def test_get_by_users_and_type_multiple_users(self):
        user_id_1 = uuid.uuid4()
        user_id_2 = uuid.uuid4()
        user_id_3 = uuid.uuid4()
        w1 = WalletCache(
            id=1,
            balance=100,
            blocked_balance=0,
            currency=Currencies.usdt,
            type=WalletType.spot,
            updated_at=ir_now().timestamp(),
        )
        w2 = WalletCache(
            id=2,
            balance=200,
            blocked_balance=0,
            currency=Currencies.btc,
            type=WalletType.spot,
            updated_at=ir_now().timestamp(),
        )
        w3 = WalletCache(
            id=3,
            balance=300,
            blocked_balance=0,
            currency=Currencies.eth,
            type=WalletType.margin,
            updated_at=ir_now().timestamp(),
        )

        self.manager.set(user_id=user_id_1, wallet=w1)
        self.manager.set(user_id=user_id_1, wallet=w2)
        self.manager.set(user_id=user_id_2, wallet=w3)

        result = self.manager.get_by_users_and_type([user_id_1, user_id_2, user_id_3], WalletType.spot)
        assert set(result.keys()) == {user_id_1, user_id_2, user_id_3}

        assert result[user_id_1][0] == w1
        assert result[user_id_1][1] == w2

        assert result[user_id_2] == []

        assert result[user_id_3] == []
