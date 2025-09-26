import datetime
import json
import random
import time
from datetime import timedelta
from decimal import Decimal
from typing import Union
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.db.models import Q
from django.test import TestCase
from django.utils import timezone

from exchange.accounts.models import User
from exchange.base.models import PRICE_PRECISIONS, Currencies
from exchange.market.inspector import (
    LongTermCandlesCache,
    LongTermCandlesCacheChartAPI,
    ShortTermCandlesCache,
    UpdateMarketCandles,
)
from exchange.market.models import Market, MarketCandle
from exchange.market.tasks import init_candles_cache
from tests.base.utils import create_trade

Number = Union[Decimal, int, str]


class BaseMarketCandleTest(TestCase):
    markets: list
    users: list

    @classmethod
    def setUpTestData(cls):
        cls.markets = [Market.by_symbol('BTCUSDT'), Market.by_symbol('DOGEIRT')]
        cls.users = list(User.objects.filter(pk__gt=200)[:2])

    @classmethod
    def create_trade(cls, market: Market, dt: datetime.datetime, price: Number, amount: Number):
        trade = create_trade(
            cls.users[0], cls.users[1], market.src_currency, market.dst_currency, Decimal(amount), Decimal(price),
        )
        trade.created_at = dt
        trade.save(update_fields=('created_at',))
        return trade

    @staticmethod
    def create_candle(
        market: Market,
        resolution: int,
        dt: datetime.datetime,
        open_price: Number,
        high_price: Number,
        low_price: Number,
        close_price: Number,
        trade_amount: Number,
        trade_total: Number,
    ):
        return MarketCandle.objects.create(
            market=market,
            resolution=resolution,
            start_time=MarketCandle.get_start_time(dt, resolution),
            open_price=Decimal(open_price),
            high_price=Decimal(high_price),
            low_price=Decimal(low_price),
            close_price=Decimal(close_price),
            trade_amount=Decimal(trade_amount),
            trade_total=Decimal(trade_total),
        )


class MarketCandleModelTest(BaseMarketCandleTest):
    def test_convert_resolution_to_timedelta(self):
        for resolution, seconds in (
            (MarketCandle.RESOLUTIONS.minute, 60),
            (MarketCandle.RESOLUTIONS.hour, 3600),
            (MarketCandle.RESOLUTIONS.day, 24 * 3600),
        ):
            duration = MarketCandle.resolution_to_timedelta(resolution)
            assert isinstance(duration, timezone.timedelta)
            assert duration.total_seconds() == seconds

    def test_get_datetime_resolution_start(self):
        for date_string in (
            '2022-06-15T02:27:16.347892',
            '2022-06-15T02:27:16.347892+04:30',
            '2022-06-14T21:57:16.347892+00:00',
        ):
            dt = timezone.datetime.fromisoformat(date_string)
            dt_minute = MarketCandle.get_start_time(dt, MarketCandle.RESOLUTIONS.minute)
            assert dt_minute.isoformat() == '2022-06-15T02:27:00+04:30'
            dt_hour = MarketCandle.get_start_time(dt, MarketCandle.RESOLUTIONS.hour)
            assert dt_hour.isoformat() == '2022-06-15T02:00:00+04:30'
            dt_day = MarketCandle.get_start_time(dt, MarketCandle.RESOLUTIONS.day)
            assert dt_day.isoformat() == '2022-06-15T00:00:00+04:30'

    def test_public_price_on_shadow_below_candle(self):
        candle = MarketCandle(
            open_price=Decimal('43800'),
            high_price=Decimal('44100'),
            low_price=Decimal('39860'),
            close_price=Decimal('42010'),
            price_lower_bound=Decimal(41200),
        )
        assert candle.public_open_price == candle.open_price
        assert candle.public_high_price == candle.high_price
        assert candle.public_low_price == candle.price_lower_bound
        assert candle.public_close_price == candle.close_price

    def test_public_price_on_shadow_above_candle(self):
        candle = MarketCandle(
            open_price=Decimal('43800'),
            high_price=Decimal('49400'),
            low_price=Decimal('41860'),
            close_price=Decimal('42010'),
            price_upper_bound=Decimal(45300),
        )
        assert candle.public_open_price == candle.open_price
        assert candle.public_high_price == candle.price_upper_bound
        assert candle.public_low_price == candle.low_price
        assert candle.public_close_price == candle.close_price

    def test_public_price_on_shadow_on_both_sides_of_candle(self):
        candle = MarketCandle(
            open_price=Decimal('43800'),
            high_price=Decimal('49400'),
            low_price=Decimal('39860'),
            close_price=Decimal('42010'),
            price_upper_bound=Decimal(45300),
            price_lower_bound=Decimal(41200),
        )
        assert candle.public_open_price == candle.open_price
        assert candle.public_high_price == candle.price_upper_bound
        assert candle.public_low_price == candle.price_lower_bound
        assert candle.public_close_price == candle.close_price

    def test_public_price_on_candle_dramatic_range_up(self):
        candle = MarketCandle(
            open_price=Decimal('43800'),
            high_price=Decimal('49400'),
            low_price=Decimal('42860'),
            close_price=Decimal('48010'),
            price_upper_bound=Decimal(45300),
        )
        assert candle.public_open_price == candle.open_price
        assert candle.public_high_price == candle.price_upper_bound
        assert candle.public_low_price == candle.low_price
        assert candle.public_close_price == candle.price_upper_bound

    def test_public_price_on_candle_dramatic_range_down(self):
        candle = MarketCandle(
            open_price=Decimal('43800'),
            high_price=Decimal('44100'),
            low_price=Decimal('39860'),
            close_price=Decimal('40010'),
            price_lower_bound=Decimal(41200),
        )
        assert candle.public_open_price == candle.open_price
        assert candle.public_high_price == candle.high_price
        assert candle.public_low_price == candle.price_lower_bound
        assert candle.public_close_price == candle.price_lower_bound

    def setup_test_set_price_bounds(self):
        market = self.markets[0]
        dt = timezone.datetime.fromisoformat('2022-06-15T02:02:16.347892')
        resolution = MarketCandle.RESOLUTIONS.minute
        candles = [
            self.create_candle(
                market, resolution, dt - timezone.timedelta(minutes=3), 20900, 21850, 20450, 21850, '0.002', '42.6',
            ),
            self.create_candle(
                market, resolution, dt - timezone.timedelta(minutes=2), 21900, 22150, 21850, 22000, '0.003', '65.1',
            ),
            self.create_candle(
                market, resolution, dt - timezone.timedelta(minutes=1), 21400, 22750, 21050, 22500, '0.004', '89.8',
            ),
            self.create_candle(market, resolution, dt, 22600, 22600, 20750, 21030, '0.002', '44.8'),
        ]
        resolution = MarketCandle.RESOLUTIONS.hour
        candles += [
            self.create_candle(
                market, resolution, dt - timezone.timedelta(hours=1), 20900, 21850, 20450, 21850, '0.002', '42.6',
            ),
            self.create_candle(market, resolution, dt, 21900, 22750, 20750, 21030, '0.009', '199.7'),
            self.create_candle(market, MarketCandle.RESOLUTIONS.day, dt, 20900, 22750, 20450, 21030, '0.011', '242.3'),
        ]
        return candles

    def test_set_price_lower_bound_for_minute_candles(self):
        candles = self.setup_test_set_price_bounds()
        for candle in candles:
            assert not candle.price_upper_bound
            assert not candle.price_lower_bound

        MarketCandle.set_price_bounds(
            candles[0].market,
            MarketCandle.RESOLUTIONS.minute,
            candles[0].start_time,
            candles[3].end_time,
            upper_bound=None,
            lower_bound=20700,
        )
        for i, candle in enumerate(candles):
            candle.refresh_from_db()
            assert not candle.price_upper_bound
            assert candle.price_lower_bound == (20700 if i in (0, 4, 6) else None)

    def test_set_price_upper_bound_for_minute_candles(self):
        candles = self.setup_test_set_price_bounds()
        for candle in candles:
            assert not candle.price_upper_bound
            assert not candle.price_lower_bound

        MarketCandle.set_price_bounds(
            candles[0].market,
            MarketCandle.RESOLUTIONS.minute,
            candles[0].start_time,
            candles[3].end_time,
            upper_bound=22500,
            lower_bound=None,
        )
        for i, candle in enumerate(candles):
            candle.refresh_from_db()
            assert candle.price_upper_bound == (22500 if i in (2, 3, 5, 6) else None)
            assert not candle.price_lower_bound

    def test_set_price_both_bounds_for_minute_candles(self):
        candles = self.setup_test_set_price_bounds()
        for candle in candles:
            assert not candle.price_upper_bound
            assert not candle.price_lower_bound

        MarketCandle.set_price_bounds(
            candles[0].market,
            MarketCandle.RESOLUTIONS.minute,
            candles[0].start_time,
            candles[3].end_time,
            upper_bound=22500,
            lower_bound=20700,
        )
        for i, candle in enumerate(candles):
            candle.refresh_from_db()
            assert candle.price_upper_bound == (22500 if i in (2, 3, 5, 6) else None)
            assert candle.price_lower_bound == (20700 if i in (0, 4, 6) else None)

    def test_set_price_bounds_override_for_minute_candles(self):
        candles = self.setup_test_set_price_bounds()
        MarketCandle.set_price_bounds(
            candles[0].market,
            MarketCandle.RESOLUTIONS.minute,
            candles[0].start_time,
            candles[3].end_time,
            upper_bound=22500,
            lower_bound=20700,
        )

        MarketCandle.set_price_bounds(
            candles[0].market,
            MarketCandle.RESOLUTIONS.minute,
            candles[0].start_time,
            candles[3].end_time,
            upper_bound=None,
            lower_bound=21500,
        )
        for i, candle in enumerate(candles):
            candle.refresh_from_db()
            assert candle.price_upper_bound is None
            assert candle.price_lower_bound == (21500 if i != 1 else None)

    def test_set_price_bounds_partial_override_for_minute_candles(self):
        candles = self.setup_test_set_price_bounds()
        MarketCandle.set_price_bounds(
            candles[0].market,
            MarketCandle.RESOLUTIONS.minute,
            candles[0].start_time,
            candles[3].end_time,
            upper_bound=22500,
            lower_bound=20700,
        )

        MarketCandle.set_price_bounds(
            candles[2].market,
            MarketCandle.RESOLUTIONS.minute,
            candles[2].start_time,
            candles[3].end_time,
            upper_bound=22400,
            lower_bound=20900,
        )
        for i, candle in enumerate(candles):
            candle.refresh_from_db()
            assert candle.price_upper_bound == (22400 if i in (2, 3, 5, 6) else None)
            assert candle.price_lower_bound == (20700 if i in (0, 4, 6) else 20900 if i in (3, 5) else None)


