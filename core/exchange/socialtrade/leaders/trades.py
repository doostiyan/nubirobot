from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, List, Optional, Union

from django.db.models import F, Max, OuterRef, Q
from django.db.models.functions import Coalesce

from exchange.accounts.models import User
from exchange.base.calendar import ir_now, to_shamsi_date
from exchange.base.decorators import cached_method
from exchange.base.formatting import get_currency_unit
from exchange.margin.models import Position
from exchange.market.models import Order
from exchange.socialtrade.constants import TRADE_TYPE_TRANSLATION
from exchange.socialtrade.models import Leader, SocialTradeSubscription
from exchange.socialtrade.notifs import SocialTradeNotifs


@dataclass
class LeaderTradesData:
    orders: List[Order] = field(default_factory=list)
    positions: List[Position] = field(default_factory=list)


class LeaderTrades:
    def __init__(
        self,
        users: Union[Iterable[User], Iterable[int]],
        delay: timedelta,
        duration: timedelta,
        side: Optional[int] = None,
    ):
        self.users = users
        self.delay = delay
        self.duration = duration
        self.side = side

    @property
    def end_date(self):
        return ir_now() - self.delay

    @property
    def start_date(self):
        return ir_now() - (self.duration + self.delay)

    def get_orders(self):
        position_side_subquery = Position.objects.filter(id=OuterRef('position')).values('side')[:1]
        queryset = (
            Order.objects.filter(
                created_at__lte=self.end_date,
                created_at__gte=self.start_date,
                user__in=self.users,
                trade_type=Order.TRADE_TYPES.margin,
            )
            .annotate(position_side=position_side_subquery)
            .order_by('-created_at')
        )

        if self.side is not None:
            queryset = queryset.filter(order_type=self.side)

        return queryset

    def get_positions(self, is_closed=None, *, include_closed=True):
        datetime_q = Q(opened_at__lt=self.end_date, opened_at__gte=self.start_date)
        if include_closed:
            datetime_q |= Q(closed_at__lt=self.end_date, closed_at__gte=self.start_date)

        queryset = Position.objects.filter(
            datetime_q,
            user__in=self.users,
            status__in=(
                Position.STATUS.open,
                Position.STATUS.closed,
                Position.STATUS.liquidated,
                Position.STATUS.expired,
            )
            if is_closed is None
            else (Position.STATUS.open,)
            if is_closed is False
            else (Position.STATUS.closed, Position.STATUS.liquidated, Position.STATUS.expired),
        ).annotate(
            last_close_order_time=Max('orders__created_at', filter=~Q(orders__order_type=F('side'))),
        )
        if self.side is not None:
            queryset = queryset.filter(side=self.side)

        order_by = Coalesce('closed_at', 'last_close_order_time', 'opened_at', 'created_at')
        return queryset.order_by(order_by.desc()).distinct()

    def get_recent_trades(self, num_of_trades: int, *, include_closed=True) -> LeaderTradesData:
        orders = self.get_orders()[:num_of_trades]
        positions = self.get_positions(include_closed=include_closed)[:num_of_trades]
        return LeaderTradesData(orders=orders, positions=positions)


class LeaderTradesSender:
    def __init__(self, leaders_id: List[int], from_dt: datetime, to_dt: datetime):
        self.leaders = Leader.objects.filter(pk__in=leaders_id).in_bulk(field_name='user_id')
        self.from_dt = from_dt
        self.to_dt = to_dt
        self.delay = ir_now() - self.to_dt
        self.duration = self.to_dt - self.from_dt
        self.leader_trades = LeaderTrades(self.leaders.keys(), self.delay, self.duration)

    @cached_method(timeout=60)
    def get_subscribers(self, leader: Leader) -> List[int]:
        return list(
            SocialTradeSubscription.get_actives()
            .filter(leader=leader, is_notif_enabled=True)
            .values_list('subscriber_id', flat=True),
        )

    def send(self):
        self.send_orders()
        self.send_positions()

    def send_positions(self):
        for position in self.leader_trades.get_positions():
            leader = self.leaders[position.user_id]
            notif = SocialTradeNotifs.position_opened_notif
            data = dict(
                nickname=leader.nickname,
                trade_type=TRADE_TYPE_TRANSLATION[Order.TRADE_TYPES.margin],
                market=(
                    f'{get_currency_unit(position.src_currency, en=True)}'
                    f'-{get_currency_unit(position.dst_currency, en=True)}'
                ),
                sell_buy='خرید' if not position.is_short else 'فروش',
                timestamp=to_shamsi_date(position.opened_at),
            )

            if position.status == Position.STATUS.closed:
                notif = SocialTradeNotifs.position_closed_notif
                data.update(dict(timestamp=to_shamsi_date(position.closed_at)))

            if position.status == Position.STATUS.liquidated:
                notif = SocialTradeNotifs.position_liquidated_notif
                data.update(dict(timestamp=to_shamsi_date(ir_now())))

            notif.send_many(self.get_subscribers(leader), data=data)

    def send_orders(self):
        order_oco_pair = set()
        for order in self.leader_trades.get_orders():
            if order in order_oco_pair:
                continue

            leader = self.leaders[order.user_id]
            notif = SocialTradeNotifs.order_limit_market_notif
            data = dict(
                nickname=leader.nickname,
                open_close='باز کردن' if order.order_type == order.position_side else 'بستن',
                side='خرید' if order.position_side == Order.ORDER_TYPES.buy else 'فروش',
                market=order.market_display,
                timestamp=to_shamsi_date(order.created_at),
            )

            if order.pair:
                order_oco_pair.add(order.pair)

            notif.send_many(self.get_subscribers(leader), data=data)
