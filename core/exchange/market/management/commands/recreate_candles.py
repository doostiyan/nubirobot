import datetime
import math

from django.core.management.base import BaseCommand
from django.db.models import Max, Min
from django.utils import timezone
from tqdm import tqdm

from exchange.base.helpers import batcher
from exchange.market.inspector import UpdateMarketCandles
from exchange.market.models import Market, MarketCandle


class Command(BaseCommand):
    """
    Examples:
        python manage.py recreate_candles
        python manage.py recreate_candles -m BTCUSDT
        python manage.py recreate_candles -s 2022-04-27
    """
    help = 'Creates candles using trades.'

    MINUTE_CANDLES_START_TIME = '2022-03-21 00:00:00.000000+03:30'  # i.e. 1400-01-01T00:00:00

    def add_arguments(self, parser):
        parser.add_argument(
            '-m', '--market', type=str,
            help='Run for specific market [use symbolic format]',
        )
        parser.add_argument(
            '-s', '--start-date', type=str,
            help='Create candles starting from specific time [use YYYY-MM-DD format]',
        )

    def handle(self, market, start_date, **options):
        run_time = timezone.now()
        self.MINUTE_CANDLES_START_TIME = timezone.datetime.fromisoformat(self.MINUTE_CANDLES_START_TIME)
        manual_start_time = timezone.datetime.fromisoformat(f'{start_date}T00:00:00+04:30') if start_date else None
        markets = Market.get_active_markets().annotate(first_trade_time=Min('trades__created_at')).exclude(
            first_trade_time=None
        ).order_by('first_trade_time')
        if market:
            markets = markets.filter(pk__in=[Market.by_symbol(market).pk])
        for resolution, _ in MarketCandle.RESOLUTIONS:
            last_candle_time = MarketCandle.objects.filter(resolution=resolution).aggregate(t=Max('start_time'))['t']
            for i, market in enumerate(markets):
                start_time = self.get_start_time(
                    resolution, market.first_trade_time, last_candle_time, manual_start_time
                )
                end_time = markets[i + 1].first_trade_time if i + 1 < len(markets) else run_time
                if end_time < start_time:
                    continue
                self.create_resolution_candles(markets[:i + 1], resolution, start_time, end_time)
                UpdateMarketCandles.clear_caches(markets, resolution, since=start_time)

    def get_start_time(self, resolution, first_trade_time, last_candle_time, manual_start_time):
        if resolution == MarketCandle.RESOLUTIONS.minute:
            first_trade_time = max(self.MINUTE_CANDLES_START_TIME, first_trade_time)
        if manual_start_time:
            return max(manual_start_time, first_trade_time)
        if last_candle_time:
            return max(last_candle_time, first_trade_time)
        return first_trade_time

    def create_resolution_candles(self, markets, resolution, start_time, end_time):
        self.stdout.write(f'[{MarketCandle.RESOLUTIONS[resolution]} Candles for {len(markets)} Markets]:')
        date_times = list(CandleTimeIterator(resolution, start_time, end_time))
        old_hours = resolution == MarketCandle.RESOLUTIONS.hour
        batch_size = 20
        for dt_s in tqdm(
            batcher(date_times, batch_size=batch_size),
            total=math.ceil(len(date_times) / batch_size),
            unit='date_times',
            unit_scale=batch_size,
        ):
            old_hours = any([dt < self.MINUTE_CANDLES_START_TIME for dt in dt_s]) if old_hours else False
            if old_hours:
                for dt in dt_s:
                    UpdateMarketCandles.update_time_candles(markets, resolution, [dt], force_base_mode=True)
            else:
                UpdateMarketCandles.update_time_candles(markets, resolution, dt_s, force_base_mode=False)



class CandleTimeIterator:
    def __init__(self, resolution: int, start_time: datetime.datetime, end_time: datetime.datetime):
        self.resolution = resolution
        self.start_time = MarketCandle.get_start_time(start_time, resolution)
        self.end_time = end_time
        self.dt = None

    def __iter__(self):
        return self

    def __next__(self):
        if not self.dt:
            self.dt = self.start_time
        else:
            self.dt = MarketCandle.get_end_time(self.dt, self.resolution) + timezone.timedelta(microseconds=1)
        if self.dt >= self.end_time:
            raise StopIteration()
        return self.dt

    def __len__(self):
        """approximate for tqdm"""
        return int((self.end_time - self.start_time) / MarketCandle.resolution_to_timedelta(self.resolution))
