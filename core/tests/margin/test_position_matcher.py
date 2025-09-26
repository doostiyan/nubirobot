import datetime
from decimal import Decimal
from typing import Optional
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from exchange.accounts.constants import SYSTEM_USER_IDS
from exchange.accounts.models import User
from exchange.base.models import Currencies, Settings
from exchange.liquidator.models import LiquidationRequest
from exchange.margin.crons import PositionExpireCron
from exchange.margin.models import MarginOrderChange, Position
from exchange.margin.tasks import (
    task_bulk_update_position_on_order_change,
    task_liquidate_positions,
    task_manage_expired_positions,
    task_manage_liquidated_positions,
    task_update_position_on_liquidation_request_change,
)
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market, Order
from exchange.wallet.models import Wallet
from tests.base.utils import TransactionTestFastFlushMixin, create_order, do_matching_round
from tests.margin.test_positions import PositionTestMixin
from tests.margin.utils import get_trade_fee_mock, get_user_fee_by_fields_mock


@patch('exchange.accounts.userstats.UserStatsManager.get_user_fee_by_fields', new=get_user_fee_by_fields_mock)
@patch.object(
    task_update_position_on_liquidation_request_change, 'delay', task_update_position_on_liquidation_request_change
)
@patch.object(task_bulk_update_position_on_order_change, 'delay', task_bulk_update_position_on_order_change)
@patch.object(task_manage_liquidated_positions, 'delay', task_manage_liquidated_positions)
@patch.object(task_manage_expired_positions, 'delay', task_manage_expired_positions)
@patch.object(task_liquidate_positions, 'delay', task_liquidate_positions)
class PositionMatcherTest(PositionTestMixin, TransactionTestFastFlushMixin, TransactionTestCase):
    truncate_models = (MarginOrderChange, Wallet,)

    def setUp(self):
        super().setUp()
        cache.clear()
        self.setUpTestData()
        self.system_fix_user = User.objects.get(id=SYSTEM_USER_IDS.system_fix)
        self.pool_profit_user = User.objects.get(id=SYSTEM_USER_IDS.system_pool_profit)

        Settings.set('liquidator_enabled_markets', '["BTCUSDT", "BTCIRT"]')

    def tearDown(self):
        super().tearDown()
        Settings.set('liquidator_enabled_markets', '[]')

    @classmethod
    def create_match(cls, amount: str, order: Order, price: Optional[str] = None, maker: bool = False):
        matching_order = create_order(
            user=cls.assistant_user,
            src=order.src_currency,
            dst=order.dst_currency,
            amount=Decimal(amount),
            price=price or order.price,
            sell=order.is_buy,
        )
        if maker:
            matching_order.created_at = order.created_at - datetime.timedelta(microseconds=1)
            matching_order.save(update_fields=('created_at',))
        do_matching_round(Market.get_for(order.src_currency, order.dst_currency))

    @classmethod
    def fill_liquidation_request(
        cls,
        liquidation_request: LiquidationRequest,
        amount: Optional[str] = None,
        price: Optional[str] = None,
    ):
        liquidation_request.filled_amount = Decimal(amount) if amount is not None else liquidation_request.amount
        price = Decimal(price or cls.MARKET_PRICE)
        liquidation_request.filled_total_price = liquidation_request.filled_amount * price
        liquidation_request.status = LiquidationRequest.STATUS.done
        liquidation_request.save(update_fields=('filled_amount', 'filled_total_price', 'status'))
        if liquidation_request.is_sell:
            liquidation_request.src_wallet.create_transaction('sell', -liquidation_request.filled_amount).commit()
            liquidation_request.dst_wallet.create_transaction('buy', liquidation_request.filled_total_price).commit()
        else:
            liquidation_request.src_wallet.create_transaction('buy', liquidation_request.filled_amount).commit()
            liquidation_request.dst_wallet.create_transaction('sell', -liquidation_request.filled_total_price).commit()

    def test_margin_sell_order_match_sell(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(amount='0.001', price='21300')
        self.src_pool.src_wallet.refresh_from_db()
        assert self.src_pool.src_wallet.balance == 2
        assert self.src_pool.available_balance == Decimal('1.999')
        before_match = timezone.now()
        self.create_match(amount='0.0009', order=order)
        after_match = timezone.now()
        self.src_pool.src_wallet.refresh_from_db()
        assert self.src_pool.src_wallet.balance == Decimal('1.9991')
        assert self.src_pool.available_balance == Decimal('1.999')
        assert self.src_pool.get_dst_wallet(self.market.dst_currency).balance == Decimal('19.15083')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0009013521',
            earned_amount='19.15083',
            liquidation_price='40798.13',
            status=Position.STATUS.open,
            entry_price='21300',
        )
        assert before_match < position.opened_at < after_match

    def test_margin_buy_order_match_buy(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_long_margin_order(amount='0.001', price='21200', leverage=2)
        self.dst_pool.src_wallet.refresh_from_db()
        assert self.dst_pool.src_wallet.balance == 40000
        assert self.dst_pool.available_balance == Decimal('39978.8')
        before_match = timezone.now()
        self.create_match(amount='0.0009', order=order)
        after_match = timezone.now()
        self.dst_pool.src_wallet.refresh_from_db()
        assert self.dst_pool.src_wallet.balance == Decimal('39980.92')
        assert self.dst_pool.available_balance == Decimal('39978.8')
        assert self.dst_pool.get_dst_wallet(self.market.src_currency).balance == Decimal('0.0008991')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0008991',
            earned_amount='-19.08',
            liquidation_price='11553.78',
            status=Position.STATUS.open,
            entry_price='21200',
        )
        assert before_match < position.opened_at < after_match

    def test_margin_sell_order_match_buy_with_better_price(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(amount='0.001', price='21300')
        self.create_match(amount='0.001', order=order)
        position = Position.objects.last()
        assert position.liability == Decimal('0.0010015023')

        order = self.create_margin_close_order(amount='0.0010015023', price='21000', position=position)
        self.create_match(amount='0.002', order=order)
        self.src_pool.src_wallet.refresh_from_db()
        assert self.src_pool.src_wallet.balance == Decimal('2.0000005008')
        assert self.src_pool.get_dst_wallet(self.market.dst_currency).balance == Decimal('0')
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
        user_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert user_wallet.balance == Decimal('25.2446801830')

    def test_margin_sell_order_match_buy_with_worse_price(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        self.src_pool.get_dst_wallet(self.market.dst_currency).create_transaction('manual', 100).commit()
        order = self.create_short_margin_order(amount='0.001', price='21300')
        self.create_match(amount='0.001', order=order)
        position = Position.objects.last()
        assert position.liability == Decimal('0.0010015023')

        order = self.create_margin_close_order(amount='0.0010015023', price='22000', position=position)
        self.create_match(amount='0.001', order=order)
        self.create_match(amount='0.0006', order=order)
        self.src_pool.src_wallet.refresh_from_db()
        assert self.src_pool.src_wallet.balance == Decimal('2.0000005008')
        assert self.src_pool.get_dst_wallet(self.market.dst_currency).balance == 100
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            earned_amount='-0.7543506',
            liquidation_price='18678024.25',
            status=Position.STATUS.closed,
            orders_count=2,
            pnl='-0.7543506',
            entry_price='21300',
            exit_price='22000',
        )
        user_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert user_wallet.balance == Decimal('24.2456494')

    def test_margin_buy_order_match_sell_with_better_price(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_long_margin_order(amount='0.001', price='21200', leverage=2)
        self.create_match(amount='0.001', order=order)
        position = Position.objects.last()
        assert position.liability == Decimal('0.000999')

        order = self.create_margin_close_order(amount='0.000999', price='22000', position=position)
        self.create_match(amount='0.001', order=order)
        self.dst_pool.src_wallet.refresh_from_db()
        assert self.dst_pool.src_wallet.balance == Decimal('40000')
        assert self.dst_pool.get_dst_wallet(self.market.src_currency).balance == Decimal('0')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            earned_amount='0.756022',
            liquidation_price='12732.73',
            status=Position.STATUS.closed,
            orders_count=2,
            pnl='0.7484617800',
            entry_price='21200',
            exit_price='22000',
        )
        user_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert user_wallet.balance == Decimal('25.7484617800')

    def test_margin_buy_order_match_sell_with_worse_price(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_long_margin_order(amount='0.001', price='21200', leverage=2)
        self.create_match(amount='0.001', order=order)
        position = Position.objects.last()
        assert position.liability == Decimal('0.000999')

        order = self.create_margin_close_order(amount='0.000999', price='21000', position=position)
        self.create_match(amount='0.0003', order=order)
        self.create_match(amount='0.0008', order=order)
        self.dst_pool.src_wallet.refresh_from_db()
        assert self.dst_pool.src_wallet.balance == Decimal('40000')
        assert self.dst_pool.get_dst_wallet(self.market.src_currency).balance == Decimal('0')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            earned_amount='-0.241979',
            liquidation_price='8293.18',
            status=Position.STATUS.closed,
            orders_count=2,
            pnl='-0.241979',
            entry_price='21200',
            exit_price='21000',
        )
        user_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert user_wallet.balance == Decimal('24.758021')

    def test_margin_sell_order_cancel_before_open(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(amount='0.001', price='21300')
        order.do_cancel()
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='0',
            status=Position.STATUS.canceled,
            pnl='0',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == 25

    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_margin_buy_order_cancel_before_open(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_long_margin_order(amount='0.001', price='21200', leverage=2)
        order.do_cancel()
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='0',
            status=Position.STATUS.canceled,
            pnl='0',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == 25

    def test_margin_sell_order_cancel_after_open(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        create_order(
            self.assistant_user, src=Currencies.btc, dst=Currencies.usdt, amount='0.0007', price='21300', sell=False
        )
        order = self.create_short_margin_order(amount='0.001', price='21100')
        do_matching_round(self.market)
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.22',
            liability='0.0007010516',
            earned_amount='14.887635',
            liquidation_price='46822.69',
            status=Position.STATUS.open,
            entry_price='21300',
        )
        order.do_cancel()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='14.91',
            liability='0.0007010516',
            earned_amount='14.887635',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
            entry_price='21300',
        )
        wallet = Wallet.get_user_wallet(self.user, self.market.dst_currency, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('10.09')

    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_margin_buy_order_cancel_after_open(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        create_order(
            self.assistant_user, src=Currencies.btc, dst=Currencies.usdt, amount='0.0007', price='21100', sell=True
        )
        order = self.create_long_margin_order(amount='0.001', price='21300', leverage=2)
        do_matching_round(self.market)
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.65',
            liability='0.00069895',
            earned_amount='-14.77',
            liquidation_price='8007.73',
            status=Position.STATUS.open,
            entry_price='21100',
        )
        order.do_cancel()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='7.385',
            liability='0.00069895',
            earned_amount='-14.77',
            liquidation_price='12679.02',
            status=Position.STATUS.open,
            entry_price='21100',
        )
        wallet = Wallet.get_user_wallet(self.user, self.market.dst_currency, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('17.615')

    def test_margin_sell_order_cancel_unmatched_to_close(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(amount='0.001', price='21300')
        self.create_match('0.0007', order)
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0007010516',
            earned_amount='14.89509',
            liquidation_price='46936.1',
            status=Position.STATUS.open,
            entry_price='21300',
        )
        close_order = self.create_margin_close_order(amount='0.0007010516', price='20800', position=position)
        self.create_match('0.0008', close_order)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            earned_amount='0.31321672',
            liquidation_price='46936.1',
            status=Position.STATUS.open,
            orders_count=2,
            entry_price='21300',
            exit_price='20800',
        )
        order.do_cancel()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='14.91',
            earned_amount='0.31321672',
            liquidation_price='46936.1',
            status=Position.STATUS.closed,
            orders_count=2,
            pnl='0.3100845528',
            entry_price='21300',
            exit_price='20800',
        )

    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_margin_buy_order_cancel_unmatched_to_close(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_long_margin_order(amount='0.001', price='21200', leverage=2)
        self.create_match('0.0007', order)
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0006993',
            earned_amount='-14.84',
            liquidation_price='8185.33',
            status=Position.STATUS.open,
            entry_price='21200',
        )
        close_order = self.create_margin_close_order(amount='0.0006993', price='22000', position=position)
        self.create_match('0.0008', close_order)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            earned_amount='0.5292154',
            liquidation_price='8185.33',
            status=Position.STATUS.open,
            orders_count=2,
            entry_price='21200',
            exit_price='22000',
        )
        order.do_cancel()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='7.42',
            earned_amount='0.5292154',
            liquidation_price='8185.33',
            status=Position.STATUS.closed,
            orders_count=2,
            pnl='0.5239232460',
            entry_price='21200',
            exit_price='22000',
        )
        wallet = Wallet.get_user_wallet(self.user, self.market.dst_currency, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('25.5239232460')

    def test_margin_sell_order_market_matched(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(amount='0.001', price='21300', execution=Order.EXECUTION_TYPES.market)
        self.create_match(amount='0.001', order=order, price='21200', maker=True)
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.1682',
            liquidation_price='38549.54',
            status=Position.STATUS.open,
            entry_price='21200',
        )

        order = self.create_margin_close_order(
            amount='0.0010015023', price='20600', execution=Order.EXECUTION_TYPES.market, position=position
        )
        self.create_match(amount='0.002', order=order, price='20700', maker=True)
        self.src_pool.src_wallet.refresh_from_db()
        assert self.src_pool.src_wallet.balance == Decimal('2')
        assert self.src_pool.get_dst_wallet(self.market.dst_currency).balance == Decimal('0')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            earned_amount='0.43710239',
            liquidation_price='38549.54',
            status=Position.STATUS.closed,
            orders_count=2,
            pnl='0.4327313661',
            entry_price='21200',
            exit_price='20700',
        )
        user_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert user_wallet.balance == Decimal('25.4327313661')

    def test_margin_buy_order_market_matched(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_long_margin_order(
            amount='0.001', price='21200', leverage=2, execution=Order.EXECUTION_TYPES.market
        )
        self.create_match(amount='0.001', order=order, price='21300', maker=True)
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0009985',
            earned_amount='-21.3',
            liquidation_price='12849.27',
            status=Position.STATUS.open,
            entry_price='21300',
        )

        order = self.create_margin_close_order(
            amount='0.0009985', price='21600', execution=Order.EXECUTION_TYPES.market, position=position
        )
        self.create_match(amount='0.001', order=order, price='21500', maker=True)
        self.dst_pool.src_wallet.refresh_from_db()
        assert self.dst_pool.src_wallet.balance == Decimal('40000')
        assert self.dst_pool.get_dst_wallet(self.market.src_currency).balance == Decimal('0')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            earned_amount='0.135548375',
            liquidation_price='12849.27',
            status=Position.STATUS.closed,
            orders_count=2,
            pnl='0.1341928912',
            entry_price='21300',
            exit_price='21500',
        )
        user_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert user_wallet.balance == Decimal('25.1341928912')

    def test_margin_sell_order_market_unmatched(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(amount='0.001', price='21300', execution=Order.EXECUTION_TYPES.market)
        self.create_match(amount='0.001', order=order, price='20500')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='0',
            status=Position.STATUS.canceled,
            pnl='0',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == 25

    def test_margin_buy_order_market_unmatched(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_long_margin_order(
            amount='0.001', price='21200', leverage=2, execution=Order.EXECUTION_TYPES.market
        )
        self.create_match(amount='0.001', order=order, price='22000')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='0',
            status=Position.STATUS.canceled,
            pnl='0',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == 25

    def test_margin_sell_order_stop_limit_activated(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(
            amount='0.001', price='20300', execution=Order.EXECUTION_TYPES.stop_limit, param1='20500'
        )
        assert not order.is_active
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.22')

        aux_order = self.create_order(amount='0.002', price='20400', sell=False)
        self.create_match(amount='0.001', order=aux_order)  # Market price falls
        position.refresh_from_db()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.22')
        order.refresh_from_db()
        assert order.is_active

        do_matching_round(self.market)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.22',
            liability='0.0010015023',
            earned_amount='20.3694',
            liquidation_price='37751.83',
            status=Position.STATUS.open,
            entry_price='20400',
        )

    def test_margin_buy_order_stop_limit_activated(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_long_margin_order(
            amount='0.001', price='22000', leverage=2, execution=Order.EXECUTION_TYPES.stop_limit, param1='21900'
        )
        assert not order.is_active
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='11')

        aux_order = self.create_order(amount='0.002', price='22000', sell=True)
        self.create_match(amount='0.001', order=aux_order)  # Market price raises
        position.refresh_from_db()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='11')
        order.refresh_from_db()
        assert order.is_active

        do_matching_round(self.market)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='11',
            liability='0.0009985',
            earned_amount='-22',
            liquidation_price='13219.83',
            status=Position.STATUS.open,
            entry_price='22000',
        )

    def test_margin_sell_order_stop_market_activated_and_matched(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(
            amount='0.001', price='0', execution=Order.EXECUTION_TYPES.stop_market, param1='20500'
        )
        assert not order.is_active
        assert order.price == 20500
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.22')

        aux_order = self.create_order(amount='0.0015', price='20400', sell=False)
        self.create_match(amount='0.001', order=aux_order)  # Market price falls
        position.refresh_from_db()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.22')
        order.refresh_from_db()
        assert order.is_active

        do_matching_round(self.market)
        order.refresh_from_db()
        assert order.status == Order.STATUS.canceled
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='10.20',
            liability='0.0005007512',
            earned_amount='10.1847',
            liquidation_price='37007.49',
            status=Position.STATUS.open,
            entry_price='20400',
        )

    def test_margin_buy_order_stop_market_activated_and_matched(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_long_margin_order(
            amount='0.001', price='0', leverage=2, execution=Order.EXECUTION_TYPES.stop_market, param1='21900'
        )
        assert not order.is_active
        assert order.price == 21900
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='10.95')

        aux_order = self.create_order(amount='0.0015', price='22000', sell=True)
        self.create_match(amount='0.001', order=aux_order)  # Market price falls
        position.refresh_from_db()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='10.95')
        order.refresh_from_db()
        assert order.is_active

        do_matching_round(self.market)
        order.refresh_from_db()
        assert order.status == Order.STATUS.canceled
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='5.5',
            liability='0.00049925',
            earned_amount='-11',
            liquidation_price='13219.83',
            status=Position.STATUS.open,
            entry_price='22000',
        )

    def test_margin_sell_order_stop_market_activated_but_not_matched(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(
            amount='0.001', price='20400', execution=Order.EXECUTION_TYPES.stop_market, param1='20500'
        )
        assert not order.is_active
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.22')

        aux_order = self.create_order(amount='0.002', price='20400', sell=False)
        self.create_match(amount='0.002', order=aux_order)  # Market price falls
        position.refresh_from_db()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.22')
        order.refresh_from_db()
        assert order.is_active

        do_matching_round(self.market)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='0',
            status=Position.STATUS.canceled,
            pnl='0',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == 25

    def test_margin_sell_order_stop_loss_close(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        self.src_pool.get_dst_wallet(self.market.dst_currency).create_transaction('manual', 100).commit()
        order = self.create_short_margin_order(amount='0.001', price='21300')
        self.create_match('0.001', order)
        position = Position.objects.last()
        assert position.liability == Decimal('0.0010015023')

        buy_order_1 = self.create_margin_close_order(
            amount='0.001', price='22100', execution=Order.EXECUTION_TYPES.stop_limit, param1='22000', position=position
        )
        buy_order_2 = self.create_margin_close_order(amount='0.0000015023', price='21000', position=position)

        position.refresh_from_db()
        self.create_match(amount='0.001', order=buy_order_2)
        position.refresh_from_db()
        assert position.liability == Decimal('0.0009999992')

        aux_order = self.create_order(amount='0.002', price='22100', sell=True)
        self.create_match(amount='0.001', order=aux_order)
        buy_order_1.refresh_from_db()
        assert buy_order_1.is_active

        do_matching_round(self.market)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            earned_amount='-0.8528483',
            liquidation_price='38679.26',
            status=Position.STATUS.closed,
            orders_count=3,
            pnl='-0.8528483',
            entry_price='21300',
            exit_price='22098.35',
        )
        user_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert user_wallet.balance == Decimal('24.1471517')

    def test_margin_buy_order_stop_loss_close(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_long_margin_order(amount='0.001', price='21200', leverage=2)
        self.create_match('0.001', order)
        position = Position.objects.last()
        assert position.liability == Decimal('0.000999')

        sell_order_1 = self.create_margin_close_order(
            amount='0.0007',
            price='20400',
            execution=Order.EXECUTION_TYPES.stop_limit,
            param1='20500',
            position=position,
        )
        sell_order_2 = self.create_margin_close_order(amount='0.000299', price='21000', position=position)

        position.refresh_from_db()
        self.create_match(amount='0.001', order=sell_order_2)
        position.refresh_from_db()
        assert position.liability == Decimal('0.0007')

        aux_order = self.create_order(amount='0.002', price='20500', sell=False)
        self.create_match(amount='0.001', order=aux_order)
        sell_order_1.refresh_from_db()
        assert sell_order_1.is_active

        do_matching_round(self.market)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            earned_amount='-0.598804',
            liquidation_price='8314.3',
            status=Position.STATUS.closed,
            orders_count=3,
            pnl='-0.598804',
            entry_price='21200',
            exit_price='20649.65',
        )
        user_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert user_wallet.balance == Decimal('24.401196')

    def create_oco_short_order(self, amount: str, price: str, stop_price: str, stop_limit_price: str) -> tuple:
        limit_order = self.create_short_margin_order(amount, price)
        stop_order = self.create_short_margin_order(
            amount, stop_limit_price, execution=Order.EXECUTION_TYPES.stop_limit, param1=stop_price, pair=limit_order
        )
        limit_order.refresh_from_db()
        return limit_order, stop_order

    def create_oco_long_order(
        self, leverage: str, amount: str, price: str, stop_price: str, stop_limit_price: str
    ) -> tuple:
        limit_order = self.create_long_margin_order(amount, price, leverage=leverage)
        stop_order = self.create_long_margin_order(
            amount,
            stop_limit_price,
            leverage = leverage,
            execution=Order.EXECUTION_TYPES.stop_limit,
            param1=stop_price,
            pair=limit_order,
        )
        limit_order.refresh_from_db()
        return limit_order, stop_order

    def create_oco_close_order(
            self, position: Position, amount: str, price: str, stop_price: str, stop_limit_price: str
    ):
        limit_order = self.create_margin_close_order(amount, price, position)
        stop_order = self.create_margin_close_order(
            amount, stop_limit_price, position, execution=Order.EXECUTION_TYPES.stop_limit, param1=stop_price,
            pair=limit_order,
        )
        limit_order.refresh_from_db()
        return limit_order, stop_order

    def test_margin_sell_order_oco_limit_partial_match(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        limit_order, stop_order = self.create_oco_short_order(
            amount='0.001', price='21300', stop_price='20500', stop_limit_price='20300'
        )
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.3', orders_count=2)

        self.create_match(amount='0.0007', order=limit_order)
        limit_order.refresh_from_db()
        assert limit_order.is_active and limit_order.is_partial
        stop_order.refresh_from_db()
        assert stop_order.is_closed and not stop_order.matched_amount
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0007010516',
            earned_amount='14.89509',
            liquidation_price='46936.1',
            status=Position.STATUS.open,
            orders_count=2,
            entry_price='21300',
        )

        limit_order.do_cancel()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='14.91',
            liability='0.0007010516',
            earned_amount='14.89509',
            liquidation_price='38649.85',
            status=Position.STATUS.open,
            orders_count=2,
            entry_price='21300',
        )

    def test_margin_sell_order_oco_stop_loss_partial_match(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        limit_order, stop_order = self.create_oco_short_order(
            amount='0.001', price='21300', stop_price='20500', stop_limit_price='20300'
        )
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.3', orders_count=2)

        aux_order = self.create_order(amount='0.002', price='20400', sell=False)
        self.create_match(amount='0.0013', order=aux_order)
        limit_order.refresh_from_db()
        assert limit_order.is_closed and not limit_order.matched_amount
        stop_order.refresh_from_db()
        assert stop_order.is_active and not stop_order.matched_amount
        position.refresh_from_db()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.22', orders_count=2)

        do_matching_round(self.market)
        stop_order.refresh_from_db()
        assert stop_order.is_active and stop_order.is_partial
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.22',
            liability='0.0007010516',
            earned_amount='14.25858',
            liquidation_price='46006.96',
            status=Position.STATUS.open,
            orders_count=2,
            entry_price='20400',
        )

        stop_order.do_cancel()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='14.28',
            liability='0.0007010516',
            earned_amount='14.25858',
            liquidation_price='37007.5',
            status=Position.STATUS.open,
            orders_count=2,
            entry_price='20400',
        )

    def test_margin_buy_order_oco_limit_partial_match(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        limit_order, stop_order = self.create_oco_long_order(
            leverage='2', amount='0.001', price='20800', stop_price='22000', stop_limit_price='21900'
        )
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='10.95', orders_count=2)

        self.create_match(amount='0.0007', order=limit_order)
        limit_order.refresh_from_db()
        assert limit_order.is_active and limit_order.is_partial
        stop_order.refresh_from_db()
        assert stop_order.is_closed and not stop_order.matched_amount
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.4',
            liability='0.0006993',
            earned_amount='-14.56',
            liquidation_price='8030.89',
            status=Position.STATUS.open,
            orders_count=2,
            entry_price='20800',
        )

        limit_order.do_cancel()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='7.28',
            liability='0.0006993',
            earned_amount='-14.56',
            liquidation_price='12492.49',
            status=Position.STATUS.open,
            orders_count=2,
            entry_price='20800',
        )

    def test_margin_buy_order_oco_stop_loss_partial_match(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        limit_order, stop_order = self.create_oco_long_order(
            leverage='2', amount='0.001', price='20800', stop_price='21900', stop_limit_price='22000'
        )
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='11', orders_count=2)

        aux_order = self.create_order(amount='0.002', price='22000', sell=True)
        self.create_match(amount='0.0013', order=aux_order)
        limit_order.refresh_from_db()
        assert limit_order.is_closed and not limit_order.matched_amount
        stop_order.refresh_from_db()
        assert stop_order.is_active and not stop_order.matched_amount
        position.refresh_from_db()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='11', orders_count=2)

        do_matching_round(self.market)
        stop_order.refresh_from_db()
        assert stop_order.is_active and stop_order.is_partial
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='11',
            liability='0.00069895',
            earned_amount='-15.4',
            liquidation_price='8498.46',
            status=Position.STATUS.open,
            orders_count=2,
            entry_price='22000',
        )

        stop_order.do_cancel()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='7.7',
            liability='0.00069895',
            earned_amount='-15.4',
            liquidation_price='13219.83',
            status=Position.STATUS.open,
            orders_count=2,
            entry_price='22000',
        )

    def test_margin_sell_order_oco_limit_cancel(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        limit_order, _ = self.create_oco_short_order(
            amount='0.001', price='21300', stop_price='20500', stop_limit_price='20300'
        )
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.3', orders_count=2)
        with transaction.atomic():
            limit_order.do_cancel()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='0',
            status=Position.STATUS.canceled,
            orders_count=2,
            pnl='0',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == 25

    def test_margin_sell_order_oco_stop_loss_cancel(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        _, stop_order = self.create_oco_short_order(
            amount='0.001', price='21300', stop_price='20500', stop_limit_price='20300'
        )
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.3', orders_count=2)
        with transaction.atomic():
            stop_order.do_cancel()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='0',
            status=Position.STATUS.canceled,
            orders_count=2,
            pnl='0',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == 25

    def test_margin_buy_order_oco_limit_cancel(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        limit_order, _ = self.create_oco_long_order(
            leverage='2', amount='0.001', price='20800', stop_price='22000', stop_limit_price='21900'
        )
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='10.95', orders_count=2)
        with transaction.atomic():
            limit_order.do_cancel()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='0',
            status=Position.STATUS.canceled,
            orders_count=2,
            pnl='0',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == 25

    def test_margin_buy_order_oco_stop_loss_cancel(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        _, stop_order = self.create_oco_long_order(
            leverage='2', amount='0.001', price='20800', stop_price='22000', stop_limit_price='21900'
        )
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='10.95', orders_count=2)
        with transaction.atomic():
            stop_order.do_cancel()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='0',
            status=Position.STATUS.canceled,
            orders_count=2,
            pnl='0',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == 25

    def test_margin_sell_order_oco_close_by_limit(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(amount='0.001', price='21300')
        self.create_match('0.001', order)
        position = Position.objects.last()
        assert position.liability == Decimal('0.0010015023')

        limit_order, stop_order = self.create_oco_close_order(
            position, amount='0.0010015023', price='20300', stop_price='22100', stop_limit_price='22300'
        )
        position.refresh_from_db()
        assert position.liability_in_order == Decimal('0.0010015023')
        assert position.asset_in_order == Decimal('22.33350129')

        self.create_match(amount='0.0007', order=limit_order)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0003011518',
            earned_amount='7.0687',
            liquidation_price='85636.97',
            status=Position.STATUS.open,
            orders_count=3,
            entry_price='21300',
            exit_price='20300',
        )
        del position.cached_orders
        assert position.liability_in_order == Decimal('0.0003015023')
        assert position.asset_in_order == Decimal('6.12049669')

        self.create_match(amount='0.002', order=limit_order)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            earned_amount='0.94820331',
            liquidation_price='85636.97',
            status=Position.STATUS.closed,
            orders_count=3,
            pnl='0.9387212769',
            entry_price='21300',
            exit_price='20300',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('25.9387212769')

    def test_margin_sell_order_oco_close_by_stop(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        self.src_pool.get_dst_wallet(self.market.dst_currency).create_transaction('manual', 100).commit()
        order = self.create_short_margin_order(amount='0.001', price='21300')
        self.create_match('0.001', order)
        position = Position.objects.last()
        assert position.liability == Decimal('0.0010015023')

        limit_order, stop_order = self.create_oco_close_order(
            position, amount='0.0010015023', price='20300', stop_price='22000', stop_limit_price='22300'
        )
        position.refresh_from_db()
        assert position.liability_in_order == Decimal('0.0010015023')
        assert position.asset_in_order == Decimal('22.33350129')

        aux_order = self.create_order(amount='0.0015', price='22100', sell=True)
        self.create_match(amount='0.001', order=aux_order)
        stop_order.refresh_from_db()
        assert stop_order.is_active
        position.refresh_from_db()
        assert position.liability == Decimal('0.0010015023')

        self.create_match(amount='0.001', price='22310', order=stop_order)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0005015023',
            earned_amount='10.2287',
            liquidation_price='57153.19',
            status=Position.STATUS.open,
            orders_count=3,
            entry_price='21300',
            exit_price='22100',
        )
        del position.cached_orders
        assert position.liability_in_order == Decimal('0.0005015023')
        assert position.asset_in_order == Decimal('11.18350129')

        self.create_match(amount='0.001', order=stop_order)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            earned_amount='-0.9548012900',
            liquidation_price='57153.19',
            status=Position.STATUS.closed,
            orders_count=3,
            pnl='-0.9548012900',
            entry_price='21300',
            exit_price='22200.15',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('24.04519871')

    def test_margin_buy_order_oco_close_by_limit(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_long_margin_order(amount='0.001', price='21200', leverage='2')
        self.create_match('0.001', order)
        position = Position.objects.last()
        assert position.liability == Decimal('0.000999')

        limit_order, stop_order = self.create_oco_close_order(
            position, amount='0.000999', price='21600', stop_price='20400', stop_limit_price='20300'
        )
        position.refresh_from_db()
        assert position.liability_in_order == Decimal('0.000999')
        assert position.asset_in_order == Decimal('21.5784')

        self.create_match(amount='0.0007', order=limit_order)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.000299',
            earned_amount='-6.09512',
            liquidation_price='0',
            status=Position.STATUS.open,
            orders_count=3,
            entry_price='21200',
            exit_price='21600',
        )
        del position.cached_orders
        assert position.liability_in_order == Decimal('0.000299')
        assert position.asset_in_order == Decimal('6.4584')

        self.create_match(amount='0.003', order=limit_order)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            earned_amount='0.3568216',
            liquidation_price='0',
            status=Position.STATUS.closed,
            orders_count=3,
            pnl='0.3532533840',
            entry_price='21200',
            exit_price='21600',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('25.3532533840')

    def test_margin_buy_order_oco_close_by_stop(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_long_margin_order(amount='0.001', price='21200', leverage='2')
        self.create_match('0.001', order)
        position = Position.objects.last()
        assert position.liability == Decimal('0.000999')

        limit_order, stop_order = self.create_oco_close_order(
            position, amount='0.000999', price='21600', stop_price='20400', stop_limit_price='20300'
        )
        position.refresh_from_db()
        assert position.liability_in_order == Decimal('0.000999')
        assert position.asset_in_order == Decimal('21.5784')

        aux_order = self.create_order(amount='0.0012', price='20400', sell=False)
        self.create_match(amount='0.001', order=aux_order)
        stop_order.refresh_from_db()
        assert stop_order.is_active
        position.refresh_from_db()
        assert position.liability == Decimal('0.000999')

        self.create_match(amount='0.0004', price='20300', order=stop_order)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.000399',
            earned_amount='-9.01424',
            liquidation_price='0',
            status=Position.STATUS.open,
            orders_count=3,
            entry_price='21200',
            exit_price='20333.33',
        )
        del position.cached_orders
        assert position.liability_in_order == Decimal('0.000399')
        assert position.asset_in_order == Decimal('8.0997')

        self.create_match(amount='0.001', order=stop_order)
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            earned_amount='-0.9226397',
            liquidation_price='0',
            status=Position.STATUS.closed,
            orders_count=3,
            pnl='-0.9226397',
            entry_price='21200',
            exit_price='20320.02',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('24.0773603')

    def _add_sell_liquidated_position(self, pool_balance: str, raise_price: str) -> Position:
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        self.src_pool.get_dst_wallet(self.market.dst_currency).create_transaction('manual', pool_balance).commit()
        order = self.create_short_margin_order(amount='0.001', price='21300')
        self.src_pool.src_wallet.refresh_from_db()
        assert self.src_pool.src_wallet.balance == 2
        self.create_match(amount='0.001', order=order)
        self.src_pool.src_wallet.refresh_from_db()
        assert self.src_pool.src_wallet.balance == Decimal('1.999')
        # raise market price
        raise_order = self.create_order(amount='0.001', price=raise_price, sell=False)
        self.create_match(amount='0.001', order=raise_order)
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.2787',
            liquidation_price='38649.85',
            status=Position.STATUS.liquidated,
            liquidation_requests_count=1,
            entry_price='21300',
        )
        liquidation_request = position.liquidation_requests.last()
        assert liquidation_request.amount == position.delegated_amount
        assert liquidation_request.is_open
        return position

    def _add_buy_liquidated_position(self, fall_price: str) -> Position:
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_long_margin_order(amount='0.001', price='21200', leverage='2')
        self.dst_pool.src_wallet.refresh_from_db()
        assert self.dst_pool.src_wallet.balance == 40000
        self.create_match(amount='0.001', order=order)
        self.dst_pool.src_wallet.refresh_from_db()
        assert self.dst_pool.src_wallet.balance == Decimal('39978.8')
        # fall market price
        fall_order = self.create_order(amount='0.001', price=fall_price, sell=True)
        self.create_match(amount='0.001', order=fall_order)
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.000999',
            earned_amount='-21.2',
            liquidation_price='12732.73',
            status=Position.STATUS.liquidated,
            liquidation_requests_count=1,
            entry_price='21200',
        )
        liquidation_request = position.liquidation_requests.last()
        assert liquidation_request.amount == position.delegated_amount
        assert liquidation_request.is_open
        return position

    def test_margin_sell_order_liquidation(self):
        position = self._add_sell_liquidated_position(pool_balance='100', raise_price='39000')
        liquidation_request = position.liquidation_requests.last()
        self.fill_liquidation_request(liquidation_request, price='39000')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0',
            earned_amount='-17.7213',
            liquidation_price='38649.85',
            status=Position.STATUS.liquidated,
            liquidation_requests_count=1,
            pnl='-17.7213',
            entry_price='21300',
            exit_price='39000',
        )
        self.src_pool.src_wallet.refresh_from_db()
        assert self.src_pool.src_wallet.balance == 2
        assert self.src_pool.get_dst_wallet(self.market.dst_currency).balance == 100

    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_margin_buy_order_liquidation(self):
        position = self._add_buy_liquidated_position(fall_price='11000')
        liquidation_request = position.liquidation_requests.last()
        self.fill_liquidation_request(liquidation_request, price='11000')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0',
            earned_amount='-10.211',
            liquidation_price='12732.73',
            status=Position.STATUS.liquidated,
            liquidation_requests_count=1,
            pnl='-10.211',
            entry_price='21200',
            exit_price='11000',
        )
        self.dst_pool.src_wallet.refresh_from_db()
        assert self.dst_pool.src_wallet.balance == 40000
        assert self.dst_pool.get_dst_wallet(self.market.src_currency).balance == 0

    def test_margin_sell_order_liquidation_first_market_settle_failed(self):
        position = self._add_sell_liquidated_position(pool_balance='100', raise_price='39000')
        assert position.liability == Decimal('0.0010015023')
        first_liquidation_request = position.liquidation_requests.last()
        assert first_liquidation_request.amount == position.delegated_amount == Decimal('0.001')
        assert first_liquidation_request.is_open

        self.fill_liquidation_request(first_liquidation_request, price='39000', amount='0.0006')
        position.refresh_from_db()
        assert position.liability == Decimal('0.0004006010')
        second_liquidation_request = position.liquidation_requests.filter(id__gt=first_liquidation_request.id).last()
        assert second_liquidation_request.amount == position.delegated_amount == Decimal('0.0004')
        assert second_liquidation_request.is_open

        self.fill_liquidation_request(second_liquidation_request, price='39000')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0',
            earned_amount='-17.7213',
            liquidation_price='38649.85',
            status=Position.STATUS.liquidated,
            liquidation_requests_count=2,
            pnl='-17.7213',
            entry_price='21300',
            exit_price='39000',
        )
        self.src_pool.src_wallet.refresh_from_db()
        assert self.src_pool.src_wallet.balance == 2
        assert self.src_pool.get_dst_wallet(self.market.dst_currency).balance == 100

    def test_margin_buy_order_liquidation_first_market_settle_failed(self):
        position = self._add_buy_liquidated_position(fall_price='11000')
        assert position.liability == Decimal('0.000999')
        first_liquidation_request = position.liquidation_requests.last()
        assert first_liquidation_request.amount == position.liability
        assert first_liquidation_request.is_open

        self.fill_liquidation_request(first_liquidation_request, price='11500', amount='0.0006')
        position.refresh_from_db()
        assert position.liability == Decimal('0.000399')

        second_liquidation_request = position.liquidation_requests.filter(id__gt=first_liquidation_request.id).last()
        assert second_liquidation_request.amount == position.liability
        assert second_liquidation_request.is_open

        self.fill_liquidation_request(second_liquidation_request, price='11200')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0',
            earned_amount='-9.8312',
            liquidation_price='12732.73',
            status=Position.STATUS.liquidated,
            liquidation_requests_count=2,
            pnl='-9.8312',
            entry_price='21200',
            exit_price='11380.18',
        )
        self.dst_pool.src_wallet.refresh_from_db()
        assert self.dst_pool.src_wallet.balance == 40000
        assert self.dst_pool.get_dst_wallet(self.market.src_currency).balance == 0

    def test_margin_sell_order_liquidation_above_max_total_price(self):
        self.__class__.market = Market.get_for(Currencies.btc, Currencies.rls)
        self.user.user_type = self.user.USER_TYPES.trusted
        self.user.save(update_fields=('user_type',))
        self.charge_wallet(Currencies.rls, 800_000_000_0, Wallet.WALLET_TYPE.margin)
        self.src_pool.get_dst_wallet(self.market.dst_currency).create_transaction('manual', 800_000_000_0).commit()
        order = self.create_short_margin_order(amount='0.6', price='1_065_000_000_0')
        self.create_match(amount='0.6', order=order)
        position = Position.objects.last()
        position_values = {
            'side': Position.SIDES.sell,
            'collateral': '639_000_000_0',
            'liability': '0.6009013521',
            'earned_amount': '638_361_000_0',
            'liquidation_price': '1_932_492_361_0',
            'status': Position.STATUS.open,
            'entry_price': '1_065_000_000_0',
        }
        self._check_position_status(position, **position_values)
        # raise market price
        raise_order = self.create_order(amount='0.001', price='1_950_000_000_0', sell=False)
        self.create_match(amount='0.001', order=raise_order)
        position.refresh_from_db()
        position_values.update(
            {
                'status': Position.STATUS.liquidated,
                'liquidation_requests_count': 1,
            },
        )
        self._check_position_status(position, **position_values)
        first_liquidation_request = position.liquidation_requests.last()
        assert first_liquidation_request.amount == Decimal('0.6') == position.delegated_amount
        assert first_liquidation_request.is_open
        self.fill_liquidation_request(first_liquidation_request, price='1_950_000_000_0', amount='0.5')
        position.refresh_from_db()
        position_values.update(
            {
                'liability': '0.1001502254',
                'earned_amount': '-336_639_000_0',
                'exit_price': '1_950_000_000_0',
                'liquidation_requests_count': 2,
            },
        )
        self._check_position_status(position, **position_values)
        second_liquidation_request = position.liquidation_requests.filter(id__gt=first_liquidation_request.id).last()
        assert second_liquidation_request.amount == Decimal('0.1') == position.delegated_amount
        assert second_liquidation_request.is_open
        self.fill_liquidation_request(second_liquidation_request, price='2_008_500_000_0')
        position.refresh_from_db()
        position_values.update(
            {
                'liability': '0',
                'earned_amount': '-537_489_000_0',
                'exit_price': '1_959_750_000_0',
                'pnl': '-537_489_000_0',
            },
        )
        self._check_position_status(position, **position_values)
        # cleanup
        self.__class__.market = Market.get_for(Currencies.btc, Currencies.usdt)

    def test_margin_sell_order_liquidation_price_jump(self):
        position = self._add_sell_liquidated_position(pool_balance='100', raise_price='43000')
        self.fill_liquidation_request(position.liquidation_requests.last(), price='43000')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0',
            earned_amount='-21.7213',
            liquidation_price='38649.85',
            status=Position.STATUS.liquidated,
            liquidation_requests_count=1,
            pnl='-21.3',
            entry_price='21300',
            exit_price='43000',
        )
        self.src_pool.src_wallet.refresh_from_db()
        assert self.src_pool.src_wallet.balance == 2
        assert self.src_pool.get_dst_wallet(self.market.dst_currency).balance == 100
        assert Wallet.get_user_wallet(self.system_fix_user, self.market.dst_currency).balance == Decimal('-0.4213')

    def test_margin_buy_order_liquidation_price_jump(self):
        position = self._add_buy_liquidated_position(fall_price='9000')
        self.fill_liquidation_request(position.liquidation_requests.last(), price='9000')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0',
            earned_amount='-12.209',
            liquidation_price='12732.73',
            status=Position.STATUS.liquidated,
            liquidation_requests_count=1,
            pnl='-10.6',
            entry_price='21200',
            exit_price='9000',
        )
        self.dst_pool.src_wallet.refresh_from_db()
        assert self.dst_pool.src_wallet.balance == 40_000
        assert self.dst_pool.get_dst_wallet(self.market.src_currency).balance == 0
        assert Wallet.get_user_wallet(self.system_fix_user, self.market.dst_currency).balance == Decimal('-1.609')

    def test_margin_order_expire_old_positions(self):
        self.charge_wallet(Currencies.usdt, 40, Wallet.WALLET_TYPE.margin)
        self.charge_wallet(Currencies.rls, 800_000_0, Wallet.WALLET_TYPE.margin)
        order_1 = self.create_short_margin_order(amount='0.001', price='21300')
        order_1.position_set.update(created_at=timezone.now() - timezone.timedelta(31))
        order_2 = self.create_short_margin_order(amount='0.001', dst=Currencies.rls, price='6300000000')
        order_2.position_set.update(created_at=timezone.now() - timezone.timedelta(30))
        order_3 = self.create_long_margin_order(amount='0.001', price='21200', leverage=2)
        order_3.position_set.update(created_at=timezone.now() - timezone.timedelta(31))
        order_4 = self.create_long_margin_order(src=Currencies.eth, amount='0.01', price='1870', leverage=3)
        order_4.position_set.update(created_at=timezone.now() - timezone.timedelta(30))
        PositionExpireCron().run()
        positions = Position.objects.all().order_by('id')
        assert len(positions) == 4
        assert positions[0].status == Position.STATUS.expired
        assert positions[1].status == Position.STATUS.new
        assert positions[2].status == Position.STATUS.expired
        assert positions[3].status == Position.STATUS.new

    def test_margin_sell_order_expire_position_not_opened(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        wallet.create_transaction('manual', 25).commit()
        order = self.create_short_margin_order(amount='0.001', price='21300')
        order.position_set.update(created_at=timezone.now() - timezone.timedelta(31))
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.7')

        PositionExpireCron().run()
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='0',
            status=Position.STATUS.expired,
            pnl='0',
        )
        assert not position.orders.filter(channel=Order.CHANNEL.system_margin).exists()
        wallet.refresh_from_db()
        assert wallet.active_balance == 25
        self.src_pool.src_wallet.refresh_from_db()
        assert self.src_pool.src_wallet.active_balance == 2

    def test_margin_buy_order_expire_position_not_opened(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        wallet.create_transaction('manual', 25).commit()
        order = self.create_long_margin_order(amount='0.001', price='21200', leverage=2)
        order.position_set.update(created_at=timezone.now() - timezone.timedelta(31))
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('14.4')

        PositionExpireCron().run()
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='0',
            status=Position.STATUS.expired,
            pnl='0',
        )
        assert not position.orders.filter(channel=Order.CHANNEL.system_margin).exists()
        wallet.refresh_from_db()
        assert wallet.active_balance == 25
        self.dst_pool.src_wallet.refresh_from_db()
        assert self.dst_pool.src_wallet.active_balance == 40000

    def test_margin_sell_order_expire_open_position(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        wallet.create_transaction('manual', 25).commit()
        self.src_pool.get_dst_wallet(self.market.dst_currency).create_transaction('manual', 100).commit()
        sell_order = self.create_short_margin_order(amount='0.001', price='21300')
        sell_order.position_set.update(created_at=timezone.now() - timezone.timedelta(31))
        position = Position.objects.last()
        with patch.object(timezone, 'now', return_value=timezone.now() - timezone.timedelta(27)):
            self.create_match(amount='0.001', order=sell_order)  # collects 1 fee for 27 days ago
            buy_order = self.create_margin_close_order(amount='0.001', price='19000', position=position)
            self.create_match(amount='0.001', order=buy_order, price='21100')  # does not match
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.7')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.285',
            liability='0.0010015023',
            earned_amount='21.26805',
            liquidation_price='38626.56',
            status=Position.STATUS.open,
            orders_count=2,
            entry_price='21300',
        )

        PositionExpireCron().run()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.285',
            liability='0.0010015023',
            earned_amount='21.26805',
            liquidation_price='38626.56',
            status=Position.STATUS.expired,
            orders_count=2,
            liquidation_requests_count=1,
            entry_price='21300',
        )
        liquidation_request = position.liquidation_requests.last()
        assert liquidation_request.amount == position.delegated_amount
        assert liquidation_request.is_open

        self.fill_liquidation_request(liquidation_request, price='21100')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.285',
            liability='0',
            earned_amount='0.16805',
            liquidation_price='38626.56',
            status=Position.STATUS.expired,
            orders_count=2,
            liquidation_requests_count=1,
            pnl='0.1159545',
            entry_price='21300',
            exit_price='21100',
        )
        self.src_pool.src_wallet.refresh_from_db()
        assert self.src_pool.src_wallet.balance == 2
        assert self.src_pool.get_dst_wallet(self.market.dst_currency).balance == 100
        assert Wallet.get_user_wallet(self.pool_profit_user, self.market.dst_currency).balance == Decimal('0.0520955')

    def test_margin_buy_order_expire_open_position(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        wallet.create_transaction('manual', 25).commit()
        buy_order = self.create_long_margin_order(amount='0.001', price='21200', leverage=2)
        buy_order.position_set.update(created_at=timezone.now() - timezone.timedelta(31))
        position = Position.objects.last()
        with patch.object(timezone, 'now', return_value=timezone.now() - timezone.timedelta(27)):
            self.create_match(amount='0.001', order=buy_order)  # collects 1 fee for 27 days ago
            sell_order = self.create_margin_close_order(amount='0.0009985', price='22000', position=position)
            self.create_match(amount='0.0005', order=sell_order, price='21400')  # does not match
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('14.4')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.585',
            liability='0.0009985',
            earned_amount='-21.2',
            liquidation_price='12754.13',
            status=Position.STATUS.open,
            orders_count=2,
            entry_price='21200',
        )

        PositionExpireCron().run()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.585',
            liability='0.0009985',
            earned_amount='-21.2',
            liquidation_price='12754.13',
            status=Position.STATUS.expired,
            orders_count=2,
            liquidation_requests_count=1,
            entry_price='21200',
        )
        liquidation_request = position.liquidation_requests.last()
        assert liquidation_request.amount == position.delegated_amount
        assert liquidation_request.is_open

        self.fill_liquidation_request(liquidation_request, price='21300')
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.585',
            liability='0',
            earned_amount='0.06805',
            liquidation_price='12754.13',
            status=Position.STATUS.expired,
            orders_count=2,
            liquidation_requests_count=1,
            pnl='0.0469545',
            entry_price='21200',
            exit_price='21300',
        )
        self.dst_pool.src_wallet.refresh_from_db()
        assert self.dst_pool.src_wallet.balance == 40_000
        assert self.dst_pool.get_dst_wallet(self.market.src_currency).balance == 0
        assert Wallet.get_user_wallet(self.pool_profit_user, self.market.dst_currency).balance == Decimal('0.0210955')

    def test_margin_sell_order_cancel_with_leverage_before_open(self):
        self.charge_wallet(Currencies.usdt, 12, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(amount='0.001', price='21300', leverage='2')
        order.do_cancel()
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='0',
            status=Position.STATUS.canceled,
            pnl='0',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == 12

    def test_margin_sell_order_cancel_with_leverage_after_open(self):
        self.charge_wallet(Currencies.usdt, 12, Wallet.WALLET_TYPE.margin)
        create_order(
            self.assistant_user, src=Currencies.btc, dst=Currencies.usdt, amount='0.0007', price='21300', sell=False
        )
        order = self.create_short_margin_order(amount='0.001', price='21100', leverage='2')
        do_matching_round(self.market)
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='10.61',
            liability='0.0007010516',
            earned_amount='14.887635',
            liquidation_price='33064.14',
            status=Position.STATUS.open,
            entry_price='21300',
        )
        order.do_cancel()
        position.refresh_from_db()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='7.455',
            liability='0.0007010516',
            earned_amount='14.887635',
            liquidation_price='28972.88',
            status=Position.STATUS.open,
            entry_price='21300',
        )
        wallet = Wallet.get_user_wallet(self.user, self.market.dst_currency, tp=Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('4.545')


@patch('exchange.market.marketmanager.MarketManager.get_trade_fee', new=get_trade_fee_mock)
@patch('django.db.transaction.on_commit', lambda t: t())
class PositionMatcherCommandTest(PositionTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        Settings.set('liquidator_enabled_markets', '["BTCUSDT"]')

    def tearDown(self):
        super().tearDown()
        Settings.set('liquidator_enabled_markets', '[]')

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

    def test_update_position_on_match(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(amount='0.001', price='21300')
        self.create_match(amount='0.001', order=order)
        call_command('manage_positions', once=True)
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.2787',
            liquidation_price='38649.85',
            status=Position.STATUS.open,
            entry_price='21300',
        )

    def test_update_position_on_cancel(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(amount='0.001', price='21300')
        order.do_cancel()
        call_command('manage_positions', once=True)
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='0',
            status=Position.STATUS.canceled,
            pnl='0'
        )

    def test_liquidate_positions(self):
        self.src_pool.get_dst_wallet(self.market.dst_currency).create_transaction('manual', 100).commit()
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(amount='0.001', price='21300')
        self.create_match(amount='0.001', order=order)

        raise_order = self.create_order(amount='0.0015', price='39000', sell=False)
        self.create_match(amount='0.001', order=raise_order)

        call_command('manage_positions', once=True)
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.2787',
            liquidation_price='38649.85',
            status=Position.STATUS.liquidated,
            liquidation_requests_count=1,
            entry_price='21300',
        )
        liquidation_request = position.liquidation_requests.last()
        assert liquidation_request.amount == position.delegated_amount
        assert liquidation_request.is_open
        self.set_market_price(self.MARKET_PRICE)

    def test_liquidate_positions_with_mark_price_around(self):
        cache.set(MarkPriceCalculator.CACHE_KEY.format(src_currency=self.market.src_currency), Decimal('21350'))
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        order = self.create_short_margin_order(amount='0.001', price='21300')
        self.create_match(amount='0.001', order=order)
        call_command('manage_positions', once=True)
        position = Position.objects.last()
        assert position.status == Position.STATUS.open
        assert position.liquidation_price == Decimal('38649.85')

        # Raise market price without mark price following
        raise_order = self.create_order(amount='0.0015', price='39000', sell=False)
        self.create_match(amount='0.001', order=raise_order)
        call_command('manage_positions', once=True)
        position.refresh_from_db()
        assert position.status == Position.STATUS.open

        # Mark price also follows market price rather close
        cache.set(MarkPriceCalculator.CACHE_KEY.format(src_currency=self.market.src_currency), Decimal('38300'))
        self.create_match(amount='0.001', order=raise_order)
        call_command('manage_positions', once=True)
        position.refresh_from_db()
        assert position.status == Position.STATUS.liquidated

        self.set_market_price(self.MARKET_PRICE)
        MarkPriceCalculator.delete_mark_price(self.market.src_currency)
