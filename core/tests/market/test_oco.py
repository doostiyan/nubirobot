import random
from decimal import Decimal

from rest_framework.test import APITestCase

from exchange.base.helpers import get_max_db_value
from exchange.market.marketmanager import MarketManager
from exchange.market.models import Order
from exchange.wallet.models import Wallet

from .test_order import OrderAPITestMixin


class OCOOrderAPITest(OrderAPITestMixin, APITestCase):
    MARKET_SYMBOL = 'BTCUSDT'
    MARKET_PRICE = 42200

    def add_oco_order(self, amount, price, stop_price, stop_limit_price, is_sell=False):
        request_data = {
            'mode': 'oco',
            'type': 'sell' if is_sell else 'buy',
            'srcCurrency': 'btc',
            'dstCurrency': 'usdt',
            'amount': amount,
            'price': price,
            'stopPrice': stop_price,
            'stopLimitPrice': stop_limit_price,
            'clientOrderId': str(random.randint(1, 10**8))
        }
        response = self.client.post('/market/orders/add', request_data)
        return response.json()

    @staticmethod
    def check_successful_oco_order_response(orders_data, price, amount, stop_price, stop_limit_price, is_sell):
        order_type = 'sell' if is_sell else 'buy'
        assert orders_data
        assert len(orders_data) == 2
        assert orders_data[0]['id']
        assert orders_data[0]['execution'] == 'Limit'
        assert orders_data[0]['type'] == order_type
        assert orders_data[0]['status'] == 'Active'
        assert orders_data[0]['price'] == price
        assert orders_data[0]['amount'] == amount
        assert 'param1' not in orders_data[0]
        assert orders_data[0]['pairId'] == orders_data[1]['id']
        assert orders_data[1]['id']
        assert orders_data[1]['execution'] == 'StopLimit'
        assert orders_data[1]['type'] == order_type
        assert orders_data[1]['status'] == 'Inactive'
        assert orders_data[1]['price'] == stop_limit_price
        assert orders_data[1]['amount'] == amount
        assert orders_data[1]['param1'] == stop_price
        assert orders_data[1]['pairId'] == orders_data[0]['id']

    def check_successful_oco_order_database(
        self, order_ids, amount, price, stop_price, stop_limit_price, is_sell=False
    ):
        limit_order = Order.objects.filter(id__in=order_ids, execution_type=Order.EXECUTION_TYPES.limit).first()
        stop_order = Order.objects.filter(id__in=order_ids, execution_type=Order.EXECUTION_TYPES.stop_limit).first()
        for order in (stop_order, limit_order):
            assert order
            assert order.is_sell == is_sell
            assert order.amount == Decimal(amount)

        assert limit_order.status == Order.STATUS.active
        assert limit_order.price == Decimal(price)
        assert limit_order.param1 is None
        assert limit_order.pair_id == stop_order.id

        assert stop_order.status == Order.STATUS.inactive
        assert stop_order.price == Decimal(stop_limit_price)
        assert stop_order.param1 == Decimal(stop_price)
        assert stop_order.pair_id == limit_order.id

        wallet = Wallet.get_user_wallet(self.user, order.selling_currency)
        balance_to_block = Decimal(amount) if is_sell else max(limit_order.total_price, stop_order.total_price)
        assert wallet.blocked_balance == balance_to_block

    def _test_successful_oco_order_add(
        self, amount, price, stop_price, stop_limit_price, is_sell=False
    ):
        self.charge_wallet(
            currency=self.market.src_currency if is_sell else self.market.dst_currency,
            amount=Decimal(amount) * (1 if is_sell else max(Decimal(price), Decimal(stop_limit_price)))
        )
        data = self.add_oco_order(amount, price, stop_price, stop_limit_price, is_sell)
        assert data['status'] == 'ok'
        self.check_successful_oco_order_response(
            data.get('orders'),
            amount=amount,
            price=price,
            stop_price=stop_price,
            stop_limit_price=stop_limit_price,
            is_sell=is_sell,
        )
        self.check_successful_oco_order_database(
            order_ids=[order['id'] for order in data['orders']],
            amount=amount,
            price=price,
            stop_price=stop_price,
            stop_limit_price=stop_limit_price,
            is_sell=is_sell,
        )

    def _test_unsuccessful_oco_order_add(
        self, amount, price, stop_price, stop_limit_price, is_sell=False, error_code=None
    ):
        data = self.add_oco_order(amount, price, stop_price, stop_limit_price, is_sell)
        assert data['status'] == 'failed'
        assert data['code'] == error_code

        wallet = Wallet.get_user_wallet(self.user, self.market.src_currency if is_sell else self.market.dst_currency)
        assert not wallet.blocked_balance

    def create_oco_order(self, amount, price, stop_price, stop_limit_price, is_sell=False):
        limit_order = self.create_order(amount=amount, price=price, sell=is_sell)
        stop_order = self.create_order(
            amount=amount, price=stop_limit_price, stop=stop_price, pair=limit_order, sell=is_sell
        )
        return limit_order, stop_order

    def test_oco_sell_order_add(self):
        self._test_successful_oco_order_add(
            is_sell=True,
            amount='0.3',
            price='42700',
            stop_price='41000',
            stop_limit_price='41100',
        )

    def test_oco_buy_order_add(self):
        self._test_successful_oco_order_add(
            is_sell=False,
            amount='0.3',
            price='41800',
            stop_price='43000',
            stop_limit_price='43050',
        )

    def test_oco_sell_order_add_with_invalid_prices(self):
        self.charge_wallet(currency=self.market.src_currency, amount=Decimal('0.5'))
        for market_price in (None, self.MARKET_PRICE):
            self.set_market_price(market_price)
            # limit price < stop price
            self._test_unsuccessful_oco_order_add(
                is_sell=True,
                amount='0.3',
                price='42300',
                stop_price='43000',
                stop_limit_price='42100',
                error_code='PriceConditionFailed',
            )
            # limit price < stop limit price
            self._test_unsuccessful_oco_order_add(
                is_sell=True,
                amount='0.3',
                price='42400',
                stop_price='41600',
                stop_limit_price='42600',
                error_code='PriceConditionFailed',
            )
        # limit price < market price
        assert 42100 < self.MARKET_PRICE
        self._test_unsuccessful_oco_order_add(
            is_sell=True,
            amount='0.3',
            price='42100',
            stop_price='41000',
            stop_limit_price='41100',
            error_code='PriceConditionFailed',
        )
        # stop price > market price
        assert 42800 > self.MARKET_PRICE
        self._test_unsuccessful_oco_order_add(
            is_sell=True,
            amount='0.3',
            price='43100',
            stop_price='42800',
            stop_limit_price='427100',
            error_code='PriceConditionFailed',
        )

    def test_oco_buy_order_add_with_invalid_prices(self):
        self.charge_wallet(currency=self.market.dst_currency, amount=Decimal('13000'))
        for market_price in (None, self.MARKET_PRICE):
            self.set_market_price(market_price)
            # limit price > stop price
            self._test_unsuccessful_oco_order_add(
                is_sell=False,
                amount='0.3',
                price='43100',
                stop_price='42800',
                stop_limit_price='42800',
                error_code='PriceConditionFailed',
            )
            # limit price > stop limit price
            self._test_unsuccessful_oco_order_add(
                is_sell=False,
                amount='0.3',
                price='42100',
                stop_price='42400',
                stop_limit_price='42050',
                error_code='PriceConditionFailed',
            )
        # limit price > market price
        assert 42500 > self.MARKET_PRICE
        self._test_unsuccessful_oco_order_add(
            is_sell=False,
            amount='0.3',
            price='42500',
            stop_price='43000',
            stop_limit_price='43000',
            error_code='PriceConditionFailed',
        )
        # stop price < market price
        assert 42000 < self.MARKET_PRICE
        self._test_unsuccessful_oco_order_add(
            is_sell=False,
            amount='0.3',
            price='41400',
            stop_price='42000',
            stop_limit_price='42050',
            error_code='PriceConditionFailed',
        )

    def test_oco_sell_order_add_with_insufficient_balance(self):
        self._test_unsuccessful_oco_order_add(
            is_sell=True,
            amount='0.3',
            price='42500',
            stop_price='41100',
            stop_limit_price='41000',
            error_code='OverValueOrder',
        )

    def test_oco_buy_order_add_with_insufficient_balance_for_limit(self):
        self.charge_wallet(self.market.dst_currency, 12500)
        self._test_unsuccessful_oco_order_add(
            is_sell=False,
            amount='0.3',
            price='41800',  # requires $12,540
            stop_price='42600',
            stop_limit_price='42500',  # requires $12,750
            error_code='OverValueOrder',
        )

    def test_oco_buy_order_add_with_insufficient_balance_for_stop_loss(self):
        self.charge_wallet(self.market.dst_currency, 12550)
        self._test_unsuccessful_oco_order_add(
            is_sell=False,
            amount='0.3',
            price='41800',  # requires $12,540
            stop_price='42600',
            stop_limit_price='42000',  # requires $12,600
            error_code='OverValueOrder',
        )

    def _test_successful_oco_order_cancel(self, order):
        initial_status = order.status
        assert initial_status != Order.STATUS.canceled
        response = self.client.post('/market/orders/update-status', {'order': order.id, 'status': 'canceled'})
        data = response.json()
        assert data['status'] == 'ok'
        assert data['updatedStatus'] == 'Canceled'
        order.refresh_from_db()
        assert order.status == Order.STATUS.canceled

    def test_oco_limit_order_cancel(self):
        limit_order, stop_order = self.create_oco_order(
            amount='0.3', price='42300', stop_price='41850', stop_limit_price='41900', is_sell=True
        )
        self._test_successful_oco_order_cancel(limit_order)
        stop_order.refresh_from_db()
        assert stop_order.status == Order.STATUS.canceled

    def test_oco_stop_order_cancel(self):
        limit_order, stop_order = self.create_oco_order(
            amount='0.3', price='42100', stop_price='42550', stop_limit_price='42500', is_sell=False
        )
        self._test_successful_oco_order_cancel(stop_order)
        limit_order.refresh_from_db()
        assert limit_order.status == Order.STATUS.canceled

    def test_oco_order_cancel_when_pair_is_just_matched(self):
        limit_order, stop_order = self.create_oco_order(
            amount='0.3', price='42300', stop_price='41910', stop_limit_price='41900', is_sell=True
        )
        # cancel stop manually before limit OCO signal is executed
        Order.objects.filter(id=limit_order.id).update(matched_amount='0.1')
        self._test_successful_oco_order_cancel(stop_order)
        limit_order.refresh_from_db()
        assert limit_order.status == Order.STATUS.active

    def test_oco_order_cancel_by_cancel_all_old_active_orders(self):
        orders = self.create_oco_order(
            amount='0.3', price='42300', stop_price='41910', stop_limit_price='41900', is_sell=True
        )
        response = self.client.post('/market/orders/cancel-old', {'srcCurrency': 'btc', 'dstCurrency': 'usdt'})
        data = response.json()
        assert data['status'] == 'ok'
        for order in orders:
            order.refresh_from_db()
            assert order.status == Order.STATUS.canceled

    def _test_successful_oco_order_blocked_balance(self, src_blocked=None, dst_blocked=None):
        response = self.client.post('/v2/wallets', {'currencies': 'btc,usdt'})
        data = response.json()
        assert data['status'] == 'ok'
        assert 'wallets' in data
        if 'BTC' in data['wallets']:
            assert Decimal(data['wallets']['BTC']['blocked']) == Decimal(src_blocked or 0)
        else:
            assert not src_blocked
        if 'USDT' in data['wallets']:
            assert Decimal(data['wallets']['USDT']['blocked']) == Decimal(dst_blocked or 0)
        else:
            assert not dst_blocked

    def test_oco_sell_order_blocked_balance_on_creation(self):
        self.create_oco_order(amount='0.3', price='42300', stop_price='41910', stop_limit_price='41900', is_sell=True)
        self._test_successful_oco_order_blocked_balance(src_blocked='0.3')

    def test_oco_buy_order_blocked_balance_on_creation(self):
        self.create_oco_order(amount='0.3', price='42100', stop_price='42550', stop_limit_price='42500', is_sell=False)
        self._test_successful_oco_order_blocked_balance(dst_blocked='12750')

    def test_oco_order_blocked_balance_on_multiple_orders(self):
        self.create_oco_order(amount='0.3', price='42100', stop_price='42550', stop_limit_price='42500', is_sell=False)
        self.create_oco_order(amount='0.2', price='42150', stop_price='42550', stop_limit_price='42600', is_sell=False)
        self.create_oco_order(amount='0.3', price='42300', stop_price='41800', stop_limit_price='41810', is_sell=True)
        self.create_oco_order(amount='0.1', price='42250', stop_price='41700', stop_limit_price='41680', is_sell=True)
        self._test_successful_oco_order_blocked_balance(src_blocked='0.4',dst_blocked='21270')

    def test_oco_order_blocked_balance_on_limit_matched(self):
        limit_order, stop_order = self.create_oco_order(
            amount='0.3', price='42100', stop_price='42550', stop_limit_price='42500', is_sell=False
        )

        MarketManager.increase_order_matched_amount(limit_order, amount=Decimal('0.2'), price=Decimal('42100'))
        limit_order.save(update_fields=('status', 'matched_amount', 'matched_total_price', 'fee'))
        self._test_successful_oco_order_blocked_balance(dst_blocked='4210')

    def test_oco_order_blocked_balance_on_stop_matched(self):
        limit_order, stop_order = self.create_oco_order(
            amount='0.3', price='42350', stop_price='41700', stop_limit_price='41690', is_sell=True
        )
        stop_order.status = Order.STATUS.active
        stop_order.save(update_fields=('status',))
        MarketManager.increase_order_matched_amount(stop_order, amount=Decimal('0.2'), price=Decimal('41690'))
        stop_order.save(update_fields=('status', 'matched_amount', 'matched_total_price', 'fee'))
        self._test_successful_oco_order_blocked_balance(src_blocked='0.1')

    def test_oco_order_block_amount_for_further_order_add(self):
        self.charge_wallet(currency=self.market.src_currency, amount=Decimal('0.4'))
        data = self.add_oco_order(
            amount='0.3', price='42300', stop_price='41700', stop_limit_price='41650', is_sell=True
        )
        assert data['status'] == 'ok'
        # Ordinary limit trade on same wallet property
        response = self.client.post('/market/orders/add', {
            'type': 'sell',
            'execution': 'limit',
            'amount': '0.2',
            'price': '42400',
            'srcCurrency': 'btc',
            'dstCurrency': 'usdt',
        })
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == 'OverValueOrder'

    def test_stop_loss_order_list(self):
        orders = [
            *self.create_oco_order(
                amount='0.3', price='42100', stop_price='42550', stop_limit_price='42500', is_sell=False
            ),
            self.create_order(amount='0.5', price='43500', stop='43000', sell=False, market=True),
            *self.create_oco_order(
                amount='0.1', price='42250', stop_price='41700', stop_limit_price='41680', is_sell=True
            ),
            self.create_order(amount='0.4', price='42500', sell=True, market=True),
        ]
        order_ids = [o.id for o in orders]
        response = self.client.get('/market/orders/list', {'details': 2})
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['orders']) == 6
        for order_data in data['orders']:
            assert order_data['id'] in order_ids

    def test_oco_prices_out_of_bound(self):
        max_allowed_price_value = get_max_db_value(Order.price)  # noQA

        self._test_unsuccessful_oco_order_add(
            is_sell=True,
            amount='0.3',
            price=str(max_allowed_price_value * 100),
            stop_price='41600',
            stop_limit_price='42600',
            error_code='ParseError',
        )

        self._test_unsuccessful_oco_order_add(
            is_sell=True,
            amount='0.3',
            price='41600',
            stop_price=str(max_allowed_price_value * 100),
            stop_limit_price='42600',
            error_code='ParseError',
        )

        self._test_unsuccessful_oco_order_add(
            is_sell=True,
            amount='0.3',
            price='41600',
            stop_price='42600',
            stop_limit_price=str(max_allowed_price_value * 100),
            error_code='ParseError',
        )