class RecreateCandlesCommandTest(BaseMarketCandleTest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        dt = timezone.datetime.fromisoformat('2022-06-19T00:00:00+04:30')
        cls.trades = [
            cls.create_trade(cls.markets[0], dt - timezone.timedelta(days=1, hours=1, minutes=50), 22170, '0.001'),
            cls.create_trade(cls.markets[0], dt - timezone.timedelta(days=1, hours=1, minutes=45), 20590, '0.002'),
            cls.create_trade(cls.markets[0], dt - timezone.timedelta(hours=13, minutes=25, seconds=15), 22060, '0.003'),
            cls.create_trade(cls.markets[0], dt - timezone.timedelta(hours=13, minutes=20, seconds=40), 21540, '0.001'),
            cls.create_trade(cls.markets[0], dt - timezone.timedelta(hours=1, minutes=5, seconds=44), 21890, '0.002'),
            cls.create_trade(cls.markets[0], dt - timezone.timedelta(hours=1, minutes=5, seconds=11), 21550, '0.001'),
            cls.create_trade(cls.markets[0], dt - timezone.timedelta(minutes=23, seconds=35), 20970, '0.001'),
            cls.create_trade(cls.markets[0], dt - timezone.timedelta(minutes=8, seconds=15), 22250, '0.002'),
            cls.create_trade(cls.markets[0], dt - timezone.timedelta(minutes=3, seconds=35), 21030, '0.001'),
            cls.create_trade(cls.markets[0], dt - timezone.timedelta(minutes=3, seconds=15), 20750, '0.003'),
            cls.create_trade(cls.markets[0], dt - timezone.timedelta(seconds=20), 22600, '0.002'),
            cls.create_trade(cls.markets[0], dt - timezone.timedelta(seconds=10), 21150, '0.001'),

            cls.create_trade(cls.markets[1], dt - timezone.timedelta(minutes=8, seconds=30), 17850, '300'),
            cls.create_trade(cls.markets[1], dt - timezone.timedelta(minutes=8, seconds=10), 17960, '410'),
            cls.create_trade(cls.markets[1], dt - timezone.timedelta(seconds=30), 18020, '600'),
            cls.create_trade(cls.markets[1], dt - timezone.timedelta(seconds=10), 17930, '250'),
        ]
        cls.run_time = dt

    def setUp(self):
        UpdateMarketCandles.get_last_candle_before.cache_clear()
        UpdateMarketCandles.get_last_trade_price.cache_clear()
        UpdateMarketCandles.previous_round_data = {}
        UpdateMarketCandles.current_round_data = {}

    @pytest.mark.slow
    @patch('exchange.market.management.commands.recreate_candles.timezone.now')
    def test_first_run(self, now_mock: Mock):
        now_mock.return_value = self.run_time
        assert not MarketCandle.objects.exists()
        call_command('recreate_candles')
        assert not MarketCandle.objects.exclude(market__in=self.markets).exists()

        candles = MarketCandle.objects.filter(market=self.markets[0]).order_by('resolution', 'start_time')
        assert len(candles) == 1578

        # Check minute candles
        assert candles[0].resolution == MarketCandle.RESOLUTIONS.minute
        assert candles[0].high_price == candles[0].open_price == candles[0].low_price == candles[0].close_price == 22170
        assert candles[1].high_price == candles[1].low_price == candles[2].high_price == candles[2].low_price == 22170
        # ... skip candles[3..1547]
        assert candles[1548].high_price == candles[1548].low_price == 20750
        assert candles[1549].high_price == candles[1549].open_price == 22600
        assert candles[1549].low_price == candles[1549].close_price == 21150
        assert candles[1549].resolution == MarketCandle.RESOLUTIONS.minute

        # Check hour candles
        assert candles[1550].resolution == MarketCandle.RESOLUTIONS.hour
        assert candles[1550].high_price == candles[1550].open_price == 22170
        assert candles[1550].low_price == candles[1550].close_price == 20590
        assert candles[1551].low_price == candles[1551].high_price == 20590
        # ... skip candles[1552..1572]
        assert candles[1573].high_price == candles[1573].low_price == 21540
        assert candles[1574].high_price == candles[1574].open_price == 21890
        assert candles[1574].low_price == candles[1574].close_price == 21550
        assert candles[1575].open_price == 20970
        assert candles[1575].high_price == 22600
        assert candles[1575].low_price == 20750
        assert candles[1575].close_price == 21150
        assert candles[1575].resolution == MarketCandle.RESOLUTIONS.hour

        # Check day candles
        assert candles[1576].resolution == MarketCandle.RESOLUTIONS.day
        assert candles[1576].high_price == candles[1576].open_price == 22170
        assert candles[1576].low_price == candles[1576].close_price == 20590
        assert candles[1577].open_price == 22060
        assert candles[1577].high_price == 22600
        assert candles[1577].low_price == 20750
        assert candles[1577].close_price == 21150
        assert candles[1577].resolution == MarketCandle.RESOLUTIONS.day

        candles = MarketCandle.objects.filter(market=self.markets[1]).order_by('resolution', 'start_time')
        assert len(candles) == 11

        # Check minute candles
        assert candles[0].resolution == MarketCandle.RESOLUTIONS.minute
        assert candles[0].low_price == candles[0].open_price == 17850
        assert candles[0].high_price == candles[0].close_price == 17960
        assert candles[1].high_price == candles[1].low_price == candles[7].high_price == candles[7].low_price == 17960
        assert candles[8].high_price == candles[8].open_price == 18020
        assert candles[8].low_price == candles[8].close_price == 17930
        assert candles[8].resolution == MarketCandle.RESOLUTIONS.minute

        # Check hour and day candles
        assert candles[9].resolution == MarketCandle.RESOLUTIONS.hour
        assert candles[10].resolution == MarketCandle.RESOLUTIONS.day
        assert candles[9].open_price == candles[10].open_price == 17850
        assert candles[9].high_price == candles[10].high_price == 18020
        assert candles[9].low_price == candles[10].low_price == 17850
        assert candles[9].close_price == candles[10].close_price == 17930

    @pytest.mark.slow
    @patch('exchange.market.management.commands.recreate_candles.timezone.now')
    def test_second_run(self, now_mock: Mock):
        now_mock.return_value = self.run_time - timezone.timedelta(hours=1)
        for trade in self.trades[6:]:
            trade.delete()

        assert not MarketCandle.objects.exists()
        start = time.time()
        call_command('recreate_candles')
        first_run = time.time() - start

        candles = MarketCandle.objects.filter(market=self.markets[0]).order_by('resolution', 'start_time')
        assert len(candles) == 1517

        # Check minute candles
        assert candles[0].resolution == MarketCandle.RESOLUTIONS.minute
        assert candles[0].high_price == candles[0].open_price == candles[0].low_price == candles[0].close_price == 22170
        # ... skip candles[1..1488]
        assert candles[1489].low_price == candles[1489].close_price == 21550
        assert candles[1489].resolution == MarketCandle.RESOLUTIONS.minute

        # Check hour candles
        assert candles[1490].resolution == MarketCandle.RESOLUTIONS.hour
        assert candles[1490].high_price == candles[1490].open_price == 22170
        assert candles[1490].low_price == candles[1490].close_price == 20590
        # ... skip candles[1491..1513]
        assert candles[1514].high_price == candles[1514].open_price == 21890
        assert candles[1514].low_price == candles[1514].close_price == 21550
        assert candles[1514].resolution == MarketCandle.RESOLUTIONS.hour

        # Check day candles
        assert candles[1515].resolution == MarketCandle.RESOLUTIONS.day
        assert candles[1515].high_price == candles[1515].open_price == 22170
        assert candles[1515].low_price == candles[1515].close_price == 20590
        assert candles[1516].open_price == candles[1516].high_price == 22060
        assert candles[1516].low_price == 21540
        assert candles[1516].close_price == 21550
        assert candles[1516].resolution == MarketCandle.RESOLUTIONS.day

        candles = MarketCandle.objects.filter(market=self.markets[1])
        assert not candles

        # Second run
        now_mock.return_value = self.run_time
        for trade in self.trades[6:]:
            trade.save()

        start = time.time()
        call_command('recreate_candles')
        second_run = time.time() - start

        candles = MarketCandle.objects.filter(market=self.markets[0]).order_by('resolution', 'start_time')
        assert len(candles) == 1578

        # Check minute candles
        assert candles[0].resolution == MarketCandle.RESOLUTIONS.minute
        assert candles[1549].high_price == candles[1549].open_price == 22600
        assert candles[1549].low_price == candles[1549].close_price == 21150
        assert candles[1549].resolution == MarketCandle.RESOLUTIONS.minute

        # Check hour candles
        assert candles[1550].resolution == MarketCandle.RESOLUTIONS.hour
        assert candles[1575].open_price == 20970
        assert candles[1575].high_price == 22600
        assert candles[1575].low_price == 20750
        assert candles[1575].close_price == 21150
        assert candles[1575].resolution == MarketCandle.RESOLUTIONS.hour

        # Check day candles
        assert candles[1576].resolution == MarketCandle.RESOLUTIONS.day
        assert candles[1577].open_price == 22060
        assert candles[1577].high_price == 22600
        assert candles[1577].low_price == 20750
        assert candles[1577].close_price == 21150
        assert candles[1577].resolution == MarketCandle.RESOLUTIONS.day

        candles = MarketCandle.objects.filter(market=self.markets[1])
        assert len(candles) == 11

        assert first_run > second_run

    @patch('exchange.market.management.commands.recreate_candles.timezone.now')
    def test_run_for_older_than_minute_candles_start_time(self, now_mock: Mock):
        now_mock.return_value = self.run_time

        with patch(
            'exchange.market.management.commands.recreate_candles.Command.MINUTE_CANDLES_START_TIME',
            new=str(self.run_time - timezone.timedelta(hours=1)),
        ):
            call_command('recreate_candles')

        candles = MarketCandle.objects.filter(market=self.markets[0]).order_by('resolution', 'start_time')
        assert len(candles) == 88

        # Check minute candles
        assert candles[0].resolution == MarketCandle.RESOLUTIONS.minute
        assert candles[0].low_price == candles[0].close_price == 21550
        # ... skip candles[1..57]
        assert candles[58].high_price == candles[58].low_price == 20750
        assert candles[59].high_price == candles[59].open_price == 22600
        assert candles[59].low_price == candles[59].close_price == 21150
        assert candles[59].resolution == MarketCandle.RESOLUTIONS.minute

        # Check hour candles
        assert candles[60].resolution == MarketCandle.RESOLUTIONS.hour
        assert candles[60].high_price == candles[60].open_price == 22170
        assert candles[60].low_price == candles[60].close_price == 20590
        assert candles[61].low_price == candles[61].high_price == 20590
        # ... skip candles[62..84]
        assert candles[85].open_price == 20970
        assert candles[85].high_price == 22600
        assert candles[85].low_price == 20750
        assert candles[85].close_price == 21150
        assert candles[85].resolution == MarketCandle.RESOLUTIONS.hour

        # Check day candles
        assert candles[86].resolution == MarketCandle.RESOLUTIONS.day
        assert candles[86].high_price == candles[86].open_price == 22170
        assert candles[86].low_price == candles[86].close_price == 20590
        assert candles[87].open_price == 22060
        assert candles[87].high_price == 22600
        assert candles[87].low_price == 20750
        assert candles[87].close_price == 21150
        assert candles[87].resolution == MarketCandle.RESOLUTIONS.day

        candles = MarketCandle.objects.filter(market=self.markets[1]).order_by('resolution', 'start_time')
        assert len(candles) == 11

    @pytest.mark.slow
    @patch('exchange.market.management.commands.recreate_candles.timezone.now')
    def test_run_from_specific_start_date(self, now_mock: Mock):
        now_mock.return_value = self.run_time

        call_command('recreate_candles', start_date='2022-06-18')

        candles = MarketCandle.objects.filter(market=self.markets[0]).order_by('resolution', 'start_time')
        assert len(candles) == 1465

        # Check minute candles
        assert candles[0].resolution == MarketCandle.RESOLUTIONS.minute
        assert candles[0].low_price == candles[0].close_price == 20590
        # ... skip candles[1..1437]
        assert candles[1438].high_price == candles[1438].low_price == 20750
        assert candles[1439].high_price == candles[1439].open_price == 22600
        assert candles[1439].low_price == candles[1439].close_price == 21150
        assert candles[1439].resolution == MarketCandle.RESOLUTIONS.minute

        # Check hour candles
        assert candles[1440].resolution == MarketCandle.RESOLUTIONS.hour
        assert candles[1440].high_price == candles[1440].open_price == 20590
        # ... skip candles[1441..1462]
        assert candles[1463].open_price == 20970
        assert candles[1463].high_price == 22600
        assert candles[1463].low_price == 20750
        assert candles[1463].close_price == 21150
        assert candles[1463].resolution == MarketCandle.RESOLUTIONS.hour

        # Check day candles
        assert candles[1464].resolution == MarketCandle.RESOLUTIONS.day
        assert candles[1464].open_price == 22060
        assert candles[1464].high_price == 22600
        assert candles[1464].low_price == 20750
        assert candles[1464].close_price == 21150

        candles = MarketCandle.objects.filter(market=self.markets[1]).order_by('resolution', 'start_time')
        assert len(candles) == 11

    @patch('exchange.market.management.commands.recreate_candles.timezone.now')
    def test_run_for_specific_market(self, now_mock: Mock):
        now_mock.return_value = self.run_time

        assert not MarketCandle.objects.exists()

        call_command('recreate_candles', market=self.markets[1].symbol)

        assert not MarketCandle.objects.exclude(market=self.markets[1]).exists()
        assert MarketCandle.objects.count() == 11


class UpdateMarketCandlesTest(BaseMarketCandleTest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.test_time = timezone.datetime.fromisoformat('2022-06-19T00:00:00+04:30')

    def setUp(self):
        UpdateMarketCandles.get_last_candle_before.cache_clear()
        UpdateMarketCandles.get_last_trade_price.cache_clear()
        UpdateMarketCandles.previous_round_data = {}
        UpdateMarketCandles.current_round_data = {}

    def _setup_candle_update_service_data(self):
        dt = self.test_time
        trades = [
            self.create_trade(self.markets[0], dt - timezone.timedelta(hours=2, minutes=10), 22060, '0.003'),
            self.create_trade(self.markets[0], dt - timezone.timedelta(minutes=8), 21890, '0.002'),
            self.create_trade(self.markets[0], dt - timezone.timedelta(seconds=30), 22600, '0.001'),

            self.create_trade(self.markets[1], dt - timezone.timedelta(hours=1, minutes=3), 17960, '410'),
            self.create_trade(self.markets[1], dt - timezone.timedelta(minutes=25), 18020, '600'),
            self.create_trade(self.markets[1], dt - timezone.timedelta(seconds=40), 17930, '250'),
        ]
        with patch('exchange.market.management.commands.recreate_candles.timezone.now', return_value=dt):
            call_command('recreate_candles')
        return trades

    @staticmethod
    def _get_last_candles(market: Market):
        return {
            MarketCandle.get_resolution_key(resolution):
            MarketCandle.objects.filter(market=market, resolution=resolution).latest('start_time')
            for resolution, _ in MarketCandle.RESOLUTIONS
        }

    def test_create_minute_candle_in_market_with_no_trades(self):
        market = self.markets[0]
        dt = timezone.datetime.fromisoformat('2022-06-15T02:27:16.347892')
        assert not MarketCandle.objects.exists()
        candles = UpdateMarketCandles.update_time_candles([market], MarketCandle.RESOLUTIONS.minute, [dt]).get(market)
        assert not candles

    def test_create_minute_candle_in_market_with_one_trade(self):
        market = self.markets[0]
        dt = timezone.datetime.fromisoformat('2022-06-15T02:27:16.347892+04:30')
        trade = self.create_trade(market, dt - timezone.timedelta(seconds=12), Decimal('21150'), Decimal('0.001'))
        candles = UpdateMarketCandles.update_time_candles([market], MarketCandle.RESOLUTIONS.minute, [dt]).get(market)
        assert candles
        candle = candles[0]
        assert candle.open_price == candle.high_price == candle.low_price == candle.close_price == trade.matched_price
        assert candle.trade_amount == trade.matched_amount
        assert candle.trade_total == trade.matched_total_price
        assert candle.timestamp == 1655243820

    def test_create_minute_candle_in_market_with_multiple_trades(self):
        market = self.markets[0]
        dt = timezone.datetime.fromisoformat('2022-06-15T02:27:16.347892+04:30')
        first_trade = self.create_trade(market, dt - timezone.timedelta(seconds=15), 21150, Decimal('0.001'))
        highest_trade = self.create_trade(market, dt - timezone.timedelta(seconds=11), 22600, Decimal('0.001'))
        lowest_trade = self.create_trade(market, dt - timezone.timedelta(seconds=7), 20750, Decimal('0.001'))
        last_trade = self.create_trade(market, dt - timezone.timedelta(seconds=3), 21030, Decimal('0.001'))
        candles = UpdateMarketCandles.update_time_candles([market], MarketCandle.RESOLUTIONS.minute, [dt]).get(market)
        assert candles
        candle = candles[0]
        assert candle.open_price == first_trade.matched_price
        assert candle.high_price == highest_trade.matched_price
        assert candle.low_price == lowest_trade.matched_price
        assert candle.close_price == last_trade.matched_price
        assert candle.trade_amount == Decimal('0.004')
        assert candle.trade_total == Decimal('85.53')
        assert candle.timestamp == 1655243820

    def test_create_successive_minute_candle_in_market_with_no_trades_in_time_range(self):
        market = self.markets[0]
        resolution = MarketCandle.RESOLUTIONS.minute
        dt = timezone.datetime.fromisoformat('2022-06-15T02:27:16.347892+04:30')
        trade = self.create_trade(market, dt - timezone.timedelta(minutes=1), 21150, Decimal('0.001'))
        previous_candle = UpdateMarketCandles.update_time_candles([market], resolution, [trade.created_at]).get(market)
        assert previous_candle
        assert previous_candle[0].close_price == trade.matched_price
        assert MarketCandle.objects.exists()
        candles = UpdateMarketCandles.update_time_candles([market], resolution, [dt]).get(market)
        assert candles
        candle = candles[0]
        assert candle.open_price == candle.high_price == candle.low_price == candle.close_price == trade.matched_price
        assert candle.trade_amount == candle.trade_total == 0
        assert candle.timestamp == 1655243820

    def test_update_minute_candle_in_market_with_new_trades(self):
        market = self.markets[0]
        resolution = MarketCandle.RESOLUTIONS.minute
        dt = timezone.datetime.fromisoformat('2022-06-15T02:27:16.347892+04:30')
        first_trade = self.create_trade(market, dt - timezone.timedelta(seconds=12), 21150, Decimal('0.001'))
        second_trade = self.create_trade(market, dt - timezone.timedelta(seconds=6), 21030, Decimal('0.001'))
        candles = UpdateMarketCandles.update_time_candles([market], resolution, [dt]).get(market)
        assert candles
        candle = candles[0]
        assert candle.open_price == candle.high_price == first_trade.matched_price
        assert candle.close_price == candle.low_price == second_trade.matched_price
        assert candle.trade_amount == Decimal('0.002')
        assert candle.trade_total == Decimal('42.18')

        lowest_trade = self.create_trade(market, dt + timezone.timedelta(seconds=6), 20750, Decimal('0.001'))
        highest_trade = self.create_trade(market, dt + timezone.timedelta(seconds=12), 22600, Decimal('0.001'))
        dt += timezone.timedelta(seconds=18)
        updated_candles = UpdateMarketCandles.update_time_candles([market], resolution, [dt]).get(market)
        assert updated_candles
        updated_candle = updated_candles[0]
        assert (candle.resolution, candle.start_time, candle.market_id) == (
            updated_candle.resolution,
            updated_candle.start_time,
            updated_candle.market_id,
        )
        assert candle.timestamp == updated_candle.timestamp == 1655243820
        assert updated_candle.open_price == candle.open_price
        assert updated_candle.high_price == updated_candle.close_price == highest_trade.matched_price
        assert updated_candle.low_price == lowest_trade.matched_price
        assert updated_candle.trade_amount == Decimal('0.004')
        assert updated_candle.trade_total == Decimal('85.53')

    def test_update_successive_minute_candle_in_market_with_new_trades_in_time_range(self):
        market = self.markets[0]
        resolution = MarketCandle.RESOLUTIONS.minute
        dt = timezone.datetime.fromisoformat('2022-06-15T02:27:16.347892+04:30')
        trade = self.create_trade(market, dt - timezone.timedelta(minutes=1), 21150, Decimal('0.001'))
        UpdateMarketCandles.update_time_candles([market], MarketCandle.RESOLUTIONS.minute, [trade.created_at])
        UpdateMarketCandles.update_time_candles([market], MarketCandle.RESOLUTIONS.minute, [trade.created_at])
        candles = UpdateMarketCandles.update_time_candles([market], resolution, [dt]).get(market)
        assert candles
        candle = candles[0]
        assert candle.open_price == candle.high_price == candle.low_price == candle.close_price == trade.matched_price
        assert candle.trade_amount == candle.trade_total == 0

        new_trade = self.create_trade(market, dt, 22600, Decimal('0.001'))
        updated_candles = UpdateMarketCandles.update_time_candles([market], resolution, [new_trade.created_at]).get(
            market
        )
        updated_candle = updated_candles[0]
        assert (candle.resolution, candle.start_time, candle.market_id) == (
            updated_candle.resolution,
            updated_candle.start_time,
            updated_candle.market_id,
        )
        assert candle.timestamp == updated_candle.timestamp == 1655243820
        assert updated_candle.open_price == updated_candle.high_price == new_trade.matched_price
        assert updated_candle.low_price == updated_candle.close_price == new_trade.matched_price
        assert updated_candle.trade_amount == Decimal('0.001')
        assert updated_candle.trade_total == Decimal('22.6')

    def test_create_compound_candle_in_market_with_no_base_candles(self):
        market = self.markets[0]
        dt = timezone.datetime.fromisoformat('2022-06-15T02:27:16.347892')
        for resolution in (MarketCandle.RESOLUTIONS.day, MarketCandle.RESOLUTIONS.hour):
            assert not MarketCandle.objects.filter(resolution__lt=resolution).exists()
            candle = UpdateMarketCandles.update_time_candles([market], resolution, [dt]).get(market)
            assert not candle

    def test_create_compound_candle_in_market_with_one_base_candle(self):
        market = self.markets[0]
        dt = timezone.datetime.fromisoformat('2022-06-15T02:27:16.347892')
        resolution = MarketCandle.RESOLUTIONS.minute
        base_candle = self.create_candle(market, resolution, dt, 21150, 22600, 20750, 21030, '0.004', '85.53')
        for resolution in (MarketCandle.RESOLUTIONS.hour, MarketCandle.RESOLUTIONS.day):
            candle = UpdateMarketCandles.update_time_candles([market], resolution, [dt]).get(market)
            assert candle
            assert candle[0].open_price == base_candle.open_price
            assert candle[0].high_price == base_candle.high_price
            assert candle[0].low_price == base_candle.low_price
            assert candle[0].close_price == base_candle.close_price
            assert candle[0].trade_amount == base_candle.trade_amount
            assert candle[0].trade_total == base_candle.trade_total
            assert candle[0].timestamp == (1655235000 if resolution == MarketCandle.RESOLUTIONS.day else 1655242200)

    def test_create_hour_candle_in_market_with_multiple_minute_candles(self):
        market = self.markets[0]
        dt = timezone.datetime.fromisoformat('2022-06-15T02:27:16.347892')
        resolution = MarketCandle.RESOLUTIONS.minute
        candles = [
            self.create_candle(
                market, resolution, dt - timezone.timedelta(minutes=8), 21150, 21150, 20750, 21250, '0.003', '64.81',
            ),
            self.create_candle(market, resolution, dt, 22600, 22600, 20960, 21030, '0.004', '83.68'),
        ]
        candle = UpdateMarketCandles.update_time_candles([market], MarketCandle.RESOLUTIONS.hour, [dt]).get(market)
        assert candle
        assert candle[0].open_price == candles[0].open_price
        assert candle[0].high_price == candles[1].high_price
        assert candle[0].low_price == candles[0].low_price
        assert candle[0].close_price == candles[1].close_price
        assert candle[0].trade_amount == Decimal('0.007')
        assert candle[0].trade_total == Decimal('148.49')
        assert candle[0].timestamp == 1655242200

    def test_create_day_candle_in_market_with_multiple_hour_candles(self):
        market = self.markets[0]
        dt = timezone.datetime.fromisoformat('2022-06-15T02:27:16.347892')
        resolution = MarketCandle.RESOLUTIONS.hour
        candles = [
            self.create_candle(
                market, resolution, dt - timezone.timedelta(hours=1), 21400, 22750, 21050, 22500, '0.004', '87.7',
            ),
            self.create_candle(market, resolution, dt, 22600, 22600, 20750, 21030, '0.007', '148.49'),
        ]
        candle = UpdateMarketCandles.update_time_candles([market], MarketCandle.RESOLUTIONS.day, [dt]).get(market)
        assert candles
        assert candle[0].open_price == candles[0].open_price
        assert candle[0].high_price == candles[0].high_price
        assert candle[0].low_price == candles[1].low_price
        assert candle[0].close_price == candles[1].close_price
        assert candle[0].trade_amount == Decimal('0.011')
        assert candle[0].trade_total == Decimal('236.19')
        assert candle[0].timestamp == 1655235000

    @patch('exchange.base.publisher._get_client')
    def test_update_current_candles(self, mock_get_client):
        mock_redis_client = MagicMock()
        mock_pipeline = MagicMock()

        mock_get_client.return_value = mock_redis_client
        mock_redis_client.pipeline.return_value.__enter__.return_value = mock_pipeline

        self._setup_candle_update_service_data()
        last_candles = {market.symbol: self._get_last_candles(market) for market in self.markets}

        for resolution in ('minute', 'hour', 'day'):
            assert last_candles['BTCUSDT'][resolution].close_price == 22600
            assert last_candles['DOGEIRT'][resolution].close_price == 17930

        self.create_trade(self.markets[1], self.test_time - timezone.timedelta(seconds=20), 17850, '225')
        self.create_trade(self.markets[0], self.test_time - timezone.timedelta(seconds=10), 22400, '0.0005')
        self.create_trade(self.markets[0], self.test_time + timezone.timedelta(seconds=15), 22350, '0.001')
        self.create_trade(self.markets[1], self.test_time + timezone.timedelta(seconds=25), 17970, '400')
        cache_data_minute = {
            'time': [1655580000, 1655580060, 1655580120, 1655580180, 1655580240, 1655580300, 1655580360, 1655580420,
                     1655580480, 1655580540, 1655580600],
            'open': [22061.0, 22060.0, 21890.0, 21890.0, 21890.0, 21890.0, 21890.0, 21890.0, 21890.0, 22600.0, 22350.0],
            'high': [22064.0, 22060.0, 21890.0, 21890.0, 21890.0, 21890.0, 21890.0, 21890.0, 21890.0, 22600.0, 22350.0],
            'low': [22060.0, 22060.0, 21890.0, 21890.0, 21890.0, 21890.0, 21890.0, 21890.0, 21890.0, 22400.0, 22350.0],
            'close': [22065.0, 22060.0, 21890.0, 21890.0, 21890.0, 21890.0, 21890.0, 21890.0, 21890.0, 22400.0,
                      22350.0],
            'volume': [0.001, 0.0, 0.002, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0015, 0.001],
        }
        with patch('exchange.market.inspector.timezone.now', return_value=self.test_time):
            LongTermCandlesCache.cache().set('marketdata_BTCUSDT_minute_1655580000', cache_data_minute)

        UpdateMarketCandles.current_round_data = {}
        UpdateMarketCandles.previous_round_data = {}

        with patch('exchange.market.inspector.timezone.now', return_value=self.test_time):
            UpdateMarketCandles.run(self.test_time + timezone.timedelta(seconds=30))

        expected_calls = [
            call(
                channel='public:candle-BTCUSDT-1',
                message='{"t": 1655580540, "o": 22600.0, "h": 22600.0, "l": 22400.0, "c": 22400.0, "v": 0.0015}',
            ),
            call(
                channel='public:candle-BTCUSDT-1',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.001}',
            ),
            call(
                channel='public:candle-BTCUSDT-5',
                message='{"t": 1655580300, "o": 21890.0, "h": 22600.0, "l": 21890.0, "c": 22400.0, "v": 0.0015}',
            ),
            call(
                channel='public:candle-BTCUSDT-5',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.001}',
            ),
            call(
                channel='public:candle-BTCUSDT-15',
                message='{"t": 1655579700, "o": 22061.0, "h": 22600.0, "l": 21890.0, "c": 22350.0, "v": 0.0055}',
            ),
            call(
                channel='public:candle-BTCUSDT-15',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.001}',
            ),
            call(
                channel='public:candle-BTCUSDT-30',
                message='{"t": 1655578800, "o": 22061.0, "h": 22600.0, "l": 21890.0, "c": 22350.0, "v": 0.0055}',
            ),
            call(
                channel='public:candle-BTCUSDT-30',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.001}',
            ),
            call(
                channel='public:candle-BTCUSDT-60',
                message='{"t": 1655577000, "o": 21890.0, "h": 22600.0, "l": 21890.0, "c": 22400.0, "v": 0.0035}',
            ),
            call(
                channel='public:candle-BTCUSDT-60',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.001}',
            ),
            call(
                channel='public:candle-BTCUSDT-180',
                message='{"t": 1655569800, "o": 22060.0, "h": 22600.0, "l": 21890.0, "c": 22400.0, "v": 0.0065}',
            ),
            call(
                channel='public:candle-BTCUSDT-180',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.001}',
            ),
            call(
                channel='public:candle-BTCUSDT-240',
                message='{"t": 1655566200, "o": 22060.0, "h": 22600.0, "l": 21890.0, "c": 22350.0, "v": 0.0075}',
            ),
            call(
                channel='public:candle-BTCUSDT-240',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.001}',
            ),
            call(
                channel='public:candle-BTCUSDT-360',
                message='{"t": 1655559000, "o": 22060.0, "h": 22600.0, "l": 21890.0, "c": 22350.0, "v": 0.0075}',
            ),
            call(
                channel='public:candle-BTCUSDT-360',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.001}',
            ),
            call(
                channel='public:candle-BTCUSDT-720',
                message='{"t": 1655537400, "o": 22060.0, "h": 22600.0, "l": 21890.0, "c": 22350.0, "v": 0.0075}',
            ),
            call(
                channel='public:candle-BTCUSDT-720',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.001}',
            ),
            call(
                channel='public:candle-BTCUSDT-D',
                message='{"t": 1655494200, "o": 22060.0, "h": 22600.0, "l": 21890.0, "c": 22400.0, "v": 0.0065}',
            ),
            call(
                channel='public:candle-BTCUSDT-D',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.001}',
            ),
            call(
                channel='public:candle-BTCUSDT-1D',
                message='{"t": 1655494200, "o": 22060.0, "h": 22600.0, "l": 21890.0, "c": 22400.0, "v": 0.0065}',
            ),
            call(
                channel='public:candle-BTCUSDT-1D',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.001}',
            ),
            call(
                channel='public:candle-BTCUSDT-2D',
                message='{"t": 1655407800, "o": 22060.0, "h": 22600.0, "l": 21890.0, "c": 22350.0, "v": 0.0075}',
            ),
            call(
                channel='public:candle-BTCUSDT-2D',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.001}',
            ),
            call(
                channel='public:candle-BTCUSDT-3D',
                message='{"t": 1655494200, "o": 22060.0, "h": 22600.0, "l": 21890.0, "c": 22350.0, "v": 0.0075}',
            ),
            call(
                channel='public:candle-BTCUSDT-3D',
                message='{"t": 1655494200, "o": 22060.0, "h": 22600.0, "l": 21890.0, "c": 22350.0, "v": 0.0075}',
            ),
            call(
                channel='public:candle-DOGEIRT-60',
                message='{"t": 1655577000, "o": 1802.0, "h": 1802.0, "l": 1785.0, "c": 1785.0, "v": 1075.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-60',
                message='{"t": 1655580600, "o": 1797.0, "h": 1797.0, "l": 1797.0, "c": 1797.0, "v": 400.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-180',
                message='{"t": 1655569800, "o": 1796.0, "h": 1802.0, "l": 1785.0, "c": 1797.0, "v": 1885.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-180',
                message='{"t": 1655580600, "o": 1797.0, "h": 1797.0, "l": 1797.0, "c": 1797.0, "v": 400.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-240',
                message='{"t": 1655566200, "o": 1796.0, "h": 1802.0, "l": 1785.0, "c": 1797.0, "v": 1885.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-240',
                message='{"t": 1655580600, "o": 1797.0, "h": 1797.0, "l": 1797.0, "c": 1797.0, "v": 400.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-360',
                message='{"t": 1655559000, "o": 1796.0, "h": 1802.0, "l": 1785.0, "c": 1797.0, "v": 1885.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-360',
                message='{"t": 1655580600, "o": 1797.0, "h": 1797.0, "l": 1797.0, "c": 1797.0, "v": 400.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-720',
                message='{"t": 1655537400, "o": 1796.0, "h": 1802.0, "l": 1785.0, "c": 1797.0, "v": 1885.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-720',
                message='{"t": 1655580600, "o": 1797.0, "h": 1797.0, "l": 1797.0, "c": 1797.0, "v": 400.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-D',
                message='{"t": 1655494200, "o": 1796.0, "h": 1802.0, "l": 1785.0, "c": 1785.0, "v": 1485.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-D',
                message='{"t": 1655580600, "o": 1797.0, "h": 1797.0, "l": 1797.0, "c": 1797.0, "v": 400.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-1D',
                message='{"t": 1655494200, "o": 1796.0, "h": 1802.0, "l": 1785.0, "c": 1785.0, "v": 1485.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-1D',
                message='{"t": 1655580600, "o": 1797.0, "h": 1797.0, "l": 1797.0, "c": 1797.0, "v": 400.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-2D',
                message='{"t": 1655407800, "o": 1796.0, "h": 1802.0, "l": 1785.0, "c": 1797.0, "v": 1885.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-2D',
                message='{"t": 1655580600, "o": 1797.0, "h": 1797.0, "l": 1797.0, "c": 1797.0, "v": 400.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-3D',
                message='{"t": 1655494200, "o": 1796.0, "h": 1802.0, "l": 1785.0, "c": 1797.0, "v": 1885.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-3D',
                message='{"t": 1655494200, "o": 1796.0, "h": 1802.0, "l": 1785.0, "c": 1797.0, "v": 1885.0}',
            ),
        ]

        mock_pipeline.publish.assert_has_calls(expected_calls, any_order=True)

        mock_pipeline.execute.assert_called_once()

        for market_last_candles in last_candles.values():
            for last_candle in market_last_candles.values():
                last_candle.refresh_from_db()

        for resolution in ('minute', 'hour', 'day'):
            assert last_candles['BTCUSDT'][resolution].close_price == 22400
            assert last_candles['DOGEIRT'][resolution].close_price == 17850

        new_last_candles = {market.symbol: self._get_last_candles(market) for market in self.markets}

        for resolution in ('minute', 'hour', 'day'):
            assert new_last_candles['BTCUSDT'][resolution].close_price == 22350
            assert new_last_candles['DOGEIRT'][resolution].close_price == 17970


    def test_update_volatile_recent_minute_candles(self):
        self._setup_candle_update_service_data()
        last_candles = list(MarketCandle.objects.filter(
            market=self.markets[0], resolution=MarketCandle.RESOLUTIONS.minute,
        ).order_by('-start_time')[:4])

        assert last_candles[0].close_price == 22600
        assert last_candles[3].close_price == 21890

        assert UpdateMarketCandles.MINUTES_TO_RECALCULATE > 4
        self.create_trade(self.markets[0], self.test_time - timezone.timedelta(minutes=4), 22400, '0.0005')
        self.create_trade(self.markets[0], self.test_time + timezone.timedelta(seconds=15), 22350, '0.001')

        UpdateMarketCandles.run(self.test_time + timezone.timedelta(seconds=10))

        last_candles = list(MarketCandle.objects.filter(
            market=self.markets[0], resolution=MarketCandle.RESOLUTIONS.minute,
        ).order_by('-start_time')[:5])

        assert last_candles[0].close_price == 22350
        assert last_candles[1].close_price == 22600
        assert last_candles[4].close_price == 22400

    @patch('exchange.base.publisher._get_client')
    def test_update_cache_minute_candles(self, mock_get_client):
        mock_redis_client = MagicMock()
        mock_pipeline = MagicMock()

        mock_get_client.return_value = mock_redis_client
        mock_redis_client.pipeline.return_value.__enter__.return_value = mock_pipeline

        self._setup_candle_update_service_data()
        market = self.markets[0]
        resolution = MarketCandle.RESOLUTIONS.minute
        UpdateMarketCandles.clear_caches(self.markets, resolution)

        cache_key = 'marketdata_BTCUSDT_minute_short'
        assert cache_key not in cache

        self.create_trade(market, self.test_time - timezone.timedelta(minutes=4), 22400, '0.0005')
        self.create_trade(market, self.test_time - timezone.timedelta(seconds=15), 22350, '0.001')
        UpdateMarketCandles.run(self.test_time)

        cache_value = cache.get(cache_key)
        assert cache_value == {
            'time': [1655580060 + 60 * i for i in range(10)],
            'open': [22060, 21890, 21890, 21890, 21890, 22400, 22400, 22400, 22600, 22350],
            'high': [22060, 21890, 21890, 21890, 21890, 22400, 22400, 22400, 22600, 22350],
            'low': [22060, 21890, 21890, 21890, 21890, 22400, 22400, 22400, 22350, 22350],
            'close': [22060, 21890, 21890, 21890, 21890, 22400, 22400, 22400, 22350, 22350],
            'volume': [0, 0.002, 0, 0, 0, 0.0005, 0, 0, 0.002, 0],
        }

        expected_calls = [
            call(
                channel='public:candle-BTCUSDT-D',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.0}',
            ),
            call(
                channel='public:candle-BTCUSDT-1D',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.0}',
            ),
            call(
                channel='public:candle-BTCUSDT-2D',
                message='{"t": 1655580600, "o": 22350.0, "h": 22350.0, "l": 22350.0, "c": 22350.0, "v": 0.0}',
            ),
            call(
                channel='public:candle-BTCUSDT-3D',
                message='{"t": 1655494200, "o": 22060.0, "h": 22600.0, "l": 21890.0, "c": 22350.0, "v": 0.0075}',
            ),
            call(
                channel='public:candle-DOGEIRT-D',
                message='{"t": 1655580600, "o": 1793.0, "h": 1793.0, "l": 1793.0, "c": 1793.0, "v": 0.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-1D',
                message='{"t": 1655580600, "o": 1793.0, "h": 1793.0, "l": 1793.0, "c": 1793.0, "v": 0.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-2D',
                message='{"t": 1655580600, "o": 1793.0, "h": 1793.0, "l": 1793.0, "c": 1793.0, "v": 0.0}',
            ),
            call(
                channel='public:candle-DOGEIRT-3D',
                message='{"t": 1655494200, "o": 1796.0, "h": 1802.0, "l": 1793.0, "c": 1793.0, "v": 1260.0}',
            ),
        ]

        mock_pipeline.publish.assert_has_calls(expected_calls, any_order=True)

        mock_pipeline.execute.assert_called_once()


