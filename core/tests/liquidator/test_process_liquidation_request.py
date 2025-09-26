from datetime import timedelta
from decimal import Decimal
from typing import List
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.models import RIAL, TETHER, Currencies
from exchange.liquidator.constants import TOLERANCE_MARK_PRICE, TOLERANCE_ORDER_PRICE
from exchange.liquidator.crons import DeleteEmptyLiquidation
from exchange.liquidator.models import Liquidation, LiquidationRequest
from exchange.liquidator.tasks import task_create_internal_order, task_process_pending_liquidation_request
from exchange.market.models import Market, Order
from exchange.wallet.models import Wallet
from tests.base.utils import mock_on_commit


class TestLiquidationRequestProcess(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pool_manager = User.objects.get(pk=410)
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
                side=LiquidationRequest.SIDES.buy,
                status=LiquidationRequest.STATUS.pending,
                amount=Decimal('1'),
            ),
            LiquidationRequest(
                src_wallet=cls.src_wallet,
                dst_wallet=cls.dst_wallets[0],
                side=LiquidationRequest.SIDES.sell,
                status=LiquidationRequest.STATUS.pending,
                amount=Decimal('2'),
            ),
            LiquidationRequest(
                src_wallet=cls.src_wallet,
                dst_wallet=cls.dst_wallets[0],
                side=LiquidationRequest.SIDES.sell,
                status=LiquidationRequest.STATUS.in_progress,
                amount=Decimal('0.75'),
            ),
            LiquidationRequest(
                src_wallet=cls.src_wallet,
                dst_wallet=cls.dst_wallets[0],
                side=LiquidationRequest.SIDES.sell,
                status=LiquidationRequest.STATUS.done,
                amount=Decimal('1.5'),
            ),
            LiquidationRequest(
                src_wallet=cls.src_wallet,
                dst_wallet=cls.dst_wallets[1],
                side=LiquidationRequest.SIDES.buy,
                status=LiquidationRequest.STATUS.pending,
                amount=Decimal('0.4'),
            ),
        ]
        LiquidationRequest.objects.bulk_create(cls.liquidation_requests)

    def setUp(self):
        cache.clear()

    @classmethod
    def _set_last_trade_price(cls, market: Market, price: Decimal = Decimal('1')):
        cache.set(f'market_{market.pk}_last_price', price)

    @classmethod
    def _charge_wallet(cls, wallet: Wallet, initial_balance: int = 10) -> Wallet:
        wallet.refresh_from_db()
        balance = wallet.balance
        wallet.create_transaction('manual', (initial_balance - balance)).commit()

    @classmethod
    def _change_creation_and_update_datetime_to(cls, liquidations: List[Liquidation], minutes: int = 5):
        for liquidation in liquidations:
            liquidation.updated_at -= timedelta(minutes=minutes)
        return liquidations

    def _call_create_order_task(self):
        with patch('django.db.transaction.on_commit', mock_on_commit):
            task_process_pending_liquidation_request()

    @patch('exchange.liquidator.services.liquidation_creator.Notification.notify_admins', new_callable=MagicMock)
    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_empty_last_price(self, notify_admins_mock: MagicMock):
        assert Liquidation.objects.count() == 0
        self._call_create_order_task()
        assert Liquidation.objects.count() == 0
        pk = LiquidationRequest.objects.order_by('id').last().pk
        notify_admins_mock.assert_called_with(
            f'Cannot create liquidation: #{pk}\nReason: Last price is empty',
            title='‼️LiquidationRequest - BTCUSDT',
            channel='liquidator',
        )

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_empty_src_wallet(self):
        """
        buy 1 btc with rls: 1*100
        buy 0.4 btc with usdt: 0.4*1
        """
        last_prices = {
            RIAL: Decimal('100'),
            TETHER: Decimal('1'),
        }
        for currency in (RIAL, TETHER):
            wallet = Wallet.get_user_wallet(self.pool_manager, currency)
            self._charge_wallet(wallet, Decimal('100000'))
            self._set_last_trade_price(self.markets[currency], last_prices[currency])

        assert Liquidation.objects.count() == 0
        self._call_create_order_task()
        liquidations = Liquidation.objects.all()
        Liquidation.objects.bulk_update(
            self._change_creation_and_update_datetime_to(liquidations),
            fields=('updated_at',),
        )
        DeleteEmptyLiquidation().run()
        liquidations = Liquidation.objects.filter(status=Liquidation.STATUS.open)
        assert len(liquidations) == 2
        for liquidation in liquidations:
            assert liquidation.side == Liquidation.SIDES.buy

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_empty_dst_wallet(self):
        last_prices = {
            RIAL: Decimal('100000'),
            TETHER: Decimal('1'),
        }
        for currency in (RIAL, TETHER):
            self._set_last_trade_price(self.markets[currency], last_prices[currency])
        self._charge_wallet(self.src_wallet)

        assert Liquidation.objects.count() == 0
        self._call_create_order_task()
        liquidations = Liquidation.objects.all()
        assert len(liquidations) == 3
        Liquidation.objects.bulk_update(
            self._change_creation_and_update_datetime_to(liquidations),
            fields=('updated_at',),
        )
        DeleteEmptyLiquidation().run()
        liquidations = Liquidation.objects.all()
        assert len(liquidations) == 1
        assert liquidations[0].side == Liquidation.SIDES.sell
        order = liquidations[0].order
        assert order.price == last_prices[liquidations[0].dst_currency] * (1 - TOLERANCE_ORDER_PRICE)

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_successful_run_cron(self):
        last_prices = {
            RIAL: Decimal('1_000_000_000_0'),
            TETHER: Decimal('1'),
        }
        for currency in (RIAL, TETHER):
            wallet = Wallet.get_user_wallet(self.pool_manager, currency)
            self._charge_wallet(wallet, Decimal('10_020_000_000_0'))
            self._set_last_trade_price(self.markets[currency], last_prices[currency])
        self._charge_wallet(self.src_wallet)
        assert Liquidation.objects.count() == 0
        self._call_create_order_task()
        assert Liquidation.objects.count() == 3

        liquidation_requests = LiquidationRequest.objects.filter(
            status=LiquidationRequest.STATUS.in_progress,
        ).prefetch_related('liquidations')

        assert len(liquidation_requests) == 4

        for liquidation_request in liquidation_requests:
            liquidations = liquidation_request.liquidations.all()
            if liquidations:
                amount = sum(l.amount for l in liquidations)
                assert amount == liquidation_request.amount

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_check_delete_cron_two_liquidations_on_one_request(self):
        last_prices = {
            RIAL: Decimal('10_000_000_000_0'),
            TETHER: Decimal('1'),
        }
        for currency in (RIAL, TETHER):
            wallet = Wallet.get_user_wallet(self.pool_manager, currency)
            self._charge_wallet(wallet, Decimal('10_020_000_000_0'))
            self._set_last_trade_price(self.markets[currency], last_prices[currency])
        self._charge_wallet(self.src_wallet)
        assert Liquidation.objects.count() == 0
        self._call_create_order_task()
        task_process_pending_liquidation_request()
        assert Liquidation.objects.filter(status=Liquidation.STATUS.open).count() == 3
        new_liquidations = Liquidation.objects.filter(status=Liquidation.STATUS.new)
        assert len(new_liquidations) == 2
        Liquidation.objects.bulk_update(
            self._change_creation_and_update_datetime_to(new_liquidations),
            fields=('updated_at',),
        )
        DeleteEmptyLiquidation().run()
        assert Liquidation.objects.count() == 3

        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.in_progress).count() == 3
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.pending).count() == 1

    @classmethod
    def _set_mark_price(cls, currency: int, price: Decimal = Decimal('1')):
        cache.set(f'mark_price_{currency}', price)

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_set_correct_price_for_liquidation_order(self):
        self._charge_wallet(self.src_wallet)
        btc_mark_price = Decimal('10')
        usdt_rls_last_trade = Decimal('100')
        self._set_mark_price(Currencies.btc, btc_mark_price)
        self._set_last_trade_price(Market.get_for(TETHER, RIAL), usdt_rls_last_trade)
        last_prices = {
            RIAL: Decimal('1000'),
            TETHER: Decimal('9'),
        }
        for currency in (RIAL, TETHER):
            wallet = Wallet.get_user_wallet(self.pool_manager, currency)
            self._charge_wallet(wallet, Decimal('100000'))
            self._set_last_trade_price(self.markets[currency], last_prices[currency])
        assert Liquidation.objects.count() == 0
        self._call_create_order_task()
        assert Liquidation.objects.count() == 3
        sell_liquidation = Liquidation.objects.filter(side=Liquidation.SIDES.sell).first()
        assert sell_liquidation is not None
        sell_order = sell_liquidation.order
        assert sell_order.price == btc_mark_price * usdt_rls_last_trade * (1 - TOLERANCE_MARK_PRICE)
        buy_orders = dict(
            Order.objects.filter(
                id__in=Liquidation.objects.filter(side=Liquidation.SIDES.buy).values('order_id'),
            ).values_list('dst_currency', 'price')
        )
        assert buy_orders[RIAL] == btc_mark_price * usdt_rls_last_trade * (1 + TOLERANCE_MARK_PRICE)
        assert buy_orders[TETHER] == last_prices[TETHER] * (1 + TOLERANCE_ORDER_PRICE)
