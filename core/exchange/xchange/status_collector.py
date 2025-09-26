"""
    https://ttxconvert.nxbo.ir/swagger/index.html#/XConvert/get_xconvert_status_pairs
"""
import signal
import time
import traceback
from decimal import Decimal

import requests
from django.core.cache import cache
from django.utils import text

from exchange.base.models import XCHANGE_CURRENCIES, Currencies
from exchange.xchange.constants import ALL_XCHANGE_PAIRS_CACHE_KEY
from exchange.xchange.exceptions import FailedFetchStatuses
from exchange.xchange.helpers import notify_admin_on_market_status_change
from exchange.xchange.marketmaker.client import Client
from exchange.xchange.models import MarketStatus


class StatusCollector:
    def __init__(self, period: int) -> None:
        self.period = period
        self.should_die = False

        signal.signal(signal.SIGINT, self.die)
        signal.signal(signal.SIGTERM, self.die)

    def die(self, *args, **kwargs):
        if self.should_die:
            print('OK. OK.')
            return
        print('Xchange status collector is dying gracefully.')
        self.should_die = True

    def run(self):
        while not self.should_die:
            self._main_loop_method()

    def _main_loop_method(self):
        changed_statuses = []
        try:
            all_markets_dict = {
                (market.base_currency, market.quote_currency): market for market in MarketStatus.objects.all()
            }
            for detail in self.fetch_statuses():
                try:
                    pair_status_dict = {text.camel_case_to_spaces(key).replace(' ', '_'): detail[key] for key in detail}
                    base_currency = getattr(Currencies, pair_status_dict.pop('base_currency'))
                    quote_currency = getattr(Currencies, pair_status_dict.pop('quote_currency'))
                    for key in pair_status_dict:
                        if key in ('base_precision', 'quote_precision'):
                            pair_status_dict[key] = Decimal(f'1e{pair_status_dict[key]}')
                        elif key == 'status':
                            pair_status_dict[key] = MarketStatus.STATUS_CHOICES._identifier_map.get(
                                pair_status_dict[key]
                            )
                        else:
                            pair_status_dict[key] = Decimal(pair_status_dict[key])
                    old_market = all_markets_dict.get((base_currency, quote_currency))

                    if old_market and old_market.status == MarketStatus.STATUS_CHOICES.delisted:
                        continue  # Don't update delisted market

                    new_market, created = MarketStatus.objects.update_or_create(
                        base_currency=base_currency,
                        quote_currency=quote_currency,
                        defaults=pair_status_dict,
                    )
                    if not created and old_market and old_market.status != new_market.status:
                        changed_statuses.append({'old_market': old_market, 'new_market': new_market})
                except Exception:
                    continue
            self.cache_xchange_currency_pairs()
        except Exception:
            print('Error in main loop')
            print(traceback.format_exc())
        if changed_statuses:
            notify_admin_on_market_status_change(changed_statuses)
        time.sleep(self.period)

    def fetch_statuses(self):
        server, _ = Client.get_base_url()
        try:
            statuses = Client.request(method=Client.Method.GET, path='/xconvert/status/pairs', verbose=True)
        except requests.RequestException as e:
            raise FailedFetchStatuses('Status pairs service is not available.') from e

        if statuses['hasError']:
            raise FailedFetchStatuses('Status pairs service is not available.')
        return statuses['result']

    def cache_xchange_currency_pairs(self):
        """
        We want to cache all pairs of currencies that at least one of them is a xhcnage-only currency and has
        a price stored as MarketStatus. Any pair (base_currency, quote_currency) has 2 sets of sell and buy prices,
        so we cache both of (base_currency, quote_currency) and (quote_currency, base_currency)
        """
        all_pairs = list(MarketStatus.objects.all().order_by('id').values_list('base_currency', 'quote_currency'))
        xchange_only_pairs = []
        for pair in all_pairs:
            if pair[0] in XCHANGE_CURRENCIES or pair[1] in XCHANGE_CURRENCIES:
                xchange_only_pairs.append(pair)
                xchange_only_pairs.append((pair[1], pair[0]))
        cache.set(ALL_XCHANGE_PAIRS_CACHE_KEY, xchange_only_pairs)
