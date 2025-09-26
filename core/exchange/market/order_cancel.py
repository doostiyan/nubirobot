from typing import Iterable, List, Optional, Tuple

from django.db.models import Case, F, IntegerField, Q, When

from exchange.market.models import Order, OrderMatching

from ..base.publisher import OrderPublishManager, private_order_publisher
from .functions import post_process_updated_margin_orders
from .ws_serializers import serialize_order_for_user

CANCEL_ORDER_BATCH_SIZE = 20


def _cancel_orders(
    order_ids: Iterable[int],
    user_id: Optional[int] = None,
) -> Tuple[Optional[List], Optional[List]]:
    """
    Shared helper to cancel orders (`user_id` is optional).
    Returns (orders_queryset, order_ids_changed).
    """
    status_list = Order.OPEN_STATUSES

    base_query = Order.objects.filter(
        Q(id__in=order_ids) | Q(pair__in=order_ids, pair__status__in=status_list),
    )

    if user_id is not None:
        base_query = base_query.filter(user_id=user_id)

    filter_orders = (
        base_query.filter(
            status__in=status_list,
            trade_type__in=(Order.TRADE_TYPES.spot, Order.TRADE_TYPES.margin),
        )
        .exclude(channel__range=Order.CHANNEL_SYSTEM_RANGE)
        .in_bulk()
    )

    Order.objects.filter(id__in=filter_orders, status__in=status_list).update(status=Order.STATUS.canceled)

    post_process_updated_margin_orders(filter_orders.values())

    if user_id is not None:
        orders = Order.objects.filter(user_id=user_id, id__in=order_ids)
    else:
        orders = Order.objects.filter(id__in=order_ids)

    if filter_orders:
        canceled_orders = Order.objects.filter(id__in=filter_orders.keys()).select_related('user')

        sell_order_ids = [o.id for o in canceled_orders if o.is_sell]
        buy_order_ids = [o.id for o in canceled_orders if o.is_buy]

        trade_qs = (
            OrderMatching.objects.filter(Q(sell_order_id__in=sell_order_ids) | Q(buy_order_id__in=buy_order_ids))
            .annotate(
                order_id=Case(
                    When(sell_order_id__in=sell_order_ids, then=F("sell_order_id")),
                    When(buy_order_id__in=buy_order_ids, then=F("buy_order_id")),
                    output_field=IntegerField(),
                )
            )
            .order_by("order_id", "-id")
            .distinct("order_id")
        )

        trades = {trade.order_id: trade for trade in trade_qs}

        order_publish_manager = OrderPublishManager()

        for order in canceled_orders:
            order: Order
            last_trade = trades.get(order.id)
            order_publish_manager.add_order(order, last_trade, order.user.uid)

        order_publish_manager.publish()

    return orders, filter_orders.keys()


def cancel_batch_of_orders(user_id: int, order_ids: Iterable[int]):
    """
    Cancel a batch of orders for specified user (batch size = 20)
    """
    return _cancel_orders(order_ids=order_ids, user_id=user_id)


def bulk_cancel_orders(order_ids: Iterable[int]):
    """
    Cancel a list of orders in bulk.
    """
    return _cancel_orders(order_ids=order_ids)
