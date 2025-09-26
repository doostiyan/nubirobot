import uuid
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.liquidator.models import Liquidation, LiquidationRequest
from exchange.liquidator.services import InternalOrderCreator
from exchange.liquidator.tasks import (
    task_check_status_internal_liquidation,
    task_create_internal_order,
    task_process_pending_liquidation_request,
    task_submit_liquidation_requests_external_wallet_transactions,
    task_update_liquidation_request,
)
from exchange.market.marketmanager import MarketManager
from exchange.market.models import Market, Order
from exchange.wallet.models import Wallet
from tests.base.utils import do_matching_round, mock_on_commit


@patch('django.db.transaction.on_commit', mock_on_commit)
class TestLiquidationRequestCreate(APITestCase):
    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.user.base_fee = Decimal('0')
        cls.user.base_fee_usdt = Decimal('0')
        cls.user.base_maker_fee = Decimal('0')
        cls.user.base_maker_fee_usdt = Decimal('0')
        cls.user.save()
        cls.btc_wallet = Wallet.get_user_wallet(cls.user, Currencies.btc)
        cls.usdt_wallet = Wallet.get_user_wallet(cls.user, Currencies.usdt)

        cls.another_user = User.objects.get(pk=200)
        cls.another_user.base_fee = Decimal('0')
        cls.another_user.base_fee_usdt = Decimal('0')
        cls.another_user.base_maker_fee = Decimal('0')
        cls.another_user.base_maker_fee_usdt = Decimal('0')
        cls.another_user.save()

        Wallet.get_user_wallet(cls.another_user, Currencies.btc).create_transaction('manual', '10').commit()
        Wallet.get_user_wallet(cls.another_user, Currencies.usdt).create_transaction('manual', '100000').commit()

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        InternalOrderCreator._get_order_user_cached.clear()

    def tearDown(self):
        InternalOrderCreator._get_order_user_cached.clear()

    @staticmethod
    def _set_last_trade_price(market: Market, price: Decimal = Decimal('1')):
        cache.set(f'market_{market.pk}_last_price', price)

    def _call_endpoint(self, data: dict):
        return self.client.post('/QA/liquidation-requests', data)

    def _call_create_order_task(self):
        task_process_pending_liquidation_request()

    def _create_standalone_order(self, amount, order_type, price):
        order, error = MarketManager.create_order(
            user=self.another_user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            amount=amount,
            order_type=order_type,
            execution_type=Order.EXECUTION_TYPES.limit,
            allow_small=True,
            price=price,
            client_order_id=str(uuid.uuid4())[:10],
        )

        return order

    @staticmethod
    def _assert_response_failed(response, status_code: str, error_code: str):
        assert response.status_code == status_code
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == error_code
        assert not LiquidationRequest.objects.exists()

    def test_add_sell_liquidation_request_successfully(self):
        self.btc_wallet.create_transaction('manual', '0.002').commit()
        response = self._call_endpoint(
            {'src': 'btc', 'dst': 'usdt', 'side': 'sell', 'amount': '0.001', 'service': 'margin'}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        liquidation_requests = LiquidationRequest.objects.select_related('src_wallet', 'dst_wallet').all()
        assert len(liquidation_requests) == 1
        assert liquidation_requests[0].src_wallet == self.btc_wallet
        assert liquidation_requests[0].dst_wallet == self.usdt_wallet
        assert liquidation_requests[0].amount == Decimal('0.001')
        assert liquidation_requests[0].is_sell
        assert liquidation_requests[0].status == LiquidationRequest.STATUS.pending
        assert liquidation_requests[0].filled_amount == 0

    def test_add_buy_liquidation_request_successfully(self):
        self._set_last_trade_price(Market.by_symbol('BTCUSDT'), Decimal(67400))
        self.usdt_wallet.create_transaction('manual', 70).commit()
        response = self._call_endpoint(
            {'src': 'btc', 'dst': 'usdt', 'side': 'buy', 'amount': '0.001', 'service': 'margin'}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        liquidation_requests = LiquidationRequest.objects.select_related('src_wallet', 'dst_wallet').all()
        assert len(liquidation_requests) == 1
        assert liquidation_requests[0].src_wallet == self.btc_wallet
        assert liquidation_requests[0].dst_wallet == self.usdt_wallet
        assert liquidation_requests[0].amount == Decimal('0.001')
        assert not liquidation_requests[0].is_sell
        assert liquidation_requests[0].status == LiquidationRequest.STATUS.pending
        assert liquidation_requests[0].filled_amount == 0

    def test_add_sell_liquidation_request_insufficient_balance(self):
        self.btc_wallet.create_transaction('manual', '0.002').commit()
        response = self._call_endpoint(
            {'src': 'btc', 'dst': 'usdt', 'side': 'sell', 'amount': '0.003', 'service': 'margin'}
        )
        self._assert_response_failed(
            response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code='InsufficientBalance',
        )

    def test_add_buy_liquidation_request_insufficient_balance(self):
        self._set_last_trade_price(Market.by_symbol('BTCUSDT'), Decimal(67400))
        self.usdt_wallet.create_transaction('manual', 60).commit()
        response = self._call_endpoint(
            {'src': 'btc', 'dst': 'usdt', 'side': 'buy', 'amount': '0.001', 'service': 'margin'}
        )
        self._assert_response_failed(
            response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code='InsufficientBalance',
        )

    def test_add_sell_liquidation_request_non_existent_src_wallet(self):
        response = self._call_endpoint(
            {'src': 'eth', 'dst': 'usdt', 'side': 'sell', 'amount': '0.003', 'service': 'margin'}
        )
        self._assert_response_failed(
            response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code='InsufficientBalance',
        )
        assert not Wallet.objects.filter(user=self.user, currency=Currencies.eth).exists()

    @patch('exchange.liquidator.models.liquidation_request.AVAILABLE_MARKETS', [[Currencies.btc, Currencies.dai]])
    def test_add_buy_liquidation_request_non_existent_dst_wallet(self):
        response = self._call_endpoint(
            {'src': 'btc', 'dst': 'dai', 'side': 'buy', 'amount': '0.001', 'service': 'margin'}
        )
        self._assert_response_failed(
            response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code='InsufficientBalance',
        )
        assert not Wallet.objects.filter(user=self.user, currency=Currencies.dai).exists()

    def test_add_liquidation_request_invalid_amount(self):
        response = self._call_endpoint(
            {'src': 'btc', 'dst': 'usdt', 'side': 'sell', 'amount': '-0.001', 'service': 'margin'}
        )
        self._assert_response_failed(
            response,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code='ParseError',
        )

    def test_add_liquidation_request_unsupported_pair(self):
        response = self._call_endpoint(
            {'src': 'btc', 'dst': 'dai', 'side': 'sell', 'amount': '0.001', 'service': 'margin'}
        )
        self._assert_response_failed(
            response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code='UnsupportedPair',
        )

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_add_buy_and_sell_liquidation_request_successfully(self):
        self.btc_wallet.create_transaction('manual', '0.002').commit()
        self.usdt_wallet.create_transaction('manual', '60000').commit()
        market = Market.objects.get(src_currency=Currencies.btc, dst_currency=Currencies.usdt, is_active=True)
        self._set_last_trade_price(market, Decimal(60000))

        response = self._call_endpoint(
            {'src': 'btc', 'dst': 'usdt', 'side': 'sell', 'amount': '0.001', 'service': 'margin'}
        )
        assert response.status_code == status.HTTP_200_OK
        response = self._call_endpoint(
            {'src': 'btc', 'dst': 'usdt', 'side': 'buy', 'amount': '0.001', 'service': 'margin'}
        )
        assert response.status_code == status.HTTP_200_OK
        liquidation_requests = LiquidationRequest.objects.all()
        assert len(liquidation_requests) == 2
        for liquidation_request in liquidation_requests:
            assert liquidation_request.status == LiquidationRequest.STATUS.pending
            assert liquidation_request.filled_amount == 0
            assert liquidation_request.liquidations.count() == 0

        self._call_create_order_task()

        assert Liquidation.objects.count() == 2
        do_matching_round(market, reinitialize_caches=True)

        task_check_status_internal_liquidation()
        task_update_liquidation_request()
        task_submit_liquidation_requests_external_wallet_transactions()

        liquidation_requests = LiquidationRequest.objects.all()
        assert len(liquidation_requests) == 2
        for liquidation_request in liquidation_requests:
            assert liquidation_request.status == LiquidationRequest.STATUS.done
            assert liquidation_request.amount == liquidation_request.filled_amount

    def test_add_zero_request(self):
        self.btc_wallet.create_transaction('manual', '0.000000001').commit()
        self.usdt_wallet.create_transaction('manual', '60000').commit()
        market = Market.objects.get(src_currency=Currencies.btc, dst_currency=Currencies.usdt, is_active=True)
        self._set_last_trade_price(market, Decimal(60000))
        response = self._call_endpoint(
            {'src': 'btc', 'dst': 'usdt', 'side': 'sell', 'amount': '0.000000001', 'service': 'margin'}
        )
        self._assert_response_failed(
            response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code='InvalidAmount',
        )

    @patch.object(task_create_internal_order, 'delay', task_create_internal_order)
    def test_add_sell_and_buy_with_fee_successfully(self):
        user_vip_level = 0
        global_maker_fee = settings.NOBITEX_OPTIONS['tradingFees']['makerFeesTether'][user_vip_level]
        global_taker_fee = settings.NOBITEX_OPTIONS['tradingFees']['takerFeesTether'][user_vip_level]
        user_fee = min(global_maker_fee, global_taker_fee)

        self.user.base_fee_usdt = user_fee
        self.user.base_maker_fee_usdt = user_fee
        self.user.save()

        self.btc_wallet.create_transaction('manual', '10').commit()
        self.usdt_wallet.create_transaction('manual', '100000').commit()
        market = Market.objects.get(src_currency=Currencies.btc, dst_currency=Currencies.usdt, is_active=True)
        self._set_last_trade_price(market, Decimal(10_000))

        order_amount = '0.01'
        self._call_endpoint({'src': 'btc', 'dst': 'usdt', 'side': 'sell', 'amount': order_amount, 'service': 'margin'})
        self._call_endpoint({'src': 'btc', 'dst': 'usdt', 'side': 'buy', 'amount': order_amount, 'service': 'margin'})
        assert LiquidationRequest.objects.count() == 2

        self._call_create_order_task()
        orders = Order.objects.all()
        assert len(orders) == 2

        buy_order = orders[0] if orders[0].is_buy else orders[1]
        buy_order_fee = buy_order.amount - Decimal(order_amount)
        self._create_standalone_order(buy_order_fee, Order.ORDER_TYPES.sell, Decimal(10_000))

        assert Liquidation.objects.count() == 2

        do_matching_round(market, reinitialize_caches=True)

        task_check_status_internal_liquidation()
        task_update_liquidation_request()
        task_submit_liquidation_requests_external_wallet_transactions()

        liquidation_requests = LiquidationRequest.objects.all()
        assert len(liquidation_requests) == 2
        for liquidation_request in liquidation_requests:
            assert liquidation_request.amount == liquidation_request.filled_amount
            assert liquidation_request.status == LiquidationRequest.STATUS.done
