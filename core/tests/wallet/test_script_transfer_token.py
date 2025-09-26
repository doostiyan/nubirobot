from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.market.models import Order
from exchange.wallet.models import Wallet, WithdrawRequest


class TransferTokenCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)

        self.wallet_agix = Wallet.get_user_wallet(user=self.user, currency=Currencies.agix)
        self.wallet_fet = Wallet.get_user_wallet(user=self.user, currency=Currencies.fet)
        self.wallet_agix.create_transaction(tp='manual', amount='100').commit()

        self.order1 = Order.objects.create(
            user=self.user,
            src_currency=Currencies.agix,
            dst_currency=Currencies.rls,
            amount='50',
            price='5_000_0',
            order_type=Order.ORDER_TYPES.sell,
            trade_type=Order.TRADE_TYPES.spot,
            status=Order.STATUS.new,
        )

        self.withdraw_agix = WithdrawRequest.objects.create(
            amount=Decimal('1'), wallet=self.wallet_agix, status=WithdrawRequest.STATUS.new
        )

    @staticmethod
    def call_transfer_command():
        call_command('transfer_token', '--src', 'agix', '--dst', 'fet', '--ratio', '2', '--yes')

    @patch('exchange.wallet.management.commands.transfer_token.Command.backup_data')
    @patch('exchange.wallet.management.commands.transfer_token.Command.persist_logs')
    def test_transfer_token(self, log, backup_data):
        self.assertEqual(self.wallet_agix.balance, Decimal('100'))
        self.assertEqual(self.wallet_fet.balance, Decimal('0'))
        self.assertEqual(self.order1.status, Order.STATUS.new)
        self.assertEqual(self.withdraw_agix.status, WithdrawRequest.STATUS.new)

        self.call_transfer_command()

        self.wallet_agix.refresh_from_db()
        self.wallet_fet.refresh_from_db()
        self.order1.refresh_from_db()
        self.withdraw_agix.refresh_from_db()

        self.assertEqual(self.order1.status, Order.STATUS.canceled)
        self.assertEqual(self.wallet_agix.balance, Decimal('0'))
        self.assertEqual(self.wallet_fet.balance, Decimal('200'))
        self.assertEqual(self.withdraw_agix.status, WithdrawRequest.STATUS.rejected)

    @patch('exchange.wallet.management.commands.transfer_token.Command.backup_data')
    @patch('exchange.wallet.management.commands.transfer_token.Command.persist_logs')
    def test_transfer_transaction_description(self, log, backup_data):
        self.call_transfer_command()

        desc = f'تبدیل 100 AGIX به 200 FET در فرآیند ادغام'
        assert self.wallet_agix.transactions.last().description == desc
        assert self.wallet_fet.transactions.last().description == desc
