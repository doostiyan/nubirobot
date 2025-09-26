from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db.models import Min
from django.utils import timezone
from tqdm import tqdm

from exchange.base.calendar import ir_tz
from exchange.base.helpers import batcher
from exchange.base.models import parse_market_symbol
from exchange.base.parsers import parse_choices
from exchange.market.inspector import LongTermCandlesCache, LongTermCandlesCacheChartAPI
from exchange.market.models import Market, MarketCandle


class Command(BaseCommand):
    """
    Examples:
        python manage.py remove_candles_caches -dt 2024-01-30-00:00 -c chart_api -r day
        python manage.py remove_candles_caches -m BTCUSDT
    """

    help = 'Clear Candles cache based on a specific cache_name, date and time.'

    def add_arguments(self, parser):
        parser.add_argument('-c', '--cache', type=str, required=True, help='Cache name [use default or chart_api]')
        parser.add_argument(
            '-dt', '--datetime', type=str, required=True, help='Datetime in YYYY-MM-DDHH:MM format (required)'
        )
        parser.add_argument(
            '-r', '--resolution', type=str, required=True, help='Resolution candles in [minute, hour, day]'
        )
        parser.add_argument('-m', '--market', type=str, help='Run for specific market [use symbolic format]')

    def handle(self, *args, **options):
        # find cache
        cache = self._get_cache(options.get('cache'))
        if not cache:
            self.stdout.write('Error: Invalid Cache.')
            return

        # find timestamp
        end_date = self._get_timestamp(options.get('datetime'))
        if not end_date:
            self.stdout.write('Error: Invalid datetime format.')
            return

        resolution = parse_choices(MarketCandle.RESOLUTIONS, options.get('resolution'))
        if not resolution:
            self.stdout.write('Error: Invalid resolution format.')
            return

        markets = self._get_markets(options.get('market'))
        self.stdout.write('=======[Clean Cache]=======')
        self.clean_cache(markets, end_date, resolution, cache)

    def _get_cache(self, cache_name: str):
        caches = {
            'default': LongTermCandlesCache,
            'chart_api': LongTermCandlesCacheChartAPI,
        }
        if cache_name in caches:
            return caches[cache_name]

    def _get_timestamp(self, date_str: str):
        try:
            return datetime.strptime(date_str, '%Y-%m-%d-%H:%M').astimezone(ir_tz())
        except ValueError:
            return None

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

    def clean_cache(self, markets, end_date: datetime, resolution: int, cache: LongTermCandlesCache):

        now = timezone.now()

        for market in tqdm(markets, leave=False):
            start_date = (
                max(now - timedelta(seconds=cache.KEEP_HISTORY_FOR_DAYS), market.first_trade_time)
                if resolution == MarketCandle.RESOLUTIONS.minute
                else market.first_trade_time
            )

            if end_date < start_date:
                self.stdout.write(f'---> SKIP Market: {market.symbol}')
                continue

            start_bucket, _ = cache.get_bucket(start_date, resolution)
            end_bucket, _ = cache.get_bucket(end_date, resolution)

            bucket_length = cache.CACHE_SIZE * int(
                MarketCandle.resolution_to_timedelta(resolution).total_seconds(),
            )
            self.stdout.write(
                f'times: [{start_date.strftime("%Y/%m/%d-%H:%M:%S")} - {end_date.strftime("%Y/%m/%d-%H:%M:%S")}]\n'
                f'buckets: [{start_bucket}] - [{end_bucket}], bucket length: [{bucket_length}]',
            )

            bucket = start_bucket
            keys = []
            while bucket <= end_bucket:
                keys.append(cache.get_cache_key(market, resolution, str(bucket)))
                bucket += bucket_length

            for batch in batcher(keys, 100):
                cache.cache().delete_many(batch)

