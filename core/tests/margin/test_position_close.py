from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import VerificationProfile
from exchange.base.models import Currencies
from exchange.margin.models import Position
from exchange.market.models import Order
from exchange.pool.models import LiquidityPool
from exchange.wallet.models import Wallet
from tests.margin.test_positions import PositionTestMixin
from tests.margin.utils import get_trade_fee_mock
from tests.market.test_order import OrderAPITestMixin


@patch('exchange.market.marketmanager.MarketManager.get_trade_fee', new=get_trade_fee_mock)
class PositionCloseAPITest(PositionTestMixin, OrderAPITestMixin, APITestCase):

    def setUp(self):
        best_active_price = Decimal(10999999)
        cache.set('orderbook_BTCUSDT_best_active_sell', best_active_price)
        cache.set('orderbook_BTCUSDT_best_active_buy', best_active_price)
        super(PositionCloseAPITest, self).setUp()
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        if 'sell_position' in self._testMethodName:
            self.create_short_margin_order(amount='0.001', price='21300')
        elif 'buy_position' in self._testMethodName:
            self.create_long_margin_order(amount='0.001', price='21200', leverage=2)
        self.position = Position.objects.last()


    def tearDown(self):
        cache.delete('orderbook_BTCUSDT_best_active_sell')
        cache.delete('orderbook_BTCUSDT_best_active_buy')

    def _test_successful_position_close(self, is_oco: bool = False, **order_params):
        request_time = timezone.now()
        if is_oco:
            order_params['mode'] = 'oco'
        response = self.client.post(f'/positions/{self.position.id}/close', order_params)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        if is_oco:
            assert 'orders' in data
            self._check_successful_position_close_order_response(data['orders'][0], order_params)
            ids = [o['id'] for o in data['orders']]
        else:
            assert 'order' in data
            self._check_successful_position_close_order_response(data['order'], order_params)
            ids = [data['order']['id']]
        orders = Order.objects.filter(id__in=ids, created_at__gt=request_time)
        assert len(orders) == len(ids)
        for order in orders:
            assert order.is_margin
            assert order.channel == order.CHANNEL.web

    def _check_successful_position_close_order_response(self, order_data, request_data):
        execution = request_data.get('execution', 'limit')
        assert order_data['id']
        assert order_data['created_at']
        assert order_data['status'] == 'Inactive' if 'stop' in execution else 'Active'
        assert order_data['execution'] == Order.EXECUTION_TYPES[getattr(Order.EXECUTION_TYPES, execution)]
        assert order_data['type'] == 'buy' if self.position.is_short else 'sell'
        assert order_data['amount'] == request_data['amount']
        assert order_data['price'] == 'market' if 'market' in execution else request_data['price']
        assert order_data['srcCurrency'] == 'btc'
        assert order_data['dstCurrency'] == 'usdt'
        assert order_data['matchedAmount'] == '0'

    def _test_unsuccessful_position_close(self, position_id: int, data: dict, code: str):
        request_time = timezone.now()
        response = self.client.post(f'/positions/{position_id}/close', data)
        if code == 'NotFound':
            assert response.status_code == status.HTTP_404_NOT_FOUND
            return
        assert response.status_code == status.HTTP_400_BAD_REQUEST if code in ['UnverifiedEmail', ''] else status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code
        assert not Order.objects.filter(created_at__gt=request_time).exists()

    @staticmethod
    def fake_position_opened(position: Position, amount: str, total_price: str):
        fee = Decimal('0.0015')
        position.delegated_amount += Decimal(amount) * (1 if position.is_short else (1 - fee))
        position.earned_amount += Decimal(total_price) * ((1 - fee) if position.is_short else -1)
        position.status = Position.STATUS.open
        position.set_liquidation_price()
        position.save(update_fields=('delegated_amount', 'earned_amount', 'status', 'liquidation_price'))
        position.refresh_from_db()
        order = position.orders.last()
        order.matched_amount += Decimal(amount)
        order.matched_total_price += Decimal(total_price)
        order.fee = Decimal(amount if order.is_buy else total_price) * fee
        order.save(update_fields=('matched_amount', 'matched_total_price', 'fee'))

    @patch('django.get_version', lambda: 'test-1')  # Since market object has a 1-min cache
    def test_sell_position_close_closed_market(self):
        self.market.is_active = False
        self.market.save(update_fields=('is_active',))
        self.fake_position_opened(self.position, amount='0.001', total_price='21.3')
        self._test_unsuccessful_position_close(
            self.position.id, {'amount': '0.001', 'price': '21300'}, code='MarketClosed',
        )

    @patch('django.get_version', lambda: 'test-1')
    def test_buy_position_close_closed_market(self):
        self.market.is_active = False
        self.market.save(update_fields=('is_active',))
        self.fake_position_opened(self.position, amount='0.001', total_price='21.2')
        self._test_unsuccessful_position_close(
            self.position.id, {'amount': '0.001', 'price': '21300'}, code='MarketClosed',
        )

    def test_sell_position_close_bad_price(self):
        self.fake_position_opened(self.position, amount='0.0005', total_price='10.65')
        self._test_unsuccessful_position_close(
            self.position.id, {'amount': '0.001', 'price': '1E-9'}, code='InvalidOrderPrice',
        )

    def test_position_close_with_no_active_position(self):
        shared_data = {
            'user': self.user,
            'src_currency': self.market.src_currency,
            'dst_currency': self.market.dst_currency,
            'collateral': 24,
        }
        for status_key in ('closed', 'liquidated', 'canceled', 'expired'):
            for side_key in ('sell', 'buy'):
                position = Position.objects.create(
                    **shared_data, status=getattr(Position.STATUS, status_key), side=getattr(Position.SIDES, side_key)
                )
                self._test_unsuccessful_position_close(
                    position.id, {'amount': '0.001', 'price': '23000'}, code='NotFound',
                )

    def test_sell_position_close_more_than_liability(self):
        self.fake_position_opened(self.position, amount='0.0005', total_price='10.65')
        self._test_unsuccessful_position_close(
            self.position.id, {'amount': '0.001', 'price': '23000'}, code='ExceedLiability',
        )

    def test_buy_position_close_more_than_liability(self):
        self.fake_position_opened(self.position, amount='0.0005', total_price='10.6')
        self._test_unsuccessful_position_close(
            self.position.id, {'amount': '0.0005', 'price': '23000'}, code='ExceedLiability',
        )

    def test_buy_position_close_no_verified_email(self):
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=False)
        self.fake_position_opened(self.position, amount='0.0005', total_price='10.65')
        self._test_unsuccessful_position_close(
            self.position.id, {'amount': '0.0005', 'price': '23000'}, code='UnverifiedEmail',
        )

    def test_sell_position_close_more_than_total_asset(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.3')
        assert self.position.total_asset == Decimal('42.56805')
        self._test_unsuccessful_position_close(
            self.position.id, {'amount': '0.001', 'price': '43000'}, code='ExceedTotalAsset',
        )

    def test_sell_position_close_partial_small_order(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.3')
        self._test_unsuccessful_position_close(
            self.position.id, {'amount': '0.0002', 'price': '21000'}, code='SmallOrder',
        )

    def test_buy_position_close_partial_small_order(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.3')
        cache.set('orderbook_BTCUSDT_best_active_sell', 21300)
        self._test_unsuccessful_position_close(
            self.position.id, {'amount': '0.0002', 'price': '21300'}, code='SmallOrder',
        )

    def test_sell_position_close(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('3.7')
        self.fake_position_opened(self.position, amount='0.001', total_price='21.3')
        self._check_position_status(
            self.position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.26805',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
        )
        self._test_successful_position_close(amount='0.0007', price='21000')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.7')
        positions = Position.objects.all()
        assert len(positions) == 1
        self._check_position_status(
            positions[0],
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.26805',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
            orders_count=2,
        )

    def test_buy_position_close(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('14.4')
        self.fake_position_opened(self.position, amount='0.001', total_price='21.2')
        self._check_position_status(
            self.position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0009985',
            earned_amount='-21.2',
            liquidation_price='12739.11',
            status=Position.STATUS.open,
        )
        self._test_successful_position_close(amount='0.0007', price='21500')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('14.4')
        positions = Position.objects.all()
        assert len(positions) == 1
        self._check_position_status(
            positions[0],
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0009985',
            earned_amount='-21.2',
            liquidation_price='12739.11',
            status=Position.STATUS.open,
            orders_count=2,
        )

    def test_buy_position_close_more_than_total_asset(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.2')
        self._check_position_status(
            self.position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0009985',
            earned_amount='-21.2',
            liquidation_price='12739.11',
            status=Position.STATUS.open,
        )
        assert self.position.total_asset == Decimal('31.78817')
        self._test_successful_position_close(amount='0.0009', price='36000')  # requires 32.4

    @patch('django.get_version', lambda: 'test-2')  # Since pool object has a 1-min cache
    def test_sell_position_close_closed_pool(self):
        self.fake_position_opened(self.position, amount='0.0007', total_price='10.65')
        self.src_pool.is_active = False
        self.src_pool.save(update_fields=('is_active',))
        LiquidityPool.get_for(self.src_pool.currency, skip_cache=True)
        self._test_successful_position_close(amount='0.0007', price='21000')

    @patch('django.get_version', lambda: 'test-2')
    def test_buy_position_close_closed_pool(self):
        self.fake_position_opened(self.position, amount='0.0007', total_price='14.84')
        self.dst_pool.is_active = False
        self.dst_pool.save(update_fields=('is_active',))
        LiquidityPool.get_for(self.dst_pool.currency, skip_cache=True)
        self._test_successful_position_close(amount='0.00069895', price='22000')

    @patch('django.get_version', lambda: 'test-3')
    def test_sell_position_close_special_limited_market(self):
        self.src_pool.is_private = True
        self.src_pool.save(update_fields=('is_private',))
        LiquidityPool.get_for(self.src_pool.currency, skip_cache=True)
        self.fake_position_opened(self.position, amount='0.0007', total_price='10.65')
        self._test_successful_position_close(amount='0.0007', price='21000')

    @patch('django.get_version', lambda: 'test-3')
    def test_buy_position_close_special_limited_market(self):
        self.dst_pool.is_private = True
        self.dst_pool.save(update_fields=('is_private',))
        LiquidityPool.get_for(self.dst_pool.currency, skip_cache=True)
        self.fake_position_opened(self.position, amount='0.0007', total_price='14.84')
        self._test_successful_position_close(amount='0.00069895', price='22000')

    @patch('django.get_version', lambda: 'test-4')
    def test_sell_position_close_market_stops_margin(self):
        self.market.allow_margin = False
        self.market.save(update_fields=('allow_margin',))
        self.fake_position_opened(self.position, amount='0.0007', total_price='10.65')
        self._test_successful_position_close(amount='0.0007', price='21000')

    @patch('django.get_version', lambda: 'test-4')
    def test_buy_position_close_market_stops_margin(self):
        self.market.allow_margin = False
        self.market.save(update_fields=('allow_margin',))
        self.fake_position_opened(self.position, amount='0.0007', total_price='14.84')
        self._test_successful_position_close(amount='0.00069895', price='22000')

    def test_sell_position_close_total_small_order(self):
        self.fake_position_opened(self.position, amount='0.0002', total_price='4.26')
        self._test_successful_position_close(amount='0.0002003005', price='21000')
        self.position.refresh_from_db()
        self._check_position_status(
            self.position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0002003005',
            earned_amount='4.25361',
            liquidation_price='115978.52',
            status=Position.STATUS.open,
            orders_count=2,
        )

    def test_buy_position_close_total_small_order(self):
        self.fake_position_opened(self.position, amount='0.0002', total_price='4.24')
        self._test_successful_position_close(amount='0.0001997', price='21500')
        self.position.refresh_from_db()
        self._check_position_status(
            self.position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0001997',
            earned_amount='-4.24',
            liquidation_price='0',
            status=Position.STATUS.open,
            orders_count=2,
        )

    def test_sell_position_close_in_two_buy(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.3')
        self._test_successful_position_close(amount='0.0006', price='21000')
        self._test_successful_position_close(amount='0.0004015023', price='20000')
        self.position.refresh_from_db()
        self._check_position_status(
            self.position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.26805',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
            orders_count=3,
        )

    def test_buy_position_close_in_two_sell(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.2')
        self._test_successful_position_close(amount='0.0006', price='21500')
        self._test_successful_position_close(amount='0.0003985', price='22000')
        self.position.refresh_from_db()
        self._check_position_status(
            self.position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0009985',
            earned_amount='-21.2',
            liquidation_price='12739.11',
            status=Position.STATUS.open,
            orders_count=3,
        )

    @patch('exchange.wallet.estimator.PriceEstimator.get_price_range', lambda *_: (21300, 21300))
    def test_sell_position_close_by_market_with_price(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.3')
        self._test_successful_position_close(amount='0.001', price='21300', execution='market')
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('3.7')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.26805',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
            orders_count=2,
        )
        assert position.orders.filter(execution_type=Order.EXECUTION_TYPES.market).exists()

    def test_sell_position_close_by_market_without_price(self):
        best_active_price = Decimal(10999999)
        cache.set(f'orderbook_BTCUSDT_best_active_sell', best_active_price)
        self.fake_position_opened(self.position, amount='0.001', total_price='21.3')
        self._test_successful_position_close(amount='0.001', execution='market')
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('3.7')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.26805',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
            orders_count=2,
        )
        assert position.orders.filter(execution_type=Order.EXECUTION_TYPES.market).exists()
        cache.delete('orderbook_BTCUSDT_best_active_sell')

    def test_buy_position_close_by_market_with_price(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('14.4')
        self.fake_position_opened(self.position, amount='0.001', total_price='21.2')
        self._check_position_status(
            self.position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0009985',
            earned_amount='-21.2',
            liquidation_price='12739.11',
            status=Position.STATUS.open,
        )
        self._test_successful_position_close(amount='0.0009985', price='21200', execution='market')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('14.4')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0009985',
            earned_amount='-21.2',
            liquidation_price='12739.11',
            status=Position.STATUS.open,
            orders_count=2,
        )
        assert position.orders.filter(execution_type=Order.EXECUTION_TYPES.market).exists()
        assert position.liability_in_order == Decimal('0.0009985')
        assert position.asset_in_order == Decimal('21.1682')

    def test_buy_position_close_by_market_without_price(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.2')
        self._test_successful_position_close(amount='0.0009985', execution='market')
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('14.4')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0009985',
            earned_amount='-21.2',
            liquidation_price='12739.11',
            status=Position.STATUS.open,
            orders_count=2,
        )
        assert position.orders.filter(execution_type=Order.EXECUTION_TYPES.market).exists()

    def test_sell_position_close_by_stop_limit(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.3')
        self._test_successful_position_close(amount='0.001', execution='stop_limit', stopPrice='21600', price='21100')
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('3.7')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.26805',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
            orders_count=2,
        )
        assert position.liability_in_order == Decimal('0.001')
        assert position.asset_in_order == Decimal('21.1')

    def test_buy_position_close_by_stop_limit(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.2')
        self._test_successful_position_close(
            amount='0.0009985', execution='stop_limit', stopPrice='20400', price='20500'
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('14.4')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0009985',
            earned_amount='-21.2',
            liquidation_price='12739.11',
            status=Position.STATUS.open,
            orders_count=2,
        )
        assert position.liability_in_order == Decimal('0.0009985')
        assert position.asset_in_order == Decimal('20.46925')

    def test_sell_position_close_by_stop_market_with_price(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.3')
        self._test_successful_position_close(amount='0.001', execution='stop_market', stopPrice='22300', price='22500')
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('3.7')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.26805',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
            orders_count=2,
        )
        assert position.liability_in_order == Decimal('0.001')
        assert position.asset_in_order == Decimal('22.5')

    def test_sell_position_close_by_stop_market_without_price(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.3')
        self._test_successful_position_close(amount='0.001', execution='stop_market', stopPrice='22300')
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('3.7')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.26805',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
            orders_count=2,
        )
        assert position.liability_in_order == Decimal('0.001')
        assert position.asset_in_order == Decimal('22.3')

    def test_buy_position_close_by_stop_market_with_price(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.2')
        self._test_successful_position_close(
            amount='0.0009985', execution='stop_market', stopPrice='20400', price='20300'
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('14.4')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0009985',
            earned_amount='-21.2',
            liquidation_price='12739.11',
            status=Position.STATUS.open,
            orders_count=2,
        )
        assert position.liability_in_order == Decimal('0.0009985')
        assert position.asset_in_order == Decimal('20.26955')

    def test_buy_position_close_by_stop_market_without_price(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.2')
        self._test_successful_position_close(amount='0.0009985', execution='stop_market', stopPrice='20400')
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('14.4')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0009985',
            earned_amount='-21.2',
            liquidation_price='12739.11',
            status=Position.STATUS.open,
            orders_count=2,
        )
        assert position.liability_in_order == Decimal('0.0009985')
        assert position.asset_in_order == Decimal('20.3694')

    def test_sell_position_close_by_oco(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.3')
        self._test_successful_position_close(
            amount='0.001', is_oco=True, price='20800', stopPrice='23000', stopLimitPrice='23200'
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('3.7')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.26805',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
            orders_count=3,
        )
        assert position.liability_in_order == Decimal('0.001')
        assert position.asset_in_order == Decimal('23.2')
        orders = position.orders.order_by('id')
        assert orders[1].price == 20800
        assert orders[1].execution_type == Order.EXECUTION_TYPES.limit
        assert orders[2].price == 23200
        assert orders[2].execution_type == Order.EXECUTION_TYPES.stop_limit
        assert orders[2].param1 == 23000

    def test_buy_position_close_by_oco(self):
        self.fake_position_opened(self.position, amount='0.001', total_price='21.2')
        self._test_successful_position_close(
            amount='0.0009985', is_oco=True, price='22000', stopPrice='20400', stopLimitPrice='20300'
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        assert wallet.active_balance == Decimal('14.4')
        position = Position.objects.last()
        self._check_position_status(
            position,
            side=Position.SIDES.buy,
            collateral='10.6',
            liability='0.0009985',
            earned_amount='-21.2',
            liquidation_price='12739.11',
            status=Position.STATUS.open,
            orders_count=3,
        )
        assert position.liability_in_order == Decimal('0.0009985')
        assert position.asset_in_order == Decimal('21.967')
        orders = position.orders.order_by('id')
        assert orders[1].price == 22000
        assert orders[1].execution_type == Order.EXECUTION_TYPES.limit
        assert orders[2].price == 20300
        assert orders[2].execution_type == Order.EXECUTION_TYPES.stop_limit
        assert orders[2].param1 == 20400

