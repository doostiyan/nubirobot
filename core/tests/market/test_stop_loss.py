import random
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from exchange.accounts.models import User, Notification
from exchange.base.models import Currencies
from exchange.market.models import Market, Order
from exchange.market.tasks import task_notify_stop_order_activation
from exchange.wallet.models import Wallet
from .test_order import OrderAPITestMixin
from ..base.utils import create_order, do_matching_round


@override_settings(ENABLE_STOP_ORDERS=True)
class MatcherStopLossTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        # this would allow matches on range 7440~11280 to activate stop-loss
        cache.set(f'orderbook_BTCUSDT_best_active_buy', 9300)
        cache.set(f'orderbook_BTCUSDT_best_active_sell', 9400)

    def test_stop_loss_sell_on_drop_1(self):
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        user3 = User.objects.get(pk=203)
        btc, usdt = Currencies.btc, Currencies.usdt
        market = Market.objects.get(src_currency=btc, dst_currency=usdt)

        # Initial market status: ~9510
        o1 = create_order(user1, btc, usdt, '0.5', '9510', sell=True)
        o2 = create_order(user2, btc, usdt, '0.45', '9500', sell=False, market=True, charge_ratio=2)

        # Adding stop sell order @9100|9100, should not be matched now
        s1 = create_order(user3, btc, usdt, '0.21', '9100', stop='9100', sell=True)
        assert s1
        do_matching_round(market)
        for order in (o1, o2, s1):
            order.refresh_from_db()
        assert s1.status == Order.STATUS.inactive
        assert not s1.is_matched
        assert o1.status == Order.STATUS.active
        assert o1.matched_amount == Decimal('0.45')
        assert o1.unmatched_amount == Decimal('0.05')
        assert o2.status == Order.STATUS.done
        assert o2.matched_amount == Decimal('0.45')
        assert o2.unmatched_amount == Decimal('0')

        # Market drops to ~9100
        o1.do_cancel()
        o3 = create_order(user1, btc, usdt, '0.1', '9100', sell=True)
        o4 = create_order(user2, btc, usdt, '0.4', '9100', sell=False)

        # Stop order should get activated now
        do_matching_round(market)
        for order in (o3, o4, s1):
            order.refresh_from_db()
        assert s1.status == Order.STATUS.active
        assert s1.matched_amount == Decimal('0')
        assert o3.status == Order.STATUS.done
        assert o3.matched_amount == Decimal('0.1')
        assert o3.unmatched_amount == Decimal('0')
        assert o4.status == Order.STATUS.active
        assert o4.matched_amount == Decimal('0.1')
        assert o4.unmatched_amount == Decimal('0.3')

        # Stop order should now match
        do_matching_round(market)
        for order in (o4, s1):
            order.refresh_from_db()
        assert s1.status == Order.STATUS.done
        assert s1.matched_amount == Decimal('0.21')
        assert s1.unmatched_amount == Decimal('0')
        assert s1.matched_total_price == Decimal('1911')
        assert o4.status == Order.STATUS.active
        assert o4.matched_amount == Decimal('0.31')
        assert o4.unmatched_amount == Decimal('0.09')

    def test_stop_loss_sell_on_drop_2(self):
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        user3 = User.objects.get(pk=203)
        btc, usdt = Currencies.btc, Currencies.usdt
        market = Market.objects.get(src_currency=btc, dst_currency=usdt)

        # Initial market status
        o1 = create_order(user1, btc, usdt, '0.9', '9310', sell=True)
        o2 = create_order(user2, btc, usdt, '0.2', '9299', sell=False)

        # Adding stop sell order @8910|8900, should not be matched now
        s1 = create_order(user3, btc, usdt, '0.34', '8910', stop='8900', sell=True)
        assert s1
        do_matching_round(market)
        for order in (o1, o2, s1):
            order.refresh_from_db()
        assert s1.status == Order.STATUS.inactive
        assert not s1.is_matched
        assert o1.status == Order.STATUS.active
        assert not o1.is_matched
        assert o2.status == Order.STATUS.active
        assert not o2.is_matched

        # Market drops to ~8900
        o1.do_cancel()
        o2.do_cancel()
        o3 = create_order(user1, btc, usdt, '0.3', '8900', sell=True)
        o4 = create_order(user2, btc, usdt, '0.2', '8900', sell=False)

        # Stop order should get activated now
        do_matching_round(market)
        for order in (o3, o4, s1):
            order.refresh_from_db()
        assert s1.status == Order.STATUS.active
        assert not s1.is_matched
        assert o3.status == Order.STATUS.active
        assert o3.matched_amount == Decimal('0.2')
        assert o4.status == Order.STATUS.done
        assert o4.matched_amount == Decimal('0.2')

        # Market buy side goes up to ~8910
        o5 = create_order(user2, btc, usdt, '0.4', '8910', sell=False)

        # Stop order should now match (without precedence)
        do_matching_round(market)
        for order in (o3, o5, s1):
            order.refresh_from_db()
        assert s1.status == Order.STATUS.active
        assert s1.matched_amount == Decimal('0.3')
        assert s1.unmatched_amount == Decimal('0.04')
        assert s1.matched_total_price == Decimal('2673')
        assert o3.status == Order.STATUS.done
        assert o3.matched_amount == Decimal('0.3')
        assert o3.unmatched_amount == Decimal('0')
        assert o5.status == Order.STATUS.done
        assert o5.matched_amount == Decimal('0.4')
        assert o5.unmatched_amount == Decimal('0')

    def test_stop_loss_buy_on_raise_1(self):
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        user3 = User.objects.get(pk=203)
        btc, usdt = Currencies.btc, Currencies.usdt
        market = Market.objects.get(src_currency=btc, dst_currency=usdt)

        # Initial market status: ~9500
        o1 = create_order(user1, btc, usdt, '0.5', '9500', sell=True)
        o2 = create_order(user2, btc, usdt, '0.45', '9510', sell=False)

        # Adding stop buy order @9700|9700, should not be matched now
        s1 = create_order(user3, btc, usdt, '0.21', '9700', stop='9700', sell=False)
        assert s1
        do_matching_round(market)
        for order in (o1, o2, s1):
            order.refresh_from_db()
        assert s1.status == Order.STATUS.inactive
        assert s1.matched_amount == Decimal(0)
        assert o1.status == Order.STATUS.active
        assert o1.matched_amount == Decimal('0.45')
        assert o1.unmatched_amount == Decimal('0.05')
        assert o2.status == Order.STATUS.done
        assert o2.matched_amount == Decimal('0.45')

        # Market raises to ~9700
        o1.do_cancel()
        o3 = create_order(user1, btc, usdt, '0.6', '9700', sell=True)
        o4 = create_order(user2, btc, usdt, '0.4', '9690', sell=False)
        o5 = create_order(user2, btc, usdt, '0.2', '9710', sell=False)

        # Stop order should get activated now
        do_matching_round(market)
        for order in (o3, o4, o5, s1):
            order.refresh_from_db()
        assert s1.status == Order.STATUS.active
        assert not s1.is_matched
        assert o3.status == Order.STATUS.active
        assert o3.matched_amount == Decimal('0.2')
        assert o3.unmatched_amount == Decimal('0.4')
        assert o4.status == Order.STATUS.active
        assert not o4.is_matched
        assert o5.status == Order.STATUS.done
        assert o5.matched_amount == Decimal('0.2')
        assert o5.unmatched_amount == Decimal('0')

        # Stop order should now match
        do_matching_round(market)
        for order in (o3, o4, s1):
            order.refresh_from_db()
        assert s1.status == Order.STATUS.done
        assert s1.matched_amount == Decimal('0.21')
        assert s1.unmatched_amount == Decimal('0')
        assert s1.matched_total_price == Decimal('2037')
        assert o3.status == Order.STATUS.active
        assert o3.matched_amount == Decimal('0.41')
        assert o3.unmatched_amount == Decimal('0.19')
        assert o4.status == Order.STATUS.active
        assert not o4.is_matched

    def test_stop_loss_sell_on_raise_2(self):
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        user3 = User.objects.get(pk=203)
        btc, usdt = Currencies.btc, Currencies.usdt
        market = Market.objects.get(src_currency=btc, dst_currency=usdt)

        # Initial market status: ~9310
        o1 = create_order(user1, btc, usdt, '0.9', '9310', sell=True)
        o2 = create_order(user2, btc, usdt, '0.2', '9299', sell=False, market=True, charge_ratio=2)

        # Adding stop buy order @9490|9500, should not be matched now
        s1 = create_order(user3, btc, usdt, '0.36', '9490', stop='9500', sell=False)
        assert s1
        do_matching_round(market)
        for order in (o1, o2, s1):
            order.refresh_from_db()
        assert s1.status == Order.STATUS.inactive
        assert not s1.is_matched
        assert o1.status == Order.STATUS.active
        assert o1.matched_amount == Decimal('0.2')
        assert o2.status == Order.STATUS.done
        assert o2.matched_amount == Decimal('0.2')

        # Market raises to ~9500
        o1.do_cancel()
        o3 = create_order(user1, btc, usdt, '0.3', '9500', sell=True)
        o4 = create_order(user2, btc, usdt, '0.2', '9490', sell=False)
        o5 = create_order(user2, btc, usdt, '0.4', '9520', sell=False, market=True, charge_ratio=2)

        # Stop order should get activated now
        do_matching_round(market)
        for order in (o3, o4, o5, s1):
            order.refresh_from_db()
        assert s1.status == Order.STATUS.active
        assert not s1.is_matched
        assert o3.status == Order.STATUS.done
        assert o3.matched_amount == Decimal('0.3')
        assert o3.unmatched_amount == Decimal('0')
        assert o4.status == Order.STATUS.active
        assert not o4.is_matched
        assert o5.status == Order.STATUS.canceled
        assert o5.matched_amount == Decimal('0.3')
        assert o5.unmatched_amount == Decimal('0.1')

        # Market sell side goes down to ~9490
        o6 = create_order(user2, btc, usdt, '0.4', '9490', sell=True)

        # Stop order should now match (without precedence)
        do_matching_round(market)
        for order in (o4, o6, s1):
            order.refresh_from_db()
        assert s1.status == Order.STATUS.active
        assert s1.matched_amount == Decimal('0.2')
        assert s1.unmatched_amount == Decimal('0.16')
        assert s1.matched_total_price == Decimal('1898')
        assert o6.status == Order.STATUS.done
        assert o6.matched_amount == Decimal('0.4')
        assert o6.unmatched_amount == Decimal('0')
        assert o6.status == Order.STATUS.done
        assert o4.matched_amount == Decimal('0.2')
        assert o4.unmatched_amount == Decimal('0')

    def test_stop_loss_activation_time_on_raise(self):
        user1, user2, user3 = list(User.objects.filter(pk__in=[201, 202, 203]))
        btc, usdt = Currencies.btc, Currencies.usdt
        market = Market.get_for(btc, usdt)

        orders = [
            create_order(user1, btc, usdt, '0.12', '9490', stop='9500', sell=False),
            create_order(user2, btc, usdt, '0.24', '9570', stop='9450', sell=False, market=True),
            create_order(user3, btc, usdt, '0.36', '9530', stop='9520', sell=False),
        ]
        create_order(user1, btc, usdt, '0.1', '9300', sell=True)
        create_order(user2, btc, usdt, '0.1', '9300', sell=False)

        do_matching_round(market)
        assert not Order.get_active_market_orders(btc, usdt).exists()

        create_order(user1, btc, usdt, '0.1', '9530', sell=True)
        create_order(user2, btc, usdt, '0.1', '9530', sell=False)
        do_matching_round(market)
        # created_at value after update is expected to be strictly increasing
        final_orders = list(Order.get_active_market_orders(btc, usdt).order_by('created_at', '-pk'))
        for i in range(3):
            assert final_orders[i] == orders[i]
            print(final_orders[i].created_at.isoformat())
            assert final_orders[i].created_at > orders[i].created_at
            assert final_orders[i].status == Order.STATUS.active

    def test_stop_loss_activation_notifs(self):
        user1, user2 = list(User.objects.filter(pk__in=[201, 202]))
        btc, usdt = Currencies.btc, Currencies.usdt
        create_order(user1, btc, usdt, '0.12', '9490', stop='9500', sell=False)
        order = create_order(user2, btc, usdt, '0.24', '9570', stop='9450', sell=False, market=True)
        last_notif = Notification.objects.latest('id')
        task_notify_stop_order_activation([order.id])
        notifications = Notification.objects.filter(id__gt=last_notif.id)
        assert len(notifications) == 1
        assert notifications[0].user == user2
        assert notifications[0].message == 'سفارش حد ضرر شما در بازار BTCUSDT فعال شد.'


