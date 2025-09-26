import json
import random
from decimal import Decimal
from typing import Optional, Union
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from exchange.accounts.models import User, UserRestriction
from exchange.base.calendar import ir_now
from exchange.base.helpers import get_individual_ratelimit_throttle_settings, get_max_db_value
from exchange.base.models import Currencies, Settings
from exchange.base.publisher import OrderPublishManager
from exchange.base.serializers import serialize_decimal
from exchange.market.marketmanager import MarketManager
from exchange.market.models import Market, Order
from exchange.usermanagement.block import BalanceBlockManager
from exchange.wallet.models import Wallet
from tests.base.utils import create_order, create_trade, do_matching_round, set_initial_values


class OrderTest(TestCase):
    def setUp(self):
        set_initial_values()
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        w1_btc = Wallet.get_user_wallet(self.user1, Currencies.btc)
        w1_btc.create_transaction(tp='manual', amount=Decimal('0.5')).commit()
        w1_irr = Wallet.get_user_wallet(self.user1, Currencies.rls)
        w1_irr.create_transaction(tp='manual', amount=Decimal('1e9')).commit()
        w1_usdt = Wallet.get_user_wallet(self.user1, Currencies.usdt)
        w1_usdt.create_transaction(tp='manual', amount=Decimal('10000')).commit()
        w1_trx = Wallet.get_user_wallet(self.user1, Currencies.trx)
        w1_trx.create_transaction(tp='manual', amount=Decimal('10000')).commit()

    def test_get_balance_in_order(self):
        user = self.user1
        Wallet.create_user_wallets(user)
        wallets = {w.currency: w for w in Wallet.get_user_wallets(user, tp=Wallet.WALLET_TYPE.spot)}
        btc, xrp, rls, usdt = Currencies.btc, Currencies.xrp, Currencies.rls, Currencies.usdt
        # Check balance in order before creating any order
        for w in wallets.values():
            assert BalanceBlockManager.get_balance_in_order(w) == Decimal('0')
        # Place order
        create_order(user, btc, rls, Decimal('0.12'), Decimal('140e7'), sell=True)
        assert BalanceBlockManager.get_balance_in_order(wallets[btc]) == Decimal('0.12')
        for w in wallets.values():
            if w.currency != btc:
                assert BalanceBlockManager.get_balance_in_order(w) == Decimal('0')
        # Place another order
        create_order(user, btc, rls, Decimal('0.091'), Decimal('141e7'), sell=True)
        assert BalanceBlockManager.get_balance_in_order(wallets[btc]) == Decimal('0.211')
        for w in wallets.values():
            if w.currency != btc:
                assert BalanceBlockManager.get_balance_in_order(w) == Decimal('0')
        # Place XRP order
        create_order(user, xrp, rls, Decimal('100.4'), Decimal('36000'), sell=True)
        assert BalanceBlockManager.get_balance_in_order(wallets[btc]) == Decimal('0.211')
        assert BalanceBlockManager.get_balance_in_order(wallets[xrp]) == Decimal('100.4')
        for w in wallets.values():
            if w.currency not in [btc, xrp]:
                assert BalanceBlockManager.get_balance_in_order(w) == Decimal('0')
        # Place BTC-USDT order
        create_order(user, btc, usdt, Decimal('0.5'), Decimal('9901'), sell=False)
        assert BalanceBlockManager.get_balance_in_order(wallets[btc]) == Decimal('0.211')
        assert BalanceBlockManager.get_balance_in_order(wallets[xrp]) == Decimal('100.4')
        assert BalanceBlockManager.get_balance_in_order(wallets[usdt]) == Decimal('4950.5')
        for w in wallets.values():
            if w.currency not in [btc, xrp, usdt]:
                assert BalanceBlockManager.get_balance_in_order(w) == Decimal('0')
        # Sell some USDT
        create_order(user, usdt, rls, Decimal('120'), Decimal('165000'), sell=True)
        assert BalanceBlockManager.get_balance_in_order(wallets[btc]) == Decimal('0.211')
        assert BalanceBlockManager.get_balance_in_order(wallets[xrp]) == Decimal('100.4')
        assert BalanceBlockManager.get_balance_in_order(wallets[usdt]) == Decimal('5070.5')
        for w in wallets.values():
            if w.currency not in [btc, xrp, usdt]:
                assert BalanceBlockManager.get_balance_in_order(w) == Decimal('0')

        margin_wallets = Wallet.get_user_wallets(user, tp=Wallet.WALLET_TYPE.margin)
        for w in margin_wallets:
            assert BalanceBlockManager.get_balance_in_order(w) == Decimal('0')

    def test_create_order_for_market_order_zero_price(self):
        # USDT markets
        market = Market.get_for(Currencies.btc, Currencies.usdt)
        order, err = MarketManager.create_order(
            user=self.user1, order_type=Order.ORDER_TYPES.buy, market=market,
            execution_type=Order.EXECUTION_TYPES.market, amount=Decimal('0.0012'),
        )
        assert not err
        assert order.price == Decimal('48985.5')
        # USDT markets - Large order
        market = Market.get_for(Currencies.btc, Currencies.usdt)
        order, err = MarketManager.create_order(
            user=self.user1, order_type=Order.ORDER_TYPES.buy, market=market,
            execution_type=Order.EXECUTION_TYPES.market, amount=Decimal('0.23'),
        )
        assert order is None
        assert err == 'OverValueOrder'
        # IRT markets - buy
        market = Market.get_for(Currencies.btc, Currencies.rls)
        order, err = MarketManager.create_order(
            user=self.user1, order_type=Order.ORDER_TYPES.buy, market=market,
            execution_type=Order.EXECUTION_TYPES.market, amount=Decimal('0.0012'),
        )
        assert not err
        assert order.price == Decimal('13250577750')
        # IRT markets - sell
        order, err = MarketManager.create_order(
            user=self.user1, order_type=Order.ORDER_TYPES.sell, market=market,
            execution_type=Order.EXECUTION_TYPES.market, amount=Decimal('0.0012'),
        )
        assert not err
        assert order.price == Decimal('13030143000')
        # IRT markets - LTC
        market = Market.get_for(Currencies.ltc, Currencies.rls)
        order, err = MarketManager.create_order(
            user=self.user1, order_type=Order.ORDER_TYPES.buy, market=market,
            execution_type=Order.EXECUTION_TYPES.market, amount=Decimal('1.2333'),
        )
        assert not err
        assert order.price == Decimal('57765280')  # bankers' rounding of 57765275 for rls

    @override_settings(DISABLE_ORDER_PRICE_GUARD=False)
    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda _, __: Decimal('0.0562'),
    )
    def test_order_bad_price_guard_binance_usdt(self):
        # USDT markets - buy
        market = Market.get_for(Currencies.trx, Currencies.usdt)
        cache.delete(f'market_{market.id}_last_price')
        order, err = MarketManager.create_order(
            user=self.user1, order_type=Order.ORDER_TYPES.buy, market=market,
            amount=Decimal('400'), price=Decimal('0.63'),
        )
        assert not order
        assert err == 'BadPrice'
        order, err = MarketManager.create_order(
            user=self.user1, order_type=Order.ORDER_TYPES.buy, market=market,
            amount=Decimal('400'), price=Decimal('0.06'),
        )
        assert not err
        assert order.price == Decimal('0.06')
        # USDT markets - sell
        order, err = MarketManager.create_order(
            user=self.user1, order_type=Order.ORDER_TYPES.sell, market=market,
            amount=Decimal('3000'), price=Decimal('0.00449'),
        )
        assert not order
        assert err == 'BadPrice'
        order, err = MarketManager.create_order(
            user=self.user1, order_type=Order.ORDER_TYPES.sell, market=market,
            amount=Decimal('300'), price=Decimal('0.045'),
        )
        assert not err
        assert order.price == Decimal('0.045')

    @override_settings(DISABLE_ORDER_PRICE_GUARD=False)
    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda _, __: Decimal('14000'),
    )
    def test_order_bad_price_guard_binance_irt(self):
        # IRT markets - buy
        market = Market.get_for(Currencies.trx, Currencies.rls)
        cache.delete(f'market_{market.id}_last_price')
        order, err = MarketManager.create_order(
            user=self.user1, order_type=Order.ORDER_TYPES.buy, market=market,
            amount=Decimal('400'), price=Decimal('164600'),
        )
        assert not order
        assert err == 'BadPrice'
        order, err = MarketManager.create_order(
            user=self.user1, order_type=Order.ORDER_TYPES.buy, market=market,
            amount=Decimal('400'), price=Decimal('16450'),
        )
        assert not err
        assert order.price == Decimal('16450')
        # IRT markets - sell
        order, err = MarketManager.create_order(
            user=self.user1, order_type=Order.ORDER_TYPES.sell, market=market,
            amount=Decimal('300'), price=Decimal('1196'),
        )
        assert not order
        assert err == 'BadPrice'
        order, err = MarketManager.create_order(
            user=self.user1, order_type=Order.ORDER_TYPES.sell, market=market,
            amount=Decimal('300'), price=Decimal('11966'),
        )
        assert not err
        assert order.price == Decimal('11970')

    @override_settings(DISABLE_ORDER_PRICE_GUARD=False)
    def test_create_sell_whole_balance_order(self):
        ltc, irt = Currencies.ltc, Currencies.rls
        # Fill market
        market = Market.get_for(ltc, irt)
        o2 = create_order(self.user2, ltc, irt, Decimal('0.1'), Decimal('5_700_000_0'), sell=False)
        # Create an order for selling all remaining LTC balance
        w1_ltc = Wallet.get_user_wallet(self.user1, ltc)
        w1_ltc.create_transaction(tp='manual', amount=Decimal('0.001001')).commit()
        w1_ltc = Wallet.get_user_wallet(self.user1, ltc)
        order, err = MarketManager.create_sell_whole_balance_order(w1_ltc, irt)
        assert not err
        assert order.amount == Decimal('0.001001')
        assert order.price == Decimal('5_680_430_0')
        # Match
        do_matching_round(market)
        order.refresh_from_db()
        o2.refresh_from_db()
        # Check trade
        assert order.status == Order.STATUS.done
        assert order.matched_amount == Decimal('0.001001')
        assert order.matched_total_price == Decimal('5_705_7')
        assert o2.status == Order.STATUS.active
        assert o2.matched_amount == Decimal('0.001001')
        assert o2.matched_total_price == Decimal('5_705_7')


