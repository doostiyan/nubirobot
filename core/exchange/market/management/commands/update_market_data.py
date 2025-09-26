from django.core.management.base import BaseCommand

from exchange.base.helpers import sleep_remaining
from exchange.market.inspector import UpdateMarketCandles
from exchange.market.marketstats import MarketStats


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        try:
            i = -1
            while True:
                i = (i + 1) % 12000  # Just to avoid large numbers
                with sleep_remaining(seconds=10):
                    UpdateMarketCandles.run()
                    MarketStats.update_all_market_stats()
                    if i % 300 == 0:
                        MarketStats.update_chart_config()
        except KeyboardInterrupt:
            print('bye!')
