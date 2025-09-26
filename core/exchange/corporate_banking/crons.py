import datetime
import json
from typing import ClassVar

from django.conf import settings

from exchange.base.calendar import get_earliest_time, get_latest_time, ir_now, ir_tz
from exchange.base.crons import CronJob, Schedule
from exchange.base.logging import report_event, report_exception
from exchange.corporate_banking.integrations.base import BaseThirdPartyAPIClient
from exchange.corporate_banking.integrations.jibit.accounts_list import CobankJibitAccountsList
from exchange.corporate_banking.integrations.jibit.authenticator import CobankJibitAuthenticator
from exchange.corporate_banking.integrations.toman.accounts_list import CobankTomanAccountsList
from exchange.corporate_banking.integrations.toman.authenticator import CobankTomanAuthenticator
from exchange.corporate_banking.models import (
    ACCOUNT_TP,
    COBANK_PROVIDER,
    COBANK_PROVIDER_MAPPING,
    CoBankAccount,
    ThirdpartyLog,
)
from exchange.corporate_banking.services.accounts import CardSyncService
from exchange.corporate_banking.services.banker import Banker
from exchange.corporate_banking.services.refunder import Refunder
from exchange.corporate_banking.services.settler import Settler


class RefreshTokenCron(CronJob):
    schedule = Schedule(run_every_mins=60)
    code = 'cobank.refresh_tokens'
    celery_beat = True
    task_name = 'corporate_banking.core.logic.refresh_tokens'

    def run(self):
        if settings.IS_TESTNET:
            return
        CobankTomanAuthenticator().refresh_token()


class GetStatementsCron(CronJob):
    """
    Get the statements of the last 12 minutes every 2 minutes
    """

    schedule = Schedule(run_every_mins=2)
    code = 'cobank.get_statements'
    celery_beat = True
    task_name = 'corporate_banking.core.logic.get_statements'
    providers: ClassVar = [
        COBANK_PROVIDER.toman,
        COBANK_PROVIDER.jibit,
    ]

    def run(self):
        to_time = ir_now()
        from_time = (self.last_successful_start or ir_now()).astimezone(ir_tz()) - datetime.timedelta(minutes=20)
        for provider in self.providers:
            try:
                Banker(from_time=from_time, to_time=to_time, provider=provider).get_statements()
            except Exception:
                report_exception()


class GetDailyStatementsCron(CronJob):
    """
    Get the statements of yesterday to make sure no statement is left unsettled
    """

    schedule = Schedule(run_at_times=['04:00'])
    code = 'cobank.get_daily_statements'
    celery_beat = True
    task_name = 'corporate_banking.core.logic.get_daily_statements'
    providers: ClassVar = [
        COBANK_PROVIDER.toman,
        COBANK_PROVIDER.jibit,
    ]

    def run(self):
        yesterday = ir_now() - datetime.timedelta(days=1)
        to_time = get_latest_time(yesterday)
        from_time = get_earliest_time(yesterday)
        for provider in self.providers:
            try:
                Banker(from_time=from_time, to_time=to_time, provider=provider).get_statements()
                ThirdpartyLog.objects.filter(
                    status=ThirdpartyLog.STATUS.failure,
                    response_details={},
                    service=ThirdpartyLog.SERVICE.cobank_statements,
                    provider=ThirdpartyLog.COBANK_TO_THIRDPARTY_PROVIDER.get(provider),
                    created_at__lte=to_time,
                ).delete()
            except Exception:
                report_exception()