class CandlesCacheTest(BaseMarketCandleTest):
    dt: datetime.datetime

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dt = timezone.datetime.fromisoformat('2022-07-04T00:00:00+04:30')
        market = cls.markets[0]
        resolution = MarketCandle.RESOLUTIONS.minute
        cls.candles = [
            cls.create_candle(
                market, resolution, cls.dt - timezone.timedelta(minutes=3), 20900, 21850, 20450, 21850, '0.002', '42.6',
            ),
            cls.create_candle(
                market, resolution, cls.dt - timezone.timedelta(minutes=2), 21900, 22150, 21850, 22000, '0.003', '65.1',
            ),
            cls.create_candle(
                market, resolution, cls.dt - timezone.timedelta(minutes=1), 21400, 22750, 21050, 22500, '0.004', '89.8',
            ),
            cls.create_candle(market, resolution, cls.dt, 22600, 22600, 20750, 21030, '0.002', '44.8'),
        ]

        cls.cache_data = {
            'time': [1656876420, 1656876480, 1656876540, 1656876600],
            'open': [20900, 21900, 21400, 22600],
            'high': [21850, 22150, 22750, 22600],
            'low': [20450, 21850, 21050, 20750],
            'close': [21850, 22000, 22500, 21030],
            'volume': [0.002, 0.003, 0.004, 0.002],
        }
        cls.short_cache_key = 'marketdata_BTCUSDT_minute_short'
        cls.long_cache_key = 'marketdata_BTCUSDT_minute_1656876000'

    def setUp(self):
        LongTermCandlesCache.get_bucket.cache_clear()

    def test_update_candle_cache_with_overlap(self):
        market = self.markets[0]
        resolution = MarketCandle.RESOLUTIONS.minute
        cache.set(self.short_cache_key, self.cache_data)
        cache.set(self.long_cache_key, self.cache_data)

        MarketCandle.objects.filter(pk=self.candles[-1].pk).update(close_price=22010, trade_amount='0.003')
        last_candle = MarketCandle.objects.get(pk=self.candles[-1].pk)
        candle = self.create_candle(
            market, resolution, self.dt + timezone.timedelta(minutes=1), 22300, 22600, 21900, 22100, '0.001', '22.4',
        )
        with patch('exchange.market.inspector.timezone.now', return_value=self.dt):
            UpdateMarketCandles.update_caches({market: [last_candle, candle]})

        expected_value = {
            'time': [1656876420, 1656876480, 1656876540, 1656876600, 1656876660],
            'open': [20900, 21900, 21400, 22600, 22300],
            'high': [21850, 22150, 22750, 22600, 22600],
            'low': [20450, 21850, 21050, 20750, 21900],
            'close': [21850, 22000, 22500, 22010, 22100],
            'volume': [0.002, 0.003, 0.004, 0.003, 0.001],
        }
        cache_value = cache.get(self.short_cache_key)
        assert cache_value == expected_value
        cache_value = cache.get(self.long_cache_key)
        assert cache_value == expected_value

    @patch('exchange.market.inspector.timezone.now')
    def test_update_candle_cache_with_gap(self, mock_timezone):
        mock_timezone.return_value = timezone.datetime.fromisoformat('2022-07-04T00:00:00+04:30')
        market = self.markets[0]
        resolution = MarketCandle.RESOLUTIONS.minute
        cache.set(self.short_cache_key, self.cache_data)
        cache.set(self.long_cache_key, self.cache_data)

        MarketCandle.objects.filter(pk=self.candles[-2].pk).update(
            close_price=22550, high_price=22800, trade_amount='0.005',
        )
        self.create_candle(
            market, resolution, self.dt + timezone.timedelta(minutes=1), 22300, 22600, 21900, 22100, '0.002', '43.7',
        )
        candle = self.create_candle(
            market, resolution, self.dt + timezone.timedelta(minutes=2), 22140, 22300, 21700, 22300, '0.001', '22.1',
        )

        UpdateMarketCandles.update_caches({market: [candle]})

        expected_value = {
            'time': [1656876420, 1656876480, 1656876540, 1656876600, 1656876660, 1656876720],
            'open': [20900, 21900, 21400, 22600, 22300, 22140],
            'high': [21850, 22150, 22800, 22600, 22600, 22300],
            'low': [20450, 21850, 21050, 20750, 21900, 21700],
            'close': [21850, 22000, 22550, 21030, 22100, 22300],
            'volume': [0.002, 0.003, 0.005, 0.002, 0.002, 0.001],
        }
        cache_value = cache.get(self.short_cache_key)
        assert cache_value == expected_value
        cache_value = cache.get(self.long_cache_key)
        assert cache_value == expected_value

    @patch.object(ShortTermCandlesCache, 'CACHE_SIZE', 5)
    def test_update_short_term_cache_with_overflow(self):
        market = self.markets[0]
        resolution = MarketCandle.RESOLUTIONS.minute
        cache.set(self.short_cache_key, self.cache_data)

        candles = [
            self.candles[-1],
            self.create_candle(
                market, resolution, self.dt + timezone.timedelta(minutes=1), 22300, 22600, 21900, 22100, '0.002',
                '43.7',
            ),
            self.create_candle(
                market, resolution, self.dt + timezone.timedelta(minutes=2), 22140, 22300, 21700, 22300, '0.001',
                '22.1',
            ),
        ]

        ShortTermCandlesCache.update_cache(candles)

        cache_value = cache.get(self.short_cache_key)
        assert cache_value == {
            'time': [1656876480, 1656876540, 1656876600, 1656876660, 1656876720],
            'open': [21900, 21400, 22600, 22300, 22140],
            'high': [22150, 22750, 22600, 22600, 22300],
            'low': [21850, 21050, 20750, 21900, 21700],
            'close': [22000, 22500, 21030, 22100, 22300],
            'volume': [0.003, 0.004, 0.002, 0.002, 0.001],
        }

    @patch.object(LongTermCandlesCache, 'CACHE_SIZE', 20)
    @patch('exchange.market.inspector.timezone.now')
    def test_update_long_term_cache_with_overflow(self, mock_timezone):
        mock_timezone.return_value = timezone.datetime.fromisoformat('2022-07-04T01:00:00+04:30')
        market = self.markets[0]
        resolution = MarketCandle.RESOLUTIONS.minute
        cache.set(self.long_cache_key, self.cache_data)

        candles = [
            self.candles[-1],
            self.create_candle(
                market, resolution, self.dt + timezone.timedelta(minutes=1), 22300, 22600, 21900, 22100, '0.002', '43',
            ),
            self.create_candle(
                market, resolution, self.dt + timezone.timedelta(minutes=10), 22140, 22300, 21700, 22300, '0.001', '22',
            ),
        ]

        LongTermCandlesCache.update_cache(candles)

        cache_value = cache.get(self.long_cache_key)
        assert cache_value == {
            'time': [1656876420, 1656876480, 1656876540, 1656876600, 1656876660],
            'open': [20900, 21900, 21400, 22600, 22300],
            'high': [21850, 22150, 22750, 22600, 22600],
            'low': [20450, 21850, 21050, 20750, 21900],
            'close': [21850, 22000, 22500, 21030, 22100],
            'volume': [0.002, 0.003, 0.004, 0.002, 0.002],
        }
        cache_value = cache.get('marketdata_BTCUSDT_minute_1656877200')
        assert cache_value == {
            'time': [1656877200],
            'open': [22140],
            'high': [22300],
            'low': [21700],
            'close': [22300],
            'volume': [0.001],
        }

    def test_clear_short_term_cache(self):
        cache.set(self.short_cache_key, self.cache_data)
        ShortTermCandlesCache.clear_cache(self.markets[0], MarketCandle.RESOLUTIONS.minute)
        assert self.short_cache_key not in cache

    def test_clear_long_term_cache(self):
        market = self.markets[0]
        resolution = MarketCandle.RESOLUTIONS.minute
        cache_keys = ['marketdata_BTCUSDT_minute_1656864000', self.long_cache_key]
        self.create_candle(
            market, resolution, self.dt - timezone.timedelta(minutes=11), 22300, 22600, 21900, 22100, '0.002', '43.7',
        )
        for cache_key in cache_keys:
            cache.set(cache_key, self.cache_data)
        LongTermCandlesCache.clear_cache(self.markets[0], MarketCandle.RESOLUTIONS.minute)
        for cache_key in cache_keys:
            assert cache_key not in cache

    def test_initialize_short_term_cache(self):
        cache.delete(self.short_cache_key)
        ShortTermCandlesCache.initialize_data(self.markets[0], MarketCandle.RESOLUTIONS.minute)
        assert self.cache_data == cache.get(self.short_cache_key)

    @patch('exchange.market.inspector.timezone.now')
    def test_initialize_long_term_cache(self, mock_timezone):
        mock_timezone.return_value = timezone.datetime.fromisoformat('2022-07-04T00:00:00+04:30')

        market = self.markets[0]
        resolution = MarketCandle.RESOLUTIONS.minute
        self.create_candle(
            market, resolution, self.dt - timezone.timedelta(minutes=11), 22300, 22600, 21900, 22100, '0.002', '43.7',
        )
        previous_long_cache_key = 'marketdata_BTCUSDT_minute_1656864000'
        cache.delete(self.long_cache_key)
        cache.delete(previous_long_cache_key)
        with patch('exchange.market.tasks.init_candles_cache.delay', new=init_candles_cache):  # run celery in thread
            LongTermCandlesCache.initialize_data(self.markets[0], MarketCandle.RESOLUTIONS.minute)
        assert self.cache_data == cache.get(self.long_cache_key)
        assert cache.get(previous_long_cache_key)


