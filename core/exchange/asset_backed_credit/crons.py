from django.conf import settings
from jdatetime import timedelta

from exchange.asset_backed_credit.models import SettlementTransaction
from exchange.asset_backed_credit.services.debit.card import register_debit_cards_in_third_party, update_cards_info
from exchange.asset_backed_credit.services.debit.invoice import send_debit_invoices_emails
from exchange.asset_backed_credit.services.debit.recon import reconcile
from exchange.asset_backed_credit.services.loan.debt_to_grant_ratio import cache_min_loan_debt_to_grant_ratio
from exchange.asset_backed_credit.services.loan.options import set_all_services_options as set_loan_services_options
from exchange.asset_backed_credit.services.logging import process_abc_outgoing_api_logs
from exchange.asset_backed_credit.services.margin_call import execute_margin_calls, execute_margin_calls_hourly
from exchange.asset_backed_credit.services.report import generate_requested_reports_attachments
from exchange.asset_backed_credit.services.settlement import settle_pending_settlements
from exchange.asset_backed_credit.services.store import fetch_stores
from exchange.asset_backed_credit.services.user import update_internal_users_data
from exchange.asset_backed_credit.services.user_service import update_credit_user_services_status
from exchange.asset_backed_credit.services.user_service_limit import update_financial_limit_on_users
from exchange.asset_backed_credit.services.wallet.transfer import process_pending_withdraw_requests
from exchange.asset_backed_credit.services.wallet.wallet import check_wallets_cache_consistency
from exchange.asset_backed_credit.services.withdraw import (
    create_provider_withdraw_requests,
    settle_provider_withdraw_request_logs,
)
from exchange.base.calendar import get_start_and_end_of_jalali_week, ir_today
from exchange.base.crons import CronJob, Schedule
from exchange.base.logging import report_exception
from exchange.base.models import Settings


