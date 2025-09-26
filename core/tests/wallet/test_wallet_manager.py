from decimal import Decimal

import pytest
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.wallet.exceptions import InsufficientBalanceError
from exchange.wallet.models import Transaction, Wallet
from exchange.wallet.wallet_manager import WalletTransactionManager


class WalletTransactionManagerTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(id=201)
        Wallet.create_user_wallets(self.user)
        self.wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        self.wallet.create_transaction('manual', Decimal('100.00')).commit()

    def test_add_transaction_valid(self):
        manager = WalletTransactionManager(wallet=self.wallet)
        manager.add_transaction(tp='manual', amount=Decimal('50.00'), description='Deposit')
        assert len(manager._transactions) == 1
        assert sum(t.amount for t in manager._transactions) == Decimal('50.00')
        txn = manager._transactions[0]
        assert txn.wallet == self.wallet
        assert txn.amount == Decimal('50.00')
        assert txn.description == 'Deposit'
        assert txn.created_at is not None

    def test_add_transaction_negative_balance_not_allowed(self):
        manager = WalletTransactionManager(wallet=self.wallet)
        with pytest.raises(ValueError, match='Transaction would result in negative wallet balance'):
            manager.add_transaction(tp='manual', amount=Decimal('-150.00'), description='Overdraw')

    def test_commit_success(self):
        manager = WalletTransactionManager(wallet=self.wallet)
        manager.add_transaction(tp='manual', amount=(tx1_amount := Decimal('25.00')), description='Deposit 1')
        manager.add_transaction(tp='manual', amount=(tx2_amount := Decimal('10.00')), description='Deposit 2')

        # manual tx in `setUp`
        assert Transaction.objects.filter(wallet=self.wallet).count() == 1
        new_wallet = manager.commit()
        assert Transaction.objects.filter(wallet=self.wallet).count() == 3

        assert new_wallet.balance == Decimal('135.00')
        self.wallet.refresh_from_db(fields=['balance'])
        assert self.wallet.balance == Decimal('135.00')

        assert len(manager._transactions) == 0

        tx0, tx1, tx2 = Transaction.objects.order_by('created_at')
        assert tx1.balance == tx0.balance + tx1_amount
        assert tx2.balance == tx0.balance + tx1_amount + tx2_amount

    def test_commit_failure_due_to_negative_balance(self):
        manager = WalletTransactionManager(wallet=self.wallet)
        manager.add_transaction(
            tp='manual', amount=Decimal('-101.00'), description='Withdrawal', allow_negative_balance=True
        )

        with pytest.raises(InsufficientBalanceError, match='InsufficientBalance'):
            manager.commit(allow_negative_balance=False)

        self.wallet.refresh_from_db(fields=['balance'])
        assert self.wallet.balance == Decimal('100.00')

    def test_commit_allow_negative_balance(self):
        manager = WalletTransactionManager(wallet=self.wallet)
        manager.add_transaction(
            tp='manual', amount=Decimal('-101.00'), description='Withdrawal', allow_negative_balance=True
        )

        # manual tx in `setUp`
        assert Transaction.objects.filter(wallet=self.wallet).count() == 1

        manager.commit(allow_negative_balance=True)
        self.wallet.refresh_from_db(fields=['balance'])
        assert self.wallet.balance == Decimal('-1.00')

        assert Transaction.objects.filter(wallet=self.wallet).count() == 2

    def test_reinitialize(self):
        manager = WalletTransactionManager(wallet=self.wallet)
        manager.add_transaction(tp='manual', amount=Decimal('20.00'), description='Test reinit')
        manager.reinitialize()
        assert len(manager._transactions) == 0

    def test_ref_module_and_service_parameters(self):
        manager = WalletTransactionManager(wallet=self.wallet)
        manager.add_transaction(
            tp='manual',
            amount=Decimal('15.00'),
            description='With ref and service',
            ref_module='Credit',
            ref_id=123,
        )
        txn = manager._transactions[0]
        assert txn.ref_module == Transaction.REF_MODULES.get('Credit')
        assert txn.ref_id == 123
