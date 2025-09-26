import contextlib
import multiprocessing
import signal
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from typing import List

import sentry_sdk
from django.conf import settings
from django.core.management.base import BaseCommand

from exchange.accounts.models import Notification
from exchange.base.calendar import ir_now
from exchange.base.decorators import measure_time_cm
from exchange.base.logging import log_time, metric_incr, metric_reset, report_exception
from exchange.base.models import LAUNCHING_CURRENCIES, Currencies, Settings
from exchange.market.models import Market
from exchange.market.sentry import capture_matcher_sentry_transaction
from exchange.matcher.divider import custom_partition_markets
from exchange.matcher.matcher import Matcher, post_processing_matcher_round
from exchange.matcher.timer import MatcherHourlyMetrics, Timer

SHOULD_EXIT = False


def graceful_exit_handler(sig, frame):
    global SHOULD_EXIT
    SHOULD_EXIT = True


def register_signal_handler():
    signal.signal(signal.SIGHUP, graceful_exit_handler)


def initializer_process():
    signal.signal(signal.SIGINT, signal.SIG_IGN)

class Command(BaseCommand):

    def send_startup_notice(self):
        """Send start notifications."""
        if not settings.IS_PROD:
            return
        Notification.notify_admins(
            f'Started on {settings.SERVER_NAME} {settings.RELEASE_VERSION}-{settings.CURRENT_COMMIT}',
            title='🏁 Matcher',
            channel='matcher',
        )

    def send_shutdown_notice(self):
        """Send shutdown notifications."""
        MatcherHourlyMetrics.send_message(
            hour=f'{ir_now().hour}:{ir_now().minute}',
        )
        if not settings.IS_PROD:
            return
        Notification.notify_admins(
            'Done',
            title='🏁 Matcher',
            channel='matcher',
        )

    def create_missing_markets(self):
        """Create Market objects for all newly defined currencies."""
        for src_currency in LAUNCHING_CURRENCIES:
            for dst_currency in [Currencies.rls, Currencies.usdt]:
                market, created = Market.objects.get_or_create(
                    src_currency=src_currency,
                    dst_currency=dst_currency,
                    defaults={'is_active': False},
                )
                if created:
                    print('Created missing market for:', market.symbol, flush=True)

    @staticmethod
    def initialize_matcher_shared_data(manager):
        # init tether price
        Matcher.SHARED_TETHER_DATA = manager.dict({})

        # init users fee
        Matcher.USERS_WITH_MANUAL_FEE = manager.dict({})

        # init market data
        Matcher.MARKET_LAST_PROCESSED_TIME = manager.dict({})
        Matcher.MARKET_LAST_BEST_PRICES = manager.dict({})
        Matcher.MARKET_PRICE_RANGE = manager.dict({})

    def handle(self, *args, **kwargs):
        register_signal_handler()

        manager = multiprocessing.Manager()
        # initialize matcher shared data
        self.initialize_matcher_shared_data(manager)

        with ProcessPoolExecutor(max_workers=2, initializer=initializer_process) as executor, ProcessPoolExecutor(
            max_workers=2,
            initializer=initializer_process,
        ) as executor_post_process:
            executor.submit(print, ('Process Pool Started',))
            executor_post_process.submit(print, ('Post Process Pool Started',))
            self.send_startup_notice()
            self.create_missing_markets()

            # Matcher start!
            ConcurrentMatcher(executor, executor_post_process).run_matcher_rounds()

        self.send_shutdown_notice()
        print('Done.', flush=True)


