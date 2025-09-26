import logging
import time
from contextlib import nullcontext
from multiprocessing import Pool

from django.conf import settings
from django.core.management.base import BaseCommand

from exchange.market.depth_chart import MarketDepthChartGenerator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Examples:
        python manage.py generate_depth_charts
        python manage.py generate_depth_charts -p8
    """
    help = 'Create orderbook for markets.'

    def add_arguments(self, parser):
        parser.add_argument(
            '-p', '--process', default=6, type=int,
            help='Specify number of processes to run in multiprocess mode',
        )

    def handle(self, process, **options):
        pool_context = Pool(process) if process and process > 1 else nullcontext()
        try:
            with pool_context as pool:
                while True:
                    MarketDepthChartGenerator.run(pool)
                    time.sleep(self.get_delay())
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received! Bye!")

    @staticmethod
    def get_delay():
        delay = 0.5
        if settings.LOAD_LEVEL >= 8:
            delay += 0.1
        if settings.LOAD_LEVEL >= 10:
            delay += 0.8
        if not settings.IS_PROD:
            delay += 1
        return delay
