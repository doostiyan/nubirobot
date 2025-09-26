from decimal import Decimal
from functools import partial
from typing import Dict, List, Optional

from exchange.base.models import Currencies, get_currency_codename
from exchange.base.money import quantize_number
from exchange.base.serializers import normalize_number, register_serializer, serialize, serialize_decimal
from exchange.margin.models import Position
from exchange.socialtrade.enums import WinratePeriods
from exchange.socialtrade.leaders.trades import LeaderTradesData
from exchange.socialtrade.models import Leader, LeadershipRequest, SocialTradeAvatar, SocialTradeSubscription

ORDER_FIELDS = {
    'type',
    'execution',
    'tradeType',
    'srcCurrency',
    'dstCurrency',
    'price',
    'amount',
    'totalPrice',
    'totalOrderPrice',
    'matchedAmount',
    'unmatchedAmount',
    'param1',
    'pairId',
    'leverage',
    'side',
    'status',
    'created_at',
    'averagePrice',
}


POSITION_FIELDS = {
    'createdAt',
    'side',
    'srcCurrency',
    'dstCurrency',
    'status',
    'marginType',
    'collateral',
    'leverage',
    'openedAt',
    'closedAt',
    'liquidationPrice',
    'entryPrice',
    'exitPrice',
    'extensionFee',
    'delegatedAmount',
    'liability',
    'totalAsset',
    'marginRatio',
    'liabilityInOrder',
    'assetInOrder',
    'unrealizedPNL',
    'unrealizedPNLPercent',
    'expirationDate',
    'PNL',
    'PNLPercent',
}


def serialize_decimal_with_precision(amount: Decimal, precision: Decimal) -> str:
    amount = quantize_number(amount, precision=precision)
    return normalize_number(amount or 0)  # Using or to fix -0


def serialize_money(fee: Decimal, currency: int) -> str:
    if currency != Currencies.rls:
        opts = {
            'symbol': f'{get_currency_codename(currency).upper()}IRT',
        }
        return serialize_decimal(fee, opts)
    return serialize_decimal_with_precision(fee, Decimal('1'))


@register_serializer(model=SocialTradeAvatar)
def serialize_avatar(avatar: SocialTradeAvatar, opts):
    return {
        'id': avatar.pk,
        'image': avatar.image.url,
    }


@register_serializer(model=LeadershipRequest)
def serialize_leadership_request(leadership_request: LeadershipRequest, opts):
    return {
        'id': leadership_request.pk,
        'nickname': leadership_request.nickname,
        'avatar': leadership_request.avatar,
        'subscriptionFee': serialize_money(
            leadership_request.subscription_fee, leadership_request.subscription_currency
        ),
        'subscriptionCurrency': get_currency_codename(leadership_request.subscription_currency),
        'createdAt': leadership_request.created_at,
        'lastUpdate': leadership_request.updated_at,
        'status': leadership_request.get_status_display(),
        'reason': leadership_request.reason,
    }


@register_serializer(model=SocialTradeSubscription)
def serialize_subscription(subscription: SocialTradeSubscription, opts):
    return {
        'id': subscription.pk,
        'createdAt': subscription.created_at,
        'subscriptionCurrency': get_currency_codename(subscription.fee_currency),
        'subscriptionFee': serialize_money(subscription.fee_amount, subscription.fee_currency),
        'isTrial': subscription.is_trial,
        'startsAt': subscription.starts_at,
        'expiresAt': subscription.expires_at,
        'canceledAt': subscription.canceled_at,
        'isAutoRenewalEnabled': subscription.is_auto_renewal_enabled,
        'isNotifEnabled': subscription.is_notif_enabled,
        'leader': subscription.leader,
    }


serialize_portfo_decimal = partial(serialize_decimal_with_precision, precision=Decimal('1e-3'))


def serialize_portfo(daily_portfos: list) -> List[dict]:
    if not daily_portfos:
        return []

    serialized_portfo = []
    for daily_portfo in daily_portfos:
        serialized_portfo.append(
            {
                'reportDate': daily_portfo['report_date'],
                'profitPercentage': daily_portfo['profit_percentage'],
                'cumulativeProfitPercentage': daily_portfo['cumulative_profit_percentage'],
            }
        )
    return serialized_portfo


def serialize_asset_ratios(asset_ratios: dict) -> dict:
    return {get_currency_codename(currency): asset_ratios[currency] for currency in asset_ratios}


@register_serializer(model=Leader)
def serialize_leader(leader: Leader, opts):
    opts = opts or {}
    data = {
        'id': leader.pk,
        'createdAt': leader.created_at,
        'subscriptionCurrency': get_currency_codename(leader.subscription_currency),
        'subscriptionFee': serialize_money(leader.subscription_fee, leader.subscription_currency),
        'nickname': leader.nickname,
        'avatar': leader.avatar,
        'winrate7': leader.get_winrate(WinratePeriods.WEEK),
        'winrate30': leader.get_winrate(WinratePeriods.MONTH),
        'winrate90': leader.get_winrate(WinratePeriods.MONTH_3),
        'lastMonthProfitPercentage': leader.last_month_profit_percentage,
    }

    if not opts.get('private') and hasattr(leader, 'is_trial_available'):
        data.update({'isTrialAvailable': leader.is_trial_available})

    if not opts.get('private') and hasattr(leader, 'is_subscribed'):
        data.update({'isSubscribed': leader.is_subscribed})

    if hasattr(leader, 'number_of_subscribers'):
        data.update({'numberOfSubscribers': leader.number_of_subscribers})

    if hasattr(leader, 'last_month_trade_volume'):
        data.update({'lastMonthTradeVolume': leader.last_month_trade_volume})

    if opts.get('private') and hasattr(leader, 'number_of_unsubscribes'):
        data.update({'numberOfUnsubscribes': leader.number_of_unsubscribes})

    if opts.get('private'):
        data.update(
            {'gainedSubscriptionFees': serialize_money(leader.gained_subscription_fees, leader.subscription_currency)}
        )

    if opts.get('profile_serialization'):
        data.update(
            {
                'assetRatios': serialize_asset_ratios(leader.asset_ratios),
                'dailyProfits': serialize_portfo(leader.daily_profits),
            }
        )

    return data


def serialize_orders(orders):
    list_orders = []
    for order in orders:
        dict_order = serialize(order, opts={'level': 2})
        filtered_order = {k: v for k, v in dict_order.items() if k in ORDER_FIELDS}
        filtered_order['createdAt'] = filtered_order['created_at']
        filtered_order['market'] = order.market_display
        list_orders.append(filtered_order)
    return list_orders


def serialize_positions(positions: List[Position], leaders: Optional[Dict[int, int]] = None):
    list_positions = []
    for position in positions:
        dict_position = serialize(position, {})
        dict_position = {k: v for k, v in dict_position.items() if k in POSITION_FIELDS}
        dict_position['closeSideOrders'] = serialize_orders(position.close_side_orders)
        if leaders:
            dict_position['leaderId'] = leaders[position.user_id]
        list_positions.append(dict_position)
    return list_positions


@register_serializer(model=LeaderTradesData)
def serialize_leader_trades_data(leader_trades_data: LeaderTradesData, opts):
    return {
        'orders': serialize_orders(leader_trades_data.orders),
        'positions': serialize_positions(leader_trades_data.positions),
    }
