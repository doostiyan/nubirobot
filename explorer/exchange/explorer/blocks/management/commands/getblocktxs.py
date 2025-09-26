import time

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from exchange.explorer.blocks.crons.get_block_txs import (GetNearBlockTxsCron, GetSolanaBlockTxsCron,
                                                          GetSonicBlockTxsCron)

TARGET_PROCESS_MAP = {
    'NEAR': GetNearBlockTxsCron,
    'SOL': GetSolanaBlockTxsCron,
    'SONIC': GetSonicBlockTxsCron,
}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--network',
            type=str,
            nargs='?',
            help='the network ',
        )
        parser.add_argument(
            '--sleep',  # if U want to set sleep time manually (optional)
            type=int,
            nargs='?',
            help='sleep in seconds ',
            default=5,
        )

    def handle(self, *args, **kwargs):
        network = kwargs.get('network')
        sleep = kwargs.get('sleep')
        target_process = TARGET_PROCESS_MAP.get(network)
        while True:
            try:
                start_time = now()
                target_process().run()
                end_time = now()
                print(f'[BlockProcessor] Spent time for {network} custom service:'
                      f'{(end_time - start_time).seconds} seconds')
                time.sleep(sleep)
            except KeyboardInterrupt:
                print('bye!')
                break
            except Exception as e:
                print(f'[BlockProcessor] {network} custom service API Error: {e}')
                time.sleep(sleep)
