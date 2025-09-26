from exchange.margin.models import Position
from exchange.market.models import Order

LEADER_WINRATE_CACHE_KEY = 'social_trade_leader_winrate_%s_%s'


EXECUTION_TYPE_TRANSLATION = {
    Order.EXECUTION_TYPES.limit: 'لیمیت',
    Order.EXECUTION_TYPES.market: 'مارکت',
    Order.EXECUTION_TYPES.stop_limit: 'حد ضرر',
    Order.EXECUTION_TYPES.stop_market: 'حد ضرر',
    'oco': 'OCO',
}

TRADE_TYPE_TRANSLATION = {
    Order.TRADE_TYPES.spot: 'اسپات',
    Order.TRADE_TYPES.margin: 'تعهدی',
}

POSITION_STATUS_TRANSLATION = {
    Position.STATUS.new: 'جدید',
    Position.STATUS.open: 'باز',
    Position.STATUS.closed: 'بسته',
    Position.STATUS.canceled: 'کنسل',
    Position.STATUS.liquidated: 'لیکویید',
    Position.STATUS.expired: 'منقضی',
}
