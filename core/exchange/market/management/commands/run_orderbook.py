import multiprocessing
import time
from contextlib import nullcontext
from multiprocessing import Pool

from django.conf import settings
from django.core.management.base import BaseCommand

from exchange.base.decorators import ram_cache
from exchange.base.models import Settings
from exchange.market.orderbook import OrderBook, OrderBookGenerator


class Command(BaseCommand):
    """
    Examples:
        python manage.py run_orderbook
        python manage.py run_orderbook -p8 -x100
    """
    help = 'Create orderbook for markets.'

    def add_arguments(self, parser):
        parser.add_argument(
            '-p', '--process', default=6, type=int,
            help='Specify number of processes to run in multiprocess mode',
        )
        parser.add_argument(
            '-x', '--max-active-orders', type=int,
            help='Specify maximum number of orders being processed in orderbook',
        )

    def handle(self, process, max_active_orders, **options):
        delay = self.get_delay()
        OrderBook.set_max_active_orders(max_active_orders)

        is_multiprocess = process and process > 1
        if is_multiprocess:
            manager = multiprocessing.Manager()
            OrderBookGenerator.all_orderbooks = manager.dict({})
            OrderBookGenerator.cache_update_times = manager.dict({})
            pool_context = Pool(process)
        else:
            pool_context = nullcontext()

        try:
            with pool_context as pool:
                while True:
                    if not self._is_orderbook_generation_disabled():
                        OrderBookGenerator.run(pool)
                    time.sleep(delay)
        except KeyboardInterrupt:
            print('bye!')

    @classmethod
    @ram_cache(default=False)
    def _is_orderbook_generation_disabled(cls):
        return settings.IS_TESTNET and Settings.is_disabled('order_book_generation')

    @staticmethod
    def get_delay():
        delay = 0.1
        if settings.LOAD_LEVEL >= 8:
            delay += 0.1
        if settings.LOAD_LEVEL >= 10:
            delay += 0.8
        if not settings.IS_PROD:
            delay += 1
        return delay
