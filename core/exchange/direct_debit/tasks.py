from typing import List, Optional

from celery import shared_task
from django.db import transaction

from exchange.accounts.models import User
from exchange.base.emailmanager import EmailManager
from exchange.base.logging import report_exception
from exchange.direct_debit.constants import (
    RETRY_ACTIVATION_CONTRACTS_COUNT,
    RETRY_ACTIVATION_CONTRACTS_COUNT_DOWN,
    FaraboomContractStatus,
)
from exchange.direct_debit.exceptions import ContractCanNotBeCanceledAtProviderError
from exchange.direct_debit.integrations.faraboom import FaraboomHandler
from exchange.direct_debit.models import DirectDebitContract
from exchange.direct_debit.notifications import ContractSuccessfullyRemovedNotification
from exchange.direct_debit.services import DirectDebitUpdateDeposit


@shared_task(name='direct_debit.core.activate_contract')
@transaction.atomic
def direct_debit_activate_contract_task(contract_id: int, retry: Optional[int] = 0):
    try:
        contract = (
            DirectDebitContract.objects.select_for_update(of=('self',)).select_related('bank').get(pk=contract_id)
        )
        if retry >= RETRY_ACTIVATION_CONTRACTS_COUNT:
            contract.status = DirectDebitContract.STATUS.failed
            contract.save(update_fields=['status'])
            transaction.on_commit(lambda: contract.notify_on_error())
            return

        contract.activate()
    except DirectDebitContract.DoesNotExist:
        return
    except:
        report_exception()
        direct_debit_activate_contract_task.apply_async(
            args=(contract_id, retry + 1), countdown=RETRY_ACTIVATION_CONTRACTS_COUNT_DOWN
        )


@shared_task(name='direct_debit.core.notif.email')
def task_send_emails(user_id: int, template: str, data: dict = None, priority='medium'):
    user = User.objects.get(pk=user_id)

    EmailManager.send_email(email=user.email, template=template, data=data, priority=priority)


@shared_task(name='direct_debit.admin.update_direct_deposit')
def task_update_direct_deposit(trace_ids: List[str]):
    for trace_id in trace_ids:
        DirectDebitUpdateDeposit(trace_id=trace_id).resolve_diff()


@shared_task(name='direct_debit.core.cancel_contract', bind=True, max_retries=5)
def task_cancel_contract_in_provider(self, contract_id: str, bank_id: str):
    try:
        FaraboomHandler().change_contract_status(contract_id, FaraboomContractStatus.CANCELLED.value, bank_id)
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            raise ContractCanNotBeCanceledAtProviderError from exc
        else:
            # Retry after 1 minute if not the last attempt
            raise self.retry(exc=exc, countdown=60)


@shared_task(name='direct_debit.core.deactivate_contract')
def task_deactivate_contract_in_provider(contract_id: str, bank_id: str, bank_name: str, user_id: int):
    try:
        FaraboomHandler().change_contract_status(contract_id, FaraboomContractStatus.DEACTIVE.value, bank_id)
        DirectDebitContract.objects.filter(contract_id=contract_id).update(status=DirectDebitContract.STATUS.deactive)
        user = User.objects.get(id=user_id)
        ContractSuccessfullyRemovedNotification(user).send(bank_name)
    except Exception:
        pass
