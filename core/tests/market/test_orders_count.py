from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.market.models import Order
from exchange.wallet.models import Wallet
from tests.margin.test_positions import PositionTestMixin
from tests.market.test_order import OrderAPITestMixin


class OrdersCountTest(APITestCase):
    def _test_orders_count(self, count: int, trade_type: str = '') -> None:
        data = {'tradeType': trade_type}
        response = self.client.get('/market/orders/open-count', data=data)
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert result['count'] == count

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)

    def setUp(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    @staticmethod
    def _create_order(
        user,
        order_type=Order.ORDER_TYPES.sell,
        execution_type=Order.EXECUTION_TYPES.limit,
        trade_type=Order.TRADE_TYPES.margin,
        amount='0.001',
        order_status=Order.STATUS.active,
        channel=Order.CHANNEL.unknown,
    ):
        if not user:
            return
        Order.objects.create(
            user_id=user.id,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            order_type=order_type,
            execution_type=execution_type,
            trade_type=trade_type,
            amount=amount,
            price='27100',
            status=order_status,
            channel=channel,
        ),

    def test_orders_count(self):
        self._test_orders_count(0, 'margin')
        self._create_order(self.user)
        self._test_orders_count(1, 'margin')

        self._test_orders_count(0, 'spot')
        self._create_order(self.user, trade_type=Order.TRADE_TYPES.spot)
        self._test_orders_count(1, 'spot')

        self._test_orders_count(2)

    def test_orders_count_margin_with_other_status(self):
        self._test_orders_count(0, 'margin')
        self._create_order(self.user)
        self._test_orders_count(1, 'margin')

        self._create_order(self.user, order_status=Order.STATUS.new)
        self._create_order(self.user, order_status=Order.STATUS.done)
        self._create_order(self.user, order_status=Order.STATUS.canceled)
        self._test_orders_count(1, 'margin')

    def test_orders_count_spot_with_other_status(self):
        self._test_orders_count(0, 'spot')
        self._create_order(self.user, trade_type=Order.TRADE_TYPES.spot)
        self._test_orders_count(1, 'spot')

        self._create_order(self.user, order_status=Order.STATUS.new, trade_type=Order.TRADE_TYPES.spot)
        self._create_order(self.user, order_status=Order.STATUS.done, trade_type=Order.TRADE_TYPES.spot)
        self._create_order(self.user, order_status=Order.STATUS.canceled, trade_type=Order.TRADE_TYPES.spot)
        self._test_orders_count(1, 'spot')

    def test_orders_count_with_other_trade_type(self):
        self._test_orders_count(0)
        self._create_order(self.user)
        self._create_order(self.user, trade_type=Order.TRADE_TYPES.spot)
        self._test_orders_count(2)
        self._test_orders_count(1, trade_type='margin')
        self._test_orders_count(1, trade_type='spot')

    def test_orders_count_margin_with_other_execution_type(self):
        self._test_orders_count(0)
        count = 1
        for order_exec, _ in Order.EXECUTION_TYPES:
            self._create_order(self.user, execution_type=order_exec)
            self._test_orders_count(count, trade_type='margin')
            count += 1

    def test_orders_count_spot_with_other_execution_type(self):
        self._test_orders_count(0, 'spot')
        count = 1
        for order_exec, _ in Order.EXECUTION_TYPES:
            self._create_order(self.user, execution_type=order_exec, trade_type=Order.TRADE_TYPES.spot)
            self._test_orders_count(count, trade_type='spot')
            count += 1

    def test_orders_count_with_ghost_orders(self):
        self._test_orders_count(0)
        self._create_order(self.user, trade_type=Order.TRADE_TYPES.spot, channel=Order.CHANNEL.system_block)
        self._test_orders_count(0)
        self._test_orders_count(0, 'spot')


class MarginOrderCountAPITest(PositionTestMixin, OrderAPITestMixin, APITestCase):
    def _test_orders_count(self, count: int, trade_type: str = 'margin') -> None:
        data = {'tradeType': trade_type}
        response = self.client.get('/market/orders/open-count', data=data)
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert result['count'] == count

    def _add_margin_order(self, **order_params):
        request_data = {'srcCurrency': 'btc', 'dstCurrency': 'usdt', 'mode': 'oco', **order_params}
        response = self.client.post('/margin/orders/add', request_data)
        assert response.status_code == status.HTTP_200_OK

    def test_margin_order_count_oco_sell(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=45).commit()
        self._add_margin_order(
            type='sell', amount='0.002', is_oco=True, price='22000', stopPrice='20000', stopLimitPrice='20100'
        )
        self._test_orders_count(1)
        all_orders = Order.objects.all()
        assert len(all_orders) == 2

    def test_margin_order_count_oco_buy(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        wallet.create_transaction(tp='manual', amount=45).commit()
        self._add_margin_order(
            type='buy', amount='0.0018', is_oco=True, price='21000', stopPrice='22000', stopLimitPrice='22100'
        )
        self._test_orders_count(1)
        all_orders = Order.objects.all()
        assert len(all_orders) == 2