class ConcurrentMatcher:
    def __init__(self, executor: ProcessPoolExecutor, executor_post_process: ProcessPoolExecutor):
        self.executor = executor
        self.executor_post_process = executor_post_process
        self.post_process_features = []

    def _reset_post_process_features(self):
        self.post_process_features = []

    @staticmethod
    def reset_global_matcher_metrics():
        MatcherHourlyMetrics.reset_metrics()
        for label in ['disabled', 'exception', 'full', 'normal']:
            metric_reset('metric_matcher_runs_total', (label,))
        metric_reset('metric_matcher_run_total_time')

    def run_matcher_round(self, markets: List[Market], run_all, round_start_time):
        # partition markets for concurrent running
        partitions = custom_partition_markets({market.symbol: market for market in markets})
        total_timer = Timer()

        # compute stop process times in previous round
        if self.post_process_features:
            time_previous_stop_process = time.time()
            total_timer = self._add_post_process_timer(total_timer)
            total_timer.timers['JoiningStopTimers'] = (time.time() - time_previous_stop_process) * 1000
            self._reset_post_process_features()

        # markets couldn't run concurrent like tether-rls
        total_markets, total_trades, timer, _ = self.run_matcher_for_list_of_markets(partitions[0], '0', '0')
        total_timer.integrate_market_timer_data(timer.timers)
        total_timer.integrate_market_counter_data(
            unexpected_price_count=timer.unexpected_price_count,
            missed_matching_count=timer.missed_matching_count,
            canceled_orders_count=timer.canceled_orders_count,
            orders_count=timer.orders_count,
        )
        self._post_processing_matcher_round(partitions[0])

        futures = self.run_with_process_on_markets(partitions)
        total_markets, total_trades, total_timer = self.integrate_results_matcher(
            futures,
            total_markets,
            total_trades,
            total_timer,
        )

        # update metrics
        metric_incr('metric_matcher_runs_total__' + ('full' if run_all else 'normal'))
        total_time = round((time.time() - round_start_time) * 1000)
        if total_time > 0:
            log_time(f'matching_round__{run_all:d}', total_time)
            tps = total_trades * 1000 / total_time
            if total_markets > 0 or total_time >= 50:
                total_timer.print_timers(
                    log=True,
                    details=f'Markets:{total_markets} Full:{1 if run_all else 0} TPS:{tps:.1f}',
                )
                metric_incr('metric_matcher_run_total_time', total_time)
                MatcherHourlyMetrics.update_metrics(
                    markets=str(total_markets),
                    trades_count=total_trades,
                    tps=round(tps, 1),
                )
            print(
                '{1} TotalTime: {0:.2f}s {1}'.format(
                    total_time / 1000,
                    '=' * 20 if run_all else '=' * 15,
                ),
                flush=True,
            )
        time.sleep(0.05 if settings.IS_PROD else 0.2)


    def _add_post_process_timer(self, total_timer: Timer):

        for future in self.post_process_features:
            timer = future.result()
            for key, value in timer.timers.items():
                timer.timers[key] = value / 2
            total_timer.integrate_market_timer_data(timer.timers)

        return total_timer

    @classmethod
    def integrate_results_matcher(cls, partition_results, total_markets: int, total_trades: int, total_timer: Timer):
        process_timers = defaultdict(list)
        for total_market, total_trade, timer, section_number in partition_results:
            total_markets += total_market
            total_trades += total_trade

            total_timer.integrate_market_counter_data(
                unexpected_price_count=timer.unexpected_price_count,
                missed_matching_count=timer.missed_matching_count,
                canceled_orders_count=timer.canceled_orders_count,
                orders_count=timer.orders_count,
            )

            process_timers[section_number].append(timer)

        for timers in process_timers.values():
            if timers:
                total_timer.integrate_market_timer_data(Timer.maximize_market_timer_data(timers).timers)

        return total_markets, total_trades, total_timer

    def run_with_process_on_markets(self, partitions):

        results = []
        # concurrent partitions 1,2
        futures = []
        for i in range(2):
            future = self.executor.submit(self.run_matcher_for_list_of_markets, partitions[i + 1], '1', str(i))
            future.add_done_callback(partial(self._post_processing_matcher_round, partitions[i + 1]))
            futures.append(future)

        for future in futures:
            results.append(future.result())

        # concurrent partitions 3,4
        futures = []
        for i in range(2):
            future = self.executor.submit(self.run_matcher_for_list_of_markets, partitions[i + 3], '2', str(i))
            future.add_done_callback(partial(self._post_processing_matcher_round, partitions[i + 3]))
            futures.append(future)

        for future in futures:
            results.append(future.result())

        return results

    def _post_processing_matcher_round(self, markets, future=None):
        for market in markets:
            if market.symbol not in Matcher.get_symbols_that_use_async_stop_process():
                continue
            last_price_range = Matcher.MARKET_PRICE_RANGE.get(market.id)
            if last_price_range:
                self.post_process_features.append(
                    self.executor_post_process.submit(
                        post_processing_matcher_round,
                        market,
                        last_price_range,
                    ),
                )

    @classmethod
    def run_matcher_for_list_of_markets(cls, markets, section_number, process_name):
        total_markets = 0
        total_trades = 0
        markets_timer = Timer()

        for market in markets:
            matcher = Matcher(market, section_number + '-' + process_name)
            try:
                # Actual matching run
                time_start = time.time()
                with sentry_sdk.start_transaction(
                    op='function',
                    name='matcher',
                ) if capture_matcher_sentry_transaction() else contextlib.nullcontext():
                    matcher.do_matching_round()

                markets_timer.integrate_market_timer_data(matcher.timer.timers)
                markets_timer.integrate_market_counter_data(
                    unexpected_price_count=matcher.timer.unexpected_price_count,
                    missed_matching_count=matcher.timer.missed_matching_count,
                    canceled_orders_count=matcher.timer.canceled_orders_count,
                    orders_count=matcher.timer.orders_count,
                )
                total_markets += 1
                total_trades += matcher.report['matches']
                # Timing the run
                time_end = time.time()
                run_time = round((time_end - time_start) * 1000)
                print(f'    [{run_time}ms]', flush=True)
            except Exception as e:  # noqa: BLE001
                print(f'[Fatal] exception: {e}', flush=True)
                Notification.notify_admins(
                    str(e),
                    title='💥 Matcher Exception',
                    channel='matcher',
                )
                report_exception()
                metric_incr('metric_matcher_runs_total__exception')
                time.sleep(20)

        markets_timer.end_timer()
        return total_markets, total_trades, markets_timer, section_number

    def run_matcher_rounds(self):
        self.reset_global_matcher_metrics()
        Matcher.initialize_globals()

        # start rounds
        try:
            run = -1
            last_cache_update_time = 0.0

            while True:
                if SHOULD_EXIT:
                    print('Received SIGHUP', flush=True)
                    break

                round_start_time = time.time()

                # Check configs
                if Settings.is_disabled('module_matching_engine'):
                    metric_incr('metric_matcher_runs_total__disabled')
                    print('[Notice] Matching Engine Disabled', flush=True)
                    time.sleep(5)
                    continue

                # Periodic checks and cache updates
                if round_start_time - last_cache_update_time > 3600.0:
                    Matcher.reinitialize_caches()
                    last_cache_update_time = round_start_time

                # Run for markets
                run = (run + 1) % 10
                run_all = run == 0
                with measure_time_cm(f'matcher_markets_query_milliseconds__{run_all:d}'):
                    markets = list(Matcher.get_pending_markets(cache_based=not run_all))
                # Run a round!
                self.run_matcher_round(markets, run_all, round_start_time)

        except KeyboardInterrupt:
            pass
