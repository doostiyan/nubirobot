import datetime
from decimal import Decimal

from django.conf import settings
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import as_ir_tz, ir_now
from exchange.base.models import Currencies, get_currency_codename
from exchange.base.serializers import serialize
from exchange.margin.models import Position
from exchange.market.models import Order
from exchange.socialtrade.leaders.trades import LeaderTrades
from exchange.socialtrade.models import SocialTradeSubscription
from tests.market.test_order import OrderTestMixin
from tests.socialtrade.helpers import SocialTradeBaseAPITest, SocialTradeTestDataMixin, to_dt_irantz


class LeaderPositionTest(OrderTestMixin, TestCase):
    MARKET_SYMBOL = 'BTCUSDT'

    def setUp(self) -> None:
        self.position = Position.objects.create(
            user=self.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            status=Position.STATUS.open,
            opened_at=ir_now(),
        )
        self.order = self.create_order(amount='0.001', price='21300')
        self.order.trade_type = Order.TRADE_TYPES.margin
        self.order.save(update_fields=('trade_type',))
        self.position.orders.add(self.order, through_defaults={})

    def test_get_all_position(self):
        leader_trade = LeaderTrades([self.user], datetime.timedelta(days=0), datetime.timedelta(days=30))
        orders = leader_trade.get_positions()
        assert orders.count() == 1

    def test_get_position_for_a_month_without_delay(self):
        duration_position = Position.objects.create(
            user=self.user,
            created_at=ir_now() - datetime.timedelta(days=50),
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            status=Position.STATUS.closed,
        )
        leader_trade = LeaderTrades([self.user], datetime.timedelta(days=0), datetime.timedelta(days=30))
        assert leader_trade.get_positions().filter(id=duration_position.id).count() == 0

    def test_get_position_with_delay(self):
        duration_position = Position.objects.create(
            user=self.user,
            created_at=ir_now(),
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            status=Position.STATUS.closed,
        )
        leader_trade = LeaderTrades([self.user], datetime.timedelta(days=1), datetime.timedelta(days=30))
        assert leader_trade.get_positions().filter(id=duration_position.id).count() == 0


class LeaderOrderTest(OrderTestMixin, TestCase):
    MARKET_SYMBOL = 'BTCUSDT'

    def setUp(self) -> None:
        self.user_2 = User.objects.get(id=202)
        self.position = Position.objects.create(
            user=self.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            status=Position.STATUS.open,
        )
        self.order = self.create_order(amount='0.001', price='21300')
        self.order.trade_type = Order.TRADE_TYPES.margin
        self.order.save(update_fields=('trade_type',))
        self.position.orders.add(self.order, through_defaults={})
        Order.objects.all().update(trade_type=Order.TRADE_TYPES.margin)

    def test_get_all_orders(self):
        leader_trade = LeaderTrades([self.user], datetime.timedelta(days=0), datetime.timedelta(days=30))
        orders = leader_trade.get_orders()
        assert orders.count() == 1
        leader_trade = LeaderTrades([self.user_2], datetime.timedelta(days=0), datetime.timedelta(days=30))
        orders = leader_trade.get_orders()
        assert orders.count() == 0

    def test_get_orders_for_a_month_without_delay(self):
        order = Order.objects.filter(user=self.user).first()
        order.created_at = ir_now() - datetime.timedelta(days=40)
        order.save()
        leader_trade = LeaderTrades([self.user], datetime.timedelta(days=0), datetime.timedelta(days=30))
        assert leader_trade.get_orders().filter(id=order.id).count() == 0

    def test_get_orders_with_delay(self):
        order = Order.objects.filter(user=self.user).first()
        order.created_at = ir_now()
        order.save()
        leader_trade = LeaderTrades([self.user], datetime.timedelta(days=1), datetime.timedelta(days=30))
        assert leader_trade.get_orders().filter(id=order.id).count() == 0


