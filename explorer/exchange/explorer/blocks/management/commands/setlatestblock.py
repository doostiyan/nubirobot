from django.core.management import BaseCommand

from exchange.explorer.blocks.models import GetBlockStats


class Command(BaseCommand):
    help = "Set latest processed block for a network in DB"

    def add_arguments(self, parser):
        parser.add_argument(
            'network',
            type=str,
            nargs='?',
            help='the network',
        )
        parser.add_argument(
            'latest_processed_block',
            type=int,
            nargs='?',
            help='latest processed block to set',
        )

    def handle(self, *args, **kwargs):
        network = kwargs.get('network')
        if not network:
            network = input('Enter network: ')

        latest_processed_block = kwargs.get('latest_processed_block')
        if not latest_processed_block:
            latest_processed_block = int(input('Enter latest processed block: '))

        try:
            (GetBlockStats.objects
             .filter(network__name__iexact=network)
             .update(latest_processed_block=latest_processed_block, latest_fetched_block=latest_processed_block))

        except Exception as e:
            print('Exception occurred: {}'.format(e))