class OrderTestMixin:
    """

    Use in conjunction with `TestCase`
    """
    MARKET_SYMBOL: str = ''
    MARKET_PRICE: Union[int, Decimal] = 0

    market: Market
    user: User

    @classmethod
    def setUpTestData(cls):
        import random

        u = random.randint(0, 10000000000)
        cls.user = User.objects.create_user(username=f'OrderTestMixin{u}@nobitex.ir')
        cls.user.user_type = User.USER_TYPES.level1
        cls.user.save(update_fields=('user_type',))
        Token.objects.create(user=cls.user)

        cls.market = Market.by_symbol(cls.MARKET_SYMBOL)
        cls.set_market_price(cls.MARKET_PRICE)

    @classmethod
    def set_market_price(cls, price: Union[int, Decimal, None], symbol: Optional[str] = None):
        market = Market.by_symbol(symbol) if symbol else cls.market
        cache.set(f'market_{market.id}_last_price', price)

    def charge_wallet(self, currency, amount, tp=None):
        wallet = Wallet.get_user_wallet(self.user, currency, tp or Wallet.WALLET_TYPE.spot)
        amount = Decimal(amount)
        while amount > Decimal('0.0'):
            _amount = min(amount, get_max_db_value(Order.amount))
            wallet.create_transaction(tp='manual', amount=_amount).commit()
            amount -= _amount

    @classmethod
    def create_order(cls, **kwargs):
        return create_order(cls.user, cls.market.src_currency, cls.market.dst_currency, **kwargs)


class OrderAPITestMixin(OrderTestMixin):
    """

    Use in conjunction with `APITestCase`
    """

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.client.defaults['HTTP_USER_AGENT'] = 'Mozilla/5.0'


