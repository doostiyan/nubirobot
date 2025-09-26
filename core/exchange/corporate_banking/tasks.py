from datetime import datetime

from celery import shared_task

from exchange.base.calendar import ir_tz
from exchange.base.logging import report_exception
from exchange.corporate_banking.models import COBANK_PROVIDER, CoBankAccount
from exchange.corporate_banking.services.banker import Banker
from exchange.corporate_banking.services.settler import Settler


@shared_task(name='corporate_banking.admin.change_statement_status')
def change_statement_status_by_admin_task(statement_pk: int, changes: dict):
    Settler().change_statement_status(statement_pk, changes)


@shared_task(name='corporate_banking.admin.rerun_get_statement_for_period')
def rerun_get_statement_for_period_task(
    from_time: str,
    to_time: str,
    cobank_account_pk: int = None,
    provider: COBANK_PROVIDER = None,
):
    from_time = datetime.fromisoformat(from_time).astimezone(ir_tz())
    to_time = datetime.fromisoformat(to_time).astimezone(ir_tz())
    account = None
    if cobank_account_pk:
        account = CoBankAccount.objects.filter(pk=cobank_account_pk).first()
    if account:
        Banker(account.provider, from_time, to_time).get_bank_statements(account)
    else:
        providers = [provider] if provider is not None else [COBANK_PROVIDER.toman, COBANK_PROVIDER.jibit]
        exception = None
        for provider in providers:
            try:
                Banker(provider, from_time, to_time).get_statements()
            except Exception as ex:
                report_exception()
                exception = ex

        if exception:
            raise exception
