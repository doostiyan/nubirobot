import datetime
from decimal import Decimal

from django.conf import settings
from django.utils.timezone import now

from exchange.base.logging import report_event
from exchange.base.models import Settings, get_currency_codename


# TODO: REMOVE CLASS AND MOVE 'get_crypto_price' somewhere else
class ExchangeConnectionManager:

    @classmethod
    def get_crypto_price(cls, currency, market='binance'):
        # Check prices to be up to date
        nw = now()
        min_last_update = nw - datetime.timedelta(hours=12)
        if market.startswith('binance'):
            last_update_spot = Settings.get_datetime('prices_binance_last_update', min_last_update)
            last_update_futures = Settings.get_datetime('prices_binance_futures_last_update', min_last_update)
            update_treshold = datetime.timedelta(minutes=2)
            if not settings.IS_PROD:
                update_treshold *= 100
            is_update_spot = nw - last_update_spot < update_treshold
            is_update_futures = nw - last_update_futures < update_treshold
            # Some exchanges usually have similar prices and can be swapped
            if market == 'binance' and not is_update_spot and is_update_futures:
                market = 'binance-futures'
            if market == 'binance-futures' and not is_update_futures and is_update_spot:
                market = 'binance'
            # Check last update
            if market == 'binance' and not is_update_spot:
                report_event('PriceNotUpdateBinance')
                return Decimal('0')
            if market == 'binance-futures' and not is_update_futures:
                report_event('PriceNotUpdateBinanceFutures')
                return Decimal('0')

        # Return symbol price
        currency_name = get_currency_codename(currency).lower()
        if market == 'kraken':
            return Settings.get_decimal('value_{}_usd'.format(currency_name))
        elif market == 'binance':
            return Decimal(Settings.get_dict('prices_binance').get(currency_name, 0))
        elif market == 'binance-futures':
            return Decimal(Settings.get_dict('prices_binance_futures').get(currency_name, 0))

        # Fallback to zero
        return Decimal('0')
