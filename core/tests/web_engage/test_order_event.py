from decimal import Decimal
from typing import Optional
from unittest import mock

from rest_framework.test import APITestCase, override_settings

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
from exchange.margin.models import Position
from exchange.market.models import Market, Order
from exchange.pool.models import LiquidityPool
from exchange.wallet.models import Wallet
from tests.base.utils import do_matching_round


class OrderMatchingEventTest(APITestCase):
    def setUp(self) -> None:
        self.src_market = Currencies.btc
        self.dst_market = Currencies.usdt
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        self.price = Decimal(10)
        self.amount = 10
        self._charge_wallet(self.user1, self.dst_market, Decimal(100))
        self._charge_wallet(self.user2, self.src_market, Decimal(100))
        self._charge_wallet(self.user2, Currencies.rls, 10000000, Wallet.WALLET_TYPE.margin)
        self.pool_btc = self._create_pool(
            currency=Currencies.btc,
            capacity=2,
            manager_id=410,
            is_active=True,
            is_private=True,
        )

    def _create_pool(
        self,
        currency: int,
        manager_id: int,
        capacity=Decimal(10000),
        filled_capacity=Decimal(0),
        *,
        is_active=True,
        is_private=False,
        min_available_ratio: Decimal = Decimal('0.2'),
    ) -> 'LiquidityPool':
        pool = LiquidityPool.objects.create(
            currency=currency,
            capacity=capacity,
            filled_capacity=filled_capacity,
            manager_id=manager_id,
            is_active=is_active,
            is_private=is_private,
            min_available_ratio=min_available_ratio,
            activated_at=ir_now(),
        )
        self._charge_wallet(manager_id, Currencies.btc, 100, Wallet.WALLET_TYPE.spot)

        return pool

    def _create_position(
        self,
        user: User,
        price: Decimal,
        amount: Decimal = Decimal(1),
        src: Optional[int] = None,
        dst: Optional[int] = None,
    ):
        order = Order.objects.create(
            user=user,
            src_currency=src,
            dst_currency=dst,
            amount=amount,
            price=price,
            order_type=Order.ORDER_TYPES.sell,
            trade_type=Order.TRADE_TYPES.margin,
            status=Order.STATUS.active,
        )
        position = Position.objects.create(
            user_id=user.pk,
            src_currency=src,
            dst_currency=dst,
            side=Position.SIDES.sell,
            leverage=Decimal(2),
            collateral=amount * price,
        )
        position.orders.add(order, through_defaults={'blocked_collateral': amount * price})

    def _charge_wallet(self, user, currency: int, initial_balance: int = 10, tp=Wallet.WALLET_TYPE.spot) -> Wallet:
        wallet = Wallet.get_user_wallet(user, currency, tp)
        wallet.create_transaction('manual', initial_balance).commit()
        wallet.refresh_from_db()
        return wallet

    def _create_match(self):
        Order.objects.create(
            user=self.user1,
            src_currency=self.src_market,
            dst_currency=self.dst_market,
            amount=self.amount,
            price=self.price,
            order_type=Order.ORDER_TYPES.buy,
            trade_type=Order.TRADE_TYPES.spot,
            status=Order.STATUS.active,
        )
        do_matching_round(Market.get_for(self.src_market, self.dst_market))

    @mock.patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=True)
    @mock.patch('exchange.web_engage.events.base.is_webengage_user', return_value=True)
    @mock.patch('exchange.web_engage.events.base.task_send_event_data_to_web_engage.delay')
    def test_check_order_event_sent(self, task_send_event_data_to_web_engage: mock.MagicMock, mock2, mock3):
        self._create_position(self.user2, self.amount, self.price, src=self.src_market, dst=self.dst_market)
        self._create_match()
        assert task_send_event_data_to_web_engage.called

    @mock.patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=True)
    @mock.patch('exchange.web_engage.events.base.is_webengage_user', return_value=True)
    @mock.patch('exchange.web_engage.events.base.task_send_event_data_to_web_engage.delay')
    def test_check_order_event_not_sent_when_in_black_list(
        self,
        task_send_event_data_to_web_engage: mock.MagicMock,
        mock2,
        mock3,
    ):
        Settings.objects.create(key="webengage_stopped_events", value="""["order_matched"]""")
        self._create_position(self.user2, self.amount, self.price, src=self.src_market, dst=self.dst_market)
        self._create_match()
        assert not task_send_event_data_to_web_engage.called
