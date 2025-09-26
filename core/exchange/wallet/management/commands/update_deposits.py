from django.core.management.base import BaseCommand

from exchange.base.models import Currencies, get_currency_codename, ALL_CRYPTO_CURRENCIES
from exchange.wallet.deposit import update_deposits


class Command(BaseCommand):
    def add_arguments(self, parser):
        for c in ALL_CRYPTO_CURRENCIES:
            currency = get_currency_codename(c)
            parser.add_argument('--' + currency, action='store_true', dest=currency)

    def handle(self, *args, **options):
        currencies = []
        for c in ALL_CRYPTO_CURRENCIES:
            currency = get_currency_codename(c)
            if options[currency]:
                currencies.append(getattr(Currencies, currency))
        update_deposits(currencies=currencies or None)