class OrderAddTest(OrderAPITestMixin, APITestCase):
    MARKET_SYMBOL = 'BTCUSDT'

    def setUp(self):
        super(OrderAddTest, self).setUp()
        set_initial_values()

    def create_order_params(
        self,
        type='sell',
        execution='limit',
        src='btc',
        dst='rls',
        amount=None,
        price=None,
        charge_ratio=None,
        client_order_id=None,
    ):
        # Set some random order values if not given
        if amount is not None:
            amount = Decimal(amount)
        if price is not None:
            price = Decimal(price)
        if amount is None:
            amount = Decimal('0.001') * random.randint(1, 20)
        if price is None:
            price = Decimal('1_046_000_0') * random.randint(900, 1100)
        if client_order_id is None:
            client_order_id = str(random.randint(1, 10**32))

        # Create transaction to provide needed wallet balance
        charge_ratio = Decimal(charge_ratio) if charge_ratio is not None else Decimal(1)
        if type == 'sell':
            self.charge_wallet(getattr(Currencies, src), amount * charge_ratio)
        else:
            total_price = amount * price
            self.charge_wallet(getattr(Currencies, dst), total_price * charge_ratio)
        # Order parameters
        return {
            'type': type,
            'execution': execution,
            'srcCurrency': src,
            'dstCurrency': dst,
            'amount': str(amount),
            'price': str(price),
            'clientOrderId': client_order_id,
        }


    def test_orders_add_level0(self):
        self.user.user_type = User.USER_TYPES.level0
        self.user.save(update_fields=['user_type'])
        r = self.client.post('/market/orders/add', data=self.create_order_params(
        )).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'TradeLimitation'

    @patch.object(OrderPublishManager, 'add_fail_message')
    @patch.object(OrderPublishManager, 'publish')
    def test_orders_add_over_value(self, mocked_publish, mocked_add_fail_message):
        r = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(charge_ratio='0.95', client_order_id='TestClientID'),
        ).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'OverValueOrder'
        assert r['clientOrderId'] == 'TestClientID'

        mocked_publish.assert_called_once()
        mocked_add_fail_message.assert_called_once_with(
            {
                'status': 'failed',
                'code': 'OverValueOrder',
                'message': 'Order Validation Failed',
                'clientOrderId': 'TestClientID',
            },
            self.user.uid,
        )

    def test_orders_add_small_order(self):
        price = 1000
        cache.set('orderbook_BTCIRT_best_active_buy', Decimal(price))
        r = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(price=price, client_order_id='TestClientID'),
        ).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'SmallOrder'
        assert r['clientOrderId'] == 'TestClientID'
        cache.delete('orderbook_BTCIRT_best_active_buy')

    def test_orders_add_normal_order_with_underpriced_value(self):
        requested_price = '10'
        order_book_price = Decimal(10460000010)
        cache.set('orderbook_BTCIRT_best_active_buy', order_book_price)
        r = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(
                amount='0.011',
                price=requested_price,
            ),
        ).json()
        assert r['status'] == 'ok'
        cache.delete('orderbook_BTCIRT_best_active_buy')

    def test_orders_add_large_order_with_rls(self):
        r = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(
                amount=2,
                price=3_927_499_999_0,
                client_order_id='TestClientID',
            ),
        ).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'LargeOrder'
        assert r['message'] == 'Order value is limited to below 50,000,000,000.'
        assert r['clientOrderId'] == 'TestClientID'

    def test_orders_add_large_order_with_usdt(self):

        r = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(
                amount=3500,
                price=65000,
                dst='usdt',
                client_order_id='TestClientID',
            ),
        ).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'LargeOrder'
        assert r['message'] == 'Order value is limited to below 200,000.'
        assert r['clientOrderId'] == 'TestClientID'

    @patch.dict(settings.NOBITEX_OPTIONS['minOrders'], {Currencies.rls: Decimal('20_000_0')})
    def test_orders_add_small_order_without_price(self):
        best_active_price = Decimal(1_000_000)
        cache.set(f'orderbook_{self.MARKET_SYMBOL}_best_active_buy', best_active_price)
        data = self.create_order_params(amount='0.00001', execution='market', client_order_id='TestClientID1')
        data.pop('price')
        r = self.client.post('/market/orders/add', data=data).json()
        assert Decimal(data['amount']) * best_active_price < settings.NOBITEX_OPTIONS['minOrders'].get(Currencies.rls)
        assert r['status'] == 'failed'
        assert r['code'] == 'SmallOrder'
        assert r['clientOrderId'] == 'TestClientID1'
        cache.delete(f'orderbook_{self.MARKET_SYMBOL}_best_active_buy')

    def test_orders_bad_price_market_order(self):
        cache.set(f'orderbook_{self.MARKET_SYMBOL}_best_active_buy', Decimal('1000'))
        cache.set(f'orderbook_{self.MARKET_SYMBOL}_best_active_sell', Decimal('1000'))
        cache.set(f'orderbook_{self.MARKET_SYMBOL}_best_buy', Decimal('1000'))
        cache.set(f'orderbook_{self.MARKET_SYMBOL}_best_sell', Decimal('1000'))

        r = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(
                type='sell',
                dst='usdt',
                execution='market',
                price=1060,
                client_order_id='TestClientID',
            ),
        ).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'UnexpectedMarketPrice'
        assert r['clientOrderId'] == 'TestClientID'

        r = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(type='buy', execution='market', price=900, client_order_id='TestClientID2'),
        ).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'UnexpectedMarketPrice'
        assert r['clientOrderId'] == 'TestClientID2'


    @patch.object(OrderPublishManager, 'add_order')
    @patch.object(OrderPublishManager, 'publish')
    def test_orders_add(self, mocked_publish, mocked_add_order):
        r = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(
                type='buy',
                amount='0.011',
                price='10460000010',
                client_order_id='order1',
            ),
        ).json()
        assert r['status'] == 'ok'
        order = r['order']
        order_id = int(order['id'])
        assert order_id > 0
        assert order['user'] == self.user.username
        assert order['status'] == 'Active'
        assert order['type'] == 'buy'
        assert order['execution'] == 'Limit'
        assert order['srcCurrency'] == 'Bitcoin'
        assert order['dstCurrency'] == '﷼'
        assert order['market'] == 'BTC-RLS'
        assert order['amount'] == '0.011'
        assert order['price'] == '10460000010'
        assert order['totalOrderPrice'] == '115060000.11'
        assert order['matchedAmount'] == '0'
        assert order['created_at'].startswith('202')
        assert order['clientOrderId'] == 'order1'

        # Also check order from DB
        order = self.user.order_set.order_by('-id').first()
        assert order.id == order_id
        assert order.order_type == Order.ORDER_TYPES.buy
        assert order.status == Order.STATUS.active
        assert order.amount == Decimal('0.011')
        assert order.matched_amount == Decimal('0')
        assert order.price == Decimal('10460000010')
        assert order.src_currency == Currencies.btc
        assert order.dst_currency == Currencies.rls
        assert order.channel == Order.CHANNEL.web
        assert order.trade_type == Order.TRADE_TYPES.spot
        assert order.client_order_id == 'order1'

        # check websocket publisher
        mocked_publish.assert_called_once()
        mocked_add_order.assert_called_once_with(order, None, order.user.uid)

    @override_settings(RATELIMIT_ENABLE=True)
    def test_rate_limit_per_market(self):
        cache.set(
            'settings_throttle_endpoint_rate_limits',
            {
                'exchange.market.views.OrderCreate.create_orders.BTCIRT': {
                    'norm': 0.0,
                    'ex_bot': 0.02,
                    'vip': 0.05,
                    'in_bot': 0.06,
                },
            },
        )
        get_individual_ratelimit_throttle_settings.clear()
        r = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(type='buy', amount='0.011', price='10460000010', client_order_id='order1'),
        )
        response = r.json()
        assert response['status'] == 'failed'
        assert response['code'] == 'MarketTemporaryClosed'

        cache.delete('settings_throttle_endpoint_rate_limits')

    def test_orders_add_parse_err(self):
        response = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(
                src='wrong_symbol',
                type='buy',
                amount='0.011',
                price='10460000010',
                client_order_id='order1',
            ),
        )
        assert response.status_code == 400
        r = response.json()
        assert r['status'] == 'failed'
        assert r['code'] == 'ParseError'
        assert r['message'] == 'Invalid choices: "wrong_symbol"'
        assert r['clientOrderId'] == 'order1'


    def test_orders_add_no_ua(self):
        r = self.client.post('/market/orders/add', data=self.create_order_params(
            amount='0.00999',
        ), HTTP_USER_AGENT='-').json()
        assert r['status'] == 'ok'
        assert r['order']['status'] == 'Active'
        assert r['order']['amount'] == '0.00999'
        order = self.user.order_set.order_by('-id').first()
        assert order.id == r['order']['id']
        assert order.amount == Decimal('0.00999')
        assert order.channel == Order.CHANNEL.api

    def test_wallets_convert(self):
        w_btc = Wallet.get_user_wallet(self.user, Currencies.btc)
        w_xrp = Wallet.get_user_wallet(self.user, Currencies.xrp)
        w_trx = Wallet.get_user_wallet(self.user, Currencies.trx)
        w_margin = Wallet.get_user_wallet(self.user, Currencies.usdt)
        w_btc.create_transaction(tp='manual', amount='0.1').commit()
        w_xrp.create_transaction(tp='manual', amount='1').commit()
        w_trx.create_transaction(tp='manual', amount='10000').commit()
        w_margin.create_transaction(tp='manual', amount='1').commit()
        # Convert balances
        r = self.client.post('/users/wallets/convert', data={
            'srcCurrency': 'btc,xrp',
            'dstCurrency': 'rls',
        }).json()
        assert r['status'] == 'ok'
        orders = self.user.order_set.order_by('-id')
        assert len(orders) == 2
        o1, o2 = sorted(orders, key=lambda o: o.src_currency)
        assert o1.src_currency == Currencies.btc
        assert o1.dst_currency == Currencies.rls
        assert o1.order_type == Order.ORDER_TYPES.sell
        assert o1.execution_type == Order.EXECUTION_TYPES.market
        assert o1.amount == Decimal('0.1')
        assert o1.price == Decimal('13030143000')
        assert o1.channel == Order.CHANNEL.web_convert
        assert o1.trade_type == Order.TRADE_TYPES.spot
        assert o2.src_currency == Currencies.xrp
        assert o2.dst_currency == Currencies.rls
        assert o2.order_type == Order.ORDER_TYPES.sell
        assert o2.execution_type == Order.EXECUTION_TYPES.market
        assert o2.amount == Decimal('1')
        assert o2.price == Decimal('147470')
        assert o2.channel == Order.CHANNEL.web_convert
        assert o2.trade_type == Order.TRADE_TYPES.spot

    def _test_order_field_precision(self, field, expected_value, **kwargs):
        assert field in kwargs and kwargs[field] != expected_value
        kwargs.setdefault('charge_ratio', '1.1')
        response = self.client.post('/market/orders/add', data=self.create_order_params(**kwargs)).json()
        assert response['status'] == 'ok' or not response
        assert response['order'] and field in response['order']
        assert response['order'][field] == expected_value
        order = self.user.order_set.get(id=response['order']['id'])
        assert getattr(order, field, None) == Decimal(expected_value)

    def test_order_price_precision_round_half_even(self):
        self._test_order_field_precision('price', '44710.95', price='44710.9548', dst='usdt', type='sell')
        self._test_order_field_precision('price', '44710.96', price='44710.955', dst='usdt', type='buy')
        self._test_order_field_precision('price', '44710.96', price='44710.9583', dst='usdt', type='sell')
        self._test_order_field_precision('price', '44710.96', price='44710.962', dst='usdt', type='buy')
        self._test_order_field_precision('price', '44710.96', price='44710.965', dst='usdt', type='sell')
        self._test_order_field_precision('price', '44710.97', price='44710.9652', dst='usdt', type='buy')

    def test_order_amount_precision_round_down(self):
        self._test_order_field_precision('amount', '0.011002', amount='0.0110028', type='buy')
        self._test_order_field_precision('amount', '0.011003', amount='0.01100307', type='sell')
        self._test_order_field_precision('amount', '0.011003', amount='0.0110035', type='buy')
        self._test_order_field_precision('amount', '0.011003', amount='0.0110038', type='sell')
        self._test_order_field_precision('amount', '0.011004', amount='0.01100401', type='buy')

    def test_orders_duplicate_client_order_id(self):
        client_order_id = '1' * 8

        first_order_req = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(client_order_id=client_order_id),
            HTTP_USER_AGENT='-',
        ).json()

        assert first_order_req['status'] == 'ok'

        second_order_req = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(client_order_id=client_order_id),
            HTTP_USER_AGENT='-',
        ).json()

        assert second_order_req['status'] == 'failed'
        assert second_order_req['code'] == 'DuplicateClientOrderId'

        order_params = self.create_order_params(client_order_id=client_order_id, execution='stop_limit')
        order_params.update(is_sell=True, price='700_000_000_0', stopPrice='700_000_000__0')
        stop_limit_order_req = self.client.post(
            '/market/orders/add',
            data=order_params,
            HTTP_USER_AGENT='-',
        ).json()

        assert stop_limit_order_req['status'] == 'failed'
        assert stop_limit_order_req['code'] == 'DuplicateClientOrderId'

        order_params.update(execution='stop_market')
        stop_market_order_req = self.client.post(
            '/market/orders/add',
            data=order_params,
            HTTP_USER_AGENT='-',
        ).json()

        assert stop_market_order_req['status'] == 'failed'
        assert stop_market_order_req['code'] == 'DuplicateClientOrderId'

        orders = Order.objects.filter(client_order_id=client_order_id)
        assert orders.count() == 1
        assert orders[0].id == first_order_req['order']['id']

    def test_orders_client_order_id_invalid(self):
        for client_order_id in ['1' * 33, '!', '@', '%']:
            r = self.client.post(
                '/market/orders/add',
                data=self.create_order_params(client_order_id=client_order_id),
                HTTP_USER_AGENT='-',
            ).json()
            assert r['status'] == 'failed'
            assert r['code'] == 'ParseError'
            assert r['message'] == f'Invalid clientOrderId "{client_order_id}"'
            assert Order.objects.filter(client_order_id=client_order_id).first() is None

    def _test_order_field_max_value(self, field, max_value, **kwargs):
        assert field in kwargs
        r = self.client.post('/market/orders/add', data=self.create_order_params(**kwargs)).json()
        if kwargs[field] > max_value:
            assert r['status'] == 'failed'
            assert r['code'] == 'ParseError'
            assert r['message'] == f'Numeric value out of bound: "{kwargs[field]}"'
        else:
            assert r['status'] != 'failed' or r['code'] != 'ParseError'

    def test_order_decimal_field_max_value_allowed(self):
        max_allowed_amount = get_max_db_value(Order.amount)
        max_allowed_price = get_max_db_value(Order.price)
        self._test_order_field_max_value('amount', max_allowed_amount, amount=max_allowed_amount)
        self._test_order_field_max_value('amount', max_allowed_amount, amount=max_allowed_amount - Decimal('1e-10'))
        self._test_order_field_max_value('amount', max_allowed_amount, amount=max_allowed_amount + Decimal('1e-10'))
        self._test_order_field_max_value('price', max_allowed_price, price=max_allowed_price)
        self._test_order_field_max_value('price', max_allowed_price, price=max_allowed_price - Decimal('1e-10'))
        self._test_order_field_max_value('price', max_allowed_price, price=max_allowed_price + Decimal('1e-10'))

    def test_orders_add_with_disabled_market_exec_type(self):
        # disable BTCIRT market exec type
        Settings.set_dict('market_execution_disabled_market_list', ['BTCIRT'])

        # market exec type orders should be prevented in BTCIRT
        r = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(
                type='buy',
                amount='0.011',
                price='10460000010',
                client_order_id='order1',
                execution='market',
            ),
        ).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'MarketExecutionTypeTemporaryClosed'
        assert (
            r['message']
            == 'در حال حاضر امکان ثبت سفارش سریع در این بازار وجود ندارد. لطفاً از سفارش گذاری با تعیین قیمت استفاده نمایید.'
        )

        # market exec type orders should be fine in other markets
        r = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(
                type='buy',
                amount='0.011',
                price='10460000010',
                client_order_id='order2',
                execution='market',
                dst='usdt',
            ),
        ).json()
        assert r['status'] == 'ok'

        # limit exec type should be fine in the disabled market
        r = self.client.post(
            '/market/orders/add',
            data=self.create_order_params(
                type='buy',
                amount='0.011',
                price='10460000010',
                client_order_id='order3',
                execution='limit',
            ),
        ).json()
        assert r['status'] == 'ok'


