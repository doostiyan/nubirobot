import time

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from exchange.wallet.crons import UpdateArbitrumDepositsCron, UpdateNearDepositCron, UpdateSolanaDepositsCron


TARGET_PROCESS_MAP = {
        'ARB': UpdateArbitrumDepositsCron,
        'NEAR': UpdateNearDepositCron,
        'SOL': UpdateSolanaDepositsCron,
}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--network',  # if U want to set starting block manually (optional)
            type=str,
            nargs='?',
            help='the network ',
        )

    def handle(self, *args, **kwargs):
        network = kwargs.get('network')
        target_process = TARGET_PROCESS_MAP.get(network)
        while True:
            try:
                start_time = now()
                target_process().run()
                end_time = now()
                print(f'[BlockProcessor] Spent time for {network} custom service:'
                      f'{(end_time - start_time).seconds} seconds')
                time.sleep(5)
            except KeyboardInterrupt:
                print('bye!')
                break
            except Exception as e:
                print(f'[BlockProcessor] {network} custom service API Error: {e}')
                time.sleep(5)

