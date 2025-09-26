from exchange.explorer.utils.logging import get_logger

from django.core.management.base import BaseCommand

from exchange.explorer.transactions.crons.wallet_monitoring_transfer_processor import WalletMonitoringTransferProcessor


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        logger = get_logger()

        try:
            WalletMonitoringTransferProcessor().run()
        except Exception as e:
            logger.exception(e)
