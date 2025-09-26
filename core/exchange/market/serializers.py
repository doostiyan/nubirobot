from decimal import Decimal

from exchange.base.models import get_currency_codename
from exchange.base.serializers import register_serializer

from .models import Order, OrderMatching, UserTradeStatus


@register_serializer(model=Order)
def serialize_order(order, opts):
    _user = opts.get('user') or order.user
    level = opts.get('level', 1)
    data = {
        'type': 'buy' if order.is_buy else 'sell',
        'execution': order.get_execution_type_display(),
        'tradeType': order.get_trade_type_display(),
        'srcCurrency': order.get_src_currency_display(),
        'dstCurrency': order.get_dst_currency_display(),
        'price': 'market' if order.is_market else order.price,
        'amount': order.amount,
        'totalPrice': order.matched_total_price,
        'totalOrderPrice': order.total_price,
        'matchedAmount': order.matched_amount,
        'unmatchedAmount': order.unmatched_amount,
        'clientOrderId': order.client_order_id,
    }
    if order.param1 is not None:
        data['param1'] = order.param1
    if order.pair_id is not None:
        data['pairId'] = order.pair_id
    if order.is_margin:
        data['leverage'] = order.leverage
        data['side'] = 'open' if order.side == order.order_type else 'close'
    if level >= 2:
        data['id'] = order.pk
        data['status'] = order.get_status_display()
        data['partial'] = order.is_partial
        data['fee'] = order.fee
        data['user'] = _user.username if _user else None
        data['created_at'] = order.created_at
        data['market'] = order.market_display
        data['averagePrice'] = order.average_price
    if level >= 3:
        data['srcCurrency'] = get_currency_codename(order.src_currency)
        data['dstCurrency'] = get_currency_codename(order.dst_currency)
        del data['market'], data['user']
    return data


@register_serializer(model=OrderMatching)
def serialize_trade(trade, opts):
    # TODO: document the meaning and use of these two parameters
    market = opts.get('market', True)
    user = opts.get('user')
    get_id = opts.get('get_id')
    get_order_id = opts.get('get_order_id')
    specified_trade_type = opts.get('trade_type')

    if specified_trade_type:
        trade_type = specified_trade_type
    elif market:
        trade_type = 'sell' if trade.is_market_sell else 'buy'
    else:
        trade_type = 'sell' if trade.seller_id == user.id else 'buy'
    if trade_type == 'sell':
        fee_amount = trade.get_sell_fee_amount()
    else:
        fee_amount = trade.get_buy_fee_amount()
    serialized_trade = {
        'srcCurrency': trade.market.get_src_currency_display(),
        'dstCurrency': trade.market.get_dst_currency_display(),
        'timestamp': trade.created_at,
        'market': trade.market.market_display,
        'price': trade.matched_price,
        'amount': trade.matched_amount,
        'total': trade.matched_total_price,
        'type': trade_type,
        'fee': fee_amount,
    }
    if get_id:
        serialized_trade['id'] = trade.id
    if get_order_id:
        order_id = trade.sell_order_id if trade_type == 'sell' else trade.buy_order_id
        serialized_trade['orderId'] = order_id

    return serialized_trade


@register_serializer(model=UserTradeStatus)
def serialize_user_trade_status(tradeStats, opts):
    data = {
        'monthTradesTotal': tradeStats.month_trades_total,
        'monthTradesCount': tradeStats.month_trades_count,
    }
    if tradeStats.month_trades_total_trader > Decimal('0'):
        data['monthTradesTotalTrader'] = tradeStats.month_trades_total_trader
    return data
