""" Command: matcher_create_test_data """
import random
from decimal import ROUND_UP, Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.accounts.models import User
from exchange.base.management.commands.send_emails import update_binance_prices
from exchange.base.models import (
    AVAILABLE_CURRENCIES,
    RIAL,
    VALID_MARKET_SYMBOLS,
    Currencies,
    Settings,
    get_currency_codename,
    get_market_symbol,
)
from exchange.market.models import Market
from tests.base.utils import create_order


class Command(BaseCommand):
    help = 'Create test data for matching engine.'

    def handle(self, *args, **kwargs):
        if settings.IS_PROD or not settings.DEBUG:
            self.stdout.write(self.style.ERROR('This command is only for local development.'))
            return
        # Create all Market objects
        for src_currency in AVAILABLE_CURRENCIES:
            for dst_currency in [Currencies.rls, Currencies.usdt]:
                market_symbol = get_market_symbol(src_currency, dst_currency)
                if market_symbol not in VALID_MARKET_SYMBOLS:
                    continue
                market, created = Market.objects.get_or_create(
                    src_currency=src_currency,
                    dst_currency=dst_currency,
                    defaults={'is_active': True},
                )
                if created:
                    print('Created missing market for:', market.symbol)
        # Fetch prices
        print('Fetching binance prices…')
        update_binance_prices(1)
        market_prices = Settings.get_dict('prices_binance')
        # Create some orders to fill orderbook
        market_symbols = ['BTCIRT']
        users = User.objects.filter(is_superuser=True)
        for symbol in market_symbols:
            market = Market.by_symbol(symbol)
            price = Decimal(market_prices.get(get_currency_codename(market.src_currency)))
            amount = Decimal(random.randint(10, 30)) / price  # noqa: S311
            amount = amount.quantize(Decimal('1E-6'), ROUND_UP)
            if market.dst_currency == RIAL:
                price *= Decimal('60_000_0')
            created_buys = created_sells = 0
            for _ in range(50):
                with transaction.atomic():
                    user = random.choice(users)  # noqa: S311
                    is_sell = random.random() < 0.5  # noqa: S311
                    if is_sell:
                        price *= Decimal('1.1')
                        created_sells += 1
                    else:
                        created_buys += 1
                    create_order(
                        user,
                        market.src_currency,
                        market.dst_currency,
                        amount,
                        price,
                        sell=is_sell,
                    )
            print(f'Created S{created_sells}/B{created_buys} in {symbol}.')
