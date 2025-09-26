from datetime import timedelta
from decimal import Decimal
from typing import List
from unittest.mock import MagicMock, patch

import responses
from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import RIAL, TETHER, Currencies, get_currency_codename
from exchange.liquidator.broker_apis import SettlementRequest
from exchange.liquidator.broker_apis.settlement_request_api import SettlementRequestErrorEnum
from exchange.liquidator.crons import DeleteEmptyLiquidation
from exchange.liquidator.models import Liquidation, LiquidationRequest
from exchange.liquidator.services import ExternalOrderCreator
from exchange.liquidator.tasks import (
    task_create_external_order,
    task_process_pending_liquidation_request,
)
from exchange.market.models import Market, Order
from exchange.wallet.models import Wallet
from tests.base.utils import mock_on_commit


def mock_get_mark_price(_, dst_currency: int):
    if dst_currency == RIAL:
        return Decimal('1')
    if dst_currency == TETHER:
        return Decimal('100')
    return None


def mock_ethereum_price(_, dst_currency):
    if dst_currency == RIAL:
        return Decimal('1000')
    if dst_currency == TETHER:
        return Decimal('1')


def mock_rial_usdt_price_range(*args, **kwargs):
    return Decimal('1000'), Decimal('1000')


IR_NOW = ir_now()


