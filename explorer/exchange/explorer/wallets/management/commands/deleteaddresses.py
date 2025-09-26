import time
import random

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from ...crons.delete_addresses import (DeleteCardanoAddressesCron, DeleteAlgorandAddressesCron,
                                       DeleteAptosAddressesCron, DeleteArbitrumAddressesCron,
                                       DeleteAvalancheAddressesCron, DeleteBitcoinCashAddressesCron,
                                       DeleteBinanceSmartChainAddressesCron, DeleteBitcoinAddressesCron,
                                       DeleteDogecoinAddressesCron, DeletePolkadotAddressesCron,
                                       DeleteElrondAddressesCron, DeleteEnjinAddressesCron,
                                       DeleteEthereumAddressesCron, DeleteFilecoinAddressesCron,
                                       DeleteFlowAddressesCron, DeleteFantomClassicAddressesCron,
                                       DeleteLitecoinAddressesCron, DeletePolygonAddressesCron, DeleteNearAddressesCron,
                                       DeleteOneAddressesCron, DeleteSolanaAddressesCron,
                                       DeleteTronAddressesCron, DeleteTezosAddressesCron)
from exchange.explorer.utils.logging import get_logger

CRONS2RUN = [
    DeleteCardanoAddressesCron,
    DeleteAlgorandAddressesCron,
    DeleteAptosAddressesCron,
    DeleteArbitrumAddressesCron,
    DeleteAvalancheAddressesCron,
    DeleteBitcoinCashAddressesCron,
    DeleteBinanceSmartChainAddressesCron,
    DeleteBitcoinAddressesCron,
    DeleteDogecoinAddressesCron,
    DeletePolkadotAddressesCron,
    DeleteElrondAddressesCron,
    DeleteEnjinAddressesCron,
    DeleteEthereumAddressesCron,
    DeleteFilecoinAddressesCron,
    DeleteFlowAddressesCron,
    DeleteFantomClassicAddressesCron,
    DeleteLitecoinAddressesCron,
    DeletePolygonAddressesCron,
    DeleteNearAddressesCron,
    DeleteOneAddressesCron,
    DeleteSolanaAddressesCron,
    DeleteTronAddressesCron,
    DeleteTezosAddressesCron
]


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--sleep',  # if U want to set sleep time manually (optional)
            type=int,
            nargs='?',
            help='sleep in seconds ',
            default=5,
        )

    def handle(self, *args, **kwargs):
        logger = get_logger()
        sleep = kwargs.get('sleep')
        while True:

            random.shuffle(CRONS2RUN)
            network = None
            try:
                for cron in CRONS2RUN:
                    network = cron.network
                    start_time = now()
                    cron().run()
                    end_time = now()
                    logger.info(f'[BlockProcessor] Spent time for {network} delete addresses service:'
                                f'{(end_time - start_time).seconds} seconds')
                    time.sleep(2)
                time.sleep(sleep)
            except KeyboardInterrupt:
                logger.info('bye!')
                break
            except Exception as e:
                logger.exception(f'[BlockProcessor] {network} delete addresses API Error: {e}')
                time.sleep(sleep)