class GetAccountsCron(CronJob):
    schedule = Schedule(run_every_mins=10 if settings.IS_PROD else 2)
    code = 'cobank.get_accounts'
    celery_beat = True
    task_name = 'corporate_banking.core.logic.get_accounts'
    clients: ClassVar = [
        CobankTomanAccountsList,
        CobankJibitAccountsList,
    ]

    def run(self):
        exception = None
        for client in self.clients:
            try:
                self.get_accounts(client())
            except Exception as ex:
                report_exception()
                exception = ex

        if exception:  # To fail the cron, so it will be retried on the next minute
            raise exception

    def get_accounts(self, client: BaseThirdPartyAPIClient):
        page = 1
        has_next = True
        while has_next:
            paginated_result = client.get_bank_accounts(page=page)
            has_next = bool(paginated_result.next)
            page += 1
            for account in paginated_result.results:
                if account.bank_id is None:
                    report_event(
                        f'{COBANK_PROVIDER_MAPPING[account.provider]} Get Account Service gave wrong '
                        f'bank_id ({account.bank_id}) for account_id {account.id}',
                    )
                    continue

                update_defaults = {
                    'provider_is_active': account.active,
                    'iban': account.iban,
                    'account_number': account.account_number,
                    'account_owner': account.account_owner,
                    'opening_date': account.opening_date,
                    'balance': account.balance,
                    'deails': json.dumps(account.details),
                }

                create_defaults = {
                    **update_defaults,
                    'account_tp': ACCOUNT_TP.operational,
                    'provider': account.provider,
                    'provider_bank_id': account.id,
                    'bank': account.bank_id,
                }

                try:
                    cobank_account = CoBankAccount.objects.get(
                        provider=account.provider,
                        provider_bank_id=account.id,
                        bank=account.bank_id,
                    )

                    for key, value in update_defaults.items():
                        setattr(cobank_account, key, value)

                    cobank_account.save()
                except CoBankAccount.DoesNotExist:
                    CoBankAccount.objects.create(**create_defaults)


class SettleDepositsCron(CronJob):
    """
    Settle the statements that are validates as deposits
    """

    schedule = Schedule(run_every_mins=1)
    code = 'cobank.settle_deposits'
    celery_beat = True
    task_name = 'corporate_banking.core.logic.settle_deposits'

    def run(self):
        Settler().settle_statements()


class SettlePendingDepositsAutomaticallyCron(CronJob):
    """
    Settle the statements that are validates as deposits
    """

    schedule = Schedule(run_every_mins=10)
    code = 'cobank.automatic_settle_pending_deposits'
    celery_beat = True
    task_name = 'corporate_banking.core.logic.automatic_settle_pending_deposits'

    def run(self):
        Settler(settling_pending_deposits=True).settle_statements()


class GetCardsCron(CronJob):
    schedule = Schedule(run_every_mins=10 if settings.IS_PROD else 2)
    code = 'cobank.get_cards'
    celery_beat = True
    task_name = 'corporate_banking.core.logic.get_cards'

    def run(self):
        banks = CoBankAccount.objects.filter(provider=COBANK_PROVIDER.jibit)
        sync_service = CardSyncService()
        for bank in banks:
            try:
                sync_service.sync_bank_cards(bank)
            except Exception:
                report_exception()


class RefundRequestsHandlerCron(CronJob):
    """
    send to provider every new refund request
    """

    schedule = Schedule(run_every_mins=2)
    code = 'cobank.send_to_provider_refund_requests'
    celery_beat = True
    task_name = 'corporate_banking.core.logic.send_to_provider_refund_requests'
    providers: ClassVar = [
        COBANK_PROVIDER.toman,
    ]

    def run(self):
        for provider in self.providers:
            try:
                Refunder(provider=provider).send_new_requests_to_provider()
            except Exception:
                report_exception()


class RefundInquiryRequestsHandlerCron(CronJob):
    """
    Inquire with the provider about every refund request that has the potential to receive a new status.
    """

    schedule = Schedule(run_every_mins=5)
    code = 'cobank.inquiry_from_provider_refund_requests'
    celery_beat = True
    task_name = 'corporate_banking.core.logic.inquiry_from_provider_refund_requests'
    providers: ClassVar = [
        COBANK_PROVIDER.toman,
    ]

    def run(self):
        for provider in self.providers:
            try:
                Refunder(provider=provider).get_refunds_latest_status()
            except Exception:
                report_exception()


# --------------------------- jibit --------------------------------


class RefreshJibitTokenCron(CronJob):
    schedule = Schedule(run_every_mins=60)
    code = 'cobank.jibit.refresh_tokens'
    celery_beat = True
    task_name = 'corporate_banking.core.logic.jibit_refresh_tokens'

    def run(self):
        CobankJibitAuthenticator().refresh_token()
