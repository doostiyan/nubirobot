import time
import random

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from ...crons.delete_block_txs import (DeleteCardanoBlockTxsCron, DeleteAlgorandBlockTxsCron, DeleteAptosBlockTxsCron,
                                       DeleteArbitrumBlockTxsCron, DeleteAvalancheBlockTxsCron,
                                       DeleteBitcoinCashBlockTxsCron, DeleteBaseBlockTxsCron,
                                       DeleteBinanceSmartChainBlockTxsCron, DeleteBitcoinBlockTxsCron,
                                       DeleteDogecoinBlockTxsCron, DeletePolkadotBlockTxsCron, DeleteElrondBlockTxsCron,
                                       DeleteEnjinBlockTxsCron, DeleteEthereumBlockTxsCron,
                                       DeleteEthereumClassicBlockTxsCron, DeleteFilecoinBlockTxsCron,
                                       DeleteFlowBlockTxsCron, DeleteFantomBlockTxsCron,
                                       DeleteLitecoinBlockTxsCron, DeleteMoneroBlockTxsCron, DeletePolygonBlockTxsCron,
                                       DeleteNearBlockTxsCron, DeleteOneBlockTxsCron, DeleteSolanaBlockTxsCron,
                                       DeleteSonicBlockTxsCron, DeleteTronBlockTxsCron, DeleteTezosBlockTxsCron)

from exchange.explorer.utils.logging import get_logger

DELETE_BLOCK_TXS_CRONS2RUN = [
    DeleteCardanoBlockTxsCron,
    DeleteAlgorandBlockTxsCron,
    DeleteAptosBlockTxsCron,
    DeleteArbitrumBlockTxsCron,
    DeleteAvalancheBlockTxsCron,
    DeleteBaseBlockTxsCron,
    DeleteBitcoinCashBlockTxsCron,
    DeleteBinanceSmartChainBlockTxsCron,
    DeleteBitcoinBlockTxsCron,
    DeleteDogecoinBlockTxsCron,
    DeletePolkadotBlockTxsCron,
    DeleteElrondBlockTxsCron,
    DeleteEnjinBlockTxsCron,
    DeleteEthereumBlockTxsCron,
    DeleteEthereumClassicBlockTxsCron,
    DeleteFilecoinBlockTxsCron,
    DeleteFlowBlockTxsCron,
    DeleteFantomBlockTxsCron,
    DeleteLitecoinBlockTxsCron,
    DeleteMoneroBlockTxsCron,
    DeletePolygonBlockTxsCron,
    DeleteNearBlockTxsCron,
    DeleteOneBlockTxsCron,
    DeleteSolanaBlockTxsCron,
    DeleteSonicBlockTxsCron,
    DeleteTronBlockTxsCron,
    DeleteTezosBlockTxsCron
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

            random.shuffle(DELETE_BLOCK_TXS_CRONS2RUN)
            network = None
            try:
                for i in range(len(DELETE_BLOCK_TXS_CRONS2RUN)):
                    delete_block_txs_cron = DELETE_BLOCK_TXS_CRONS2RUN[i]
                    network = delete_block_txs_cron.network
                    start_time = now()
                    delete_block_txs_cron().run()
                    end_time = now()
                    logger.info(f'[BlockProcessor] Spent time for {network} delete block txs service:'
                                f'{(end_time - start_time).seconds} seconds')
                    time.sleep(sleep)


            except KeyboardInterrupt:
                logger.info('bye!')
                break
            except Exception as e:
                logger.exception(f'[BlockProcessor] {network} delete block txs API Error: {e}')
                time.sleep(sleep)
