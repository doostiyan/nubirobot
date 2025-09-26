import datetime
from unittest.mock import patch

from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.system.checker import OnlineChecker
from exchange.wallet.models import Transaction, Wallet


class OnlineCheckerTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user1 = User.objects.get(pk=201)
        cls.user2 = User.objects.get(pk=202)
        cls.tx_time = ir_now() - datetime.timedelta(minutes=2)

    @patch.object(OnlineChecker, 'notif')
    def test_wallet_balance_check_successful(self, notif_patch):
        wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)
        wallet.create_transaction(tp='deposit', amount='100').commit()
        checker = OnlineChecker()
        checker.enqueue_wallet(wallet)
        checker.check_wallets()
        notif_patch.assert_not_called()

    @patch.object(OnlineChecker, 'notif')
    def test_wallet_balance_check_diff(self, notif_patch):
        wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)
        wallet.create_transaction(tp='deposit', amount='100').commit()
        # Malicious manipulation
        wallet.balance -= 20
        wallet.save()
        checker = OnlineChecker()
        checker.enqueue_wallet(wallet)
        checker.check_wallets()
        notif_patch.assert_called_with(wallet, 'Wallet balance mismatch last tx: 80 != 100 in', 'C13 user1@example.com')

    @patch.object(OnlineChecker, 'notif')
    def test_wallet_balance_check_diff_created_at_and_id_inconsistent_order(self, notif_patch):
        wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)
        wallet.create_transaction(tp='deposit', amount='100', created_at=self.tx_time).commit()
        wallet.create_transaction(
            tp='deposit', amount='80', created_at=self.tx_time - datetime.timedelta(seconds=30)
        ).commit()

        # Malicious manipulation
        wallet.balance = 100
        wallet.save()
        checker = OnlineChecker()
        checker.enqueue_wallet(wallet)
        checker.check_wallets()
        notif_patch.assert_called_with(
            wallet, 'Wallet balance mismatch last tx: 100 != 180 in', 'C13 user1@example.com'
        )

    @patch.object(OnlineChecker, 'notif')
    def test_transaction_balance_check_successful(self, notif_patch):
        wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)
        wallet.create_transaction(tp='deposit', amount='100', created_at=self.tx_time).commit()
        wallet.create_transaction(tp='deposit', amount='150', created_at=self.tx_time).commit()
        checker = OnlineChecker()
        checker.check_recent_transactions()
        notif_patch.assert_not_called()

    @patch.object(OnlineChecker, 'notif')
    def test_transaction_balance_check_diff_1(self, notif_patch):
        wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)
        wallet.create_transaction(tp='deposit', amount='100', created_at=self.tx_time).commit()
        Wallet.objects.filter(id=wallet.id).update(balance=50)
        tx = wallet.create_transaction(tp='deposit', amount='150', created_at=self.tx_time)
        tx.commit()
        assert wallet.balance == 200
        checker = OnlineChecker()
        checker.check_recent_transactions()
        notif_patch.assert_called_with(tx, 'Invalid transaction balance', f'W#{wallet.id} TP10')

    @patch.object(OnlineChecker, 'notif')
    def test_transaction_balance_check_diff_invalid_created_at_and_id_inconsistent_order(self, notif_patch):
        wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)

        # Second Last TX, should not picked as last_transaction
        wallet.create_transaction(
            tp='deposit', amount='50', created_at=self.tx_time - datetime.timedelta(minutes=30)
        ).commit()

        # Last TX
        wallet.create_transaction(
            tp='withdraw', amount='-50', created_at=self.tx_time - datetime.timedelta(minutes=100)
        ).commit()

        Wallet.objects.filter(id=wallet.id).update(balance=50)
        tx = wallet.create_transaction(tp='deposit', amount='150', created_at=self.tx_time)
        tx.commit()
        assert wallet.balance == 200
        checker = OnlineChecker()
        checker.wallets_last_balance[wallet.id] = (0, 1)
        checker.check_recent_transactions()
        notif_patch.assert_called_with(tx, 'Invalid transaction balance', f'W#{wallet.id} TP10')

    @patch.object(OnlineChecker, 'notif')
    def test_transaction_balance_check_diff_2(self, notif_patch):
        wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)
        tx1 = wallet.create_transaction(tp='deposit', amount='100')
        tx1.created_at = ir_now() - datetime.timedelta(minutes=3)
        tx1.commit()

        checker = OnlineChecker()
        checker.check_recent_transactions()
        notif_patch.assert_not_called()

        tx1_id = tx1.id
        tx1.delete()
        Wallet.objects.filter(id=wallet.id).update(balance=0)
        tx2 = wallet.create_transaction(tp='deposit', amount='150')
        tx2.created_at = ir_now() - datetime.timedelta(minutes=2)
        tx2.commit()

        checker.check_recent_transactions()
        notif_patch.assert_called_with(tx2, 'Deleted previous transaction', f'W#{wallet.id} TX#{tx1_id}')

    @patch.object(OnlineChecker, 'notif')
    def test_transaction_balance_check_diff_deleted_created_at_and_id_inconsistent_order(self, notif_patch):
        wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)
        tx1 = wallet.create_transaction(tp='deposit', amount='100')
        tx1.created_at = ir_now() - datetime.timedelta(minutes=3)
        tx1.commit()

        checker = OnlineChecker()
        checker.check_recent_transactions()
        notif_patch.assert_not_called()

        tx1_id = tx1.id
        tx1.delete()
        Wallet.objects.filter(id=wallet.id).update(balance=0)
        tx2 = wallet.create_transaction(tp='deposit', amount='150')
        tx2.created_at = ir_now() - datetime.timedelta(minutes=5)
        tx2.commit()

        checker.check_recent_transactions()
        notif_patch.assert_called_with(tx2, 'Deleted previous transaction', f'W#{wallet.id} TX#{tx1_id}')

    @patch.object(OnlineChecker, 'notif')
    def test_transaction_balance_check_negative_balance(self, notif_patch):
        wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)
        wallet.balance = 10
        tx = wallet.create_transaction(tp='withdraw', amount='-10', description='test', allow_negative_balance=True)
        tx.created_at = ir_now() - datetime.timedelta(minutes=2)
        tx.commit(allow_negative_balance=True)
        assert wallet.balance == -10
        checker = OnlineChecker()
        checker.check_recent_transactions()
        notif_patch.assert_called_with(tx, 'Negative transaction balance\ntp: Withdraw test')

    @patch.object(OnlineChecker, 'notif')
    def test_transaction_balance_allowed_negative_balance(self, notif_patch):
        wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)
        wallet.balance = 10
        wallet.create_transaction(
            tp='convert', amount='-10', ref_module=Transaction.REF_MODULES['ExchangeSystemSrc'], created_at=self.tx_time
        ).commit(allow_negative_balance=True)
        wallet.create_transaction(tp='buy', amount='2', allow_negative_balance=True, created_at=self.tx_time).commit(
            allow_negative_balance=True
        )
        assert wallet.balance == -8
        checker = OnlineChecker()
        checker.check_recent_transactions()
        notif_patch.assert_not_called()

    @patch.object(OnlineChecker, 'notif')
    def test_transaction_balance_check_none(self, notif_patch):
        wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)
        tx = wallet.create_transaction(tp='deposit', amount='100', created_at=self.tx_time)
        tx.commit()
        Transaction.objects.filter(id=tx.id).update(balance=None)
        checker = OnlineChecker()
        checker.check_recent_transactions()
        notif_patch.assert_called_with(tx, 'None transaction balance')