class StopLossOrderAPITest(OrderAPITestMixin, APITestCase):
    MARKET_SYMBOL = 'BTCUSDT'
    MARKET_PRICE = 42200

    def add_stop_loss_order(self, amount, stop_price, is_sell=False, is_market=False, price=None):
        request_data = {
            'type': 'sell' if is_sell else 'buy',
            'execution': 'stop_market' if is_market else 'stop_limit',
            'srcCurrency': 'btc',
            'dstCurrency': 'usdt',
            'amount': amount,
            'stopPrice': stop_price,
            'clientOrderId': str(random.randint(1, 10**8))
        }
        if price:
            request_data['price'] = price
        response = self.client.post('/market/orders/add', request_data)
        return response.json()

    @staticmethod
    def check_successful_stop_loss_order_response(order_data, expected_price, amount, stop_price, is_sell, is_market):
        assert order_data
        assert order_data['id']
        assert order_data['execution'] == 'StopMarket' if is_market else 'StopLimit'
        assert order_data['type'] == 'sell' if is_sell else 'buy'
        assert order_data['status'] == 'Inactive'
        assert order_data['price'] == expected_price
        assert order_data['amount'] == amount
        assert 'param1' in order_data and order_data['param1'] == stop_price

    def check_successful_stop_loss_order_database(
        self, order_id, amount, expected_price, stop_price, is_sell=False, is_market=False
    ):
        order = Order.objects.filter(id=order_id).first()
        assert order
        assert order.is_sell == is_sell
        assert order.is_market == is_market
        assert order.execution_type == Order.STOP_EXECUTION_TYPES[is_market]
        assert order.status == Order.STATUS.inactive
        assert order.param1 == Decimal(stop_price)
        assert order.price == Decimal(expected_price)
        assert order.amount == Decimal(amount)
        wallet = Wallet.get_user_wallet(self.user, order.selling_currency)
        assert wallet.blocked_balance == order.amount if is_sell else order.total_price

    def _test_successful_stop_loss_order_add(
        self, amount, stop_price, is_sell=False, is_market=False, price=None, expected_price=None, serialized_price=None
    ):
        self.charge_wallet(
            currency=self.market.src_currency if is_sell else self.market.dst_currency,
            amount=Decimal(amount) * (1 if is_sell else Decimal(price or stop_price))
        )
        data = self.add_stop_loss_order(amount, stop_price, is_sell, is_market, price)
        assert data['status'] == 'ok'
        self.check_successful_stop_loss_order_response(
            data.get('order'),
            expected_price=serialized_price,
            amount=amount,
            stop_price=stop_price,
            is_sell=is_sell,
            is_market=is_market,
        )
        self.check_successful_stop_loss_order_database(
            order_id=data['order']['id'],
            expected_price=expected_price,
            amount=amount,
            stop_price=stop_price,
            is_sell=is_sell,
            is_market=is_market,
        )

    def _test_unsuccessful_stop_loss_order_add(
        self, amount, stop_price, is_sell=False, is_market=False, price=None, error_code=None
    ):
        data = self.add_stop_loss_order(amount, stop_price, is_sell, is_market, price)
        assert data['status'] == 'failed'
        assert data['code'] == error_code

    def test_stop_market_sell_order_add(self):
        self._test_successful_stop_loss_order_add(
            is_sell=True,
            is_market=True,
            amount='0.3',
            stop_price='41000',
            expected_price='41000',
            serialized_price='market',
        )

    def test_stop_market_buy_order_add(self):
        self._test_successful_stop_loss_order_add(
            is_sell=False,
            is_market=True,
            amount='0.3',
            stop_price='43000',
            expected_price='43000',
            serialized_price='market',
        )

    def test_stop_limit_sell_order_add(self):
        self._test_successful_stop_loss_order_add(
            is_sell=True,
            amount='0.3',
            stop_price='41000',
            price='41100',
            expected_price='41100',
            serialized_price='41100',
        )

    def test_stop_limit_buy_order_add(self):
        self._test_successful_stop_loss_order_add(
            is_sell=False,
            amount='0.3',
            stop_price='43000',
            price='43200',
            expected_price='43200',
            serialized_price='43200',
        )

    def test_stop_market_sell_order_add_with_guard_price(self):
        self._test_successful_stop_loss_order_add(
            is_sell=True,
            is_market=True,
            amount='0.3',
            stop_price='41000',
            price='40800',
            expected_price='40800',
            serialized_price='market',
        )

    def test_stop_market_buy_order_add_with_guard_price(self):
        self._test_successful_stop_loss_order_add(
            is_sell=False,
            is_market=True,
            amount='0.3',
            stop_price='43000',
            price='43400',
            expected_price='43400',
            serialized_price='market',
        )

    def test_stop_market_sell_order_add_with_invalid_guard_price(self):
        self._test_unsuccessful_stop_loss_order_add(
            is_sell=True,
            is_market=True,
            amount='0.3',
            stop_price='41000',
            price='41200',
            error_code='BadPrice',
        )

    def test_stop_market_buy_order_add_with_invalid_guard_price(self):
        self._test_unsuccessful_stop_loss_order_add(
            is_sell=False,
            is_market=True,
            amount='0.3',
            stop_price='43000',
            price='42800',
            error_code='BadPrice',
        )

    def test_stop_market_order_add_with_insufficient_balance(self):
        self._test_unsuccessful_stop_loss_order_add(
            is_sell=True,
            is_market=True,
            amount='0.3',
            stop_price='41000',
            error_code='OverValueOrder',
        )

    def test_stop_limit_order_add_with_insufficient_balance(self):
        self._test_unsuccessful_stop_loss_order_add(
            is_sell=False,
            amount='0.3',
            stop_price='43000',
            price='43300',
            error_code='OverValueOrder',
        )

    def test_stop_limit_order_block_amount_for_further_order_add(self):
        self.create_order(balance=Decimal('0.4'), amount='0.3', price='41000', stop='41000')
        # Ordinary limit trade on same wallet property
        response = self.client.post('/market/orders/add', {
            'type': 'sell',
            'execution': 'limit',
            'amount': '0.2',
            'price': '42500',
            'srcCurrency': 'btc',
            'dstCurrency': 'usdt',
        })
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == 'OverValueOrder'

    def test_stop_loss_order_cancel(self):
        order = self.create_order(amount='0.3', price='41000', stop='41000')
        response = self.client.post('/market/orders/update-status', {
            'order': order.id,
            'status': 'canceled',
        })
        data = response.json()
        assert data['status'] == 'ok'
        assert data['updatedStatus'] == 'Canceled'
        order.refresh_from_db()
        assert order.status == Order.STATUS.canceled

    def test_stop_loss_order_list(self):
        orders = [
            self.create_order(amount='0.3', price='41000', stop='41000', sell=True),
            self.create_order(amount='0.5', price='42000', sell=False),
            self.create_order(amount='0.2', price='43500', stop='43000', sell=False, market=True),
            self.create_order(amount='0.2', price='42500', sell=True, market=True),
        ]
        order_ids = [o.id for o in orders]
        response = self.client.get('/market/orders/list', {'details': 2})
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['orders']) == 4
        for order_data in data['orders']:
            assert order_data['id'] in order_ids