class LeaderTradesTest(SocialTradeTestDataMixin, TestCase):

    def setUp(self) -> None:
        super().create_test_data()
        super().setUp()
        self._create_trades()

    def test_get_recent_trades_for_subscribed_leaders(self):
        # There are 2 leaders, each leader has 4 orders, 4 positions, and 4 exchanges.
        # All the trades the subscribers can see, are the last 3 orders, the last 3 positions and the last 3 xchanges.
        # Of the above 18 total trades of both leaders, the 4 most recent ones are:
        #  4 recent orders, 4 recent positions, and 4 recent xchanges according to the timedeltas defined in setUp
        # See the comments of SocialTradeLeaderAndSubscribersTest
        delay = settings.SOCIAL_TRADE['delayWhenSubscribed']
        duration = settings.SOCIAL_TRADE['durationWhenSubscribed']
        leader_trades = LeaderTrades([leader.user for leader in self.leaders], delay, duration)
        recent_trades = leader_trades.get_recent_trades(4)

        assert len(recent_trades.orders) == 4
        for i, order in enumerate(recent_trades.orders):
            assert order.created_at == self.current_time - self.order_timedeltas[i // 2]

        assert len(recent_trades.positions) == 4
        for i, position in enumerate(recent_trades.positions):
            assert position.opened_at == self.current_time - self.position_timedeltas[i // 2]

    def test_get_recent_trades_for_not_subscribed_leaders(self):
        # There are 2 leaders, each leader has 4 orders, 4 positions, and 4 exchanges.
        # All the trades the normal users (!=subscribers) can see are:
        #  the second last order, the second last position, and the second last xchange of each leader.
        # Of the above 6 total trades of both leaders, all of them are the 4 most recent trades.
        # See the comments of SocialTradeLeaderAndSubscribersTest
        delay = settings.SOCIAL_TRADE['delayWhenUnsubscribed']
        duration = settings.SOCIAL_TRADE['durationWhenUnsubscribed']
        leader_trades = LeaderTrades([leader.user for leader in self.leaders], delay, duration)
        recent_trades = leader_trades.get_recent_trades(10)

        assert len(recent_trades.orders) == 2
        for i, order in enumerate(recent_trades.orders):
            assert order.created_at == self.current_time - self.order_timedeltas[i // 2 + 1]

        assert len(recent_trades.positions) == 2
        for i, position in enumerate(recent_trades.positions):
            assert position.opened_at == self.current_time - self.position_timedeltas[i // 2 + 1]


class LeaderTradeTestMixin:
    @classmethod
    def _check_order_output(cls, order: Order, dict_order):
        assert dict_order['srcCurrency'] == order.get_src_currency_display()
        assert dict_order['dstCurrency'] == order.get_dst_currency_display()
        assert dict_order['side'] == 'open' if order.side == order.order_type else 'close'
        assert dict_order['execution'] == order.get_execution_type_display()
        assert dict_order['tradeType'] == order.get_trade_type_display()
        assert dict_order['price'] == serialize(order.price)
        assert dict_order['status'] == order.get_status_display()
        assert dict_order['market'] == order.market_display
        assert dict_order['averagePrice'] == serialize(order.average_price)
        assert as_ir_tz(datetime.datetime.fromisoformat(dict_order['created_at'])) == order.created_at

    @classmethod
    def _check_position_output(cls, position: Position, dict_position):
        assert dict_position['closedAt'] == position.closed_at
        assert dict_position['dstCurrency'] == get_currency_codename(position.dst_currency)
        assert dict_position['entryPrice'] == position.entry_price
        assert dict_position['exitPrice'] == position.exit_price
        assert dict_position['leverage'] == str(position.leverage)
        assert dict_position['marginType'] == position.get_margin_type_display()
        assert as_ir_tz(datetime.datetime.fromisoformat(dict_position['openedAt'])) == position.opened_at
        assert dict_position['side'] == position.get_side_display().lower()
        assert dict_position['srcCurrency'] == get_currency_codename(position.src_currency)
        assert dict_position['status'] == position.get_status_display()
        assert as_ir_tz(datetime.datetime.fromisoformat(dict_position['createdAt'])) == position.created_at
        close_side_orders = [*position.close_side_orders]
        assert len(close_side_orders) == len([*position.close_side_orders])
        for i, order in enumerate(position.close_side_orders):
            cls._check_order_output(order, dict_position['closeSideOrders'][i])


class LeaderPositionsAPITest(LeaderTradeTestMixin, SocialTradeBaseAPITest):
    URL = '/social-trade/leaders/positions'

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.user_leader = User.objects.get(pk=203)
        self.leader = self.create_leader(user=self.user_leader)
        self.leader_2 = self.create_leader()

        self.subscription = SocialTradeSubscription.objects.create(
            leader=self.leader,
            subscriber=self.user,
            expires_at=ir_now() + datetime.timedelta(days=4),
            starts_at=ir_now(),
            is_trial=True,
            fee_amount=1000,
            fee_currency=2,
        )

        self.open_position = Position.objects.create(
            user=self.user_leader,
            opened_at=ir_now() - datetime.timedelta(days=5),
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            side=Position.SIDES.buy,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            entry_price='123',
            status=Position.STATUS.open,
        )

        position_close_side_order = Order.objects.create(
            user=self.leader.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            order_type=Order.ORDER_TYPES.sell,
            trade_type=Order.TRADE_TYPES.margin,
            execution_type=1,
            price=1000,
            amount=1000,
        )
        position_open_side_order = Order.objects.create(
            user=self.leader.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            order_type=Order.ORDER_TYPES.buy,
            trade_type=Order.TRADE_TYPES.margin,
            execution_type=1,
            price=1000,
            amount=1000,
        )
        self.open_position.orders.add(position_open_side_order, position_close_side_order)

        self.position_without_delay = Position.objects.create(
            user=self.user_leader,
            opened_at=ir_now(),
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            entry_price='123',
            exit_price='123.45',
            status=Position.STATUS.closed,
        )
        self.position_for_28_days_ago = Position.objects.create(
            user=self.user_leader,
            opened_at=ir_now() - datetime.timedelta(days=28),
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            entry_price='123.45',
            liquidation_price='455.45',
            status=Position.STATUS.liquidated,
        )

        # old (visible) position_for_non_subscriber_leader
        Position.objects.create(
            user=self.leader_2.user,
            opened_at=ir_now() - datetime.timedelta(days=10),
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            side=Position.SIDES.buy,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            entry_price='123',
            status=Position.STATUS.open,
        )

        # new (invisible) position_for_non_subscriber_leader
        self.position_for_non_subscriber_leader = Position.objects.create(
            user=self.leader_2.user,
            opened_at=ir_now() - datetime.timedelta(days=1),
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            side=Position.SIDES.buy,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            entry_price='123',
            status=Position.STATUS.open,
        )

    def test_get_positions_with_unsubscribe_user_successfully(self):
        other_user = User.objects.get(id=202)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {other_user.auth_token.key}')
        response = self.client.get(path=self.URL + f'?leaderId={self.leader.id}')
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 1
        assert not response.json()['hasNext']
        self._check_position_output(self.open_position, output['positions'][0])
        assert output['positions'][0]['leaderId'] == self.leader.id

    def test_get_positions_with_subscribe_user_successfully(self):
        response = self.client.get(path=self.URL + f'?leaderId={self.leader.id}')
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 3
        assert not response.json()['hasNext']

    def test_get_positions_without_leader_filter(self):
        # Should return only subscribed leaders positions
        response = self.client.get(path=self.URL)
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 3
        assert not response.json()['hasNext']
        for position in output['positions']:
            assert position['leaderId'] == self.leader.id

    def test_get_positions_with_non_subscribed_leader(self):
        response = self.client.get(path=self.URL + f'?leaderId={self.leader_2.id}')
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 1
        assert not response.json()['hasNext']
        self._check_position_output(self.position_for_non_subscriber_leader, output['positions'][0])

    def test_get_positions_with_invalid_leader_id_fail(self):
        response = self.client.get(path=self.URL + '?leaderId=10000')
        assert response.status_code == 404
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'NotFound'
        assert response.json()['message'] == 'Leader does not exist'

    def test_get_positions_when_unsubscribe_leader(self):
        response = self.client.get(path=self.URL + f'?leaderId={self.leader.id}')
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 3

        self.subscription.unsubscribe()
        response = self.client.get(path=self.URL + f'?leaderId={self.leader.id}')
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 1

    def test_get_trade_when_leader_deleted_for_subscribers(self):
        self.subscription.is_trial = False
        self.subscription.save()
        self.leader.delete_leader(1)
        response = self.client.get(self.URL + f'?leaderId={self.leader.id}')
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 3
        assert not response.json()['hasNext']

    def test_get_trade_when_leader_deleted_for_non_subscribers(self):
        self.subscription.canceled_at = ir_now()
        self.subscription.save()
        self.leader.delete_leader(1)
        response = self.client.get(self.URL + f'?leaderId={self.leader.id}')
        assert response.status_code == 404
        assert response.json() == {
            'code': 'NotFound',
            'message': 'Leader does not exist',
            'status': 'failed',
        }

    def test_get_positions_with_inactive_leader(self):
        inactive_leader = self.create_leader()
        inactive_leader.activates_at = ir_now() + datetime.timedelta(minutes=1)
        inactive_leader.save()

        response = self.client.get(self.URL + f'?leaderId={self.leader.id}')
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 3
        assert not response.json()['hasNext']

    def test_get_positions_side_filter(self):
        response = self.client.get(path=self.URL + '?side=buy')
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 1

        response = self.client.get(path=self.URL + '?side=sell')
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 2

    def test_get_positions_invalid_side_filter(self):
        response = self.client.get(path=self.URL + '?side=invalid-side')
        assert response.status_code == 400
        assert response.json() == {
            'code': 'ParseError',
            'message': 'Invalid choices: "invalid-side"',
            'status': 'failed',
        }

    def test_get_positions_is_closed_filter(self):
        response = self.client.get(path=self.URL + '?isClosed=true')
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 2

        response = self.client.get(path=self.URL + '?isClosed=false')
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 1

    def test_get_positions_invalid_is_closed_filter(self):
        response = self.client.get(path=self.URL + '?isClosed=invalid-bool')
        assert response.status_code == 400
        assert response.json() == {
            'code': 'ParseError',
            'message': 'Invalid boolean value: "invalid-bool"',
            'status': 'failed',
        }


class LeaderPositionsOrderingAPITest(LeaderTradeTestMixin, SocialTradeBaseAPITest):
    URL = '/social-trade/leaders/positions'

    @staticmethod
    def create_position(user, opened_at=None, closed_at=None, last_close_order_at=None):
        position = Position.objects.create(
            user=user,
            opened_at=opened_at,
            closed_at=closed_at,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            side=Position.SIDES.buy,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            entry_price='123',
            status=Position.STATUS.open,
        )
        if last_close_order_at:
            order = Order.objects.create(
                user=user,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                order_type=Order.ORDER_TYPES.sell,
                trade_type=Order.TRADE_TYPES.margin,
                execution_type=1,
                price=1000,
                amount=1000,
            )
            order.created_at = last_close_order_at
            order.save(update_fields=('created_at',))
            position.orders.add(order)

        return position

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.user_leader = User.objects.get(pk=203)
        self.leader = self.create_leader(user=self.user_leader)

        self.subscription = SocialTradeSubscription.objects.create(
            leader=self.leader,
            subscriber=self.user,
            expires_at=ir_now() + datetime.timedelta(days=4),
            starts_at=ir_now(),
            is_trial=True,
            fee_amount=1000,
            fee_currency=2,
        )

    def test_positions_order_1(self):
        user = self.leader.user
        open_position_without_order = self.create_position(
            user,
            opened_at=ir_now() - datetime.timedelta(days=5),
        )

        open_position_with_close_order = self.create_position(
            user,
            opened_at=ir_now() - datetime.timedelta(days=6),
            last_close_order_at=ir_now() - datetime.timedelta(days=3),
        )

        closed_position = self.create_position(
            user,
            opened_at=ir_now() - datetime.timedelta(days=7),
            closed_at=ir_now() - datetime.timedelta(days=2),
        )

        response = self.client.get(path=self.URL)
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 3
        assert to_dt_irantz(output['positions'][0]['openedAt']) == closed_position.opened_at
        assert to_dt_irantz(output['positions'][1]['openedAt']) == open_position_with_close_order.opened_at
        assert to_dt_irantz(output['positions'][2]['openedAt']) == open_position_without_order.opened_at

    def test_positions_order_2(self):
        user = self.leader.user
        open_position_without_order = self.create_position(
            user,
            opened_at=ir_now() - datetime.timedelta(days=5),
        )

        open_position_with_close_order = self.create_position(
            user,
            opened_at=ir_now() - datetime.timedelta(days=6),
            last_close_order_at=ir_now() - datetime.timedelta(days=99),
        )

        closed_position = self.create_position(
            user,
            opened_at=ir_now() - datetime.timedelta(days=11),
            closed_at=ir_now() - datetime.timedelta(days=10),
        )

        response = self.client.get(path=self.URL)
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 3
        assert to_dt_irantz(output['positions'][0]['openedAt']) == open_position_without_order.opened_at
        assert to_dt_irantz(output['positions'][1]['openedAt']) == closed_position.opened_at
        assert to_dt_irantz(output['positions'][2]['openedAt']) == open_position_with_close_order.opened_at

    def test_positions_order_3(self):
        user = self.leader.user
        open_position_without_order1 = self.create_position(
            user,
            opened_at=ir_now() - datetime.timedelta(days=5),
        )
        open_position_without_order2 = self.create_position(
            user,
            opened_at=ir_now() - datetime.timedelta(days=11),
        )
        open_position_with_close_order1 = self.create_position(
            user,
            opened_at=ir_now() - datetime.timedelta(days=6),
            last_close_order_at=ir_now() - datetime.timedelta(days=8),
        )
        open_position_with_close_order2 = self.create_position(
            user,
            opened_at=ir_now() - datetime.timedelta(days=7),
            last_close_order_at=ir_now() - datetime.timedelta(days=9),
        )
        closed_position1 = self.create_position(
            user,
            opened_at=ir_now() - datetime.timedelta(days=11),
            closed_at=ir_now() - datetime.timedelta(days=1),
        )
        closed_position2 = self.create_position(
            user,
            opened_at=ir_now() - datetime.timedelta(days=10),
            closed_at=ir_now() - datetime.timedelta(days=10),
        )

        response = self.client.get(path=self.URL)
        assert response.status_code == 200
        output = response.json()
        assert len(output['positions']) == 6
        assert to_dt_irantz(output['positions'][0]['openedAt']) == closed_position1.opened_at
        assert to_dt_irantz(output['positions'][1]['openedAt']) == open_position_without_order1.opened_at
        assert to_dt_irantz(output['positions'][2]['openedAt']) == open_position_with_close_order1.opened_at
        assert to_dt_irantz(output['positions'][3]['openedAt']) == open_position_with_close_order2.opened_at
        assert to_dt_irantz(output['positions'][4]['openedAt']) == closed_position2.opened_at
        assert to_dt_irantz(output['positions'][5]['openedAt']) == open_position_without_order2.opened_at


class LeaderOrdersAPITest(LeaderTradeTestMixin, SocialTradeBaseAPITest):
    URL = '/social-trade/leaders/{leader_id}/orders'

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.user_leader = User.objects.get(pk=203)
        self.leader = self.create_leader(user=self.user_leader)
        self.subscription = SocialTradeSubscription.objects.create(
            leader=self.leader,
            subscriber=self.user,
            expires_at=ir_now() + datetime.timedelta(days=4),
            starts_at=ir_now(),
            is_trial=True,
            fee_amount=Decimal(1000),
            fee_currency=2,
        )

        self.order = Order.objects.create(
            user=self.leader.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            order_type=Order.ORDER_TYPES.sell,
            trade_type=Order.TRADE_TYPES.margin,
            execution_type=1,
            price=Decimal(1000),
            amount=Decimal(1000),
        )
        self.order.created_at = ir_now() - datetime.timedelta(days=5)
        self.order.save()

        self.order_without_delay = Order.objects.create(
            user=self.leader.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            order_type=Order.ORDER_TYPES.sell,
            trade_type=Order.TRADE_TYPES.margin,
            execution_type=1,
            price=Decimal(1000),
            amount=Decimal(1000),
        )
        self.order_without_delay2 = Order.objects.create(
            user=self.leader.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            order_type=Order.ORDER_TYPES.buy,
            trade_type=Order.TRADE_TYPES.margin,
            execution_type=1,
            price=Decimal(1000),
            amount=Decimal(1000),
        )
        self.order_without_delay3 = Order.objects.create(
            user=self.leader.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            order_type=Order.ORDER_TYPES.sell,
            trade_type=Order.TRADE_TYPES.margin,
            execution_type=1,
            price=Decimal(1000),
            amount=Decimal(1000),
        )
        self.order_for_28_days_ago = Order.objects.create(
            user=self.leader.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            order_type=Order.ORDER_TYPES.sell,
            trade_type=Order.TRADE_TYPES.margin,
            execution_type=1,
            price=Decimal(1000),
            amount=Decimal(1000),
        )
        self.order_for_28_days_ago.created_at = ir_now() - datetime.timedelta(days=28)
        self.order_for_28_days_ago.save()

        # Non-Margin order
        Order.objects.create(
            user=self.leader.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            order_type=1,
            trade_type=Order.TRADE_TYPES.spot,
            execution_type=1,
            price=Decimal(1000),
            amount=Decimal(1000),
        )

    def test_get_orders_with_unsubscribe_user_successfully(self):
        other_user = User.objects.get(id=202)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {other_user.auth_token.key}')
        response = self.client.get(path=self.URL.format(leader_id=self.leader.id))
        assert response.status_code == 200
        output = response.json()
        assert len(output['orders']) == 1
        assert not response.json()['hasNext']
        self._check_order_output(self.order, output['orders'][0])

    def test_get_orders_with_subscribe_user_successfully(self):
        response = self.client.get(path=self.URL.format(leader_id=self.leader.id))
        assert response.status_code == 200
        output = response.json()
        assert len(output['orders']) == 5
        assert not response.json()['hasNext']

    def test_get_orders_with_invalid_leader_id_fail(self):
        response = self.client.get(path=self.URL.format(leader_id=10000))
        assert response.status_code == 404
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'NotFound'
        assert response.json()['message'] == 'Leader does not exist'

    def test_get_orders_when_unsubscribe_leader(self):
        response = self.client.get(path=self.URL.format(leader_id=self.leader.id))
        assert response.status_code == 200
        output = response.json()
        assert len(output['orders']) == 5

        self.subscription.unsubscribe()
        response = self.client.get(path=self.URL.format(leader_id=self.leader.id))
        assert response.status_code == 200
        output = response.json()
        assert len(output['orders']) == 1

    def test_get_trade_when_leader_deleted_for_subscribers(self):
        self.subscription.is_trial = False
        self.subscription.save()
        self.leader.delete_leader(1)
        response = self.client.get(self.URL.format(leader_id=self.leader.id))
        assert response.status_code == 200
        output = response.json()
        assert len(output['orders']) == 5
        assert not response.json()['hasNext']

    def test_get_trade_when_leader_deleted_for_non_subscribers(self):
        self.subscription.canceled_at = ir_now()
        self.subscription.save()
        self.leader.delete_leader(1)
        response = self.client.get(self.URL.format(leader_id=self.leader.id))
        assert response.status_code == 404
        assert response.json() == {
            'code': 'NotFound',
            'message': 'Leader does not exist',
            'status': 'failed',
        }

    def test_get_orders_with_inactive_leader(self):
        inactive_leader = self.create_leader()
        inactive_leader.activates_at = ir_now() + datetime.timedelta(minutes=1)
        inactive_leader.save()

        response = self.client.get(self.URL.format(leader_id=self.leader.id))
        assert response.status_code == 200
        output = response.json()
        assert len(output['orders']) == 5
        assert not response.json()['hasNext']

    def test_get_orders_side_filter(self):
        response = self.client.get(path=self.URL.format(leader_id=self.leader.id) + '?side=buy')
        assert response.status_code == 200
        output = response.json()
        assert len(output['orders']) == 1

        response = self.client.get(path=self.URL.format(leader_id=self.leader.id) + '?side=sell')
        assert response.status_code == 200
        output = response.json()
        assert len(output['orders']) == 4

    def test_get_orders_invalid_side_filter(self):
        response = self.client.get(path=self.URL.format(leader_id=self.leader.id) + '?side=invalid-side')
        assert response.status_code == 400
        assert response.json() == {
            'code': 'ParseError',
            'message': 'Invalid choices: "invalid-side"',
            'status': 'failed',
        }