class OrderListTest(APITestCase):
    def setUp(self) -> None:
        self.list_url = '/market/orders/list'
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        # No need to create orders by MarketManager in this test.
        for i in range(1, 21):
            Order.objects.create(
                id=i,
                user=cls.user,
                src_currency=Currencies.btc,
                dst_currency=Currencies.rls,
                order_type=Order.ORDER_TYPES.sell,
                execution_type=Order.EXECUTION_TYPES.limit,
                trade_type=Order.TRADE_TYPES.spot,
                amount=0.01,
                price=1000000000,
                status=Order.STATUS.new,
                client_order_id=str(random.randint(1, 10 ** 32)),
            )
        for i in range(21, 51):
            Order.objects.create(
                id=i,
                user=cls.user,
                src_currency=Currencies.ltc,
                dst_currency=Currencies.btc,
                order_type=Order.ORDER_TYPES.buy,
                execution_type=Order.EXECUTION_TYPES.stop_market,
                trade_type=Order.TRADE_TYPES.margin,
                amount=0.01,
                price=1000000000,
                status=Order.STATUS.active,
                client_order_id=str(random.randint(1, 10 ** 32)),
            )

    def test_list_all(self):
        # first page
        response = self.client.post(self.list_url, data={'pageSize': 15})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert result['hasNext'] is True
        assert len(result['orders']) == 15
        first = result['orders'][0]
        assert 'type' in first
        assert 'execution' in first
        assert 'srcCurrency' in first
        assert 'dstCurrency' in first
        assert 'price' in first
        assert 'amount' in first
        assert 'totalPrice' in first
        assert 'totalOrderPrice' in first
        assert 'matchedAmount' in first
        assert 'unmatchedAmount' in first
        assert 'totalPrice' in first
        assert 'tradeType' in first
        assert 'clientOrderId' in first

        # last page
        response = self.client.post(self.list_url, data={'page': 4, 'pageSize': 15, 'details': 2})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert result['hasNext'] is False
        assert len(result['orders']) == 5
        first = result['orders'][0]
        assert 'id' in first
        assert 'status' in first
        assert 'partial' in first
        assert 'fee' in first
        assert 'user' in first
        assert 'created_at' in first
        assert 'market' in first
        assert 'averagePrice' in first
        assert 'totalPrice' in first
        assert 'clientOrderId' in first

        # out of index page
        response = self.client.post(self.list_url, data={'page': 5})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['orders']) == 0

        # page size
        response = self.client.post(self.list_url, data={'page': 2, 'pageSize': 30})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['orders']) == 20

    def test_filter_by_src_currency(self):
        response = self.client.post(self.list_url, data={'pageSize': 50, 'srcCurrency': 'btc'})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['orders']) == 20

    def test_filter_by_dst_currency(self):
        response = self.client.post(self.list_url, data={'pageSize': 50, 'dstCurrency': 'btc'})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['orders']) == 30

    def test_filter_by_order_type(self):
        response = self.client.post(self.list_url, data={'pageSize': 50, 'type': 'sell'})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['orders']) == 20

    def test_filter_by_execution_type(self):
        response = self.client.post(self.list_url, data={'pageSize': 50, 'execution': 'limit'})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['orders']) == 20

    def test_filter_by_trade_type(self):
        for trade_type, count in {'spot': 20, 'margin': 30}.items():
            response = self.client.post(self.list_url, data={'pageSize': 50, 'tradeType': trade_type})
            assert response.status_code == 200
            result = response.json()
            assert result['status'] == 'ok'
            assert len(result['orders']) == count
            assert {order['tradeType'] for order in result['orders']} == {trade_type.title()}

    def test_filter_by_status(self):
        response = self.client.post(self.list_url, data={'pageSize': 50, 'status': 'undone'})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['orders']) == 30

    def test_filter_by_from_id(self):
        last_id = Order.objects.last().pk
        response = self.client.post(self.list_url, data={'pageSize': 50, 'fromId': last_id - 23})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['orders']) == 24

    @override_settings(LOAD_LEVEL=4)
    def test_download_csv(self):
        response = self.client.post(f'{self.list_url}?download=true')
        assert response.status_code == 200
        assert response['Content-Type'] == 'text/csv'
        assert len(str(response.content).split(r'\n')) == 52

    def test_asc_ordering_by_date(self):
        # Test asc order by created_at
        response1 = self.client.post(self.list_url, data={'order': 'created_at'})
        assert response1.status_code == 200
        orders = Order.objects.all().order_by('created_at').values_list('client_order_id', flat=True)
        result1 = response1.json()['orders']
        assert len(orders) == len(result1)
        for i in range(len(result1)):
            assert orders[i] == result1[i]['clientOrderId']

        # Test desc order by created_at
        response2 = self.client.post(self.list_url)
        result2 = response2.json()['orders'][::-1]
        for i in range(len(result2)):
            assert orders[i] == result2[i]['clientOrderId']

    def test_id_filter_and_non_id_ordering(self):
        Order.objects.filter(pk__range=(19, 22)).update(created_at=ir_now())
        response = self.client.post(self.list_url, data={'order': 'created_at', 'fromId': 11, 'details': 2})
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        orders = Order.objects.filter(id__gte=11).order_by('created_at', '-id').values_list('id', flat=True)
        assert len(orders) == len(data['orders']) == 40
        for i in range(40):
            assert orders[i] == data['orders'][i]['id']


