from django.core.management.base import BaseCommand
from django.db.models import Q

from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.models import Currencies, get_currency_codename
from exchange.wallet.deposit import refresh_address_deposits
from exchange.wallet.models import WalletDepositAddress


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('currency')
        parser.add_argument('address')
        parser.add_argument(
            '--network',
            help='Network of currency',
        )
        parser.add_argument(
            '--contract',
            help='contract address',
        )

    def handle(self, *args, **options):
        currency = getattr(Currencies, options['currency'])
        network = options['network']
        if network is None:
            network = CURRENCY_INFO[currency]['default_network']
        address = options['address']
        contract = options.get('contract')

        try:
            print("{0!r}, {1!r}, {2!r}".format(address, currency, network))
            address = WalletDepositAddress.get_unique_instance(address=address, currency=currency, network=network, contract_address=contract)
        except WalletDepositAddress.DoesNotExist:
            print('No such {} address: {}'.format(get_currency_codename(currency), address))
            return
        refresh_address_deposits(address)
