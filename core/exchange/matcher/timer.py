""" Matching Engine Main Logic
"""
import os
import time
from collections import defaultdict
from typing import ClassVar, Dict, List

from django.conf import settings
from django.core.cache import cache

from exchange.accounts.models import Notification
from exchange.base.calendar import ir_now
from exchange.base.logging import log_time, metric_incr

ENV_TIMING_ENABLED = os.environ.get('TIMING') == 'yes'


class MarketTimer:
    def __init__(self) -> None:
        self.timer = 0
        self.timers: Dict[str, int] = defaultdict(int)
        self.timing_enabled = ENV_TIMING_ENABLED or not settings.IS_PROD or cache.get('matcher_timing_enabled') == 'yes'

        self.unexpected_price_count: int = 0
        self.missed_matching_count: int = 0
        self.canceled_orders_count: int = 0
        self.orders_count: int = 0

    def start_timer(self):
        if not self.timing_enabled:
            return
        self.timer = time.time()

    def end_timer(self, name):
        if not self.timing_enabled:
            return
        run_time = round((time.time() - self.timer) * 1000)
        self.timers[name] = self.timers.get(name, 0) + run_time
        self.start_timer()

    def update_missed_matchings_metric(self, missed_matchings: int):
        self.missed_matching_count += missed_matchings

    def inc_unexpected_price_metric(self):
        self.unexpected_price_count += 1

    def update_orders_metric(self, all_orders: int, canceled_orders: int):
        self.canceled_orders_count += canceled_orders
        self.orders_count += all_orders


class Timer:
    def __init__(self) -> None:
        self.total_timer = time.time()
        self.timers: Dict[str, int] = defaultdict(int)
        self.timing_enabled = ENV_TIMING_ENABLED or not settings.IS_PROD or cache.get('matcher_timing_enabled') == 'yes'

        self.unexpected_price_count: int = 0
        self.missed_matching_count: int = 0
        self.canceled_orders_count: int = 0
        self.orders_count: int = 0

    def end_timer(self):
        self.total_timer = time.time() - self.total_timer

    def integrate_market_timer_data(self, market_timer: Dict[str, int]):
        if not self.timing_enabled:
            return
        for key, value in market_timer.items():
            self.timers[key] += value

    def integrate_market_counter_data(
        self,
        unexpected_price_count: int = 0,
        missed_matching_count: int = 0,
        canceled_orders_count: int = 0,
        orders_count: int = 0,
    ):
        self.unexpected_price_count += unexpected_price_count
        self.missed_matching_count += missed_matching_count
        self.canceled_orders_count += canceled_orders_count
        self.orders_count += orders_count

    @staticmethod
    def maximize_market_timer_data(timers: List['Timer']):
        return max(timers, key=lambda timer: timer.total_timer)

    def print_timers(self, *, log=False, details=''):
        if not self.timing_enabled:
            return
        times = [(v, k) for k, v in self.timers.items()]
        times.sort(reverse=True)
        total = sum(t[0] for t in times) or 1
        message = ''
        MatcherHourlyMetrics.update_round_times(
            longest_step=times[0][1] if len(times) else '',
            total_time=total / 1000,
            unexpected_price_count=self.unexpected_price_count,
            missed_matching_count=self.missed_matching_count,
            canceled_orders_count=self.canceled_orders_count,
            orders_count=self.orders_count,
        )
        for t, section in times:
            p = round(t * 100 / total)
            if p <= 1:
                continue
            message += f'{section}:{t}ms/{p}%  '
            if log:
                log_time('matching_time', t, (section,))

        if details:
            message += '\n' + details
        print(message, flush=True)
        if total >= 5000:
            Notification.notify_admins(
                message,
                title=f'⏳ Matcher: {total / 1000:.1f}s',
                channel='matcher',
            )
        if log:
            for i in (3, 5):
                if total < i * 1000:
                    break
                metric_incr('metric_matcher_slow_round_total', labels=(i,))