class TestOrderHelpers:
    def test_detect_order_channel(self):
        # API
        assert MarketManager.detect_order_channel('') == Order.CHANNEL.api
        assert MarketManager.detect_order_channel('-') == Order.CHANNEL.api
        assert MarketManager.detect_order_channel('python-requests/2.25.1') == Order.CHANNEL.api
        assert MarketManager.detect_order_channel('TraderBot/ras') == Order.CHANNEL.api
        assert MarketManager.detect_order_channel('TraderBot/x@gmail.com', is_convert=True) == Order.CHANNEL.api_convert
        assert MarketManager.detect_order_channel('TraderBot/Nobitex2') == Order.CHANNEL.api_internal
        assert MarketManager.detect_order_channel('TraderBot/Nobitex3', is_convert=True) == Order.CHANNEL.api_internal
        # Android
        assert MarketManager.detect_order_channel('Android/3.7.0 (SM-J200F)') == Order.CHANNEL.android
        assert MarketManager.detect_order_channel('Android/3.5.1 (SM-A515F)') == Order.CHANNEL.android
        assert MarketManager.detect_order_channel('Android/3.7.0 (SM-A600FN)', is_convert=True) == Order.CHANNEL.android_convert
        # Web
        assert MarketManager.detect_order_channel('Mozilla/5.0 (X11; Linux x86_64; rv:98.0) Gecko/20100101 Firefox/98.0') == Order.CHANNEL.web
        assert MarketManager.detect_order_channel('Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/97.0.4692.84 Mobile/15E148 Safari/604.1') == Order.CHANNEL.web
        assert MarketManager.detect_order_channel('Mozilla/5.0 (iPhone; CPU iPhone OS 15_1 like Mac OS X)', is_convert=True) == Order.CHANNEL.web_convert
        # iOS
        assert MarketManager.detect_order_channel('iOSApp/1.0 (iPhone; iOS 15.2.1; Scale/2.00)') == Order.CHANNEL.ios
        assert MarketManager.detect_order_channel('iOSApp/1.0 (iPhone; iOS 15.2.1; Scale/2.00)', is_convert=True) == Order.CHANNEL.ios_convert
        # Other
        assert MarketManager.detect_order_channel('XXX', is_convert=True) == Order.CHANNEL.unknown
        assert MarketManager.detect_order_channel('-/-') == Order.CHANNEL.unknown


