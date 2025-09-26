from collections import defaultdict
from decimal import Decimal
from itertools import chain
from typing import List, Union

from celery import shared_task
from celery.schedules import crontab
from django.core.cache import cache
from django.core.management import call_command

from exchange.accounts.models import Notification
from exchange.base.decorators import measure_function_execution, measure_time
from exchange.base.helpers import batcher
from exchange.celery import app
from exchange.margin.models import MarginOrderChange, Position, PositionLiquidationRequest, PositionOrder
from exchange.margin.services import MarginManager


@shared_task(name='margin.bulk_update_position_on_order_change')
@measure_function_execution(
    metric_prefix='margin_tasks', metric='updatePositionOnOrderChange', metrics_flush_interval=10
)
def task_bulk_update_position_on_order_change(order_ids: List[int]) -> bool:
    order_ids = set(order_ids)
    if not order_ids:
        return False

    changes_qs = list(MarginOrderChange.objects.filter(order_id__in=order_ids))
    if not changes_qs:
        return False

    change_map = defaultdict(list)
    for ch in changes_qs:
        change_map[ch.order_id].append(ch.id)

    intersection_of_orders = order_ids.intersection(set(change_map))
    position_orders_qs = (
        PositionOrder.objects.select_related('order').filter(order_id__in=intersection_of_orders).order_by('id')
    )
    for position_orders in batcher(position_orders_qs, 10):
        MarginManager.bulk_update_positions_on_order_change(position_orders)

    all_change_ids = list(chain.from_iterable(change_map.values()))
    MarginOrderChange.objects.filter(id__in=all_change_ids).delete()

    return True


@shared_task(name='margin.task_update_position_on_liquidation_request_change')
@measure_function_execution(
    metric_prefix='margin_tasks', metric='updatePositionOnLiquidationRequestChange', metrics_flush_interval=10
)
def task_update_position_on_liquidation_request_change(liquidation_request_id: int) -> bool:
    try:
        position_liq_quest = PositionLiquidationRequest.objects.select_related('liquidation_request').get(
            liquidation_request_id=liquidation_request_id,
            is_processed=False,
        )
    except PositionLiquidationRequest.DoesNotExist:
        return False
    else:
        MarginManager.update_position_on_liquidation_request_change(position_liq_quest)
    return True


def _manage_inactive_positions(status: int) -> int:
    stats = defaultdict(list)

    unsettled_positions = list(Position.objects.filter(status=status, pnl__isnull=True).values_list('id', flat=True))
    for position_ids in batcher(unsettled_positions, 50):
        settled_positions = MarginManager.bulk_settle_positions_in_system(position_ids)
        for position in settled_positions:
            stats[(position.market.symbol, position.side)].append(position.liability)

    if stats:
        message_id_cache_key = f'message_id_unsettled_positions_notif_{status}'
        Notification.notify_admins(
            '\n'.join(
                f'- {symbol}: {len(amounts)} {Position.SIDES[side]} of total {sum(amounts).normalize():,f}'
                for (symbol, side), amounts in stats.items()
            ),
            title=f'🧭 {Position.STATUS[status]} positions to settle',
            channel='pool',
            message_id= cache.get(message_id_cache_key),
            cache_key=message_id_cache_key,
            cache_timeout=120,
        )

    return len(unsettled_positions)


@shared_task(name='margin.manage_liquidated_positions')
@measure_function_execution(metric_prefix='margin_tasks', metric='manageLiquidatedPositions', metrics_flush_interval=10)
def task_manage_liquidated_positions() -> int:
    return _manage_inactive_positions(Position.STATUS.liquidated)


@shared_task(name='margin.manage_expired_positions')
@measure_function_execution(metric_prefix='margin_tasks', metric='manageExpiredPositions', metrics_flush_interval=10)
def task_manage_expired_positions() -> int:
    return _manage_inactive_positions(Position.STATUS.expired)


@shared_task(name='margin.liquidate_positions')
@measure_time(metric='liquidate_positions_task', verbose=False)
def task_liquidate_positions(
    src_currency: int, dst_currency: int, min_price: Union[Decimal, str], max_price: Union[Decimal, str], *, sync=False
) -> int:
    liquidated_positions_count = MarginManager.liquidate_positions(
        src_currency, dst_currency, Decimal(min_price), Decimal(max_price)
    )
    if liquidated_positions_count and not sync:
        task_manage_liquidated_positions.delay()
    return liquidated_positions_count


@shared_task(name='margin.manage_and_send_margin_call_crons')
def task_manage_and_send_margin_call():
    call_command(
        'runcrons',
        'exchange.margin.crons.MarginCallManagementCron',
        'exchange.margin.crons.MarginCallSendingCron',
        force=True,
    )


@shared_task(name='margin.expire_and_extend_positions_crons')
def task_expire_and_extend_positions():
    call_command(
        'runcrons',
        'exchange.margin.crons.PositionExpireCron',
        'exchange.margin.crons.PositionExtensionFeeCron',
        force=False,
    )


@shared_task(name='margin.notify_upcoming_position_expirations_crons')
def task_notify_upcoming_position_expirations():
    call_command(
        'runcrons',
        'exchange.margin.crons.NotifyUpcomingPositionsExpirationCron',
        force=False,
    )


app.add_periodic_task(60, task_manage_and_send_margin_call, name='manage_and_send_margin_call')

app.add_periodic_task(crontab(minute=0, hour=0), task_expire_and_extend_positions, name='expire_and_extend_positions')

app.add_periodic_task(
    crontab(minute=0, hour=11),
    task_notify_upcoming_position_expirations,
    name='notify_upcoming_position_expirations',
)