class MatcherHourlyMetrics:
    SLA_CUTOFFS: ClassVar[Dict[str, float]] = {
        '0.5"': 0.5,
        '1"': 1,
        '5"': 5,
        '20"': 20,
        "2'": 120,
        ">2'": float('inf'),
    }
    round_longest_step: str = ''
    last_round_time: float = 0
    rounds_by_time: ClassVar[Dict[str, int]] = {sla: 0 for sla in SLA_CUTOFFS}
    max_tps_by_time: ClassVar[Dict[str, float]] = {sla: 0 for sla in SLA_CUTOFFS}
    max_tps_markets: ClassVar[Dict[str, str]] = {sla: '-' for sla in SLA_CUTOFFS}
    long_steps_by_time: ClassVar[Dict[str, dict]] = {sla: defaultdict(int) for sla in SLA_CUTOFFS}
    LAST_SENT_NOTIF_HOUR: int = 0
    total_trades: int = 0
    unexpected_price_count: int = 0
    missed_matching_count: int = 0
    canceled_orders_count: int = 0
    orders_count: int = 0

    @classmethod
    def _get_time_key(cls, round_time) -> str:
        for sla, cutoff in cls.SLA_CUTOFFS.items():
            if round_time <= cutoff:
                return sla
        raise RuntimeError()

    @classmethod
    def update_metrics(cls, trades_count: int = 0, tps: float = 0, markets='-'):
        cls.total_trades += trades_count
        key = cls._get_time_key(cls.last_round_time)
        cls.rounds_by_time[key] += 1
        if cls.round_longest_step:
            cls.long_steps_by_time[key][cls.round_longest_step] += 1
        cls.max_tps_by_time[key], cls.max_tps_markets[key] = max(
            (cls.max_tps_by_time[key], cls.max_tps_markets[key]),
            (tps, markets),
        )

        current_hour = ir_now().hour
        if current_hour != cls.LAST_SENT_NOTIF_HOUR:
            cls.send_message(current_hour)

    @classmethod
    def update_round_times(
        cls,
        longest_step,
        total_time,
        *,
        unexpected_price_count=0,
        missed_matching_count=0,
        canceled_orders_count=0,
        orders_count=0,
    ):
        cls.round_longest_step = longest_step
        cls.last_round_time = total_time

        cls.unexpected_price_count += unexpected_price_count
        cls.missed_matching_count += missed_matching_count
        cls.canceled_orders_count += canceled_orders_count
        cls.orders_count += orders_count

    @classmethod
    def get_report(cls):
        """
        Trades:12,323 Runs:1,234 Orders:25,344 Cancels:541 MaxT:72
        UP:100 MM:2
        SLA: 0.5"/1"/5"/20"/2'/>2'
        Runs: 10/20/30/40/50/10
        MaxTPS: 15/25/27/10/30/20
        """
        total_runs = sum(cls.rounds_by_time.values())
        message = (
            f'Trades:{cls.total_trades:,} Runs:{total_runs:,} '
            f'Orders:{cls.orders_count:,} Cancels:{cls.canceled_orders_count:,} '
            f'MaxT:{max(cls.max_tps_by_time.values()):,}\n'
        )
        message += f'UP:{cls.unexpected_price_count:,} MM:{cls.missed_matching_count:,}\n'
        message += 'SLA: ' + '/'.join(cls.SLA_CUTOFFS) + '\n'
        message += 'Runs: ' + '/'.join(f'{round_cnt}' for round_cnt in cls.rounds_by_time.values()) + '\n'
        message += 'MaxTPS: ' + '/'.join(f'{max_tps}' for max_tps in cls.max_tps_by_time.values()) + '\n'
        message += 'Markets: ' + '/'.join(cls.max_tps_markets.values()) + '\n'
        long_steps_by_time = []
        for long_steps_dict in cls.long_steps_by_time.values():
            if long_steps_dict:
                steps = [(v, k) for k, v in long_steps_dict.items()]
                steps.sort(reverse=True)
                step = steps[0][1]
            else:
                step = '-'
            long_steps_by_time.append(step)
        message += 'LongestStep: ' + '/'.join(long_steps_by_time) + '\n'
        return message

    @classmethod
    def send_message(cls, hour):
        message = cls.get_report()
        Notification.notify_admins(
            message,
            title=f'🧭 Hourly Summary ({hour})',
            channel='matcher',
        )
        cls.reset_metrics()

    @classmethod
    def reset_metrics(cls):
        cls.LAST_SENT_NOTIF_HOUR = ir_now().hour
        cls.round_longest_step = ''
        cls.last_round_time = 0
        cls.rounds_by_time = {sla: 0 for sla in cls.SLA_CUTOFFS}
        cls.max_tps_by_time = {sla: 0 for sla in cls.SLA_CUTOFFS}
        cls.max_tps_markets = {sla: '-' for sla in cls.SLA_CUTOFFS}
        cls.long_steps_by_time = {sla: defaultdict(int) for sla in cls.SLA_CUTOFFS}
        cls.total_trades = 0
        cls.unexpected_price_count = 0
        cls.missed_matching_count = 0
        cls.canceled_orders_count = 0
        cls.orders_count = 0