class TestUpdateStatus(TestCase):
    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)

    def setUp(self):
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'
        self.client.defaults['HTTP_USER_AGENT'] = 'Mozilla/5.0'

    def test_orders_parse_error(self):
        response = self.client.post(
            '/market/orders/update-status',
            {
                'order': 0,
                'status': 'canceled',
            },
        )
        result = {'status': 'failed', 'code': 'ParseError', 'message': 'Value must be greater than or equal to 1'}
        assert response.json() == result
        assert response.status_code == 400

    @patch.object(OrderPublishManager, 'add_order')
    @patch.object(OrderPublishManager, 'publish')
    def test_successful(self, mocked_publish, mocked_add_order):
        order = create_order(
            self.user,
            Currencies.usdt,
            Currencies.rls,
            amount='60',
            price='42500',
            sell=True,
            market=True,
            validate=False,
        )
        response = self.client.post(
            '/market/orders/update-status',
            {
                'order': order.id,
                'status': 'canceled',
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        order.refresh_from_db()
        assert order.status == Order.STATUS.canceled

        assert 'order' in data
        assert data['order']['type'] == 'sell'
        assert data['order']['amount'] == '60'
        assert data['order']['execution'] == 'Market'
        assert data['order']['price'] == 'market'
        assert data['order']['srcCurrency'] == 'Tether'
        assert data['order']['dstCurrency'] == '﷼'
        assert data['order']['totalPrice'] == '0'
        assert int(data['order']['totalOrderPrice']) > 0
        assert data['order']['matchedAmount'] == '0'
        assert data['order']['unmatchedAmount'] == '60'
        assert data['order']['market'] == 'USDT-RLS'
        assert data['order']['status'] == 'Canceled'
        assert data['order']['partial'] is False
        assert data['order']['fee'] == '0'

        mocked_add_order.assert_called_once_with(order, None, order.user.uid)
        mocked_publish.assert_called_once()


class TestCancelOrders(TestCase):
    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.active_order = Order.objects.create(
            user=cls.user,
            src_currency=Currencies.ltc,
            dst_currency=Currencies.rls,
            status=Order.STATUS.active,
            amount=Decimal('1'),
            price=Decimal('1_653_570'),
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.market,
        )
        cls.ltc_limit_order = Order.objects.create(
            user=cls.user,
            src_currency=Currencies.ltc,
            dst_currency=Currencies.usdt,
            status=Order.STATUS.active,
            amount=Decimal('0.2'),
            price=Decimal('70'),
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.limit,
        )
        cls.limit_order = Order.objects.create(
            user=cls.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            status=Order.STATUS.active,
            amount=Decimal('1'),
            price=Decimal('622_400_000'),
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.limit,
        )
        cls.inactive_order = Order.objects.create(
            user=cls.user,
            src_currency=Currencies.ltc,
            dst_currency=Currencies.rls,
            amount=Decimal('1'),
            price=Decimal('1_653_570'),
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.market,
            status=Order.STATUS.inactive,
        )
        cls.system_order = Order.objects.create(
            user=cls.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            amount=Decimal('1'),
            price=Decimal('622_400_000'),
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.limit,
            status=Order.STATUS.active,
            channel=Order.CHANNEL.system_block,
        )
        cls.active_order_channel = Order.objects.create(
            user=cls.user,
            src_currency=Currencies.ltc,
            dst_currency=Currencies.rls,
            amount=Decimal('1'),
            price=Decimal('1_653_570'),
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.market,
            status=Order.STATUS.active,
            channel=Order.CHANNEL.system_block,
        )
        cls.done_order = Order.objects.create(
            user=cls.user,
            src_currency=Currencies.ltc,
            dst_currency=Currencies.rls,
            amount=Decimal('1'),
            price=Decimal('1_653_570'),
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.market,
            status=Order.STATUS.done,
        )
        cls.cancel_order = Order.objects.create(
            user=cls.user,
            src_currency=Currencies.ltc,
            dst_currency=Currencies.rls,
            amount=Decimal('1'),
            price=Decimal('1_653_570'),
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.market,
            status=Order.STATUS.canceled,
        )
        cls.active_order_web_channel = Order.objects.create(
            user=cls.user,
            src_currency=Currencies.ltc,
            dst_currency=Currencies.rls,
            amount=Decimal('1'),
            price=Decimal('1_653_570'),
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.market,
            status=Order.STATUS.active,
            channel=Order.CHANNEL.web,
        )
        cls.margin_order = Order.objects.create(
            user=cls.user,
            src_currency=Currencies.ltc,
            dst_currency=Currencies.rls,
            amount=Decimal('0.01'),
            price=Decimal('3_500_000_0'),
            order_type=Order.ORDER_TYPES.buy,
            trade_type=Order.TRADE_TYPES.margin,
            execution_type=Order.EXECUTION_TYPES.limit,
            status=Order.STATUS.active,
        )
        cls.other_user_order = Order.objects.create(
            user_id=202,
            src_currency=Currencies.ltc,
            dst_currency=Currencies.rls,
            amount=Decimal('0.01'),
            price=Decimal('3_600_000_0'),
            order_type=Order.ORDER_TYPES.sell,
            status=Order.STATUS.active,
        )
        cls.initial_orders = list(Order.objects.order_by('id'))

    def setUp(self):
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'
        self.client.defaults['HTTP_USER_AGENT'] = 'Mozilla/5.0'

    def get_response(self, data):
        return self.client.post('/market/orders/cancel-old', data)

    def assert_successful_response(self, response, canceled_orders: set):
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'

        for i, order in enumerate(Order.objects.order_by('id')):
            if order in canceled_orders:
                assert order.status == Order.STATUS.canceled
            else:
                assert order.status == self.initial_orders[i].status

    @patch.object(OrderPublishManager, 'add_order')
    @patch.object(OrderPublishManager, 'publish')
    def test_canceling_with_src_currency(self, mocked_publish, mocked_add_order):
        response = self.get_response({'srcCurrency': 'ltc'})
        canceled_orders = {self.active_order, self.ltc_limit_order, self.active_order_web_channel, self.margin_order}
        self.assert_successful_response(response, canceled_orders)


        assert mocked_publish.call_count == 1
        assert mocked_add_order.call_count == len(canceled_orders)

        for order in canceled_orders:
            mocked_add_order.assert_any_call(order, None, order.user.uid)

    def test_canceling_with_dst_currency(self):
        response = self.get_response({'dstCurrency': 'rls'})
        canceled_orders = {self.active_order, self.limit_order, self.active_order_web_channel, self.margin_order}
        self.assert_successful_response(response, canceled_orders)

    def test_canceling_with_execution_type(self):
        response = self.get_response({'execution': 'limit'})
        canceled_orders = {self.limit_order, self.ltc_limit_order, self.margin_order}
        self.assert_successful_response(response, canceled_orders)

    def test_canceling_with_trade_type(self):
        response = self.get_response({'tradeType': 'margin'})
        canceled_orders = {self.margin_order}
        self.assert_successful_response(response, canceled_orders)

    def test_canceling_system_orders(self):
        response = self.get_response({'srcCurrency': 'btc'})
        canceled_orders = {self.limit_order}
        self.assert_successful_response(response, canceled_orders)

        assert not self.system_order.do_cancel(manual=True)
        assert self.system_order.status != Order.STATUS.canceled

        assert self.system_order.do_cancel()
        assert self.system_order.status == Order.STATUS.canceled

    def create_oco_order(self, amount, price, stop_price, stop_limit_price, is_sell=False):
        limit_order = create_order(self.user, Currencies.btc, Currencies.usdt, amount=amount, price=price, sell=is_sell)
        stop_order = create_order(
            self.user,
            Currencies.btc,
            Currencies.usdt,
            amount=amount,
            price=stop_limit_price,
            stop=stop_price,
            pair=limit_order,
            sell=is_sell,
        )
        return limit_order, stop_order

    def test_cancel_batch_of_orders_parse_error(self):
        order = create_order(
            self.user,
            Currencies.usdt,
            Currencies.rls,
            amount='60',
            price='42500',
            sell=True,
            market=True,
            validate=False,
        )
        response = self.client.post('/market/orders/cancel-batch', data={'orderIds': [order.id, 0]})
        result = {'status': 'failed', 'code': 'ParseError', 'message': 'Value must be greater than or equal to 1'}
        assert response.json() == result
        assert response.status_code == 400

    def test_canceling_batch_of_orders(self):
        for _ in range(20):
            create_order(
                self.user,
                Currencies.usdt,
                Currencies.rls,
                amount='60',
                price='42500',
                sell=True,
                market=True,
                validate=False,
            )

        # check batch size
        orders = Order.objects.filter(user=self.user).order_by('id')
        # get ids and add fake ids
        ids = [*orders.values_list('id', flat=True), '1010101']

        # check one order
        response = self.client.post('/market/orders/cancel-batch', data={'orderIds': [ids[-2], ids[-2]]}).json()
        assert response['status'] == 'ok'
        assert 'orders' in response
        assert len(response and response['orders']) == 1
        assert response['orders'][str(ids[-2])]['status'] == 'ok'
        assert Order.objects.get(id=ids[-2]).status == Order.STATUS.canceled
        assert Order.objects.get(id=ids[-3]).status == Order.STATUS.active

        response = self.client.post('/market/orders/cancel-batch', data={'orderIds': ids}).json()

        assert response['status'] == 'failed'
        assert response['message'] == 'The maximum number of orderIds should be 20.'

        # check not send id numbers
        response = self.client.post('/market/orders/cancel-batch', data={'orderIds': ['f', 't']}).json()
        assert response['status'] == 'failed'
        assert response['message'] == 'Invalid integer value: "f"'

        # send json test
        response = self.client.post('/market/orders/cancel-batch', data={'orderIds': ['f', 't']},
                                     content_type='application/json').json()
        assert response['status'] == 'failed'
        assert response['message'] == 'Invalid integer value: "f"'

        # send empty order_ids
        response = self.client.post('/market/orders/cancel-batch', data={'orderIds': []}).json()
        assert response['status'] == 'failed'
        assert response['message'] == 'Order_ids list is empty'

        # check not send id numbers
        response = self.client.post(
            '/market/orders/cancel-batch', data={}).json()
        assert response['status'] == 'failed'
        assert response['message'] == 'Order_ids list is empty'

        # check status and message error
        new_ids = ids[:19] + [ids[-1]]
        response = self.client.post('/market/orders/cancel-batch', data={'orderIds': new_ids}).json()

        check_ids = [str(new_ids[i]) for i in [0, 1, 2, 3, 4, 6, 7, 8, 19]]
        check_status = ['ok', 'ok', 'ok', 'ok', 'failed', 'failed', 'failed', 'ok', 'failed']
        check_msg = ['', '', '', '', 'Systematically placed orders are immutable.', 'The order is already completed.',
                     'The order is already canceled.', '', 'The order id not found']
        for i in range(9):
            if 'orders' in response and check_ids[i] in response['orders']:
                if 'status' in response['orders'][check_ids[i]]:
                    assert response['orders'][check_ids[i]]['status'] == check_status[i]

                if 'message' in response['orders'][check_ids[i]]:
                    assert response['orders'][check_ids[i]]['message'] == check_msg[i]

        # Test cancel OCO orders in batch
        #  1) active limit, inactive stop:
        #       cancel limit --> canceled stop
        #  2) active limit, inactive stop:
        #       cancel stop --> canceled limit
        #  3) matched limit, canceled stop:
        #       cancel stop --> active limit
        #  3) canceled limit, active stop:
        #       cancel limit --> active stop
        oco_orders = [
            dict(
                zip(
                    ['limit_order', 'stop_order'],
                    self.create_oco_order(
                        amount='0.3',
                        price='42300',
                        stop_price='41850',
                        stop_limit_price='41900',
                        is_sell=True,
                    ),
                ),
            )
            for _ in range(4)
        ]

        MarketManager.increase_order_matched_amount(
            oco_orders[2]['limit_order'],
            amount=Decimal('0.2'),
            price=Decimal('42300'),
        )
        oco_orders[2]['limit_order'].save(update_fields=('status', 'matched_amount', 'matched_total_price', 'status'))

        oco_orders[3]['stop_order'].status = Order.STATUS.active
        oco_orders[3]['stop_order'].save(update_fields=('status',))
        MarketManager.increase_order_matched_amount(
            oco_orders[3]['stop_order'],
            amount=Decimal('0.2'),
            price=Decimal('42300'),
        )

        cancel_ids = [
            oco_orders[0]['limit_order'].id,
            oco_orders[1]['stop_order'].id,
            oco_orders[2]['stop_order'].id,
            oco_orders[3]['limit_order'].id,
        ]
        response = self.client.post('/market/orders/cancel-batch', data={'orderIds': cancel_ids}).json()

        expected_resp_msgs = ['', '', 'The order is already canceled.', 'The order is already canceled.']
        if 'orders' in response:
            for i, order_id in enumerate(cancel_ids):
                assert response['orders'][str(order_id)].get('message', '') == expected_resp_msgs[i]

        expected_statuses = [Order.STATUS.canceled, Order.STATUS.canceled, Order.STATUS.active, Order.STATUS.active]
        pair_ids = [
            oco_orders[0]['stop_order'].id,
            oco_orders[1]['limit_order'].id,
            oco_orders[2]['limit_order'].id,
            oco_orders[3]['stop_order'].id,
        ]
        pair_orders_statuses = Order.objects.filter(id__in=pair_ids).order_by('id').values_list('status', flat=True)
        for i, pair_status in enumerate(pair_orders_statuses):
            assert pair_status == expected_statuses[i]


class OrderGetTest(APITestCase):
    def setUp(self) -> None:
        self.get_url = '/market/orders/status'
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.user2 = User.objects.get(pk=202)
        # No need to create orders by MarketManager in this test.
        for i in range(4):
            Order.objects.create(
                user=cls.user,
                src_currency=Currencies.btc,
                dst_currency=Currencies.rls,
                order_type=Order.ORDER_TYPES.sell,
                execution_type=Order.EXECUTION_TYPES.limit,
                trade_type=Order.TRADE_TYPES.spot,
                amount=0.01,
                price=1000000000,
                status=Order.STATUS.new,
                client_order_id=str(random.randint(1, 10 ** 32)),
            )

    def test_orders_parse_error(self):
        response = self.client.post(self.get_url, data={'id': 0})
        result = {'status': 'failed', 'code': 'ParseError', 'message': 'Value must be greater than or equal to 1'}
        assert response.json() == result
        assert response.status_code == 400

    def test_get_by_id(self):
        order0 = Order.objects.filter(user=self.user).first()
        response = self.client.post(self.get_url, data={'id': order0.id})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'

        order = result['order']
        assert order['id'] == order0.id
        assert order['type'] == 'buy' if order0.is_buy else 'sell'
        assert order['execution'] == order0.get_execution_type_display()
        assert order['srcCurrency'] == order0.get_src_currency_display()
        assert order['dstCurrency'] == order0.get_dst_currency_display()
        assert order['price'] == 'market' if order0.is_market else order0.price
        assert order['amount'] == serialize_decimal(order0.amount)
        assert order['totalPrice'] == serialize_decimal(order0.average_price * order0.matched_amount)
        assert order['totalOrderPrice'] == serialize_decimal(order0.total_price)
        assert order['matchedAmount'] == serialize_decimal(order0.matched_amount)
        assert order['unmatchedAmount'] == serialize_decimal(order0.unmatched_amount)
        assert order['tradeType'] == order0.get_trade_type_display()
        assert order['clientOrderId'] == order0.client_order_id

    def test_get_by_client_order_id(self):
        order0 = Order.objects.filter(user=self.user).first()
        response = self.client.post(self.get_url, data={'clientOrderId': order0.client_order_id})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'

        order = result['order']
        assert order['clientOrderId'] == order0.client_order_id

        # Add a done order with same client_order_id to check it gets the correct one (new/active/inactive)
        Order.objects.create(
            user=order0.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            order_type=Order.ORDER_TYPES.sell,
            execution_type=Order.EXECUTION_TYPES.limit,
            trade_type=Order.TRADE_TYPES.spot,
            amount=0.01,
            price=1000000000,
            status=Order.STATUS.done,
            client_order_id=order0.client_order_id,
        )
        response = self.client.post(self.get_url, data={'clientOrderId': order0.client_order_id})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        order = result['order']
        assert order['id'] == order0.id

        # Get a active order by clientOrderId
        active_order = Order.objects.create(
            user=order0.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            order_type=Order.ORDER_TYPES.sell,
            execution_type=Order.EXECUTION_TYPES.limit,
            trade_type=Order.TRADE_TYPES.spot,
            amount=0.01,
            price=1000000000,
            status=Order.STATUS.active,
            client_order_id='active-order',
        )
        response = self.client.post(self.get_url, data={'clientOrderId': 'active-order'})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        order = result['order']
        assert order['id'] == active_order.id
        assert order['clientOrderId'] == active_order.client_order_id

        # Get a inactive order by clientOrderId
        inactive_order = Order.objects.create(
            user=order0.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            order_type=Order.ORDER_TYPES.sell,
            execution_type=Order.EXECUTION_TYPES.limit,
            trade_type=Order.TRADE_TYPES.spot,
            amount=0.01,
            price=1000000000,
            status=Order.STATUS.active,
            client_order_id='inactive-order',
        )
        response = self.client.post(self.get_url, data={'clientOrderId': 'inactive-order'})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        order = result['order']
        assert order['id'] == inactive_order.id
        assert order['clientOrderId'] == inactive_order.client_order_id

        # Get a new order by clientOrderId
        new_order = Order.objects.create(
            user=order0.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            order_type=Order.ORDER_TYPES.sell,
            execution_type=Order.EXECUTION_TYPES.limit,
            trade_type=Order.TRADE_TYPES.spot,
            amount=0.01,
            price=1000000000,
            status=Order.STATUS.active,
            client_order_id='new-order',
        )
        response = self.client.post(self.get_url, data={'clientOrderId': 'new-order'})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        order = result['order']
        assert order['id'] == new_order.id
        assert order['clientOrderId'] == new_order.client_order_id

        # Get a canceled order by clientOrderId
        new_order = Order.objects.create(
            user=order0.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            order_type=Order.ORDER_TYPES.sell,
            execution_type=Order.EXECUTION_TYPES.limit,
            trade_type=Order.TRADE_TYPES.spot,
            amount=0.01,
            price=1000000000,
            status=Order.STATUS.canceled,
            client_order_id='canceled-order',
        )
        response = self.client.post(self.get_url, data={'clientOrderId': 'canceled-order'})
        assert response.status_code == 404
        data = response.json()
        assert data['error'] == 'NotFound'
        assert data['message'] == 'No Order matches the given query.'

    def test_get_by_both_id_and_client_order_id(self):
        # id has precedence to clientOrderId
        order0 = Order.objects.filter(user=self.user).first()
        other_order = Order.objects.filter(user=self.user).last()
        response = self.client.post(self.get_url, data={
            'id': order0.id,
            'clientOrderId': other_order.client_order_id,
        })
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        order = result['order']
        assert order['id'] == order0.id

    def test_get_by_id_not_found(self):
        response = self.client.post(self.get_url, data={'id': '1'})
        assert response.status_code == 404
        assert response.json()['error'] == 'NotFound'

    def test_get_order_with_trades(self):
        trade = create_trade(self.user, self.user2, Currencies.bch, Currencies.usdt, amount='1.7', price='257.9',
                             fee_rate='0.003')
        response = self.client.post(self.get_url, data={'id': trade.sell_order_id, 'level': 3})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert 'trades' in result and len(result['trades']) == 1
        assert 'price' in result['trades'][0] and result['trades'][0]['price'] == '257.9'

        order0 = Order.objects.filter(user=self.user).first()
        response = self.client.post(self.get_url, data={'id': order0.id, 'level': 3})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert 'trades' in result and len(result['trades']) == 0

    def test_get_by_client_order_id_not_found(self):
        response = self.client.post(self.get_url, data={'clientOrderId': '-1'})
        assert response.status_code == 404
        assert response.json()['error'] == 'NotFound'

    def test_get_missing_both_params(self):
        response = self.client.post(self.get_url)
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'NullIdAndClientOrderId'
        assert result['message'] == 'Both id and clientOrderId cannot be null'

    def test_get_by_client_order_id_invalid(self):
        response = self.client.post(self.get_url, data={'clientOrderId': '1' * 33})
        assert response.status_code == 400
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'ParseError'
        assert result['message'] == 'Invalid clientOrderId "111111111111111111111111111111111"'

        # When value is not string.
        # Using json because form data converts everything to string
        response = self.client.post(
            self.get_url,
            data=json.dumps({'clientOrderId': True}),
            content_type='application/json',
        )
        assert response.status_code == 400
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'ParseError'
        assert result['message'] == 'clientOrderId should be string'


class OrderBatchAddTest(OrderAPITestMixin, APITestCase):
    MARKET_SYMBOL = 'BTCUSDT'

    def setUp(self):
        super(OrderBatchAddTest, self).setUp()
        set_initial_values()
        self.set_market_price(386500, 'USDTIRT')

    def assert_sub_json(self, item_a, item_b):
        assert type(item_a) == type(item_b)
        if isinstance(item_a, list):
            assert len(item_a) == len(item_b)
            for sub_item_a, sub_item_b in zip(item_a, item_b):
                self.assert_sub_json(sub_item_a, sub_item_b)
        elif isinstance(item_a, dict):
            for key in item_a:
                assert key in item_b
                self.assert_sub_json(item_a[key], item_b[key])

    def _test_successful_add_batch_orders(self, orders_data: list, expected_results: list, **kwargs):
        response = self.client.post(
            '/market/orders/batch-add',
            data={
                'data': orders_data,
                **kwargs,
            },
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert 'results' in data
        self.assert_sub_json(expected_results, data['results'])

    def _test_unsuccessful_add_batch_orders(self, orders_data: list, code: str, **kwargs):
        initial_orders = Order.objects.count()
        response = self.client.post(
            '/market/orders/batch-add',
            data={
                'data': orders_data,
                **kwargs,
            },
            content_type='application/json',
        )
        assert response.status_code == 400 if code == 'ParseError' else 200
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code
        assert Order.objects.count() == initial_orders

    def test_add_batch_orders_with_trade_restriction(self):
        UserRestriction.add_restriction(user=self.user, restriction='Trading')
        self._test_unsuccessful_add_batch_orders([
            {'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '16800', 'type': 'sell'},
            {'srcCurrency': 'btc', 'dstCurrency': 'rls', 'amount': '0.01', 'price': '666_000_000_0', 'type': 'buy'},
        ], code='TradingUnavailable')

    def test_add_batch_orders_with_trade_limit(self):
        User.objects.filter(pk=self.user.pk).update(user_type=User.USER_TYPES.level0)
        self._test_unsuccessful_add_batch_orders([
            {'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'price': '16800', 'type': 'sell'},
            {'srcCurrency': 'btc', 'dstCurrency': 'rls', 'amount': '0.01', 'price': '666_000_000_0', 'type': 'buy'},
        ], code='TradeLimitation')

    def test_add_batch_orders_when_some_inputs_are_incorrect(self):
        self.charge_wallet(Currencies.usdt, '200')

        data = [
            {
                'srcCurrency': 'usdt',
                'dstCurrency': 'rls',
                'amount': '40',
                'price': '401000',
                'type': 'sell',
                'clientOrderId': 'TestClientOrderID1',
            },
            {
                'srcCurrency': 'بیت‌کوین',
                'dstCurrency': 'تتر',
                'amount': '0.001',
                'price': '16800',
                'type': 'sell',
                'clientOrderId': 'TestClientOrderID2',
            },
            {
                'srcCurrency': 'btc',
                'dstCurrency': 'usdt',
                'amount': '-2',
                'price': '16800',
                'type': 'buy',
                'clientOrderId': 'TestClientOrderID3',
            },
            {
                'srcCurrency': 'btc',
                'dstCurrency': 'usdt',
                'amount': '0.1',
                'price': '16,800',
                'type': 'sell',
                'clientOrderId': 'TestClientOrderID4',
            },
            {
                'srcCurrency': 'btc',
                'dstCurrency': 'usdt',
                'amount': '0.01',
                'price': '16800',
                'clientOrderId': 'TestClientOrderID5',
            },
            {
                'srcCurrency': 'btc',
                'dstCurrency': 'usdt',
                'price': '16800',
                'type': 'sell',
                'execution': 'default',
                'clientOrderId': 'TestClientOrderID6',
            },
            {
                'srcCurrency': 'btc',
                'dstCurrency': 'usdt',
                'amount': '0.01',
                'price': '16800',
                'type': 'sell',
                'execution': 'stop_limit',
                'clientOrderId': 'TestClientOrderID7',
            },
            {
                'srcCurrency': 'btc',
                'dstCurrency': 'usdt',
                'amount': '0.01',
                'price': '16800',
                'type': 'sell',
                'mode': 'oco',
                'stopPrice': '14200',
                'clientOrderId': 'TestClientOrderID8',
            },
        ]

        expected_results = [
            {
                'status': 'ok',
                'order': {
                    'market': 'BTC-USDT',
                    'type': 'buy',
                    'execution': 'Market',
                    'price': 'market',
                    'clientOrderId': 'TestClientOrderID1',
                },
            },
            {'status': 'failed', 'code': 'ParseError', 'clientOrderId': 'TestClientOrderID2'},
            {'status': 'failed', 'code': 'ParseError', 'clientOrderId': 'TestClientOrderID3'},
            {'status': 'failed', 'code': 'ParseError', 'clientOrderId': 'TestClientOrderID4'},
            {'status': 'failed', 'code': 'ParseError', 'clientOrderId': 'TestClientOrderID5'},
            {'status': 'failed', 'code': 'ParseError', 'clientOrderId': 'TestClientOrderID6'},
            {'status': 'failed', 'code': 'ParseError', 'clientOrderId': 'TestClientOrderID7'},
            {'status': 'failed', 'code': 'ParseError', 'clientOrderId': 'TestClientOrderID8'},
        ]
        self._test_successful_add_batch_orders(data, expected_results=expected_results)


    @patch.object(OrderPublishManager, 'add_order')
    @patch.object(OrderPublishManager, 'publish')
    def test_add_batch_orders_all_successful(self, mocked_publish, mocked_add_order):
        self.charge_wallet(Currencies.usdt, '90')
        self._test_successful_add_batch_orders(
            [
                {'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'execution': 'market', 'type': 'buy'},
                {
                    'srcCurrency': 'usdt',
                    'dstCurrency': 'rls',
                    'amount': '40',
                    'price': '401000',
                    'type': 'sell',
                    'mode': 'oco',
                    'stopPrice': '375000',
                    'stopLimitPrice': '374000',
                },
            ],
            expected_results=[
                {
                    'status': 'ok',
                    'order': {'market': 'BTC-USDT', 'type': 'buy', 'execution': 'Market', 'price': 'market'},
                },
                {
                    'status': 'ok',
                    'orders': [
                        {'market': 'USDT-RLS', 'type': 'sell', 'execution': 'Limit', 'price': '401000'},
                        {
                            'market': 'USDT-RLS',
                            'type': 'sell',
                            'execution': 'StopLimit',
                            'price': '374000',
                            'param1': '375000',
                        },
                    ],
                },
            ],
        )

        orders = Order.objects.all().order_by('-id')[:3]

        assert mocked_publish.call_count == 1
        assert mocked_add_order.call_count == 3

        for order in orders:
            mocked_add_order.assert_any_call(order, None, order.user.uid)

    @patch.object(OrderPublishManager, "add_order")
    @patch.object(OrderPublishManager, "add_fail_message")
    @patch.object(OrderPublishManager, 'publish')
    def test_add_batch_orders_few_successful(self, mocked_publish, mocked_add_fail_message, mocked_add_order, *_):
        self.charge_wallet(Currencies.usdt, '75')

        self._test_successful_add_batch_orders(
            [
                {'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'amount': '0.001', 'execution': 'market', 'type': 'buy'},
                {
                    'srcCurrency': 'usdt',
                    'dstCurrency': 'rls',
                    'amount': '40',
                    'price': '401000',
                    'type': 'sell',
                    'mode': 'oco',
                    'stopPrice': '375000',
                    'stopLimitPrice': '374000',
                    'clientOrderId': 'TestClientOrderID',
                },
                {'srcCurrency': 'bnb', 'dstCurrency': 'usdt', 'amount': '0.1', 'price': '248', 'type': 'buy'},
            ],
            expected_results=[
                {
                    'status': 'ok',
                    'order': {'market': 'BTC-USDT', 'type': 'buy', 'execution': 'Market', 'price': 'market'},
                },
                {'status': 'failed', 'code': 'OverValueOrder', 'clientOrderId': 'TestClientOrderID'},
                {'status': 'ok', 'order': {'market': 'BNB-USDT', 'type': 'buy', 'execution': 'Limit', 'price': '248'}},
            ],
        )

        orders = Order.objects.all().order_by('-id')[:2]

        assert mocked_publish.call_count == 1
        assert mocked_add_fail_message.call_count == 1
        assert mocked_add_order.call_count == 2

        for order in orders:
            mocked_add_order.assert_any_call(order, None, order.user.uid)

        mocked_add_fail_message.assert_called_once_with(
            {
                'status': 'failed',
                'code': 'OverValueOrder',
                'message': 'Order Validation Failed',
                'clientOrderId': 'TestClientOrderID',
            },
            self.user.uid,
        )
