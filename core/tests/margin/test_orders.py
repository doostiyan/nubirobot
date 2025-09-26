from typing import Optional
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies, Settings
from exchange.margin.models import Position
from exchange.margin.services import MarginManager
from exchange.market.models import Order
from tests.market.test_order import OrderTestMixin


class PositionOrderCancelTest(OrderTestMixin, APITestCase):
    MARKET_SYMBOL = 'BTCUSDT'

    position: Position
    order: Order

    @classmethod
    def setUpTestData(cls):
        super(PositionOrderCancelTest, cls).setUpTestData()
        cls.position = Position.objects.create(
            user=cls.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            status=Position.STATUS.open,
        )
        cls.order = cls.create_order(amount='0.001', price='21300')
        cls.order.trade_type = Order.TRADE_TYPES.margin
        cls.order.save(update_fields=('trade_type',))
        cls.position.orders.add(cls.order, through_defaults={})

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _successful_order_cancel(self, order: Order):
        response = self.client.post('/market/orders/update-status', {
            'order': order.id, 'status': 'canceled'
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        order.refresh_from_db()
        assert order.status == Order.STATUS.canceled

    def _unsuccessful_order_cancel(self, order: Order):
        response = self.client.post('/market/orders/update-status', {
            'order': order.id, 'status': 'canceled'
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'failed'
        order.refresh_from_db()
        assert order.status != Order.STATUS.canceled

    def test_user_margin_order_cancel(self):
        self._successful_order_cancel(self.order)

    def test_system_settlement_margin_order_cancel(self):
        Order.objects.filter(pk=self.order.pk).update(matched_amount='0.001', matched_total_price='21')
        self.position.status = Position.STATUS.liquidated
        self.position.save(update_fields=('status',))

        Settings.set('liquidator_enabled_markets', '[]')
        MarginManager.settle_position_in_system(pid=self.position.id)
        order = self.position.orders.last()
        self._unsuccessful_order_cancel(order)


class MarginOrderListTest(APITestCase):
    orders: list

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.orders = [
            Order.objects.create(
                user_id=201,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                order_type=Order.ORDER_TYPES.sell,
                execution_type=Order.EXECUTION_TYPES.limit,
                trade_type=Order.TRADE_TYPES.spot,
                amount='0.0001',
                price='27100',
                status=Order.STATUS.active,
            ),
            Order.objects.create(
                user_id=202,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                order_type=Order.ORDER_TYPES.buy,
                execution_type=Order.EXECUTION_TYPES.limit,
                trade_type=Order.TRADE_TYPES.spot,
                amount='0.0001',
                price='27000',
                status=Order.STATUS.active,
            ),
            Order.objects.create(
                user_id=201,
                src_currency=Currencies.shib,
                dst_currency=Currencies.rls,
                order_type=Order.ORDER_TYPES.sell,
                execution_type=Order.EXECUTION_TYPES.limit,
                trade_type=Order.TRADE_TYPES.margin,
                amount='800',
                price='4_400_0',
                status=Order.STATUS.done,
            ),
            Order.objects.create(
                user_id=201,
                src_currency=Currencies.shib,
                dst_currency=Currencies.rls,
                order_type=Order.ORDER_TYPES.buy,
                execution_type=Order.EXECUTION_TYPES.stop_limit,
                trade_type=Order.TRADE_TYPES.margin,
                amount='801.2018027041',
                price='5_000_0',
                status=Order.STATUS.inactive,
            ),
            Order.objects.create(
                user_id=201,
                src_currency=Currencies.eth,
                dst_currency=Currencies.usdt,
                order_type=Order.ORDER_TYPES.buy,
                execution_type=Order.EXECUTION_TYPES.limit,
                trade_type=Order.TRADE_TYPES.margin,
                amount='0.01',
                price='1900',
                status=Order.STATUS.done,
            ),
            Order.objects.create(
                user_id=201,
                src_currency=Currencies.eth,
                dst_currency=Currencies.usdt,
                order_type=Order.ORDER_TYPES.sell,
                execution_type=Order.EXECUTION_TYPES.limit,
                trade_type=Order.TRADE_TYPES.margin,
                amount='0.006',
                price='1860',
                status=Order.STATUS.done,
            ),
            Order.objects.create(
                user_id=201,
                src_currency=Currencies.eth,
                dst_currency=Currencies.usdt,
                order_type=Order.ORDER_TYPES.sell,
                execution_type=Order.EXECUTION_TYPES.limit,
                trade_type=Order.TRADE_TYPES.margin,
                amount='0.00399',
                price='1840',
                status=Order.STATUS.active,
            ),
        ]
        positions = [
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.shib,
                dst_currency=Currencies.rls,
                side=Position.SIDES.sell,
                collateral='3_520_000_0',
                leverage=5,
            ),
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.eth,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.buy,
                collateral='3_520_000_0',
                leverage=3,
            ),
        ]
        positions[0].orders.set(cls.orders[2:4])
        positions[1].orders.set(cls.orders[4:7])

    def setUp(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _test_successful_orders_list(self, filters: Optional[dict] = None, has_next: bool = False):
        response = self.client.get('/market/orders/list', filters)
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert result['hasNext'] == has_next
        assert 'orders' in result
        return result['orders']

    def test_orders_list_all(self):
        orders = self._test_successful_orders_list({'status': 'all', 'details': '2'})
        assert len(orders) == 6
        assert orders[0]['id'] == self.orders[6].id
        assert orders[0]['leverage'] == '3'
        assert orders[0]['side'] == 'close'
        assert orders[1]['id'] == self.orders[5].id
        assert orders[1]['leverage'] == '3'
        assert orders[1]['side'] == 'close'
        assert orders[2]['id'] == self.orders[4].id
        assert orders[2]['leverage'] == '3'
        assert orders[2]['side'] == 'open'
        assert orders[3]['id'] == self.orders[3].id
        assert orders[3]['leverage'] == '5'
        assert orders[3]['side'] == 'close'
        assert orders[4]['id'] == self.orders[2].id
        assert orders[4]['leverage'] == '5'
        assert orders[4]['side'] == 'open'
        assert orders[5]['id'] == self.orders[0].id
        assert 'leverage' not in orders[5]

    def test_orders_list_spot(self):
        orders = self._test_successful_orders_list({'status': 'all', 'details': '2', 'tradeType': 'spot'})
        assert len(orders) == 1
        assert orders[0]['id'] == self.orders[0].id
        assert 'leverage' not in orders[0]

    def test_orders_list_margin(self):
        orders = self._test_successful_orders_list({'details': '2', 'tradeType': 'margin'})
        assert len(orders) == 2
        assert orders[0]['id'] == self.orders[6].id
        assert orders[0]['leverage'] == '3'
        assert orders[0]['side'] == 'close'
        assert orders[1]['id'] == self.orders[3].id
        assert orders[1]['leverage'] == '5'
        assert orders[1]['side'] == 'close'
