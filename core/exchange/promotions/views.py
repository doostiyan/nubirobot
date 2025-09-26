from django_ratelimit.decorators import ratelimit

from exchange.base.api_v2 import api, post_api
from exchange.base.calendar import ir_today
from exchange.base.helpers import paginate
from exchange.base.parsers import parse_int
from exchange.promotions.discount import (
    get_active_user_discount,
    get_history_discount_transaction_log,
    get_history_trades_for_user_discount,
    get_user_discount_history,
)
from exchange.promotions.exceptions import DiscountTransactionLogDoesNotExist, UserDiscountDoesNotExist
from exchange.promotions.serializers import serialize_discount_trades


@ratelimit(key='user_or_ip', rate='50/1h', block=True)
@api
def get_user_discount_history_api(request):
    user_discounts = get_user_discount_history(request.user.id)
    user_discounts, has_next = paginate(user_discounts, page_size=50, request=request, check_next=True)
    return {
        'status': 'ok',
        'hasNext': has_next,
        'discounts': user_discounts
    }


@ratelimit(key='user_or_ip', rate='50/1h', block=True)
@api
def get_active_user_discount_api(request):
    user_discount = get_active_user_discount(request.user.id, ir_today(), get_remain_amount=True)
    if user_discount is None:
        return {
            'status': 'failed',
            'message': 'There is no active discount existed for this user.',
            'code': 'ActiveDiscountDoesNotExist'
        }
    return {
        'status': 'ok',
        'discount': user_discount
    }


@ratelimit(key='user_or_ip', rate='50/1h', block=True)
@post_api
def get_history_trades_for_user_discount_api(request):
    user_id = request.user.id
    discount_transaction_log_id = parse_int(request.g('transactionLogId'), required=True)
    try:
        trades = get_history_trades_for_user_discount(user_id, discount_transaction_log_id)
    except DiscountTransactionLogDoesNotExist:
        return {
            'status': 'failed',
            'message': 'There is no transaction log existed for this user.',
            'code': 'DiscountTransactionLogDoesNotExist'
        }
    return {
        'status': 'ok',
        'trades': [serialize_discount_trades(trade, user_id) for trade in trades]
    }


@ratelimit(key='user_or_ip', rate='50/1h', block=True)
@post_api
def get_history_discount_transaction_log_api(request):
    user_discount_id = parse_int(request.g('userDiscountId'), required=True)
    try:
        discount_transaction_logs = get_history_discount_transaction_log(request.user.id, user_discount_id)
    except UserDiscountDoesNotExist:
        return {
            'status': 'failed',
            'code': 'UserDiscountDoesNotExist',
            'message': 'user discount does not exist.',
        }
    return {
        'status': 'ok',
        'transactions': discount_transaction_logs,
    }
