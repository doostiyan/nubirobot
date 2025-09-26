from pprint import pprint

from django.core.management import BaseCommand

from exchange.explorer.transactions.services import TransactionExplorerService


class Command(BaseCommand):
    help = "Read Transaction from DB by hash"

    def add_arguments(self, parser):
        parser.add_argument(
            'tx_hash',
            type=str,
            nargs='?',
            help='the transaction hash',
        )

        parser.add_argument(
            '--network',
            type=str,
            nargs='?',
            help='the network ',
        )

    def handle(self, *args, **kwargs):
        network = kwargs.get('network', '')
        if not network:
            network = input('Enter network: ')
        network = network.upper()

        tx_hash = kwargs.get('tx_hash')
        if not tx_hash:
            tx_hash = input('Enter transaction hash: ')
        try:
            transfers = TransactionExplorerService.read_transfers_from_db_by_hash(tx_hash=tx_hash, network=network)
            if transfers:
                pprint(transfers)
            else:
                print('There is no transaction with this hash in the database')
        except Exception as e:
            print('Exception occurred: {}'.format(e))
