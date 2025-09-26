from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Min
from django.utils import timezone
from tqdm import tqdm

from exchange.base.models import parse_market_symbol
from exchange.market.inspector import LongTermCandlesCacheChartAPI
from exchange.market.marketstats import MarketStats
from exchange.market.models import Market, MarketCandle


class Command(BaseCommand):
    """
    Examples:
        python manage.py fill_cache_candle_buckets
        python manage.py fill_cache_candle_buckets -m BTCUSDT
        python manage.py fill_cache_candle_buckets --config_only

    """

    help = 'Fills Redis cache with buckets of candle data'

    def add_arguments(self, parser):
        parser.add_argument('-m', '--market', type=str, help='Run for specific market [use symbolic format]')
        parser.add_argument(
            '--config_only',
            action='store_true',
            help='Fill cache with only candle configs (skip data).',
        )

    def handle(self, *args, **options):
        markets = self._get_markets(options.get('market'))
        self.stdout.write('=======[Fill Configs]=======')
        MarketStats.update_chart_config()
        if options['config_only']:
            return
        self._fill_candles(markets)

    def _get_markets(self, market_symbol):
        self.stdout.write('=======[Get Markets]=======')
        start_get_markets = timezone.now()

        markets = Market.get_active_markets()
        if market_symbol:
            src, dst = parse_market_symbol(market_symbol)
            markets = markets.filter(src_currency=src, dst_currency=dst)
        markets = (
            markets.annotate(first_trade_time=Min('trades__created_at'))
            .exclude(first_trade_time=None)
            .order_by('first_trade_time')
        )
        self.stdout.write(f'---> get markets time : {(timezone.now()-start_get_markets).total_seconds()} ms')
        return markets

    def _fill_candles(self, markets):
        candle_cache = LongTermCandlesCacheChartAPI

        end_time = timezone.now()

        for market in markets:
            self.stdout.write(f'=======[ Start creating candles for {market.symbol}]=======')

            for resolution, _resolution_name in MarketCandle.RESOLUTIONS:
                start_time = (
                    max(end_time - timedelta(seconds=candle_cache.KEEP_HISTORY_FOR_DAYS), market.first_trade_time)
                    if resolution == MarketCandle.RESOLUTIONS.minute
                    else market.first_trade_time
                )

                _, end_bucket = candle_cache.get_bucket(end_time, resolution)
                start_bucket, _ = candle_cache.get_bucket(start_time, resolution)

                bucket_length = candle_cache.CACHE_SIZE * int(
                    MarketCandle.resolution_to_timedelta(resolution).total_seconds(),
                )
                self.stdout.write(
                    f'resolution: [{_resolution_name}]\n'
                    f'times: [{start_time.strftime("%Y/%m/%d-%H:%M:%S")} - {end_time.strftime("%Y/%m/%d-%H:%M:%S")}]\n'
                    f'buckets: [{end_bucket}] - [{start_bucket}], bucket length: [{bucket_length}]',
                )

                count_saved = 0
                buckets = BucketIterator(end_bucket, start_bucket, bucket_length)
                for bucket in tqdm(buckets):
                    saved = candle_cache.save_bucket_data(market, resolution, bucket - bucket_length, bucket)
                    count_saved += 1 * (1 if saved else 0)

                self.stdout.write(f'---> Saved buckets : {count_saved}')


class BucketIterator:
    def __init__(self, start_bucket: int, end_bucket: int, bucket_length: int):

        self.start_bucket = start_bucket
        self.end_bucket = end_bucket
        self.length = bucket_length
        self.dt = None

    def __iter__(self):
        return self

    def __next__(self):
        if not self.dt:
            self.dt = self.start_bucket
        else:
            self.dt = self.dt - self.length
        if self.dt < self.end_bucket:
            raise StopIteration()
        return self.dt

    def __len__(self):
        """approximate for tqdm"""
        return (self.start_bucket - self.end_bucket) // self.length + 1
