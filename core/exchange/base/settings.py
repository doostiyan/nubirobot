from decimal import Decimal

from django.core.cache import cache

from exchange.base.models import RIAL, Settings, get_currency_codename, get_currency_codename_binance


class NobitexSettings:
    @classmethod
    def get_system_usd_price(cls, tp='avg') -> int:
        """Return USDT-IRR conversion rate based on system settings."""
        if tp == 'avg':
            cache_key = 'settings_usd_value_avg'
            avg_price = cache.get(cache_key)
            if not avg_price:
                usd_value = Settings.get_dict('usd_value')
                avg_price = (usd_value.get('sell', 0) + usd_value.get('buy', 0)) / 2
                avg_price = round(avg_price)
                cache.set(cache_key, avg_price, 300)
            return avg_price
        if tp in ['buy', 'sell']:
            return round(Settings.get_dict('usd_value').get(tp) or 0)
        return 0

    @classmethod
    def get_binance_price(cls, currency, default=None):
        prices_binance = cache.get('binance_prices') or {}
        price = prices_binance.get(get_currency_codename_binance(currency), default)
        if price is None:
            return price
        return Decimal(price)

    @classmethod
    def get_nobitex_usdt_price(cls, currency):
        currency = get_currency_codename(currency).upper()
        usdt_price = cache.get(f'orderbook_{currency}USDT_best_buy') or Decimal('0')
        return usdt_price

    @classmethod
    def get_nobitex_irr_price(cls, currency):
        if currency == RIAL:
            return Decimal('1')
        currency = get_currency_codename(currency).upper()
        irr_price = cache.get(f'orderbook_{currency}IRT_best_buy') or Decimal('0')
        return irr_price


class Flags:
    @classmethod
    def is_enabled(cls, feature):
        return True
