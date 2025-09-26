from copy import copy
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TransactionTestCase

from exchange.base.models import Currencies
from exchange.margin.models import Position
from exchange.margin.tasks import task_bulk_update_position_on_order_change
from exchange.market.models import Market, Order
from exchange.wallet.models import Transaction, Wallet
from tests.base.utils import TransactionTestFastFlushMixin, create_order, do_matching_round
from tests.margin.test_positions import PositionTestMixin
from tests.margin.utils import get_trade_fee_mock


@patch('exchange.market.marketmanager.MarketManager.get_trade_fee', new=get_trade_fee_mock)
@patch.object(task_bulk_update_position_on_order_change, 'delay', task_bulk_update_position_on_order_change)
class PositionFixCommandTest(PositionTestMixin, TransactionTestFastFlushMixin, TransactionTestCase):
    truncate_models = (Wallet,)

    def setUp(self):
        super().setUp()
        cache.clear()
        self.setUpTestData()
        self.src_pool.get_dst_wallet(self.market.dst_currency).create_transaction('manual', '1000').commit()

    @classmethod
    def create_match(cls, amount: str, order: Order):
        create_order(
            user=cls.assistant_user,
            src=order.src_currency,
            dst=order.dst_currency,
            amount=Decimal(amount),
            price=order.price,
            sell=order.is_buy,
        )
        do_matching_round(Market.get_for(order.src_currency, order.dst_currency))
        task_bulk_update_position_on_order_change([order.id])

    @classmethod
    def add_concurrent_similar_order(cls, position: Position, order: Order):
        order = copy(order)
        order.id = None
        order.save()
        position.orders.add(order, through_defaults={})
        return order

    def test_update_position_on_match(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        sell_order = self.create_short_margin_order(amount='0.001', price='21300')
        self.create_match(amount='0.001', order=sell_order)

        position = Position.objects.last()

        buy_order1 = self.create_margin_close_order(amount='0.0010015023', price='21000', position=position)
        buy_order2 = self.add_concurrent_similar_order(position, buy_order1)

        self.create_match(amount='0.003', order=buy_order1)

        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            earned_amount='-20.7843966',
            liquidation_price='38649.85',
            status=Position.STATUS.closed,
            orders_count=3,
            pnl='-20.7843966',
            entry_price='21300',
            exit_price='21000',
        )

        call_command('fix_position', position.id, detach_order=buy_order2.id)

        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            earned_amount='0.2471517',
            liquidation_price='38649.85',
            status=Position.STATUS.closed,
            orders_count=2,
            pnl='0.2446801830',
            entry_price='21300',
            exit_price='21000',
        )

        wallet = Wallet.get_user_wallet(self.user, self.market.dst_currency, Wallet.WALLET_TYPE.margin)
        assert wallet.balance == Decimal('25.2446801830')
        assert wallet.blocked_balance == 0

        reverse_transactions = Transaction.objects.filter(ref_module=Transaction.REF_MODULES['ReverseTransaction'])
        assert len(reverse_transactions) == 1
        assert reverse_transactions[0].amount == Decimal('21.0290767830')
        assert reverse_transactions[0].wallet == wallet

    def test_cancel_new_position_with_manually_canceled_and_deleted_order(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        sell_order = self.create_short_margin_order(amount='0.001', price='21300')
        Order.objects.update(status=Order.STATUS.canceled)
        sell_order.delete()

        position = Position.objects.last()

        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            orders_count=0,
        )

        call_command('fix_position', position.id, cancel=True)

        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            status=Position.STATUS.canceled,
            orders_count=0,
            pnl='0',
        )

        wallet = Wallet.get_user_wallet(self.user, self.market.dst_currency, Wallet.WALLET_TYPE.margin)
        assert wallet.balance == Decimal('25')
        assert wallet.blocked_balance == 0
