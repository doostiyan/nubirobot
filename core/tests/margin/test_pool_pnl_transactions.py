from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import Notification
from exchange.config.config.models import Currencies
from exchange.margin.models import Position
from exchange.margin.tasks import task_bulk_update_position_on_order_change
from exchange.market.models import Market, Order
from exchange.wallet.exceptions import InsufficientBalanceError
from exchange.wallet.models import Transaction, Wallet
from exchange.wallet.wallet_manager import WalletTransactionManager
from tests.base.utils import create_order, do_matching_round
from tests.margin.test_positions import PositionTestMixin


class PoolPNLUnsettledTransactionsTest(PositionTestMixin, TestCase):
    """
    Tests for the `create_pool_pnl_transactions` management command
    """
    MARKET_PRICE = 24

    @classmethod
    def match_position_order(cls, order: Order):
        create_order(
            user=cls.assistant_user,
            src=order.src_currency,
            dst=order.dst_currency,
            amount=order.amount,
            price=order.price,
            sell=order.is_buy,
        )
        do_matching_round(Market.get_for(order.src_currency, order.dst_currency))
        task_bulk_update_position_on_order_change([order.id])

    @classmethod
    def close_position_order(cls, position: Position):
        order = cls.create_margin_close_order(amount=position.liability, price='22', position=position)
        create_order(
            user=cls.assistant_user,
            src=order.src_currency,
            dst=order.dst_currency,
            amount=order.amount,
            price=order.price,
            sell=order.is_buy,
        )
        do_matching_round(Market.get_for(order.src_currency, order.dst_currency), settle_positions_command=False)
        task_bulk_update_position_on_order_change([order.id])

    def create_and_close_position(self):
        order = self.create_long_margin_order(amount='1', price='20', leverage=2)
        self.match_position_order(order)
        position = Position.objects.get()
        self.close_position_order(position)
        position.refresh_from_db()
        return position

    def setUp(self):
        self.charge_wallet(Currencies.usdt, 50, Wallet.WALLET_TYPE.margin)

    def test_deferred_pnl_transaction(self):
        order = self.create_long_margin_order(amount='1', price='20', leverage=2)
        self.match_position_order(order)
        assert Position.objects.count() == 1

        p1 = Position.objects.last()
        assert p1.pnl is None
        self.close_position_order(p1)
        p1.refresh_from_db()
        assert p1.pnl == Decimal('1.9364617800')
        assert p1.pnl_transaction is None

        call_command('create_pool_pnl_transactions', '--once')

        p1.refresh_from_db()
        assert p1.pnl_transaction is not None

    def test_successful_pnl_transaction(self):
        position = self.create_and_close_position()
        assert position.pnl_transaction is None

        call_command('create_pool_pnl_transactions', '--once')

        position.refresh_from_db()
        assert position.pnl_transaction is not None
        assert Transaction.objects.filter(
            ref_id=position.id, ref_module=Transaction.REF_MODULES['PositionPoolPNL']
        ).exists()
        assert Transaction.objects.filter(
            ref_id=position.id, ref_module=Transaction.REF_MODULES['PositionAdjustPNL']
        ).exists()

    def test_pool_insufficient_balance_skips_positions(self):
        position = self.create_and_close_position()

        def fake_commit(self, allow_negative_balance=False):
            if allow_negative_balance:
                return self.wallet
            raise InsufficientBalanceError("pool OOM")

        with patch.object(WalletTransactionManager, 'commit', new=fake_commit):
            with patch.object(Notification, 'notify_admins') as mock_notify:
                call_command('create_pool_pnl_transactions', '--once')
                mock_notify.assert_called()

        position.refresh_from_db()
        assert position.pnl_transaction is None
