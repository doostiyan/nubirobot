from datetime import timedelta

from celery import shared_task
from django.db.models import Count

from exchange.base.calendar import ir_now
from exchange.base.decorators import measure_time
from exchange.base.metrics import _gauge_meter as gauge_meter
from exchange.celery import app as celery_app
from exchange.liquidator.models import Liquidation, LiquidationRequest
from exchange.liquidator.services import (
    ExternalBrokerStatusChecker,
    ExternalLiquidationProcessor,
    ExternalOrderCreator,
    InternalLiquidationProcessor,
    InternalOrderCreator,
    LiquidationCreator,
    LiquidationRequestProcessor,
)


@shared_task(name='liquidator.core.check_external_broker_service_status')
@measure_time(metric='liquidator_check_external_broker_service_status_time')
def task_check_external_broker_service_status():
    ExternalBrokerStatusChecker.run()


@shared_task(name='liquidator.core.process_pending_liquidation_request')
@measure_time(metric='liquidator_process_pending_requests_time')
def task_process_pending_liquidation_request():
    LiquidationCreator().execute()


@shared_task(name='liquidator.core.create_internal_order')
@measure_time(metric='liquidator_create_internal_order_time')
def task_create_internal_order(liquidation_id: int):
    return InternalOrderCreator.process(liquidation_id=liquidation_id)


@shared_task(name='liquidator.core.create_external_order')
@measure_time(metric='liquidator_create_external_order_time')
def task_create_external_order(liquidation_id: int):
    return ExternalOrderCreator.process(liquidation_id=liquidation_id)


@shared_task(name='liquidator.core.check_status_internal_liquidation')
@measure_time(metric='liquidator_check_internal_liquidations_status_time')
def task_check_status_internal_liquidation():
    InternalLiquidationProcessor().process_liquidation_orders()


@shared_task(name='liquidator.core.check_status_external_liquidation')
@measure_time(metric='liquidator_check_external_liquidations_status_time')
def task_check_status_external_liquidation():
    start_time = ir_now() - timedelta(seconds=5)
    liquidations = (
        Liquidation.objects.filter(
            market_type=Liquidation.MARKET_TYPES.external,
            status=Liquidation.STATUS.open,
            created_at__lte=start_time,
        )
        .order_by('id')
        .values_list('id', flat=True)
    )
    for liquidation_id in liquidations:
        task_update_status_external_liquidation.delay(liquidation_id)


@shared_task(name='liquidator.core.update_status_external_liquidation')
@measure_time(metric='liquidator_update_external_liquidation_time')
def task_update_status_external_liquidation(liquidation_id: int):
    ExternalLiquidationProcessor().update_status(liquidation_id)


@shared_task(name='liquidator.core.update_liquidation_request')
@measure_time(metric='liquidator_update_liquidation_requests_time')
def task_update_liquidation_request():
    LiquidationRequestProcessor().update_in_progress_liquidation_request()


@shared_task(name='liquidator.core.submit_liquidation_requests_external_transactions')
@measure_time(metric='liquidator_submit_external_wallet_trx_time')
def task_submit_liquidation_requests_external_wallet_transactions():
    LiquidationRequestProcessor().submit_wallet_transactions_for_external_liquidations()


@shared_task(name='liquidator.core.retry_liquidation_requests_failed_wallet_transactions')
@measure_time(metric='liquidator_retry_failed_external_wallet_trx_time')
def task_retry_liquidation_requests_failed_wallet_transactions():
    LiquidationRequestProcessor().submit_wallet_transactions_for_external_liquidations(is_retry=True)


@shared_task(name='liquidator.core.task_update_liquidator_periodic_metrics')
@measure_time(metric='liquidator_update_periodic_metrics_time')
def task_update_liquidator_periodic_metrics():
    def convert_to_dict(annotation_result, status_choices):
        stats = {data['status']: data['cnt'] for data in annotation_result}
        for status_code, name in status_choices:
            stats.setdefault(status_code, 0)
        return stats

    requests_cnt_per_status = LiquidationRequest.objects.values('status').annotate(cnt=Count('id'))
    for status, cnt in convert_to_dict(requests_cnt_per_status, LiquidationRequest.STATUS).items():
        gauge_meter(
            metric='metric_liquidation_requests_count',
            amount=cnt,
            status=status,
        )

    liquidations_cnt_per_status = Liquidation.objects.values('status').annotate(cnt=Count('id'))
    for status, cnt in convert_to_dict(liquidations_cnt_per_status, Liquidation.STATUS).items():
        gauge_meter(
            metric='metric_liquidations_count',
            amount=cnt,
            status=status,
        )


celery_app.add_periodic_task(
    10,
    task_check_external_broker_service_status.s(),
    name='liquidator.core.check_external_broker_service_status_beat',
)
celery_app.add_periodic_task(
    5,
    task_process_pending_liquidation_request.s(),
    name='liquidator.core.process_pending_request_beat',
)
celery_app.add_periodic_task(
    5,
    task_check_status_internal_liquidation.s(),
    name='liquidator.core.check_status_internal_liquidation_beat',
)
celery_app.add_periodic_task(
    5,
    task_check_status_external_liquidation.s(),
    name='liquidator.core.check_status_external_liquidation_beat',
)
celery_app.add_periodic_task(20, task_update_liquidation_request.s(), name='liquidator.core.process_request_beat')
celery_app.add_periodic_task(
    5,
    task_submit_liquidation_requests_external_wallet_transactions.s(),
    name='liquidator.core.task_submit_liquidation_requests_external_wallet_transactions_beat',
)
celery_app.add_periodic_task(
    5 * 60,
    task_retry_liquidation_requests_failed_wallet_transactions.s(),
    name='liquidator.core.task_retry_liquidation_requests_failed_wallet_transactions_beat',
)
celery_app.add_periodic_task(
    60,
    task_update_liquidator_periodic_metrics.s(),
    name='liquidator.core.task_update_liquidator_periodic_metrics_beat',
)