class ABCUserSettlementCron(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'abc_settle_users'
    celery_beat = True
    task_name = 'abc.core.task_user_settlement_cron'

    def run(self):
        settle_pending_settlements()


class ABCMarginCallManagementCron(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'abc_manage_margin_calls'
    celery_beat = True
    task_name = 'abc.core.task_margin_call_management_cron'

    def run(self):
        execute_margin_calls()


class ABCMarginCallManagementHourlyCron(CronJob):
    RUN_AT_TIMES = ['01:30', '04:30', '07:30', '10:30', '13:30', '16:30', '19:30', '22:30']

    if settings.IS_TESTNET:
        schedule = Schedule(run_every_mins=15)
    else:
        schedule = Schedule(run_at_times=RUN_AT_TIMES)

    code = 'abc_manage_margin_calls_hourly'
    celery_beat = True
    task_name = 'abc.core.task_margin_call_management_hourly_cron'

    def run(self):
        execute_margin_calls_hourly()


class ProcessWalletWithdrawsCron(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'abc_process_withdraws'
    celery_beat = True
    task_name = 'abc.core.task_process_collateral_withdraws_cron'

    def run(self):
        process_pending_withdraw_requests()


class ABCProvidersWithdrawalsCron(CronJob):
    if settings.IS_TESTNET:
        schedule = Schedule(run_every_mins=15)
    else:
        schedule = Schedule(run_at_times=('02:15',))

    code = 'abc_providers_withdrawals'
    celery_beat = True
    task_name = 'abc.core.task_process_provider_withdraws_cron'

    def run(self):
        create_provider_withdraw_requests()


class ABCSettleProviderWithdrawalsCron(CronJob):
    schedule = Schedule(run_every_mins=15)
    code = 'abc_settle_providers_withdrawals'
    celery_beat = True
    task_name = 'abc.core.task_settle_provider_withdraws_cron'

    def run(self):
        settle_provider_withdraw_request_logs()


class ABCUnknownConfirmInitiatedUserSettlementCron(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'abc_unknown_confirm_initiated_user_settlements'
    celery_beat = True
    task_name = 'abc.core.task_unknown_confirm_initiated_user_settlements_cron'

    def run(self):
        SettlementTransaction.unknown_confirm_initiated_user_settlements()


class ABCUpdateUserFinancialServiceLimitCron(CronJob):
    schedule = Schedule(run_every_mins=5)
    code = 'abc_update_user_financial_service_limit'
    celery_beat = True
    task_name = 'abc.core.task_update_financial_limit_on_users_cron'

    def run(self):
        update_financial_limit_on_users()


class ABCReconDebitSettlements(CronJob):
    schedule = Schedule(run_at_times=('09:30',))
    code = 'abc_recon_debit_settlements'
    celery_beat = True
    task_name = 'abc.core.task_debit_recon_settlements_cron'

    def run(self):
        if not Settings.get_flag('abc_debit_recon_enabled'):
            return
        try:
            reconcile()
        except Exception:
            report_exception()


class ABCCacheMinLoanDebtToGrantRatio(CronJob):
    schedule = Schedule(run_every_mins=15)
    code = 'abc_cache_min_loan_debt_to_grant_ratio'
    celery_beat = True
    task_name = 'abc.core.task_cache_min_loan_debt_to_grant_ratio_cron'

    def run(self):
        cache_min_loan_debt_to_grant_ratio()


class ABCDebitWeeklyInvoiceEmail(CronJob):
    RUN_WEEKLY_ON_DAYS = [
        5,
    ]  # Saturday
    RUN_AT_TIMES = ['09:00']

    if settings.IS_TESTNET:
        schedule = Schedule(run_every_mins=15)
    else:
        schedule = Schedule(run_on_days=RUN_WEEKLY_ON_DAYS, run_at_times=RUN_AT_TIMES)
    code = 'abc_debit_weekly_invoice_email'
    celery_beat = True
    task_name = 'abc.core.task_send_weekly_debit_invoices_emails_cron'

    def run(self):
        if Settings.get_flag('abc_enable_debit_weekly_invoice_cron'):
            this_week_start = get_start_and_end_of_jalali_week(ir_today())[0].togregorian()
            previous_week_start, previous_week_end = get_start_and_end_of_jalali_week(
                this_week_start - timedelta(days=2)
            )
            send_debit_invoices_emails(previous_week_start.togregorian(), previous_week_end.togregorian())


class ABCUpdateDebitCardsInfo(CronJob):
    schedule = Schedule(run_every_mins=10)
    code = 'abc_update_debit_cards_info'
    celery_beat = True
    task_name = 'abc.core.task_debit_update_cards_info_cron'

    def run(self):
        update_cards_info()


class ABCDebitCardRegisterRequestedCards(CronJob):
    schedule = Schedule(run_every_mins=10)
    code = 'abc_debit_card_register_requested_cards'
    celery_beat = True
    task_name = 'abc.core.task_debit_register_cards_in_third_party_cron'

    def run(self):
        register_debit_cards_in_third_party()


class UpdateInternalUsersData(CronJob):
    if settings.IS_TESTNET:
        schedule = Schedule(run_every_mins=10)
    else:
        schedule = Schedule(run_at_times=('01:30',))
    code = 'abc_update_internal_user_data'
    celery_beat = True
    task_name = 'abc.core.task_update_internal_user_data'

    def run(self):
        update_internal_users_data()


class UpdateCreditUserServicesStatus(CronJob):
    schedule = Schedule(run_every_mins=5)
    code = 'abc_update_credit_user_services_status'
    celery_beat = True
    task_name = 'abc.core.task_update_credit_user_services_status'

    def run(self):
        update_credit_user_services_status()


class ProcessApiCallLogs(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'abc_process_api_call_logs'
    celery_beat = True
    task_name = 'abc_process_abc_api_logs_beat'

    def run(self):
        process_abc_outgoing_api_logs()


class SetLoanServiceOptions(CronJob):
    interval = 5 if settings.IS_TESTNET else 30
    schedule = Schedule(run_every_mins=interval)
    code = 'abc_set_loan_service_options'
    celery_beat = True
    task_name = 'abc_set_loan_service_options'

    def run(self):
        set_loan_services_options()


class CheckWalletsCacheConsistency(CronJob):
    schedule = Schedule(run_every_mins=30)
    code = 'abc_check_wallets_cache_consistency'
    celery_beat = True
    task_name = 'abc_check_wallets_cache_consistency'

    def run(self):
        check_wallets_cache_consistency()


class FetchStores(CronJob):
    interval = 60
    schedule = Schedule(run_every_mins=interval)
    code = 'abc_fetch_stores'
    celery_beat = True
    task_name = 'abc_fetch_stores'

    def run(self):
        fetch_stores()

        
class GenerateReportAttachments(CronJob):
    schedule = Schedule(run_every_mins=5)
    code = 'abc_generate_report_attachments'
    celery_beat = True
    task_name = 'abc_generate_report_attachments'

    def run(self):
        generate_requested_reports_attachments()
