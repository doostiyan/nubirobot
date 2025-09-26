from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand

from ...services import WalletExplorerService
from exchange.base.models import Currencies


class Command(BaseCommand):
    """
        This command saves address txs in DB defaults for tokens on TON in a given period of time.

        Run with:
            python manage.py retrytokentxs --start-date=<timestamp> --end-date=<timestamp>
        or simply:
            python manage.py retrytokentxs
        and let the command get needed inputs by shell
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--network',
            type=str,
            nargs='?',
            help='the network ',
            default='TON'
        )
        parser.add_argument(
            '--currency',
            type=str,
            nargs='?',
            help='the currency',
            default='hmstr',
        )
        parser.add_argument(
            '--start-date',
            type=int,
            nargs='?',
            help='the start date timestamp'
        )
        parser.add_argument(
            '--end-date',
            type=int,
            nargs='?',
            help='the end date timestamp'
        )
        parser.add_argument(
            '--client',
            type=str,
            nargs='?',
            help='the client',
            default='core'
        )

    def handle(self, *args, **kwargs):
        network = kwargs.get('network').upper()
        currency = kwargs.get('currency')

        start_date = kwargs.get('start-date')
        end_date = kwargs.get('end-date')

        if not start_date:
            start_date = int(input('Enter start date timestamp: '))

        if not end_date:
            end_date = int(input('Enter end date timestamp: '))

        client = kwargs.get('client')

        addresses = WalletExplorerService.get_registered_addresses_of_client(client, currency=currency)

        for address in addresses:
            # set cache to use get_token_txs_by_time_with_retry in BlockchainExplorer for given period of time
            cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}token_txs_retry', True)
            cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}token_txs_start_date', start_date)
            cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}token_txs_end_date', end_date)

            try:
                WalletExplorerService.get_wallet_transactions_dto_from_default_provider(network=network,
                                                                                        address=address.blockchain_address,
                                                                                        currency=currency,
                                                                                        register=True,
                                                                                        save=True)
            except Exception as e:
                print(e)