class FillAndClearCandleCacheCommand(BaseMarketCandleTest):
    dt: datetime.datetime

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        dt = timezone.datetime.fromisoformat('2022-06-19T00:00:00+04:30')
        cls.trades = [
            cls.create_trade(cls.markets[1], dt - timezone.timedelta(minutes=8, seconds=30), 17850, '300'),
            cls.create_trade(cls.markets[1], dt - timezone.timedelta(minutes=8, seconds=10), 17960, '410'),
            cls.create_trade(cls.markets[1], dt - timezone.timedelta(seconds=30), 18020, '600'),
            cls.create_trade(cls.markets[1], dt - timezone.timedelta(seconds=10), 17930, '250'),
        ]
        cls.run_time = dt

    def setUp(self):
        UpdateMarketCandles.current_round_data = {}
        UpdateMarketCandles.previous_round_data = {}

    @patch('django.utils.timezone.now')
    def test_fill_for_specific_market(self, now_mock: Mock):
        now_mock.return_value = self.run_time
        LongTermCandlesCacheChartAPI.KEEP_HISTORY_FOR_DAYS = 400 * 60
        assert not MarketCandle.objects.exists()

        call_command('recreate_candles', market=self.markets[1].symbol)
        assert MarketCandle.objects.count() == 11

        assert not LongTermCandlesCacheChartAPI.cache().get('marketdata_DOGEIRT_minute_1655580000')
        call_command('fill_cache_candle_buckets', market=self.markets[1].symbol)
        assert LongTermCandlesCacheChartAPI.cache().get('marketdata_DOGEIRT_minute_1655580000')

    @patch('django.utils.timezone.now')
    def test_clear_for_specific_market(self, now_mock: Mock):
        now_mock.return_value = self.run_time
        LongTermCandlesCacheChartAPI.KEEP_HISTORY_FOR_DAYS = 400 * 60
        assert not MarketCandle.objects.exists()

        call_command('recreate_candles', market=self.markets[1].symbol)
        assert MarketCandle.objects.count() == 11

        assert not LongTermCandlesCacheChartAPI.cache().get('marketdata_DOGEIRT_minute_1655580000')
        call_command('fill_cache_candle_buckets', market=self.markets[1].symbol)
        assert LongTermCandlesCacheChartAPI.cache().get('marketdata_DOGEIRT_minute_1655580000')

        call_command(
            'remove_candles_caches',
            cache='chart_api',
            market=self.markets[1].symbol,
            datetime='2022-06-18-00:00',
            resolution='minute',
        )

        assert LongTermCandlesCacheChartAPI.cache().get('marketdata_DOGEIRT_minute_1655580000')

        call_command(
            'remove_candles_caches',
            cache='chart_api',
            market=self.markets[1].symbol,
            datetime='2022-06-19-00:00',
            resolution='minute',
        )
        assert not LongTermCandlesCacheChartAPI.cache().get('marketdata_DOGEIRT_minute_1655580000')


