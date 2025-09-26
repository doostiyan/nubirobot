from django.core.cache import cache
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from exchange.accounts.models import Notification
from exchange.base.formatting import f_m
from exchange.base.models import XCHANGE_CURRENCIES, get_currency_codename
from exchange.base.strings import _t
from exchange.xchange.constants import XCHANGE_PAIR_PRICES_CACHE_KEY
from exchange.xchange.models import ExchangeTrade, MarketStatus
from exchange.xchange.types import XchangeCurrencyPairPrices


@receiver(pre_save, sender=ExchangeTrade, dispatch_uid='successful_xchange_trade_performed')
def successful_xchange_trade_performed(sender, instance, **kwargs):
    if instance.status != ExchangeTrade.STATUS.succeeded:
        return

    def send_new_successful_trade_notification(trade: ExchangeTrade) -> None:
        trade_type = 'فروش' if trade.is_sell else 'خرید'
        Notification.objects.create(
            user=trade.user,
            message=f'تبدیل انجام شد: '
            f'{trade_type} '
            f'{f_m(trade.src_amount, c=trade.src_currency, exact=True)} '
            f'{_t(get_currency_codename(trade.src_currency))}',
        )

    if instance.pk is None:  # newly-created successful trade
        send_new_successful_trade_notification(instance)
        return
    previously_saved_trade = ExchangeTrade.objects.filter(pk=instance.id).first()
    if previously_saved_trade and previously_saved_trade.status != ExchangeTrade.STATUS.succeeded:
        send_new_successful_trade_notification(instance)


@receiver(post_save, sender=MarketStatus, dispatch_uid='cache_xchange_prices')
def new_price_received(sender, instance, created, **kwargs):
    """
    Cache the xchange-only prices both ways (base_currency to quote_currency and the other way around)
    """
    if instance.base_currency in XCHANGE_CURRENCIES or instance.quote_currency in XCHANGE_CURRENCIES:
        base_to_quote_prices = XchangeCurrencyPairPrices(
            buy_price=instance.base_to_quote_price_buy,
            sell_price=instance.base_to_quote_price_sell,
        )
        quote_to_base_prices = XchangeCurrencyPairPrices(
            buy_price=instance.quote_to_base_price_buy,
            sell_price=instance.quote_to_base_price_sell,
        )
        cache.set(
            XCHANGE_PAIR_PRICES_CACHE_KEY.format(currency=instance.base_currency, to_currency=instance.quote_currency),
            vars(base_to_quote_prices),
        )
        cache.set(
            XCHANGE_PAIR_PRICES_CACHE_KEY.format(currency=instance.quote_currency, to_currency=instance.base_currency),
            vars(quote_to_base_prices),
        )

