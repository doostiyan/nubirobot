import random
from decimal import Decimal
from typing import Optional
from unittest.mock import patch

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User, UserRestriction, VerificationProfile
from exchange.base.models import Currencies, Settings
from exchange.margin.models import Position
from exchange.margin.services import MarginManager
from exchange.market.models import Order
from exchange.pool.models import PoolAccess
from exchange.wallet.models import Wallet
from tests.margin.test_positions import PositionTestMixin
from tests.margin.utils import get_trade_fee_mock
from tests.market.test_order import OrderAPITestMixin


@patch('exchange.market.marketmanager.MarketManager.get_trade_fee', new=get_trade_fee_mock)
class MarginOrderAddAPITest(PositionTestMixin, OrderAPITestMixin, APITestCase):

    def _test_successful_margin_order_add(
        self,
        src: Optional[str] = None,
        dst: Optional[str] = None,
        leverage: Optional[str] = None,
        is_oco: bool = False,
        **order_params,
    ):
        request_time = timezone.now()
        request_data = {
            'srcCurrency': src or 'btc',
            'dstCurrency': dst or 'usdt',
            'clientOrderId': str(random.randint(1, 10 ** 32)),
            **order_params
        }
        if leverage:
            request_data['leverage'] = leverage
        if is_oco:
            request_data['mode'] = 'oco'
        response = self.client.post('/margin/orders/add', request_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        if is_oco:
            assert 'orders' in data
            self._check_successful_margin_order_response(data['orders'][0], request_data)
            ids = [o['id'] for o in data['orders']]
        else:
            assert 'order' in data
            self._check_successful_margin_order_response(data['order'], request_data)
            ids = [data['order']['id']]
        orders = Order.objects.filter(id__in=ids, created_at__gt=request_time)
        assert len(orders) == len(ids)
        for order in orders:
            assert order.is_margin
            assert order.channel == order.CHANNEL.web

    @staticmethod
    def _check_successful_margin_order_response(order_data, request_data):
        execution = request_data.get('execution', 'limit')
        assert order_data['id']
        assert order_data['created_at']
        assert order_data['status'] == 'Inactive' if 'stop' in execution else 'Active'
        assert order_data['execution'] == Order.EXECUTION_TYPES[getattr(Order.EXECUTION_TYPES, execution)]
        assert order_data['type'] == request_data['type']
        assert order_data['amount'] == request_data['amount']
        assert order_data['price'] == 'market' if 'market' in execution else request_data['price']
        assert order_data['srcCurrency'] == request_data['srcCurrency']
        assert order_data['dstCurrency'] == request_data['dstCurrency']
        assert order_data['matchedAmount'] == '0'

    def _test_unsuccessful_margin_order_add(self, data: dict, code: str, message: Optional[str] = None):
        request_time = timezone.now()
        response = self.client.post('/margin/orders/add', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST if code in ['ParseError', 'UnverifiedEmail'] else status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code
        if message:
            assert data['message'] == message
        assert not Order.objects.filter(created_at__gt=request_time).exists()

    def test_margin_order_add_non_existent_market(self):
        for order_type in ('buy', 'sell'):
            self._test_unsuccessful_margin_order_add(
                {'srcCurrency': 'btc', 'dstCurrency': 'ltc', 'type': order_type, 'amount': '0.001', 'price': '351'},
                code='InvalidMarketPair'
            )

    @patch('django.get_version', lambda: 'test-1')  # Since market object has a 1-min cache
    def test_margin_order_add_closed_market(self):
        self.market.is_active = False
        self.market.save(update_fields=('is_active',))
        self._test_unsuccessful_margin_order_add(
            {'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '21300'},
            code='MarketClosed',
        )

    def test_margin_order_add_non_existent_pool(self):
        self._test_unsuccessful_margin_order_add(
            {'type': 'sell', 'srcCurrency': 'ltc', 'dstCurrency': 'usdt', 'amount': '4.5', 'price': '61'},
            code='UnsupportedMarginSrc',
        )
        self._test_unsuccessful_margin_order_add(
            {'type': 'buy', 'srcCurrency': 'ltc', 'dstCurrency': 'rls', 'amount': '4.5', 'price': '61'},
            code='UnsupportedMarginSrc',
        )

    def test_margin_order_add_bad_price(self):
        for order_type in ('buy', 'sell'):
            self._test_unsuccessful_margin_order_add(
                {'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'type': order_type, 'amount': '0.001', 'price': '1E-9'},
                code='InvalidOrderPrice',
            )

    @patch('django.get_version', lambda: 'test-2')  # Since pool object has a 1-min cache
    def test_margin_order_add_closed_pool(self):
        self.src_pool.is_active = False
        self.src_pool.save(update_fields=('is_active',))
        self._test_unsuccessful_margin_order_add(
            {'type': 'sell', 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '21300'},
            code='MarginClosed',
        )

    @patch('django.get_version', lambda: 'test-3')  # Since pool object has a 1-min cache
    def test_margin_order_add_buy_closed_pool(self):
        self.dst_pool.is_active = False
        self.dst_pool.save(update_fields=('is_active',))
        self._test_unsuccessful_margin_order_add(
            {'type': 'buy', 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '21300'},
            code='MarginClosed',
        )

    @patch('django.get_version', lambda: 'test-6')  # Since pool object has a 1-min cache
    def test_margin_order_add_market_stops_margin(self):
        self.market.allow_margin = False
        self.market.save(update_fields=('allow_margin',))
        self._test_unsuccessful_margin_order_add(
            {'type': 'buy', 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '21300'},
            code='MarginClosed',
        )

    @patch('django.get_version', lambda: 'test-4')  # Since pool object has a 1-min cache
    def test_margin_order_add_sell_special_limited_market(self):
        self.src_pool.is_private = True
        self.src_pool.save(update_fields=('is_private',))
        PoolAccess.objects.create(
            liquidity_pool=self.src_pool,
            access_type=PoolAccess.ACCESS_TYPES.trader,
            user_type=User.USER_TYPES.verified,
        )
        self._test_unsuccessful_margin_order_add(
            {'type': 'sell', 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '21300'},
            code="UnsupportedMarginSrc",
        )

    @patch('django.get_version', lambda: 'test-5')  # Since pool object has a 1-min cache
    def test_margin_order_add_buy_special_limited_market(self):
        self.dst_pool.is_private = True
        self.dst_pool.save(update_fields=('is_private',))
        PoolAccess.objects.create(
            liquidity_pool=self.dst_pool,
            access_type=PoolAccess.ACCESS_TYPES.trader,
            user_type=User.USER_TYPES.verified,
        )
        self._test_unsuccessful_margin_order_add(
            {'type': 'buy', 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '21300'},
            code="UnsupportedMarginSrc",
        )

    def test_margin_order_add_sell_on_pool_insufficient_balance(self):
        self.src_pool.src_wallet.refresh_from_db()
        self.src_pool.src_wallet.create_transaction('manual', '-1.5').commit()
        wallet = Wallet.get_user_wallet(self.assistant_user, Currencies.rls, tp=Wallet.WALLET_TYPE.margin)
        wallet.create_transaction('manual', '2E9').commit()
        self.assistant_user.user_type = User.USER_TYPES.trusted
        self.create_short_margin_order(user=self.assistant_user, amount='0.2', price='7E9', dst=Currencies.rls)
        self._test_unsuccessful_margin_order_add(
            {'type': 'sell', 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.4', 'price': '21300'},
            code='AmountUnavailable',
        )

    def test_margin_order_add_buy_on_pool_insufficient_balance(self):
        self.dst_pool.src_wallet.refresh_from_db()
        self.dst_pool.src_wallet.create_transaction('manual', '-39000').commit()
        wallet = Wallet.get_user_wallet(self.assistant_user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        wallet.create_transaction('manual', '1000').commit()
        self.assistant_user.user_type = User.USER_TYPES.trusted
        self.create_long_margin_order(user=self.assistant_user, amount='12', price='83', leverage=2, src=Currencies.ltc)
        self._test_unsuccessful_margin_order_add(
            {'type': 'buy', 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.0015', 'price': '21300'},
            code='AmountUnavailable',
        )

    def test_margin_order_add_sell_user_insufficient_margin_balance(self):
        self.charge_wallet(Currencies.usdt, '21.2', Wallet.WALLET_TYPE.margin)
        for price in ('21200', '21300'):  # requires $21.22, $21.3 collateral respectively
            self._test_unsuccessful_margin_order_add(
                {'type': 'sell', 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': price},
                code='InsufficientBalance',
            )

    def test_margin_order_add_buy_user_insufficient_margin_balance(self):
        self.charge_wallet(Currencies.usdt, '21.2', Wallet.WALLET_TYPE.margin)
        self._test_unsuccessful_margin_order_add(
            {'type': 'buy', 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '21300'},
            code='InsufficientBalance',
        )

    def test_margin_order_add_sell_small_order(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        for order_type in ('buy', 'sell'):
            self._test_unsuccessful_margin_order_add(
                {'type': order_type, 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.0001', 'price': '21300'},
                code='SmallOrder',
            )

    def test_margin_order_add_sell_unverified_email(self):
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=False)
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        self._test_unsuccessful_margin_order_add(
            {'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.002', 'price': '21300'}, code='UnverifiedEmail',
        )

    def test_margin_order_add_first_sell(self):
        assert not Position.objects.exists()
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        self._test_successful_margin_order_add(type='sell', amount='0.001', price='21300')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.7')
        positions = Position.objects.all()
        assert len(positions) == 1
        self._check_position_status(positions[0], side=Position.SIDES.sell, collateral='21.3')

    def test_margin_order_add_first_buy(self):
        assert not Position.objects.exists()
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        self._test_successful_margin_order_add(type='buy', amount='0.001', price='21300')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.7')
        positions = Position.objects.all()
        assert len(positions) == 1
        self._check_position_status(positions[0], side=Position.SIDES.buy, collateral='21.3')

    def test_margin_order_add_sell_below_market_price(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        self._test_successful_margin_order_add(type='sell', amount='0.001', price='21200')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.78')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.22')

    def test_margin_order_add_buy_below_market_price(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        self._test_successful_margin_order_add(type='buy', amount='0.001', price='21200')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.8')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='21.2')

    def test_margin_order_add_with_previous_ended_position(self):
        shared_data = {
            'user': self.user,
            'src_currency': self.market.src_currency,
            'dst_currency': self.market.dst_currency,
            'side': Position.SIDES.sell,
            'collateral': 24,
        }
        Position.objects.bulk_create([
            Position(**shared_data, status=getattr(Position.STATUS, status_key))
            for status_key in ('closed', 'liquidated', 'canceled', 'expired')
        ])
        self.charge_wallet(Currencies.usdt, 45, Wallet.WALLET_TYPE.margin)
        self._test_successful_margin_order_add(type='sell', amount='0.001', price='21300')
        self._test_successful_margin_order_add(type='buy', amount='0.001', price='21200')
        positions = Position.objects.all().order_by('id')
        assert len(positions) == 6
        self._check_position_status(positions[4], side=Position.SIDES.sell, collateral='21.3')
        self._check_position_status(positions[5], side=Position.SIDES.buy, collateral='21.2')

    @staticmethod
    def fake_position_opened(position: Position, amount: str, total_price: str):
        fee = Decimal('0.0015')
        position.delegated_amount += Decimal(amount)
        position.earned_amount += Decimal(total_price) * (1 - fee)
        position.status = Position.STATUS.open
        position.set_liquidation_price()
        position.save(update_fields=('delegated_amount', 'earned_amount', 'status', 'liquidation_price'))
        position.refresh_from_db()
        order = position.orders.last()
        order.matched_amount += Decimal(amount)
        order.save(update_fields=('matched_amount',))

    def test_margin_order_add_second_sell_to_active_position(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=50).commit()
        self.create_short_margin_order(amount='0.001', price='21300')
        positions = Position.objects.all()
        assert len(positions) == 1
        self.fake_position_opened(positions[0], amount='0.001', total_price='21.3')
        self._check_position_status(
            positions[0],
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.26805',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
        )

        self._test_successful_margin_order_add(type='sell', amount='0.001', price='22700')
        wallet.refresh_from_db()
        assert wallet.active_balance == 6
        positions = Position.objects.order_by('id')
        assert len(positions) == 2
        self._check_position_status(
            positions[0],
            side=Position.SIDES.sell,
            collateral='21.3',
            liability='0.0010015023',
            earned_amount='21.26805',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
        )
        self._check_position_status(positions[1], side=Position.SIDES.sell, collateral='22.7')

    def test_margin_order_add_above_user_pool_limit(self):
        assert self.src_pool.get_user_delegation_limit(self.user) < Decimal('0.32')
        assert self.dst_pool.get_user_delegation_limit(self.user) < 7000
        for order_type in ('sell', 'buy'):
            self._test_unsuccessful_margin_order_add(
                {'type': order_type, 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.32', 'price': '21300'},
                code='ExceedDelegationLimit',
            )

    def test_margin_order_add_above_user_pool_limit_legacy_code(self):
        assert self.src_pool.get_user_delegation_limit(self.user) < Decimal('0.32')
        self.client.defaults['HTTP_USER_AGENT'] = 'Android/5.3.2'
        self._test_unsuccessful_margin_order_add(
            {'type': 'sell', 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.32', 'price': '21300'},
            code='ExceedSellLimit',
        )

    def test_margin_order_add_sell_market_with_price(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        self._test_successful_margin_order_add(type='sell', amount='0.001', price='21300', execution='market')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.7')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.3')

    def test_margin_order_add_buy_market_with_price(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        self._test_successful_margin_order_add(type='buy', amount='0.001', price='21200', execution='market')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.8')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='21.2')

    def test_margin_order_add_sell_market_without_price(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        best_active_price = Decimal(10999999)
        cache.set('orderbook_BTCUSDT_best_active_buy', best_active_price)
        self._test_successful_margin_order_add(type='sell', amount='0.001', execution='market')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.78')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.22')
        cache.delete('orderbook_BTCUSDT_best_active_buy')

    def test_margin_order_add_buy_market_without_price(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        best_active_price = Decimal(10999999)
        cache.set('orderbook_BTCUSDT_best_active_sell', best_active_price)
        self._test_successful_margin_order_add(type='buy', amount='0.001', execution='market')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.78')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='21.22')
        cache.delete('orderbook_BTCUSDT_best_active_sell')

    def test_margin_order_add_sell_stop_limit(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        self._test_successful_margin_order_add(
            type='sell', amount='0.001', execution='stop_limit', stopPrice='21000', price='21500'
        )
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.5')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.5')

    def test_margin_order_add_buy_stop_limit(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        self._test_successful_margin_order_add(
            type='buy', amount='0.001', execution='stop_limit', stopPrice='22000', price='21900'
        )
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.1')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='21.9')

    def test_margin_order_add_sell_stop_market_with_price(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        self._test_successful_margin_order_add(
            type='sell', amount='0.001', execution='stop_market', stopPrice='21000', price='20400'
        )
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.78')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.22')
        order = position.orders.last()
        assert order.price == 20400

    def test_margin_order_add_buy_stop_market_with_price(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        self._test_successful_margin_order_add(
            type='buy', amount='0.001', execution='stop_market', stopPrice='22000', price='22100'
        )
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('2.9')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='22.1')
        order = position.orders.last()
        assert order.price == 22100

    def test_margin_order_add_sell_stop_market_without_price(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        self._test_successful_margin_order_add(type='sell', amount='0.001', execution='stop_market', stopPrice='20000')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3.78')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='21.22')
        order = position.orders.last()
        assert order.price == 20000

    def test_margin_order_add_buy_stop_market_without_price(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        self._test_successful_margin_order_add(type='buy', amount='0.001', execution='stop_market', stopPrice='22000')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('3')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='22')
        order = position.orders.last()
        assert order.price == 22000

    def test_margin_order_add_sell_oco(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=45).commit()
        self._test_successful_margin_order_add(
            type='sell', amount='0.002', is_oco=True, price='22000', stopPrice='20000', stopLimitPrice='20100'
        )
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('1')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.sell, collateral='44', orders_count=2)
        orders = position.orders.order_by('id')
        assert orders[0].price == 22000
        assert orders[0].execution_type == Order.EXECUTION_TYPES.limit
        assert orders[1].price == 20100
        assert orders[1].execution_type == Order.EXECUTION_TYPES.stop_limit
        assert orders[1].param1 == 20000

    def test_margin_order_add_buy_oco(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=45).commit()
        self._test_successful_margin_order_add(
            type='buy', amount='0.0018', is_oco=True, price='21000', stopPrice='22000', stopLimitPrice='22100'
        )
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('5.22')
        position = Position.objects.last()
        self._check_position_status(position, side=Position.SIDES.buy, collateral='39.78', orders_count=2)
        orders = position.orders.order_by('id')
        assert orders[0].price == 21000
        assert orders[0].execution_type == Order.EXECUTION_TYPES.limit
        assert orders[1].price == 22100
        assert orders[1].execution_type == Order.EXECUTION_TYPES.stop_limit
        assert orders[1].param1 == 22000

    def test_margin_order_add_buy_oco_insufficient_margin_balance(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=38).commit()
        self._test_unsuccessful_margin_order_add(
            {
                'mode': 'oco',
                'type': 'buy',
                'srcCurrency': 'btc',
                'dstCurrency': 'usdt',
                'amount': '0.0018',
                'price': '21000',
                'stopPrice': '22000',
                'stopLimitPrice': '22100',
            },
            code='InsufficientBalance',
        )

    def test_margin_order_add_with_trade_restriction(self):
        UserRestriction.add_restriction(user=self.user, restriction='Trading')
        for order_type in ('buy', 'sell'):
            self._test_unsuccessful_margin_order_add(
                {'type': order_type, 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '21300'},
                code='TradingUnavailable',
            )

    def test_margin_order_add_with_position_restriction(self):
        UserRestriction.add_restriction(user=self.user, restriction='Position')
        for order_type in ('buy', 'sell'):
            self._test_unsuccessful_margin_order_add(
                {'type': order_type, 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '21300'},
                code='TradingUnavailable',
            )

    def test_margin_order_add_on_invalid_leverage(self):
        for leverage in (0, -2, 1.234, 'X4'):
            self._test_unsuccessful_margin_order_add(
                {'srcCurrency': 'ltc', 'dstCurrency': 'usdt', 'amount': '4.5', 'price': '61', 'leverage': leverage},
                code='ParseError',
            )

    def test_margin_order_add_with_leverage_restriction(self):
        UserRestriction.add_restriction(user=self.user, restriction='Leverage')
        self._test_unsuccessful_margin_order_add(
            {'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '21300', 'leverage': '2'},
            code='LeverageUnavailable',
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=25).commit()
        self._test_successful_margin_order_add(type='sell', amount='0.001', price='21300')

    def test_margin_order_add_sell_with_leverage(self):
        assert not Position.objects.exists()
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=12).commit()
        self._test_successful_margin_order_add(type='sell', amount='0.001', price='21300', leverage='2')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('1.35')
        positions = Position.objects.all()
        assert len(positions) == 1
        self._check_position_status(positions[0], side=Position.SIDES.sell, collateral='10.65')
        assert positions[0].margin_ratio == Decimal('1.5')

    def test_margin_order_add_buy_with_leverage(self):
        assert not Position.objects.exists()
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=12).commit()
        self._test_successful_margin_order_add(type='buy', amount='0.001', price='21200', leverage='2')
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('1.4')
        positions = Position.objects.all()
        assert len(positions) == 1
        self._check_position_status(positions[0], side=Position.SIDES.buy, collateral='10.6')
        assert positions[0].margin_ratio == Decimal('1.5')

    def test_margin_order_add_with_leverage_above_pool_limit(self):
        self._test_unsuccessful_margin_order_add(
            {'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '21300', 'leverage': '6'},
            code='LeverageTooHigh',
        )

    def test_margin_order_add_with_leverage_above_user_limit(self):
        Settings.set(f'margin_max_leverage_{User.USER_TYPES.level1}', '3')
        MarginManager._get_user_type_max_leverages(skip_cache=True)
        self._test_unsuccessful_margin_order_add(
            {'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '21300', 'leverage': '4'},
            code='LeverageTooHigh',
        )

    def test_margin_order_add_with_disabled_market_exec_type(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=250).commit()
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=2500000).commit()

        # disable BTCIRT market exec type
        Settings.set_dict('market_execution_disabled_market_list', ['BTCUSDT'])
        msg = (
            'در حال حاضر امکان ثبت سفارش سریع در این بازار وجود ندارد.'
            ' لطفاً از سفارش گذاری با تعیین قیمت استفاده نمایید.'
        )
        self._test_unsuccessful_margin_order_add(
            {
                'srcCurrency': 'btc',
                'dstCurrency': 'usdt',
                'type': 'buy',
                'amount': '0.011',
                'price': '2000',
                'execution': 'market',
                'leverage': '2',
            },
            code='MarketExecutionTypeTemporaryClosed',
            message=msg,
        )

        # limit exec type should be fine in the disabled market
        self._test_successful_margin_order_add(type='buy', amount='0.011', price='2000', leverage='2')

        # market exec type orders should be fine in other markets
        Settings.set_dict('market_execution_disabled_market_list', ['BTCIRT'])
        self._test_successful_margin_order_add(
            type='buy',
            amount='0.011',
            price='2000',
            leverage='2',
            execution='market',
        )


@patch('exchange.market.marketmanager.MarketManager.get_trade_fee', new=get_trade_fee_mock)
class PredictMarginOrderAddAPITest(PositionTestMixin, OrderAPITestMixin, APITestCase):

    def _test_successful_margin_order_add_predict(
        self, amount: str, collateral: str, trade_fee: str, extension_fee: str, side: str = '',
        price: str = '', stop_price: str = '', stop_limit_price: str = '', leverage: str = ''
    ):
        data = {'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': amount}
        if side:
            data['type'] = side
        if price:
            data['price'] = price
        if stop_price:
            data['stopPrice'] = stop_price
        if stop_limit_price:
            data['stopLimitPrice'] = stop_limit_price
        if leverage:
            data['leverage'] = leverage
        response = self.client.post('/margin/predict/add-order', data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert data['collateral'] == collateral
        assert data['tradeFee'] == trade_fee
        assert data['extensionFee'] == extension_fee
        assert not Position.objects.exists()

    def _test_unsuccessful_margin_order_add_predict(self, data: dict, expected_code='ParseError'):
        response = self.client.post('/margin/predict/add-order', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == expected_code

    def test_margin_order_add_predict_above_market_price(self):
        self._test_successful_margin_order_add_predict(
            side='sell', amount='0.001', price='21300', collateral='21.3', trade_fee='0.03195', extension_fee='0.015'
        )
        self._test_successful_margin_order_add_predict(
            side='buy', amount='0.001', price='21300', collateral='21.3', trade_fee='0.0000015', extension_fee='0.015'
        )
        self._test_successful_margin_order_add_predict(
            side='sell', amount='0.007', price='22000', collateral='154', trade_fee='0.231', extension_fee='0.09'
        )
        self._test_successful_margin_order_add_predict(
            side='buy', amount='0.007', price='22000', collateral='154', trade_fee='0.0000105', extension_fee='0.09'
        )

    def test_margin_order_add_predict_sell_below_market_price(self):
        self._test_successful_margin_order_add_predict(
            side='sell', amount='0.001', price='21000', collateral='21.22', trade_fee='0.03183', extension_fee='0.015'
        )
        self._test_successful_margin_order_add_predict(
            side='sell', amount='0.007', price='21100', collateral='148.54', trade_fee='0.22281', extension_fee='0.075'
        )

    def test_margin_order_add_predict_buy_below_market_price(self):
        self._test_successful_margin_order_add_predict(
            side='buy', amount='0.001', price='21000', collateral='21', trade_fee='0.0000015', extension_fee='0.015'
        )
        self._test_successful_margin_order_add_predict(
            side='buy', amount='0.007', price='21100', collateral='147.7', trade_fee='0.0000105', extension_fee='0.075'
        )

    def test_margin_order_add_predict_precision(self):
        self._test_successful_margin_order_add_predict(
            amount='0.1000001', price='21499.995', collateral='2150', trade_fee='3.225', extension_fee='1.08'
        )

    def test_margin_order_add_predict_invalid_input(self):
        data = {'type': 'sell', 'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '21300'}
        self._test_unsuccessful_margin_order_add_predict({**data, 'srcCurrency': 10})
        self._test_unsuccessful_margin_order_add_predict({**data, 'dstCurrency': '﷼'})
        self._test_unsuccessful_margin_order_add_predict({**data, 'amount': '-3'})
        self._test_unsuccessful_margin_order_add_predict({**data, 'price': '-200'})
        self._test_unsuccessful_margin_order_add_predict({**data, 'type': 'purchase'})
        self._test_unsuccessful_margin_order_add_predict(
            {**data, 'srcCurrency': 'usdt'}, expected_code='InvalidMarketPair'
        )

    def test_margin_order_add_predict_market(self):
        self._test_successful_margin_order_add_predict(
            side='sell', amount='0.001', collateral='21.22', trade_fee='0.03183', extension_fee='0.015'
        )
        self._test_successful_margin_order_add_predict(
            side='buy', amount='0.001', collateral='21.22', trade_fee='0.0000015', extension_fee='0.015'
        )

    def test_margin_order_add_predict_sell_stop_loss(self):
        self._test_successful_margin_order_add_predict(
            side='sell', amount='0.001', stop_price='20300', price='20400',
            collateral='21.22', trade_fee='0.03183', extension_fee='0.015'
        )

    def test_margin_order_add_predict_buy_stop_loss(self):
        self._test_successful_margin_order_add_predict(
            side='buy',
            amount='0.001',
            stop_price='22000',
            price='22100',
            collateral='22.1',
            trade_fee='0.0000015',
            extension_fee='0.015',
        )

    def test_margin_order_add_predict_sell_oco(self):
        self._test_successful_margin_order_add_predict(
            side='sell', amount='0.001', price='21300', stop_price='20300', stop_limit_price='20100',
            collateral='21.3', trade_fee='0.03195', extension_fee='0.015'
        )

    def test_margin_order_add_predict_buy_oco(self):
        self._test_successful_margin_order_add_predict(
            side='buy',
            amount='0.001',
            price='21000',
            stop_price='22000',
            stop_limit_price='22100',
            collateral='22.1',
            trade_fee='0.0000015',
            extension_fee='0.015',
        )

    def test_margin_order_add_predict_with_leverage(self):
        shared_data = dict(amount='0.001', price='21300')
        shared_result = {
            'sell': dict(trade_fee='0.03195', extension_fee='0.015'),
            'buy': dict(trade_fee='0.0000015', extension_fee='0.015'),
        }
        for side in ('sell', 'buy'):
            self._test_successful_margin_order_add_predict(
                **shared_data, side=side, leverage='1.5', collateral='14.2', **shared_result[side]
            )
            self._test_successful_margin_order_add_predict(
                **shared_data, side=side, leverage='2', collateral='10.65', **shared_result[side]
            )
            self._test_successful_margin_order_add_predict(
                **shared_data, side=side, leverage='3', collateral='7.1', **shared_result[side]
            )
            self._test_successful_margin_order_add_predict(
                **shared_data, side=side, leverage='4', collateral='5.325', **shared_result[side]
            )
            self._test_successful_margin_order_add_predict(
                **shared_data, side=side, leverage='5', collateral='4.26', **shared_result[side]
            )