class CandlePublisherTest(TestCase):

    def setUp(self):
        self.test_dt = timezone.datetime.fromisoformat('2024-11-03 14:06:20.884565')
        UpdateMarketCandles.current_round_data = {}
        UpdateMarketCandles.previous_round_data = {}

    @staticmethod
    def _normalize_data(symbol, expected_calls):
        for data in expected_calls:
            is_rial = Market.by_symbol(symbol).dst_currency == Currencies.rls
            precision = -PRICE_PRECISIONS.get(symbol, Decimal('1e-2')).adjusted()
            for key in ('o', 'h', 'l', 'c'):
                data['message'][key] = round(data['message'][key], precision)
                if is_rial:
                    data['message'][key] /= 10
                data['message']['v'] = round(data['message']['v'], 8)
            data['message'] = json.dumps(data['message'])

        expected_calls = [call(**data) for data in expected_calls]

        return expected_calls

    def _assert_daily_candles_published_data(self, cache_data, symbol, mock_pipeline):
        t = [1730579400, 1730579400, 1730406600]

        expected_calls = [
            {
                'channel': f'public:candle-{symbol}-D',
                'message': {
                    't': t[0],
                    'o': cache_data['open'][-1],
                    'h': max(cache_data['high'][-1:]),
                    'l': min(cache_data['low'][-1:]),
                    'c': cache_data['close'][-1],
                    'v': sum(cache_data['volume'][-1:]),
                },
            },
            {
                'channel': f'public:candle-{symbol}-1D',
                'message': {
                    't': t[0],
                    'o': cache_data['open'][-1],
                    'h': max(cache_data['high'][-1:]),
                    'l': min(cache_data['low'][-1:]),
                    'c': cache_data['close'][-1],
                    'v': sum(cache_data['volume'][-1:]),
                },
            },
            {
                'channel': f'public:candle-{symbol}-2D',
                'message': {
                    't': t[1],
                    'o': cache_data['open'][-1],
                    'h': max(cache_data['high'][-1:]),
                    'l': min(cache_data['low'][-1:]),
                    'c': cache_data['close'][-1],
                    'v': sum(cache_data['volume'][-1:]),
                },
            },
            {
                'channel': f'public:candle-{symbol}-3D',
                'message': {
                    't': t[2],
                    'o': cache_data['open'][-3],
                    'h': max(cache_data['high'][-3:]),
                    'l': min(cache_data['low'][-3:]),
                    'c': cache_data['close'][-1],
                    'v': sum(cache_data['volume'][-3:]),
                },
            },
        ]

        expected_calls = self._normalize_data(symbol, expected_calls)

        mock_pipeline.publish.assert_has_calls(expected_calls, any_order=True)

        mock_pipeline.execute.assert_called_once()

    def _assert_minute_candles_published_data(self, test_dt, cache_data, symbol, mock_pipeline):
        resolutions = (1, 5, 15, 30)

        convert_to_time_stamp = lambda i: int(
            test_dt.timestamp() - test_dt.timestamp() % timedelta(minutes=i).total_seconds())

        resolution_to_index = {r:cache_data['time'].index(convert_to_time_stamp(r)) for r in resolutions}

        expected_calls = []
        for factor in resolutions:
            from_index = resolution_to_index[factor]
            to_index = min(resolution_to_index[factor] + factor, len(cache_data['time']))
            data = {
                'channel': f'public:candle-{symbol}-{factor}',
                'message': {
                    't': convert_to_time_stamp(factor),
                    'o': cache_data["open"][from_index],
                    'h': max(cache_data["high"][from_index:to_index]),
                    'l': min(cache_data["low"][from_index:to_index]),
                    'c': cache_data["close"][to_index - 1],
                    'v': sum(cache_data["volume"][from_index:to_index]),
                },
            }
            expected_calls.append(data)
        expected_calls = self._normalize_data(symbol, expected_calls)

        mock_pipeline.publish.assert_has_calls(expected_calls, any_order=True)
        mock_pipeline.execute.assert_called_once()

    @staticmethod
    def _generate_candles_data(start_timestamp, num_intervals=20, base_price=68000, volume_range=(0.001, 0.05)):
        data = {
            'time': [start_timestamp + factor * 60 for factor in range(num_intervals)],
            'open': [],
            'high': [],
            'low': [],
            'close': [],
            'volume': []
        }

        current_price = base_price
        for _ in range(num_intervals):
            open_price = current_price
            high_price = open_price + random.uniform(0, 50)
            low_price = open_price - random.uniform(0, 50)
            close_price = low_price + random.uniform(0, high_price - low_price)
            volume = round(random.uniform(*volume_range), 10)

            data['open'].append(round(open_price, 2))
            data['high'].append(round(high_price, 2))
            data['low'].append(round(low_price, 2))
            data['close'].append(round(close_price, 2))
            data['volume'].append(volume)
            current_price = close_price

        return data

    @patch('exchange.base.publisher._get_client')
    def test_minute_candles(self, mock_get_client):
        mock_redis_client = MagicMock()
        mock_pipeline = MagicMock()

        mock_get_client.return_value = mock_redis_client
        mock_redis_client.pipeline.return_value.__enter__.return_value = mock_pipeline

        # BTCUSDT, DOGEIRT
        markets = Market.objects.filter(Q(src_currency=10, dst_currency=13)| Q(src_currency=18, dst_currency=2))

        start_timestamp = 1730784000
        btc_cache_data = self._generate_candles_data(start_timestamp, base_price=68000, num_intervals=117)
        doge_cache_data = self._generate_candles_data(start_timestamp, base_price=9723, num_intervals=117)

        LongTermCandlesCache.cache().set(f'marketdata_BTCUSDT_minute_{start_timestamp}', btc_cache_data)
        LongTermCandlesCache.cache().set(f'marketdata_DOGEIRT_minute_{start_timestamp}', doge_cache_data)

        test_dt = timezone.datetime.fromisoformat('2024-11-05 10:46:24.884565+03:30')

        to_be_published_data = UpdateMarketCandles.get_to_be_published_data(markets, [(1, [test_dt])])
        UpdateMarketCandles.publish_candles(to_be_published_data)

        self._assert_minute_candles_published_data(test_dt, btc_cache_data, 'BTCUSDT', mock_pipeline)
        self._assert_minute_candles_published_data(test_dt, doge_cache_data, 'DOGEIRT', mock_pipeline)

    @patch('exchange.base.publisher._get_client')
    def test_missing_minute_candles(self, mock_get_client):
        mock_redis_client = MagicMock()
        mock_pipeline = MagicMock()

        mock_get_client.return_value = mock_redis_client
        mock_redis_client.pipeline.return_value.__enter__.return_value = mock_pipeline

        # BTCUSDT, DOGEIRT
        markets = Market.objects.filter(Q(src_currency=10, dst_currency=13) | Q(src_currency=18, dst_currency=2))

        start_timestamp = 1730784000
        btc_cache_data = self._generate_candles_data(start_timestamp, base_price=68000, num_intervals=71)
        doge_cache_data = self._generate_candles_data(start_timestamp, base_price=9723, num_intervals=71)
        LongTermCandlesCache.cache().set(f'marketdata_BTCUSDT_minute_{start_timestamp}', btc_cache_data)
        LongTermCandlesCache.cache().set(f'marketdata_DOGEIRT_minute_{start_timestamp}', doge_cache_data)

        test_dt2 = timezone.datetime.fromisoformat('2024-11-05 10:00:53.884565+03:30')
        test_dt1 = test_dt2 - timedelta(minutes=1)

        start_time = MarketCandle.get_start_time(test_dt1, 1)
        for market in markets:
            key = (market.id, 1, start_time)
            UpdateMarketCandles.current_round_data[key] = {'test_key': 'test_value'}

        to_be_published_data = UpdateMarketCandles.get_to_be_published_data(markets, [(1, [test_dt1, test_dt2])])
        UpdateMarketCandles.publish_candles(to_be_published_data)

        self._assert_minute_candles_published_data(test_dt1, btc_cache_data, 'BTCUSDT', mock_pipeline)
        self._assert_minute_candles_published_data(test_dt2, btc_cache_data, 'BTCUSDT', mock_pipeline)
        self._assert_minute_candles_published_data(test_dt2, doge_cache_data, 'DOGEIRT', mock_pipeline)
        self._assert_minute_candles_published_data(test_dt2, doge_cache_data, 'DOGEIRT', mock_pipeline)

    @patch('exchange.base.publisher._get_client')
    def test_daily_candles(self, mock_get_client):
        mock_redis_client = MagicMock()
        mock_pipeline = MagicMock()

        mock_get_client.return_value = mock_redis_client
        mock_redis_client.pipeline.return_value.__enter__.return_value = mock_pipeline

        # BTCUSDT, DOGEIRT
        markets = Market.objects.filter(Q(src_currency=10, dst_currency=13) | Q(src_currency=18, dst_currency=2))

        btc_cache_data = {
            'time': [1729801800, 1729888200, 1729974600, 1730061000, 1730147400, 1730233800, 1730320200, 1730406600,
                     1730493000, 1730579400],
            'open': [67890.0, 66368.83, 67209.0, 67700.0, 69076.0, 71479.32, 71798.97, 69966.0, 69465.82, 69219.99],
            'high': [68390.0, 67248.9, 67799.0, 69400.0, 73000.0, 72499.99, 72496.0, 71600.0, 69904.99, 69248.99],
            'low': [65727.37, 65502.74, 66700.01, 67250.0, 68600.0, 71057.49, 69799.0, 68800.0, 68908.0, 67400.0],
            'close': [66112.0, 67209.0, 67700.0, 69080.01, 71500.0, 71798.98, 69966.0, 69465.98, 69180.0, 68624.97],
            'volume': [27.5793885248, 24.7207661043, 7.5821136065, 26.435996808, 68.6558450532, 20.9914040869,
                       26.9866710232, 38.1432814161, 14.2643929295, 27.5060541018],
        }

        doge_cache_data = {
            'time': [1729801800, 1729888200, 1729974600, 1730061000, 1730147400, 1730233800, 1730320200, 1730406600,
                     1730493000, 1730579400],
            'open': [9723.0, 9160.4, 9088.0, 9484.0, 10610.0, 11412.0, 11627.9, 11022.2, 11180.4, 11126.0],
            'high': [9820.0, 9310.0, 9642.0, 10950.0, 12300.0, 12274.0, 11928.0, 11740.0, 11359.9, 11196.9],
            'low': [9053.0, 8500.0, 8956.6, 9440.0, 10560.0, 11400.0, 11000.0, 10660.0, 10820.0, 10450.0],
            'close': [9160.4, 9088.0, 9484.0, 10635.0, 11412.0, 11588.0, 11080.0, 11199.0, 11125.5, 10616.3],
            'volume': [14297589.758212058, 16094334.506766533, 10516208.89804325, 33971744.57779698, 47103887.56239172,
                       24472236.782816123, 19348118.732016426, 25843042.314511634, 11773937.945343558,
                       7637268.457211587],
        }

        ShortTermCandlesCache.cache().set('marketdata_BTCUSDT_day_short', btc_cache_data)
        ShortTermCandlesCache.cache().set('marketdata_DOGEIRT_day_short', doge_cache_data)

        test_dt = timezone.datetime.fromisoformat('2024-11-03 14:06:20.884565')

        to_be_published_data = UpdateMarketCandles.get_to_be_published_data(markets, [(3, [test_dt])])
        UpdateMarketCandles.publish_candles(to_be_published_data)

        self._assert_daily_candles_published_data(btc_cache_data, 'BTCUSDT', mock_pipeline)
        self._assert_daily_candles_published_data(doge_cache_data, 'DOGEIRT', mock_pipeline)

    def tearDown(self):
        ShortTermCandlesCache.cache().clear()
        LongTermCandlesCache.cache().clear()