@patch('exchange.liquidator.services.liquidation_creator.LIQUIDATOR_EXTERNAL_CURRENCIES', {Currencies.eth})
@patch('django.db.transaction.on_commit', mock_on_commit)
class TestLiquidationRequestProcess(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.src_currencies = (Currencies.btc, Currencies.eth)
        cls.dst_currencies = [RIAL, TETHER]
        cls.pool_managers = [User.objects.get(pk=410), User.objects.get(pk=411)]
        cls.src_wallets = [Wallet.get_user_wallet(p, c) for p, c in zip(cls.pool_managers, cls.src_currencies)]
        cls.dst_wallets = [Wallet.get_user_wallet(p, d) for p in cls.pool_managers for d in cls.dst_currencies]

        cls.pool_ethereum_wallet = cls.src_wallets[1]
        cls.pool_rial_wallet = cls.dst_wallets[2]
        cls.pool_tether_wallet = cls.dst_wallets[3]

        cls.markets = {
            (src, dst): Market.objects.get(src_currency=src, dst_currency=dst, is_active=True)
            for src in cls.src_currencies
            for dst in cls.dst_currencies
        }

    def setUp(self):
        self.liquidation_requests = [
            LiquidationRequest(
                src_wallet=self.src_wallets[1],
                dst_wallet=self.dst_wallets[2],
                side=LiquidationRequest.SIDES.buy,
                status=LiquidationRequest.STATUS.pending,
                amount=Decimal('1'),
            ),
            LiquidationRequest(
                src_wallet=self.src_wallets[1],
                dst_wallet=self.dst_wallets[2],
                side=LiquidationRequest.SIDES.sell,
                status=LiquidationRequest.STATUS.pending,
                amount=Decimal('2'),
            ),
            LiquidationRequest(
                src_wallet=self.src_wallets[1],
                dst_wallet=self.dst_wallets[2],
                side=LiquidationRequest.SIDES.sell,
                status=LiquidationRequest.STATUS.in_progress,
                amount=Decimal('0.75'),
            ),
            LiquidationRequest(
                src_wallet=self.src_wallets[1],
                dst_wallet=self.dst_wallets[2],
                side=LiquidationRequest.SIDES.sell,
                status=LiquidationRequest.STATUS.done,
                amount=Decimal('1.5'),
            ),
            LiquidationRequest(
                src_wallet=self.src_wallets[1],
                dst_wallet=self.dst_wallets[2],
                side=LiquidationRequest.SIDES.buy,
                status=LiquidationRequest.STATUS.pending,
                amount=Decimal('0.4'),
            ),
        ]
        LiquidationRequest.objects.bulk_create(self.liquidation_requests)

        cache.clear()

    def tearDown(self) -> None:
        cache.clear()

    @staticmethod
    def _set_last_trade_price(market: Market, price: Decimal = Decimal('1')):
        cache.set(f'market_{market.pk}_last_price', price)

    @staticmethod
    def _charge_wallet(wallet: Wallet, initial_balance: int = 10):
        wallet.refresh_from_db()
        wallet.create_transaction('manual', initial_balance - wallet.balance).commit()

    @classmethod
    def charge_wallets(cls, last_prices):
        for currency in (RIAL, TETHER):
            wallet = Wallet.get_user_wallet(cls.pool_managers[1], currency)
            cls._charge_wallet(wallet, Decimal('100000'))
            cls._set_last_trade_price(cls.markets[Currencies.eth, currency], last_prices[currency])
        cls._charge_wallet(cls.src_wallets[1])

    @classmethod
    def run_order_creator_tasks(cls):
        task_process_pending_liquidation_request()

    @staticmethod
    def _check_amounts(liquidation_requests: List[LiquidationRequest]):
        for liquidation_request in liquidation_requests:
            liquidations = liquidation_request.liquidations.all()
            if liquidations:
                amount = sum(liq.amount for liq in liquidations)
                assert amount == liquidation_request.amount

    @staticmethod
    def create_response_with_complete_body(
        liquidation: Liquidation,
    ):
        responses.post(
            url=SettlementRequest.get_base_url() + SettlementRequest.url,
            json={
                'result': {'liquidationId': 1012, 'clientId': 'clid_00000008', 'status': 'open'},
                'message': 'request accepted',
                'error': None,
                'hasError': False,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'clientId': f'{ExternalOrderCreator.prefix_id}{liquidation.pk}',
                        'baseCurrency': get_currency_codename(liquidation.src_currency),
                        'quoteCurrency': get_currency_codename(liquidation.dst_currency),
                        'side': 'sell' if liquidation.is_sell else 'buy',
                        'amount': str(liquidation.amount),
                        'ttl': SettlementRequest.ttl,
                    },
                    strict_match=False,
                ),
            ],
        )

    @staticmethod
    def create_response_4xx(
        liquidation: Liquidation,
    ):
        responses.post(
            url=SettlementRequest.get_base_url() + SettlementRequest.url,
            status=400,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'clientId': f'{ExternalOrderCreator.prefix_id}{liquidation.pk}',
                        'baseCurrency': get_currency_codename(liquidation.src_currency),
                        'quoteCurrency': get_currency_codename(liquidation.dst_currency),
                        'side': 'sell' if liquidation.is_sell else 'buy',
                        'amount': str(liquidation.amount),
                        'ttl': SettlementRequest.ttl,
                    },
                    strict_match=False,
                ),
            ],
        )

    @staticmethod
    def create_small_amount_response_400(liquidation: Liquidation):
        resp_json = {
            "result": None,
            "message": "error",
            "error": SettlementRequestErrorEnum.SMALL_ORDER.value,
            "hasError": True,
        }
        responses.post(
            url=SettlementRequest.get_base_url() + SettlementRequest.url,
            status=400,
            json=resp_json,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'clientId': f'{ExternalOrderCreator.prefix_id}{liquidation.pk}',
                    },
                    strict_match=False,
                ),
            ],
        )

    @staticmethod
    def create_orders():
        for liq in Liquidation.objects.all():
            ExternalOrderCreator.process(liquidation_id=liq.id)

    @patch('exchange.liquidator.services.liquidation_creator.Notification.notify_admins', new_callable=MagicMock)
    def test_empty_last_price(self, notify_admins_mock: MagicMock):
        with patch(
            'exchange.liquidator.services.liquidation_creator.MarkPriceCalculator.get_mark_price',
            mock_get_mark_price,
        ):
            assert Liquidation.objects.count() == 0
            task_process_pending_liquidation_request()
            assert Liquidation.objects.count() == 3

        Liquidation.objects.update(primary_price=Decimal(0))
        self.create_orders()
        assert notify_admins_mock.call_count == 3
        liquidation = Liquidation.objects.last()
        notify_admins_mock.assert_called_with(
            f'Cannot create order. liquidation: #{liquidation.pk} - type: 2\nReason: price is empty',
            title=f'‼️Ordering - {liquidation.symbol}',
            channel='liquidator',
        )

    @patch('exchange.liquidator.services.liquidation_creator.MarkPriceCalculator.get_mark_price', mock_get_mark_price)
    @patch('exchange.liquidator.services.liquidation_creator.Notification.notify_admins', new_callable=MagicMock)
    def test_empty_wallet(self, notify_admins_mock: MagicMock):
        with patch('django.utils.timezone.now', lambda: IR_NOW - timedelta(minutes=5)):
            assert Liquidation.objects.count() == 0

            with patch.object(task_create_external_order, 'delay', task_create_external_order):
                self.run_order_creator_tasks()

            assert notify_admins_mock.call_count == 3
            liquidation = Liquidation.objects.last()
            notify_admins_mock.assert_called_with(
                f'Cannot create order. liquidation: #{liquidation.pk} - type: 2\nReason: Insufficient Balance',
                title=f'‼️Ordering - {liquidation.symbol}',
                channel='liquidator',
            )

        assert Liquidation.objects.filter(status=Liquidation.STATUS.new).count() == 3
        DeleteEmptyLiquidation().run()
        assert Liquidation.objects.count() == 0

    @responses.activate
    @patch('exchange.liquidator.services.liquidation_creator.MarkPriceCalculator.get_mark_price', mock_get_mark_price)
    def test_successful_run_cron(self):
        last_prices = {
            RIAL: Decimal('1000'),
            TETHER: Decimal('1'),
        }
        self.charge_wallets(last_prices)
        assert Liquidation.objects.count() == 0

        with patch.object(task_create_external_order, 'delay'):
            task_process_pending_liquidation_request()

        liquidations = Liquidation.objects.all()
        assert len(liquidations) == 3
        for liquidation in liquidations:
            assert not liquidation.order_id
            self.create_response_with_complete_body(liquidation)

        self.create_orders()
        assert Liquidation.objects.filter(status=Liquidation.STATUS.open).count() == 3

        liquidation_requests = LiquidationRequest.objects.filter(
            status=LiquidationRequest.STATUS.in_progress,
        ).prefetch_related('liquidations')

        assert len(liquidation_requests) == 4
        self._check_amounts(liquidation_requests)

    @responses.activate
    @patch('exchange.liquidator.services.liquidation_creator.MarkPriceCalculator.get_mark_price', mock_get_mark_price)
    def test_successful_run_cron_with_duplication_error(self):
        responses.post(
            url=SettlementRequest.get_base_url() + SettlementRequest.url,
            json={
                'result': None,
                'message': 'internal error',
                'error': 'duplicate clientId',
                'hasError': True,
            },
            status=400,
        )
        assert Liquidation.objects.count() == 0
        with patch.object(task_create_external_order, 'delay', task_create_external_order):
            self.run_order_creator_tasks()
        assert Liquidation.objects.count() == 3

        liquidation_requests = LiquidationRequest.objects.filter(
            status=LiquidationRequest.STATUS.in_progress,
        ).prefetch_related('liquidations')

        assert len(liquidation_requests) == 4
        self._check_amounts(liquidation_requests)

    @responses.activate
    @patch('exchange.liquidator.services.liquidation_creator.MarkPriceCalculator.get_mark_price', mock_get_mark_price)
    def test_successful_run_cron_with_other_4xx_errors(self):
        last_prices = {
            RIAL: Decimal('1000'),
            TETHER: Decimal('1'),
        }
        self.charge_wallets(last_prices)

        assert Order.objects.count() == 0
        assert Liquidation.objects.count() == 0

        with patch.object(task_create_external_order, 'delay'):
            task_process_pending_liquidation_request()

        liquidations = Liquidation.objects.all()
        assert len(liquidations) == 3
        for liquidation in liquidations:
            assert not liquidation.order_id
            self.create_response_4xx(liquidation)

        self.create_orders()

        liquidations = Liquidation.objects.filter(status=Liquidation.STATUS.open)
        assert len(liquidations) == 3
        for liq in liquidations:
            assert liq.tracking_id.startswith('!liquidation')
            assert liq.order is not None
            assert liq.market_type == Liquidation.MARKET_TYPES.internal
        assert Order.objects.count() == 3

        liquidation_requests = LiquidationRequest.objects.filter(
            status=LiquidationRequest.STATUS.in_progress,
        ).prefetch_related('liquidations')

        assert len(liquidation_requests) == 4
        self._check_amounts(liquidation_requests)

    @patch(
        'exchange.liquidator.services.order_creator.PriceEstimator.get_price_range',
        side_effect=mock_rial_usdt_price_range,
    )
    @patch('exchange.liquidator.services.liquidation_creator.MarkPriceCalculator.get_mark_price', mock_ethereum_price)
    def test_switch_to_internal_order_for_below_threshold(self, mock_rial_usdt):
        """
        Test prices:
            Rial -> Usdt = 1000
            Eth -> Usdt = 1
            Eth -> Rial = 1000
        """
        last_prices = {
            RIAL: Decimal('1000'),
            TETHER: Decimal('1'),
        }
        self.charge_wallets(last_prices)

        LiquidationRequest.objects.all().delete()

        LiquidationRequest.objects.create(
            src_wallet=self.pool_ethereum_wallet,
            dst_wallet=self.pool_rial_wallet,
            side=LiquidationRequest.SIDES.buy,
            status=LiquidationRequest.STATUS.pending,
            amount=Decimal('1'),
            filled_amount=Decimal('0.9'),
            filled_total_price=Decimal('900'),
        )

        assert Liquidation.objects.count() == 0
        with patch.object(task_create_external_order, 'delay'):
            task_process_pending_liquidation_request()

        assert Liquidation.objects.count() == 1

        liquidation = Liquidation.objects.first()

        self.create_orders()

        mock_rial_usdt.assert_called()

        liquidation.refresh_from_db()
        assert liquidation.market_type == Liquidation.MARKET_TYPES.internal

    @responses.activate
    @patch(
        'exchange.liquidator.services.order_creator.PriceEstimator.get_price_range',
        side_effect=mock_rial_usdt_price_range,
    )
    @patch('exchange.liquidator.services.liquidation_creator.MarkPriceCalculator.get_mark_price', mock_ethereum_price)
    def test_switch_to_internal_on_small_order_error(self, mock_rial_usdt):
        """
        Test prices:
            Rial -> Usdt = 1000
            Eth -> Usdt = 1
            Eth -> Rial = 1000
        """
        last_prices = {
            RIAL: Decimal('1000'),
            TETHER: Decimal('1'),
        }
        self.charge_wallets(last_prices)

        LiquidationRequest.objects.all().delete()

        LiquidationRequest.objects.create(
            src_wallet=self.pool_ethereum_wallet,
            dst_wallet=self.pool_rial_wallet,
            side=LiquidationRequest.SIDES.buy,
            status=LiquidationRequest.STATUS.pending,
            amount=Decimal('10'),
            filled_amount=Decimal('3'),
            filled_total_price=Decimal('3000'),
        )

        assert Liquidation.objects.count() == 0

        with patch.object(task_create_external_order, 'delay'):
            task_process_pending_liquidation_request()

        assert Liquidation.objects.count() == 1

        liquidation = Liquidation.objects.first()
        self.create_small_amount_response_400(liquidation)

        self.create_orders()

        mock_rial_usdt.assert_called()

        liquidation.refresh_from_db()
        assert liquidation.market_type == Liquidation.MARKET_TYPES.internal
