from typing import TYPE_CHECKING

from django.utils import timezone

from exchange.base.models import get_currency_codename
from exchange.base.serializers import serialize, serialize_decimal, serialize_timestamp

if TYPE_CHECKING:
    from exchange.market.models import Order, OrderMatching

def serialize_trade_for_user(trade, user_id: int):
    trade_type = 'sell' if trade.seller_id == user_id else 'buy'

    if trade_type == 'sell':
        fee_amount = trade.get_sell_fee_amount()
    else:
        fee_amount = trade.get_buy_fee_amount()

    order_id = trade.sell_order_id if trade_type == 'sell' else trade.buy_order_id

    serialized_trade = {
        'timestamp': trade.created_at,
        'srcCurrency': get_currency_codename(trade.market.src_currency),
        'dstCurrency': get_currency_codename(trade.market.dst_currency),
        'price': serialize_decimal(trade.matched_price),
        'amount': serialize_decimal(trade.matched_amount),
        'total': serialize_decimal(trade.matched_total_price),
        'type': trade_type,
        'fee': serialize_decimal(fee_amount),
        'id': trade.id,
        'orderId': order_id,
    }

    return serialized_trade


def serialize_order_for_user(order: 'Order', last_trade: 'OrderMatching'):
    data = {
        'orderId': order.id,
        'tradeId': last_trade.id if last_trade else None,
        'clientOrderId': order.client_order_id,
        'srcCurrency': get_currency_codename(order.src_currency),
        'dstCurrency': get_currency_codename(order.dst_currency),
        'eventTime': serialize_timestamp(timezone.now()),
        'lastFillTime': serialize_timestamp(last_trade.created_at) if last_trade else None,
        'side': order.get_order_type_display(),
        'status': order.get_status_display(),
        'fee': order.fee,
        'price': None if order.is_market else order.price,
        'avgFilledPrice': order.average_price if last_trade else None,
        'tradePrice': last_trade.matched_price if last_trade else None,
        'amount': order.amount,
        'tradeAmount': last_trade.matched_amount if last_trade else None,
        'filledAmount': order.matched_amount,
        'param1': order.param1,
        'orderType': order.get_execution_type_display(),
        'marketType': order.get_trade_type_display(),
    }

    return serialize(data)


def serialize_rejected_order_for_user(data):
    data = {'eventTime': serialize_timestamp(timezone.now()), **data}
    data['status'] = 'Failed'
    return data
