import datetime
import functools
from typing import List

from django.conf import settings
from django.db.models.aggregates import Sum
from django.db.models.functions import Coalesce
from user_agents import parse

from exchange.accounts.models import Notification, User
from exchange.base.calendar import ir_now, to_shamsi_date
from exchange.base.constants import ZERO
from exchange.base.models import XCHANGE_TESTING_CURRENCIES, Currencies, get_currency_codename
from exchange.features.utils import is_feature_enabled
from exchange.xchange.constants import USER_AGENT_MAP
from exchange.xchange.models import ExchangeTrade, MarketLimitation, MarketStatus
from exchange.xchange.types import ConsumedPercentageOfMarket, Quote


@functools.lru_cache(maxsize=1)
def get_market_maker_system_user() -> User:
    return User.objects.get(username=settings.XCHANGE_MARKET_MAKER_USERNAME)


@functools.lru_cache(maxsize=1)
def get_small_assets_convert_system_user() -> User:
    return User.objects.get(username=settings.XCHANGE_SMALL_ASSETS_CONVERT_USERNAME)

def get_exchange_trade_kwargs_from_quote(quote: Quote):
    return {
        'is_sell': quote.is_sell,
        'src_currency': quote.base_currency,
        'dst_currency': quote.quote_currency,
        'src_amount': quote.base_amount,
        'dst_amount': quote.quote_amount,
        'quote_id': quote.quote_id,
        'client_order_id': quote.client_order_id,
    }

def notify_admin_on_market_status_change(changed_statuses: List[dict]):
    current_time = to_shamsi_date(ir_now())
    notification_message = f'تغییر وضعیت بازارها در {current_time} : \n'

    for status_change in changed_statuses:
        new_market, old_market = status_change['new_market'], status_change['old_market']
        market_symbol = (
            f'{get_currency_codename(old_market.base_currency).upper()}'
            f'{get_currency_codename(old_market.quote_currency).upper()}'
        )
        notification_message += (
            f'{market_symbol}: {old_market.get_status_display()} -> {new_market.get_status_display()}\n'
        )

    Notification.notify_admins(
        message=notification_message,
        title='هشدار تغییر وضعیت بازارها 🔔',
        channel='important_xchange',
    )

def calculate_market_consumption_percentage() -> List[ConsumedPercentageOfMarket]:
    """
    Calculates the consumed percentage of markets based on active market limitations.

    Returns:
        List[ConsumedPercentageOfMarket]: A list of market consumption percentages.
    """
    consumed_percentages = []
    active_limitations = MarketLimitation.objects.filter(
        limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE, is_active=True
    ).select_related('market')

    current_time = ir_now()

    for limitation in active_limitations:
        # Determine the appropriate amount field based on market currencies(in the usdtrls market usdt is base_currency)
        amount_field = (
            'src_amount'
            if (
                limitation.market.base_currency == Currencies.usdt
                and limitation.market.quote_currency == Currencies.rls
            )
            else 'dst_amount'
        )

        # Calculate the start time for the trade filter
        trade_start_time = current_time - datetime.timedelta(hours=limitation.interval)

        # Sum trades matching the filter criteria
        total_traded_amount = (
            ExchangeTrade.objects.filter(
                src_currency=limitation.market.base_currency,
                dst_currency=limitation.market.quote_currency,
                created_at__gte=trade_start_time,
                is_sell=limitation.is_sell,
            )
            .exclude(status=ExchangeTrade.STATUS.failed)
            .aggregate(total=Coalesce(Sum(amount_field), ZERO))['total']
        )

        # Calculate consumption percentage
        consumption_percentage = (total_traded_amount / limitation.max_amount) * 100

        market_symbol = (
            f'{get_currency_codename(limitation.market.base_currency).upper()}'
            f'{get_currency_codename(limitation.market.quote_currency).upper()}'
        )

        consumed_percentages.append(
            ConsumedPercentageOfMarket(
                percentage=consumption_percentage, symbol=market_symbol, is_sell=limitation.is_sell
            )
        )

    return consumed_percentages

def detect_user_agent(request):
    ua = request.META.get('HTTP_USER_AGENT') or ''
    slash_ind = ua.find('/')
    category_lower = ua[:slash_ind].lower() if slash_ind >= 0 else ''
    if category_lower == 'mozilla':
        browser = parse(ua).browser.family
        user_agent = USER_AGENT_MAP.get(browser.lower(), ExchangeTrade.USER_AGENT.mozilla)
    elif category_lower == 'android':
        # It's Android, so check the X_APP_MODE header
        android_type = request.META.get('HTTP_X_APP_MODE', '').lower()
        user_agent = USER_AGENT_MAP['android'].get(android_type, USER_AGENT_MAP['android']['default'])
    else:
        user_agent = USER_AGENT_MAP.get(category_lower, ExchangeTrade.USER_AGENT.unknown)
    return user_agent


def has_user_beta_market_feature_flag(user: User) -> bool:
    return user.is_authenticated and is_feature_enabled(user, 'new_coins')


def has_market_access(market: MarketStatus, user: User) -> bool:
    if market.base_currency not in XCHANGE_TESTING_CURRENCIES:
        return True
    return has_user_beta_market_feature_flag(user)
