from datetime import timedelta
from decimal import Decimal
from typing import List, Optional
from unittest.mock import patch

from django.core.cache import cache
from django.db.models import F
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import RIAL, TETHER, Currencies
from exchange.liquidator.constants import FEE_RATE
from exchange.liquidator.models import Liquidation, LiquidationRequest
from exchange.liquidator.services import InternalOrderCreator
from exchange.liquidator.tasks import (
    task_check_status_internal_liquidation,
    task_create_internal_order,
    task_process_pending_liquidation_request,
    task_submit_liquidation_requests_external_wallet_transactions,
    task_update_liquidation_request,
)
from exchange.market.models import Market, Order
from exchange.pool.models import LiquidityPool
from exchange.wallet.models import Wallet
from tests.base.utils import do_matching_round, mock_on_commit

IR_NOW = ir_now()


@patch('django.db.transaction.on_commit', mock_on_commit)
@patch.object(task_create_internal_order, 'delay', task_create_internal_order)
class TestInternalLiquidationProcess(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pool_manager = User.objects.get(pk=410)
        cls.pool_manager.base_fee = Decimal('0')
        cls.pool_manager.base_fee_usdt = Decimal('0')
        cls.pool_manager.base_maker_fee = Decimal('0')
        cls.pool_manager.base_maker_fee_usdt = Decimal('0')
        cls.pool_manager.save(update_fields=('base_fee', 'base_fee_usdt', 'base_maker_fee', 'base_maker_fee_usdt'))
        cls.pools = [
            LiquidityPool.objects.create(
                currency=Currencies.btc,
                capacity=10,
                manager_id=410,
                is_active=True,
                activated_at=ir_now(),
            ),
            LiquidityPool.objects.create(
                currency=Currencies.rls,
                capacity=10,
                manager_id=402,
                is_active=True,
                activated_at=ir_now(),
            ),
        ]

        cls.src_wallet = Wallet.get_user_wallet(cls.pool_manager, Currencies.btc)
        cls.dst_wallets = []
        for currency in (RIAL, TETHER):
            cls.dst_wallets.append(Wallet.get_user_wallet(cls.pool_manager, currency))

        cls.markets = {
            RIAL: Market.objects.get(src_currency=Currencies.btc, dst_currency=RIAL, is_active=True),
            TETHER: Market.objects.get(src_currency=Currencies.btc, dst_currency=TETHER, is_active=True),
        }
        cls.liquidation_requests = [
            LiquidationRequest(
                src_wallet=cls.src_wallet,
                dst_wallet=cls.dst_wallets[0],
                side=LiquidationRequest.SIDES.sell,
                status=LiquidationRequest.STATUS.pending,
                amount=Decimal('0.5'),
            ),
            LiquidationRequest(
                src_wallet=cls.src_wallet,
                dst_wallet=cls.dst_wallets[0],
                side=LiquidationRequest.SIDES.buy,
                status=LiquidationRequest.STATUS.done,
                amount=Decimal('1.5'),
            ),
        ]
        LiquidationRequest.objects.bulk_create(cls.liquidation_requests)

    def setUp(self):
        cache.clear()
        # set key cache
        last_prices = {
            RIAL: Decimal('10_000_000_000_0'),
            TETHER: Decimal('1'),
        }
        # charge wallets
        for currency in (RIAL, TETHER):
            wallet = Wallet.get_user_wallet(self.pool_manager, currency)
            self._charge_wallet(wallet, Decimal('10_200_000_000_1'))
            self._set_last_trade_price(self.markets[currency], last_prices[currency])
        self._charge_wallet(self.src_wallet)
        for w in self.dst_wallets:
            w.refresh_from_db()

    @classmethod
    def _set_last_trade_price(cls, market: Market, price: Decimal = Decimal('1')):
        cache.set(f'market_{market.pk}_last_price', price)

    @classmethod
    def _charge_wallet(cls, wallet: Wallet, initial_balance: int = 10) -> Wallet:
        balance = wallet.balance
        wallet.create_transaction('manual', (initial_balance - balance)).commit()
        return wallet

    @classmethod
    def _change_creation_and_update_datetime_to(cls, liquidations: List[Liquidation], minutes: int = 3):
        orders = []
        for liquidation in liquidations:
            liquidation.created_at -= timedelta(minutes=minutes)
            liquidation.updated_at -= timedelta(minutes=minutes)
            orders.append(liquidation.order_id)
        Liquidation.objects.bulk_update(liquidations, fields=('created_at', 'updated_at'))
        Order.objects.filter(id__in=orders).update(created_at=F('created_at') - timedelta(minutes=minutes))

    def _call_create_order_task(self):
        task_process_pending_liquidation_request()

    def _convert_pending_request_to_in_progress(self, *, should_change_order_time: bool = True):
        assert Liquidation.objects.count() == 0
        self._call_create_order_task()
        assert Liquidation.objects.count() == 2

        # nothing happened because of expired ordered time
        task_check_status_internal_liquidation()
        liquidations = Liquidation.objects.all()
        for liq in liquidations:
            assert liq.status == Liquidation.STATUS.open
            assert liq.order_id

        # change order time
        if should_change_order_time:
            self._change_creation_and_update_datetime_to(liquidations)

    def _update_liquidations(
        self,
        liquidation_status: int = Liquidation.STATUS.ready_to_share,
        order_status: Optional[int] = None,
    ):
        task_check_status_internal_liquidation()
        liquidations = Liquidation.objects.all()

        for liq in liquidations:
            assert liq.status == liquidation_status
            if order_status:
                assert liq.order.status == order_status

    def _update_liquidation_requests(self, liquidation_status: int):
        task_update_liquidation_request()
        task_submit_liquidation_requests_external_wallet_transactions()
        liquidations = Liquidation.objects.all()
        for liq in liquidations:
            assert liq.status == liquidation_status

    @staticmethod
    def fill_order(order: Order, filled_amount: str, filled_total_price: str, fee: str):
        order.matched_amount += Decimal(filled_amount)
        order.matched_total_price += Decimal(filled_total_price)
        order.fee += Decimal(fee)
        if order.matched_amount < order.amount:
            order.status = Order.STATUS.active
        else:
            order.status = Order.STATUS.done
        order.save(update_fields=('matched_amount', 'matched_total_price', 'fee', 'status'))

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_order_market_new_status(self):
        self._convert_pending_request_to_in_progress(should_change_order_time=False)
        liquidation_status = Liquidation.STATUS.open
        self._update_liquidations(liquidation_status=liquidation_status, order_status=Order.STATUS.active)
        self._update_liquidation_requests(liquidation_status=liquidation_status)

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_order_market_unfilled(self):
        with patch('django.utils.timezone.now', return_value=IR_NOW - timedelta(minutes=3)):
            self._convert_pending_request_to_in_progress()

        self._update_liquidations(order_status=Order.STATUS.canceled)
        self._update_liquidation_requests(liquidation_status=Liquidation.STATUS.done)
        liquidation_requests = LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.pending)
        assert len(liquidation_requests) == 1
        assert liquidation_requests[0].filled_amount == Decimal('0')

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_order_market_almost_filled(self):
        with patch('django.utils.timezone.now', return_value=IR_NOW - timedelta(minutes=3)):
            self._convert_pending_request_to_in_progress()

        liquidation = Liquidation.objects.first()
        order = liquidation.order
        amount = order.amount / 2
        total = amount * order.price
        fee = total * FEE_RATE
        self.fill_order(order, amount, total, fee)
        self._update_liquidations(order_status=Order.STATUS.canceled)
        self._update_liquidation_requests(liquidation_status=Liquidation.STATUS.done)
        liquidation_requests = LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.pending)
        assert len(liquidation_requests) == 1
        assert liquidation_requests[0].filled_amount == amount
        assert liquidation_requests[0].filled_total_price == (total - fee)
        assert liquidation_requests[0].fee == (total - fee) * FEE_RATE

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_order_market_filled(self):
        self._convert_pending_request_to_in_progress()
        liquidations = Liquidation.objects.select_related('order').all()
        for liquidation in liquidations:
            order = liquidation.order
            amount = order.amount
            total = amount * order.price
            fee = total * FEE_RATE
            self.fill_order(order, amount, total, fee)
        self._update_liquidations(order_status=Order.STATUS.done)
        self._update_liquidation_requests(liquidation_status=Liquidation.STATUS.done)
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.pending).count() == 0
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.done).count() == 2
        liquidation = LiquidationRequest.objects.get(status=LiquidationRequest.STATUS.done, amount=Decimal('0.5'))
        assert liquidation.amount == liquidation.filled_amount

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_order_market_almost_filled_two_orders(self):
        self._convert_pending_request_to_in_progress()
        liquidations = Liquidation.objects.select_related('order').all()
        for liquidation in liquidations:
            order = liquidation.order
            amount = order.amount / 2
            total = amount * order.price
            fee = total * FEE_RATE
            self.fill_order(order, amount, total, fee)
        order.created_at += timedelta(minutes=2)
        order.save(update_fields=('created_at',))
        task_check_status_internal_liquidation()
        task_update_liquidation_request()
        task_submit_liquidation_requests_external_wallet_transactions()
        assert Liquidation.objects.filter(status=Liquidation.STATUS.open).count() == 1
        assert Liquidation.objects.filter(status=Liquidation.STATUS.done).count() == 1
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.in_progress).count() == 1
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.pending).count() == 0
        self._call_create_order_task()
        assert Liquidation.objects.filter(status=Liquidation.STATUS.open).count() == 1

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_order_market_with_matcher(self):
        # save balance wallets
        balance_btc = self.src_wallet.balance
        balance_rial = self.dst_wallets[0].balance
        LiquidationRequest.objects.create(
            src_wallet=self.src_wallet,
            dst_wallet=self.dst_wallets[0],
            side=LiquidationRequest.SIDES.buy,
            status=LiquidationRequest.STATUS.pending,
            amount=Decimal('1'),
        )
        assert Liquidation.objects.count() == 0
        self._call_create_order_task()
        self._call_create_order_task()
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.in_progress).count() == 2
        assert Liquidation.objects.count() == 4
        do_matching_round(self.markets[RIAL], reinitialize_caches=True)
        task_check_status_internal_liquidation()
        task_update_liquidation_request()
        task_submit_liquidation_requests_external_wallet_transactions()
        assert Liquidation.objects.filter(status=Liquidation.STATUS.open).count() == 0
        assert Liquidation.objects.filter(status=Liquidation.STATUS.done).count() == 4
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.in_progress).count() == 0
        # check balance wallets after liquidations is done
        self.src_wallet.refresh_from_db()
        assert self.src_wallet.balance == balance_btc
        self.dst_wallets[0].refresh_from_db()
        assert self.dst_wallets[0].balance == balance_rial

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_near_to_zero_unfilled_amount(self):
        self._convert_pending_request_to_in_progress()
        liquidation = Liquidation.objects.first()
        order = liquidation.order
        amount = order.amount - Decimal('0.000000001')
        total = amount * order.price
        fee = total * FEE_RATE
        self.fill_order(order, amount, total, fee)
        self._update_liquidations(order_status=Order.STATUS.canceled)
        self._update_liquidation_requests(liquidation_status=Liquidation.STATUS.done)
        liquidation_request = liquidation.liquidation_requests.first()
        assert liquidation_request.filled_amount == amount
