import contextlib
from datetime import datetime
from typing import List

from celery import shared_task
from django.conf import settings
from django.db import transaction

from exchange.asset_backed_credit.exceptions import CannotEstimateSrcAmount
from exchange.asset_backed_credit.externals.restriction import UserRestrictionProvider
from exchange.asset_backed_credit.models import UserService
from exchange.asset_backed_credit.services.adjust import AdjustService
from exchange.asset_backed_credit.services.debit.bank_switch import reverse_payment
from exchange.asset_backed_credit.services.debit.recon import reconcile
from exchange.asset_backed_credit.services.liquidation import liquidate_settlement
from exchange.asset_backed_credit.services.margin_call import (
    cleanup_margin_call_resolved_candidates,
    send_adjustment_notification,
    send_liquidation_notification,
    send_margin_call_notification,
)
from exchange.asset_backed_credit.services.settlement import settle, settle_pending_settlements
from exchange.asset_backed_credit.services.user_service import (
    close_user_services,
    force_close_user_services,
    update_user_service_status,
)
from exchange.asset_backed_credit.services.wallet.transfer import process_wallet_transfer_log, process_withdraw_request
from exchange.base.calendar import ir_tz
from exchange.base.decorators import measure_time_cm
from exchange.base.logging import report_event
from exchange.wallet.models import WalletBulkTransferRequest as ExchangeWalletBulkTransferRequest


@shared_task(name='abc.core.liquidate_margin_call', max_retries=0)
@measure_time_cm(metric='abc_liquidateMarginCall')
def task_margin_call_adjust(margin_call_id: int):
    AdjustService(margin_call_id).execute()


@shared_task(name='abc.core.cleanup_margin_call', max_retries=0)
def task_margin_call_cleanup():
    cleanup_margin_call_resolved_candidates()


@shared_task(name='abc.core.send_margin_call_notif', max_retries=3)
def task_margin_call_notify(margin_call_id: int):
    send_margin_call_notification(margin_call_id=margin_call_id)


@shared_task(name='abc.core.send_adjust_notification', max_retries=3)
def task_margin_call_send_adjust_notifications(margin_call_id: int):
    send_adjustment_notification(margin_call_id=margin_call_id)


@shared_task(name='abc.core.send_liquidation_notification', max_retries=3)
def task_margin_call_send_liquidation_notifications(margin_call_id: int):
    send_liquidation_notification(margin_call_id=margin_call_id)


@shared_task(name='abc.core.settle_pending_user_settlements')
def task_settle_pending_user_settlements():
    settle_pending_settlements()


@shared_task(name='abc.core.settle_with_user', max_retries=0)
def task_settlement_settle_user(settlement_id: int):
    settle(settlement_id)


@shared_task(name='abc.core.reverse_settlement', max_retries=0)
@transaction.atomic
def task_reverse_debit_payment(settlement_id: int):
    reverse_payment(settlement_id)


@shared_task(
    name='abc.core.task_liquidate_and_try_settle',
    max_retries=4,
    default_retry_delay=3,
    autoretry_for=(CannotEstimateSrcAmount,),
)
@measure_time_cm(metric='abc_liquidate')
def task_settlement_liquidation(settlement_id: int):
    liquidate_settlement(settlement_id=settlement_id, wait_before_retry=settings.MARGIN_SYSTEM_ORDERS_MAX_AGE)


@shared_task(name='abc.core.process_withdraw_request', max_retries=0)
@measure_time_cm(metric='abc_withdrawRequest')
def task_process_withdraw_request(wallet_bulk_transfer_id: int):
    with contextlib.suppress(ExchangeWalletBulkTransferRequest.DoesNotExist):
        process_withdraw_request(wallet_bulk_transfer_id)


@shared_task(name='abc.core.process_wallet_transfer_log', max_retries=0)
@measure_time_cm(metric='abc_processWalletTransferLog')
def process_wallet_transfer_log_task(wallet_transfer_log_id: int):
    process_wallet_transfer_log(wallet_transfer_log_id)


@shared_task(name='abc.core.task_close_user_service')
def task_close_user_service(user_service_ids: List[int]):
    return close_user_services(user_service_ids)


@shared_task(name='abc.core.task_force_close_user_service')
def task_force_close_user_service(user_service_ids: List[int]):
    return force_close_user_services(user_service_ids)


@shared_task(bind=True, name='abc.core.task_add_user_restriction', max_retries=None)
def add_user_restriction_task(self, user_service_id: int, restriction: str, description_key: str, considerations: str):
    user_service = UserService.objects.get(id=user_service_id)
    try:
        UserRestrictionProvider.add_restriction(
            user_service=user_service,
            restriction=restriction,
            description_key=description_key,
            considerations=considerations,
        )
    except Exception as e:
        report_event('add restriction task error', extras={'exception': str(e)})
        raise self.retry(countdown=5)


@shared_task(bind=True, name='abc.core.task_remove_user_restriction', max_retries=None)
def remove_user_restriction_task(self, user_service_id: int, restriction: str):
    user_service = UserService.objects.get(id=user_service_id)
    try:
        UserRestrictionProvider.remove_restriction(user_service, restriction)
    except Exception as e:
        report_event('remove restriction task error', extras={'exception': str(e)})
        raise self.retry(countdown=5)


@shared_task(bind=True, name='abc.core.task_update_user_service_status', max_retries=None)
def task_update_user_service_status(self, user_service_id: int):
    update_user_service_status(user_service_id)


@shared_task(name='abc.core.task_add_debit_reconcile')
def task_add_debit_reconcile(iso_formated_datetime: str):
    recon_date = datetime.fromisoformat(iso_formated_datetime).astimezone(ir_tz())
    reconcile(recon_date)
