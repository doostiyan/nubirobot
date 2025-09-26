from exchange.base.calendar import ir_today
from exchange.base.serializers import register_serializer
from exchange.base.models import get_currency_codename
from .models import FeeDiscount, UserDiscount, Discount, DiscountTransactionLog


@register_serializer(model=FeeDiscount)
def serialize_fee_discount(obj, opts=None):
    return {
        'discountedFee': obj.discounted_fee,
        'description': obj.description,
    }


@register_serializer(model=UserDiscount)
def serialize_user_discount(obj, opts=None):
    user_discount = {
        'id': obj.id,
        'name': obj.discount.name,
        'currency': get_currency_codename(obj.discount.currency) if obj.discount.currency else 'all',
        'amount': obj.discount.amount_rls,
        'percent': obj.discount.percent,
        'remainAmount':  (obj.discount.amount_rls - obj.received_amount),
        'activationDate': obj.activation_date,
        'endDate': obj.end_date,
        'isActive': bool(obj.discount.status == Discount.STATUS.active) if obj.end_date >= ir_today() else False,
        'status': obj.get_user_status(),
        'receivedAmount': obj.received_amount,
        'tradeTypes': obj.discount.trade_types,
    }
    return user_discount


def serialize_discount_trades(obj, user_id):
    if obj.buyer_id == user_id:
        trade_type = 'buy'
        fee_amount = obj.get_buy_fee_amount()
    else:
        trade_type = 'sell'
        fee_amount = obj.get_sell_fee_amount()

    serialized_trade = {
        'srcCurrency': get_currency_codename(obj.market.src_currency),
        'dstCurrency': get_currency_codename(obj.market.dst_currency),
        'timestamp': obj.created_at,
        'market': obj.market.market_display,
        'price': obj.matched_price,
        'amount': obj.matched_amount,
        'total': obj.matched_total_price,
        'type': trade_type,
        'fee': fee_amount,
    }
    if obj.rial_value is not None:
        serialized_trade.update({'totalRLS': obj.rial_value})

    return serialized_trade


@register_serializer(model=DiscountTransactionLog)
def serialize_discount_transaction_log(obj, opts=None):
    return {
        'id': obj.id,
        'amount': obj.amount,
        'date': obj.created_at,
    }
