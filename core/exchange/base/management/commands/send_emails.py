import datetime
import time
from decimal import Decimal

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from post_office.models import Email

from exchange.base.config import special_coins_price_convert_info
from exchange.base.logging import metric_incr, report_exception
from exchange.base.models import ALL_CRYPTO_CURRENCIES_BINANCE_SYMBOL, Settings


def send_emails_cron(_):
    status_failed = 1
    status_queued = 2
    # Resend recent failed emails
    Email.objects.filter(
        created__gt=now() - datetime.timedelta(minutes=5),
        status=status_failed,
    ).update(status=status_queued)
    # Cancel old queued emails
    Email.objects.filter(
        scheduled_time__isnull=True,
        created__lt=now() - datetime.timedelta(minutes=15),
        status=status_queued,
    ).update(status=status_failed)
    print('Email cleanup done.')


def parse_prices_from_tickers(spot_tickers, futures_tickers):
    """Extract coin prices from ticker data of Binance API.
    """
    binance_prices = {}
    binance_prices_btc = {}
    for ticker in futures_tickers:
        if not ticker:
            continue
        symbol = ticker['symbol'].lower()
        if symbol in special_coins_price_convert_info['coins_with_scale']:
            symbol_src, scale = special_coins_price_convert_info['coins_with_scale'][symbol]
            binance_prices[symbol_src] = round(
                float(Decimal(ticker['price']) * Decimal(scale)) if scale else float(ticker['price']), 9
            )
        elif symbol.endswith('usdt'):
            symbol_src = symbol[:-4]
            binance_prices[symbol_src] = round(float(ticker['price']), 9)

    for ticker in spot_tickers:
        if not ticker:
            continue
        symbol = ticker['symbol'].lower()
        if symbol in special_coins_price_convert_info['binance_only_coins']:
            symbol_src, scale = special_coins_price_convert_info['binance_only_coins'][symbol]
            binance_prices[symbol_src] = (
                float(Decimal(ticker['price']) * Decimal(scale)) if scale else float(ticker['price'])
            )
        elif symbol.endswith('btc'):
            symbol_src = symbol[:-3]
            binance_prices_btc[symbol_src] = round(float(ticker['price']), 5)

    binance_prices['usdt'] = 1
    binance_prices['usdc'] = 1
    binance_prices['busd'] = 1
    binance_prices['dai'] = 1
    binance_prices['wbtc'] = binance_prices['btc']
    binance_prices['egala'] = binance_prices.pop('gala', 0)
    binance_prices_btc['btc'] = 1
    return {
        'usdtFutures': binance_prices,
        'usdtSpot': binance_prices,
        'btcSpot': binance_prices_btc,
    }


def update_binance_prices(_):
    """Update system crypto prices from Binance."""
    # Fetch prices from Binance API
    try:
        futures_tickers = requests.get(
            'https://cdn.nobitex.ir/data/prices/binance-futures.json', timeout=10,
        ).json()
        spot_tickers = requests.get(
            'https://cdn.nobitex.ir/data/prices/binance-spot.json', timeout=10,
        ).json()
    except requests.exceptions.RequestException:
        metric_incr('metric_api_price_data__nxbo_failed')
        print('Fetching Binance prices from cdn/data failed!')
        return
    api_prices = parse_prices_from_tickers(spot_tickers, futures_tickers)
    # Fill missing coins from OKX
    okx_prices = cache.get('okx_prices') or {}
    binance_missing_coins = set(ALL_CRYPTO_CURRENCIES_BINANCE_SYMBOL) - set(api_prices['usdtFutures'].keys())
    binance_missing_coins -= {'pmn', 'pgala', 'gala'}
    for missing_coin in binance_missing_coins:
        missing_coin_price = okx_prices.get(missing_coin)
        if missing_coin_price and missing_coin_price > 0.0005:
            api_prices['usdtFutures'][missing_coin] = missing_coin_price
    # Parse prices
    binance_prices = Settings.get_cached_json('prices_binance', default={})
    binance_prices.update(api_prices['usdtFutures'])
    binance_prices_btc = Settings.get_cached_json('prices_binance_btc', default={})
    binance_prices_btc.update(api_prices['btcSpot'])
    metric_incr('metric_api_price_data__nxbo_ok')
    # Save results
    Settings.set_cached_json('prices_binance', binance_prices)
    Settings.set_cached_json('prices_binance_futures', binance_prices)
    Settings.set_cached_json('prices_binance_btc', binance_prices_btc)
    Settings.set_datetime('prices_binance_last_update', now())
    Settings.set_datetime('prices_binance_futures_last_update', now())
    print('Binance BTC price: ${}'.format(binance_prices['btc']))


def update_okx_prices(_):
    """Update system crypto prices from OKX."""
    # Fetch prices from OKX API
    try:
        spot_tickers = requests.get(
            'https://cdn.nobitex.ir/data/prices/okx-spot.json', timeout=10,
        ).json()
    except requests.exceptions.RequestException:
        metric_incr('metric_api_price_data__nxbo_failed')
        print('Fetching OKX prices from cdn/data failed!')
        return
    api_prices = parse_prices_from_tickers({}, spot_tickers)
    # Parse prices
    okx_prices = cache.get('okx_prices') or {}
    okx_prices.update(api_prices['usdtFutures'])
    metric_incr('metric_api_price_data__nxbo_ok')
    # Save results
    cache.set('okx_prices', okx_prices)
    cache.set('okx_prices_last_update', now().isoformat())
    print(f'OKX BTC price: ${okx_prices["btc"]}')


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        crons = [
            {'function': send_emails_cron, 'mod': 100},
            {'function': update_okx_prices, 'mod': 3 if settings.IS_PROD else 15},
            {'function': update_binance_prices, 'mod': 3 if settings.IS_PROD else 15},
        ]
        state = {}
        rnd = 0
        try:
            while True:
                state['rnd'] = rnd
                for cron in crons:
                    if rnd % cron['mod'] == 0:
                        try:
                            cron['function'](state)
                        except:
                            report_exception()
                rnd += 1
                time.sleep(1)
                if rnd > 21600:
                    print('Closing for cleanup')
                    break
        except KeyboardInterrupt:
            print('bye!')
