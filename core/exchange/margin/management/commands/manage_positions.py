import datetime
import time

from django.core.management.base import BaseCommand
from tqdm import tqdm

from exchange.base.calendar import ir_now
from exchange.base.constants import PRICE_GUARD_RANGE
from exchange.base.decorators import measure_time
from exchange.base.logging import report_exception
from exchange.margin.models import MarginOrderChange, PositionLiquidationRequest
from exchange.margin.services import MarginManager
from exchange.margin.tasks import (
    task_bulk_update_position_on_order_change,
    task_liquidate_positions,
    task_manage_expired_positions,
    task_manage_liquidated_positions,
)
from exchange.market.inspector import get_markets_last_price_range
from exchange.wallet.estimator import PriceEstimator


class Command(BaseCommand):
    """
    Examples:
        python manage.py manage_positions
    """
    help = 'Backup manager for positions when celery is down.'

    last_start_time = None

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Run once [useful for testing]')

    def handle(self, once, **options):
        try:
            while True:
                self.update_positions_with_order_changes()
                self.update_positions_with_liquidation_requests()
                self.liquidate_positions()
                self.manage_inactive_positions()
                if once:
                    break
                time.sleep(4)
        except KeyboardInterrupt:
            print('bye!')

    @staticmethod
    @measure_time(metric='manage_active_positions')
    def update_positions_with_order_changes():
        order_ids = MarginOrderChange.objects.values_list('order_id', flat=True).distinct().order_by('order_id')
        last_id = 0
        updated_count = 0
        batch_size = 500
        while batch_order_ids := order_ids.filter(order_id__gt=last_id)[:batch_size]:
            for order_id in tqdm(batch_order_ids, initial=updated_count, total=batch_size + updated_count, leave=False):
                try:
                    updated_count += task_bulk_update_position_on_order_change([order_id])
                except:
                    report_exception()
                last_id = order_id
        return f'Updated orders={updated_count}'

    @staticmethod
    @measure_time(metric='manage_active_positions')
    def update_positions_with_liquidation_requests():
        position_liquidation_requests = PositionLiquidationRequest.objects.filter(is_processed=False).order_by('id')
        last_id = 0
        updated_count = 0
        batch_size = 500
        while batch_items := position_liquidation_requests.filter(id__gt=last_id)[:batch_size]:
            for position_liq_quest in tqdm(
                batch_items, initial=updated_count, total=batch_size + updated_count, leave=False
            ):
                try:
                    MarginManager.update_position_on_liquidation_request_change(position_liq_quest)
                    updated_count += 1
                except:
                    report_exception()
                last_id = position_liq_quest.id
        return f'Processed liquidation requests={updated_count}'

    @classmethod
    @measure_time(metric='liquidate_positions')
    def liquidate_positions(cls):
        if not cls.last_start_time:
            cls.last_start_time = ir_now() - datetime.timedelta(seconds=5)
        market_data = get_markets_last_price_range(since=cls.last_start_time, exact=True)
        liquidated_count = 0
        for src_currency, dst_currency, high_price, low_price, last_time in tqdm(market_data, leave=False):
            estimate_buy, estimate_sell = PriceEstimator.get_price_range(src_currency, dst_currency)
            min_price = max(estimate_buy * (1 - PRICE_GUARD_RANGE), low_price)
            max_price = min(estimate_sell * (1 + PRICE_GUARD_RANGE), high_price) or high_price
            liquidated_count += task_liquidate_positions(src_currency, dst_currency, min_price, max_price, sync=True)
            cls.last_start_time = max(cls.last_start_time, last_time + datetime.timedelta(microseconds=1))
        return f'Liquidating positions={liquidated_count}'

    @staticmethod
    @measure_time(metric='manage_inactive_positions')
    def manage_inactive_positions():
        liquidated_count = task_manage_liquidated_positions()
        expired_count = task_manage_expired_positions()
        return f'Liquidated positions={liquidated_count}, Expired positions={expired_count}'
