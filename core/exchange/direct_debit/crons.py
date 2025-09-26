import datetime

from django.db.models import Case, When

from exchange.base.calendar import ir_now
from exchange.base.crons import CronJob, Schedule
from exchange.base.logging import log_event, report_exception
from exchange.direct_debit.models import DirectDebitContract, DirectDeposit
from exchange.direct_debit.services import DirectDebitUpdateDeposit


class DirectDebitExpiredContracts(CronJob):
    schedule = Schedule(run_at_times=['00:00', '06:00', '12:00', '18:00'])
    code = 'direct_debit_expired_contracts'

    def run(self):
        DirectDebitContract.objects.filter(
            expires_at__lt=ir_now(),
            status=DirectDebitContract.STATUS.active,
        ).update(status=DirectDebitContract.STATUS.expired)


class DirectDebitContractCreateOrUpdateTimeoutCron(CronJob):
    schedule = Schedule(run_every_mins=10)
    code = 'direct_debit_contract_create_or_update_timeout'

    def run(self):
        DirectDebitContract.objects.filter(
            created_at__lt=ir_now() - datetime.timedelta(minutes=15),
            status__in=[
                DirectDebitContract.STATUS.waiting_for_confirm,
                DirectDebitContract.STATUS.created,
                DirectDebitContract.STATUS.initializing,
                DirectDebitContract.STATUS.waiting_for_update,
            ],
        ).update(
            status=Case(
                When(
                    status=DirectDebitContract.STATUS.waiting_for_update, then=DirectDebitContract.STATUS.failed_update
                ),
                default=DirectDebitContract.STATUS.failed,
            )
        )


class DirectDebitCheckTimeoutDepositCron(CronJob):
    schedule = Schedule(run_every_mins=5)
    code = 'direct_debit_check_timeout_deposit'

    def run(self):
        timeout_deposits = DirectDeposit.objects.filter(
            status=DirectDeposit.STATUS.timeout, created_at__gte=ir_now() - datetime.timedelta(minutes=15)
        )
        for deposit in timeout_deposits:
            try:
                DirectDebitUpdateDeposit(trace_id=deposit.trace_id).resolve_diff()
            except Exception:
                report_exception()
