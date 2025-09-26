from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List
from unittest.mock import MagicMock, patch

import responses
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone as django_timezone

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import RIAL, TETHER, Currencies, get_currency_codename
from exchange.liquidator.broker_apis import SettlementRequest, SettlementStatus
from exchange.liquidator.models import Liquidation, LiquidationRequest
from exchange.liquidator.tasks import (
    task_check_status_external_liquidation,
    task_create_external_order,
    task_process_pending_liquidation_request,
    task_update_status_external_liquidation,
)
from exchange.market.models import Market
from exchange.wallet.models import Wallet
from tests.base.utils import mock_on_commit


def mock_get_mark_price(_, dst_currency: int):
    if dst_currency == RIAL:
        return Decimal('1')
    if dst_currency == TETHER:
        return Decimal('100')
    return None


IR_NOW = ir_now()
PRICE = Decimal(100)
NOW = django_timezone.now()

@patch('exchange.liquidator.services.liquidation_creator.LIQUIDATOR_EXTERNAL_CURRENCIES', {Currencies.eth})
@patch('django.db.transaction.on_commit', mock_on_commit)
@patch.object(task_create_external_order, 'delay', task_create_external_order)
@patch.object(task_update_status_external_liquidation, 'delay', task_update_status_external_liquidation)
@patch('exchange.liquidator.services.liquidation_creator.MarkPriceCalculator.get_mark_price', mock_get_mark_price)
@patch('exchange.liquidator.services.order_creator.ir_now', lambda: IR_NOW)
@patch('exchange.liquidator.tasks.ir_now', lambda: IR_NOW + timedelta(minutes=5))
class TestLiquidationRequestProcess(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.src_currencies = (Currencies.btc, Currencies.eth)
        cls.dst_currencies = [RIAL, TETHER]
        cls.pool_managers = [User.objects.get(pk=410), User.objects.get(pk=411)]
        cls.src_wallets = [Wallet.get_user_wallet(p, c) for p, c in zip(cls.pool_managers, cls.src_currencies)]
        cls.dst_wallets = [Wallet.get_user_wallet(p, d) for p in cls.pool_managers for d in cls.dst_currencies]

        cls.markets = {
            (src, dst): Market.objects.get(src_currency=src, dst_currency=dst, is_active=True)
            for src in cls.src_currencies
            for dst in cls.dst_currencies
        }
        cls.liquidation_requests = [
            LiquidationRequest(
                src_wallet=cls.src_wallets[1],
                dst_wallet=cls.dst_wallets[2],
                side=LiquidationRequest.SIDES.buy,
                status=LiquidationRequest.STATUS.pending,
                amount=Decimal('1'),
            ),
            LiquidationRequest(
                src_wallet=cls.src_wallets[1],
                dst_wallet=cls.dst_wallets[2],
                side=LiquidationRequest.SIDES.sell,
                status=LiquidationRequest.STATUS.pending,
                amount=Decimal('2'),
            ),
            LiquidationRequest(
                src_wallet=cls.src_wallets[1],
                dst_wallet=cls.dst_wallets[2],
                side=LiquidationRequest.SIDES.sell,
                status=LiquidationRequest.STATUS.in_progress,
                amount=Decimal('0.75'),
            ),
            LiquidationRequest(
                src_wallet=cls.src_wallets[1],
                dst_wallet=cls.dst_wallets[2],
                side=LiquidationRequest.SIDES.sell,
                status=LiquidationRequest.STATUS.done,
                amount=Decimal('1.5'),
            ),
        ]
        LiquidationRequest.objects.bulk_create(cls.liquidation_requests)

    def setUp(self):
        cache.clear()
        for wallet in self.src_wallets:
            self._charge_wallet(wallet, Decimal('3'))
        for wallet in self.dst_wallets:
            self._charge_wallet(wallet, Decimal('100'))

    def tearDown(self) -> None:
        cache.clear()

    @staticmethod
    def _charge_wallet(wallet: Wallet, final_balance: Decimal):
        balance = wallet.balance
        wallet.create_transaction('manual', (final_balance - balance)).commit()

    @classmethod
    def run_order_creator_tasks(cls):
        task_process_pending_liquidation_request()

    @staticmethod
    def _check_amounts(liquidations: List[Liquidation], coefficient: Decimal = Decimal(1), price: Decimal = PRICE):
        for liquidation in liquidations:
            liquidation_request = liquidation.liquidation_requests.first()
            assert liquidation_request.amount * coefficient == liquidation.filled_amount
            assert liquidation.filled_total_price == liquidation_request.amount * coefficient * price

    @staticmethod
    def create_external_order_successful_response():
        responses.post(
            url=SettlementRequest.get_base_url() + SettlementRequest.url,
            json={
                'result': {'liquidationId': 1012, 'clientId': 'clid_00000008', 'status': 'open'},
                'message': 'request accepted',
                'error': None,
                'hasError': False,
            },
            status=200,
        )

    def _create_response_with_complete_body(
        self,
        liquidation: Liquidation,
        status: str,
        filled_amount: Decimal,
        filled_price: Decimal,
        server_time: datetime = IR_NOW,
    ):

        created_time = IR_NOW.astimezone(timezone.utc)
        expire_time = created_time + timedelta(milliseconds=SettlementRequest.ttl)
        responses.get(
            url=SettlementStatus.get_base_url() + SettlementStatus.url,
            json={
                'result': {
                    'liquidationId': liquidation.pk,
                    'status': status,
                    'clientId': liquidation.tracking_id,
                    'baseCurrency': get_currency_codename(liquidation.src_currency),
                    'quoteCurrency': get_currency_codename(liquidation.dst_currency),
                    'side': 'sell' if liquidation.is_sell else 'buy',
                    'amount': str(liquidation.amount),
                    'price': 0,
                    'filledAmount': str(filled_amount),
                    'averageFillPrice': str(filled_price),
                    'createdAt': created_time.timestamp(),
                    'expiredAt': expire_time.timestamp(),
                    'serverTime': server_time.timestamp(),
                },
                'message': 'success',
                'error': None,
                'hasError': False,
            },
            status=200,
            match=[
                responses.matchers.query_param_matcher({'clientOrderId': liquidation.tracking_id}, strict_match=False)
            ],
        )

    def _order_open_response(self, liquidation: Liquidation, server_time=NOW):
        self._create_response_with_complete_body(liquidation, 'open', Decimal(0), Decimal(0), server_time)

    def _order_filled_response(self, liquidation: Liquidation, server_time=NOW):
        self._create_response_with_complete_body(liquidation, 'filled', liquidation.amount, PRICE, server_time)

    def _order_partially_response(self, liquidation: Liquidation, server_time=NOW):
        self._create_response_with_complete_body(liquidation, 'partially', liquidation.amount / 2, PRICE, server_time)

    def _order_failed_response(self, liquidation: Liquidation, server_time=NOW):
        self._create_response_with_complete_body(liquidation, 'failed', Decimal(0), Decimal(0), server_time)

    def _error_response(self, order_id, json):
        responses.get(
            url=SettlementStatus.get_base_url() + SettlementStatus.url,
            status=400,
            json=json,
            match=[responses.matchers.query_param_matcher({'clientOrderId': order_id}, strict_match=False)],
        )

    def _error_400_response(self, liquidation: Liquidation):
        self._error_response(
            liquidation.tracking_id,
            {
                'result': None,
                'message': 'bad request',
                'error': '...',
                'hasError': True,
            },
        )

    def _error_not_found_response(self, liquidation: Liquidation):
        self._error_response(
            liquidation.tracking_id,
            {
                'result': None,
                'message': 'bad request',
                'error': 'settlement not found',
                'hasError': True,
            },
        )

    def _create_orders_and_check_liquidations(self):
        assert Liquidation.objects.count() == 0
        self.create_external_order_successful_response()
        self.run_order_creator_tasks()
        assert Liquidation.objects.exclude(status=Liquidation.STATUS.new).count() == 2
        return Liquidation.objects.order_by('id')

    @responses.activate
    @patch('exchange.liquidator.services.liquidation_processor.ir_now', lambda: IR_NOW)
    @patch('exchange.liquidator.services.liquidation_processor.now', lambda: NOW)
    def test_get_status_with_error_before_sla_time(self):
        liquidations = self._create_orders_and_check_liquidations()
        assert len(liquidations) == 2
        self._order_open_response(liquidations[0])
        self._error_400_response(liquidations[1])
        task_check_status_external_liquidation()
        assert Liquidation.objects.filter(status=Liquidation.STATUS.open).count() == 2

    @responses.activate
    @patch('exchange.liquidator.services.liquidation_processor.now', lambda: NOW)
    def test_get_status_with_not_exist_error(self):
        liquidations = self._create_orders_and_check_liquidations()
        assert len(liquidations) == 2
        self._order_open_response(liquidations[0])
        self._error_not_found_response(liquidations[1])
        task_check_status_external_liquidation()
        liquidations = Liquidation.objects.order_by('id')
        assert liquidations[0].status == Liquidation.STATUS.open
        assert liquidations[1].status == Liquidation.STATUS.ready_to_share
        self._check_amounts(liquidations, Decimal(0), Decimal(0))

    @responses.activate
    def test_get_status_with_not_exist_after_sla_time(self):
        liquidations = self._create_orders_and_check_liquidations()
        assert len(liquidations) == 2
        self._order_open_response(liquidations[0], server_time=NOW + timedelta(minutes=5))
        self._error_not_found_response(liquidations[1])
        with patch('exchange.liquidator.services.liquidation_processor.now', lambda: NOW + timedelta(minutes=5)):
            task_check_status_external_liquidation()
        liquidations = Liquidation.objects.order_by('id')
        assert liquidations[0].status == Liquidation.STATUS.overstock
        assert liquidations[1].status == Liquidation.STATUS.ready_to_share
        self._check_amounts(liquidations, Decimal(0), Decimal(0))

    @responses.activate
    @patch('exchange.liquidator.services.liquidation_processor.ir_now', lambda: IR_NOW + timedelta(minutes=5))
    def test_get_status_with_error_after_sla_time(self):
        liquidations = self._create_orders_and_check_liquidations()
        assert len(liquidations) == 2
        self._order_open_response(liquidations[0], server_time=NOW + timedelta(minutes=5))
        self._error_400_response(liquidations[1])
        with patch('exchange.liquidator.services.liquidation_processor.now', lambda: NOW + timedelta(minutes=5)):
            task_check_status_external_liquidation()
        liquidations = Liquidation.objects.order_by('id')
        assert liquidations[0].status == Liquidation.STATUS.overstock
        assert liquidations[1].status == Liquidation.STATUS.overstock
        self._check_amounts(liquidations, Decimal(0), Decimal(0))

    @responses.activate
    @patch('exchange.liquidator.services.liquidation_processor.now', lambda: NOW)
    @patch('exchange.liquidator.services.liquidation_processor.ir_now', lambda: IR_NOW)
    def test_get_status_open_before_sal_time(self):
        liquidations = self._create_orders_and_check_liquidations()
        assert len(liquidations) == 2
        self._order_open_response(liquidations[0])
        self._error_400_response(liquidations[1])
        task_check_status_external_liquidation()
        assert Liquidation.objects.filter(status=Liquidation.STATUS.open).count() == 2

    @responses.activate
    def test_get_status_open_after_sal_time(self):
        liquidations = self._create_orders_and_check_liquidations()
        assert len(liquidations) == 2
        for liquidation in liquidations:
            self._order_open_response(liquidation, server_time=NOW + timedelta(minutes=5))

        task_check_status_external_liquidation()
        assert Liquidation.objects.filter(status=Liquidation.STATUS.overstock).count() == 2

    @responses.activate
    def test_get_status_filled_before_sal_time(self):
        liquidations = self._create_orders_and_check_liquidations()
        assert len(liquidations) == 2
        for liquidation in liquidations:
            self._order_filled_response(liquidation)
        task_check_status_external_liquidation()
        liquidations = Liquidation.objects.filter(status=Liquidation.STATUS.ready_to_share)
        assert len(liquidations) == 2
        self._check_amounts(liquidations)

    @responses.activate
    def test_get_status_filled_after_sal_time(self):
        liquidations = self._create_orders_and_check_liquidations()
        assert len(liquidations) == 2
        for liquidation in liquidations:
            self._order_filled_response(liquidation)
        with patch('exchange.liquidator.services.liquidation_processor.ir_now', lambda: IR_NOW + timedelta(minutes=5)):
            task_check_status_external_liquidation()
        liquidations = Liquidation.objects.filter(status=Liquidation.STATUS.ready_to_share)
        assert len(liquidations) == 2
        self._check_amounts(liquidations)

    @responses.activate
    def test_get_status_partially_before_sal_time(self):
        liquidations = self._create_orders_and_check_liquidations()
        assert len(liquidations) == 2
        for liquidation in liquidations:
            self._order_partially_response(liquidation)
        with patch('exchange.liquidator.services.liquidation_processor.now', lambda: NOW + timedelta(minutes=5)):
            task_check_status_external_liquidation()
        liquidations = Liquidation.objects.filter(status=Liquidation.STATUS.ready_to_share)
        assert len(liquidations) == 2
        self._check_amounts(liquidations, Decimal(0.5))

    @responses.activate
    def test_get_status_partially_after_sal_time(self):
        liquidations = self._create_orders_and_check_liquidations()
        assert len(liquidations) == 2
        for liquidation in liquidations:
            self._order_partially_response(liquidation)
        task_check_status_external_liquidation()
        liquidations = Liquidation.objects.filter(status=Liquidation.STATUS.ready_to_share)
        assert len(liquidations) == 2
        self._check_amounts(liquidations, Decimal(0.5))

    @responses.activate
    def test_get_status_failed_before_sal_time(self):
        liquidations = self._create_orders_and_check_liquidations()
        assert len(liquidations) == 2
        for liquidation in liquidations:
            self._order_failed_response(liquidation)
        task_check_status_external_liquidation()
        liquidations = Liquidation.objects.filter(status=Liquidation.STATUS.ready_to_share)
        assert len(liquidations) == 2
        self._check_amounts(liquidations, Decimal(0), Decimal(0))

    @responses.activate
    def test_get_status_failed_after_sal_time(self):
        liquidations = self._create_orders_and_check_liquidations()
        assert len(liquidations) == 2
        for liquidation in liquidations:
            self._order_failed_response(liquidation)
        with patch('exchange.liquidator.services.liquidation_processor.now', lambda: NOW + timedelta(minutes=5)):
            task_check_status_external_liquidation()
        liquidations = Liquidation.objects.filter(status=Liquidation.STATUS.ready_to_share)
        assert len(liquidations) == 2
        self._check_amounts(liquidations, Decimal(0), Decimal(0))

    @responses.activate
    @patch('exchange.liquidator.services.liquidation_processor.ir_now', lambda: IR_NOW)
    @patch('exchange.liquidator.services.liquidation_processor.now', lambda: NOW)
    @patch('exchange.liquidator.services.liquidation_processor.Notification.notify_admins', new_callable=MagicMock)
    def test_get_status_return_wrong_data(self, notify_admins_mock):
        liquidations = self._create_orders_and_check_liquidations()
        assert len(liquidations) == 2

        for liquidation in liquidations:
            liquidation.amount = liquidation.amount / 2
            self._order_open_response(liquidation)

        task_check_status_external_liquidation()
        liquidations = Liquidation.objects.filter(status=Liquidation.STATUS.open)

        assert len(liquidations) == 2
        notify_admins_mock.assert_called_with(
            f'Invalid settlement data. liquidation: #{liquidations[1].pk}',
            title=f'‼️Settlement Status- {liquidations[1].symbol}',
            channel='liquidator',
        )
