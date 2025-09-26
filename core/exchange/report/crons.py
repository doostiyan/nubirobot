import datetime
from decimal import Decimal
from typing import Any, Callable, Optional, Union

import pytz
from django.conf import settings
from django.db.models import Max, Min
from django.utils.timezone import make_aware

from exchange.base.api import ParseError
from exchange.base.calendar import ir_now
from exchange.base.crons import CronJob, Schedule
from exchange.base.logging import report_event, report_exception
from exchange.base.models import Settings
from exchange.base.parsers import parse_bool, parse_choices, parse_int, parse_iso_date, parse_money, parse_str
from exchange.base.tasks import run_admin_task
from exchange.direct_debit.constants import PAGE_SIZE_IN_FETCH_DEPOSITS
from exchange.direct_debit.integrations.faraboom import FaraboomHandler
from exchange.direct_debit.models import DailyDirectDeposit, DirectDeposit
from exchange.report.models import (
    AdoptionStats,
    BanksGatewayStats,
    DailyJibitDeposit,
    DailyShetabDeposit,
    DailyWithdraw,
)
from exchange.report.parsers import (
    parse_daily_bank_deposit_status,
    parse_daily_shetab_deposit_status,
    parse_daily_withdraw_status,
    parse_jibit_reference_number,
)
from exchange.report.periodic_metrics_calculator import PeriodicMetricsCalculator
from exchange.shetab.handlers import JibitHandler, JibitHandlerV2, JibitPip
from exchange.shetab.handlers.pay import PayIrHandler
from exchange.shetab.handlers.vandar import VandarP2P
from exchange.shetab.models import JibitDeposit, ShetabDeposit
from exchange.wallet.models import BankDeposit, WithdrawRequest
from exchange.wallet.settlement import JibitSettlementV2


class UpdateDailyStatsCron(CronJob):
    # TODO: run at specific times to have more accurate stats, specially in the first minutes of day
    schedule = Schedule(run_every_mins=120)
    code = 'update_daily_stats'

    def run(self):
        print('[CRON] Updating daily statistics for user activities')
        nw = ir_now()
        today = nw.date()
        if settings.LOAD_LEVEL < 10:
            AdoptionStats.get(today).update_stats()


class SaveDailyMixin:
    guard_duration: datetime.timedelta
    filter_duration: datetime.timedelta
    api_func: Callable[[datetime.datetime, datetime.datetime, int], Any]
    model: Union[DailyShetabDeposit, DailyWithdraw, DailyJibitDeposit, DailyDirectDeposit]
    max_page = 300

    last_object_check = True
    # Triggers checking wether from_date will change to creation date of that obtained

    def run(self):
        to_date = ir_now().replace(minute=0, second=0, microsecond=0) - self.guard_duration
        from_date = to_date - self.filter_duration
        if self.last_object_check:
            last_object = self.model.objects.aggregate(date=Max('created_at'))['date']
            from_date = last_object if (last_object and last_object > from_date) else from_date
        from_date = self.get_from_date(from_date) or from_date
        self.update_items(from_date, to_date)

    @classmethod
    def update_items(cls, from_date, to_date):
        has_next = True
        page = 1

        while has_next and page < cls.max_page:
            response = cls.api_func(from_date, to_date, page)
            for item in cls.get_items(response):
                try:
                    data = cls.parse_item(item)
                    record, created = cls.model.objects.get_or_create(**data)
                    if created:
                        continue
                    changed_fields = {key for key, value in data['defaults'].items() if getattr(record, key) != value}
                    if changed_fields:
                        if not (
                            record.status in cls.model.STATUSES_TRANSIENT  # Broker can change values
                            or not changed_fields - cls.model.INTERNAL_FIELDS  # Internal fields can change
                        ):
                            raise AssertionError(f'{cls.model.__name__} values are changed after final state')
                        cls.model.objects.filter(pk=record.pk).update(**data['defaults'])
                except:
                    report_exception()
            has_next = cls.has_next(response)
            page += 1

        if has_next:
            report_event(
                'Too many iterations', extras={'from': from_date, 'to': to_date, 'api': cls.api_func.__qualname__}
            )

    @staticmethod
    def get_items(response: Any) -> list:
        raise NotImplementedError

    @staticmethod
    def has_next(response: Any) -> bool:
        raise NotImplementedError

    @classmethod
    def parse_item(cls, item: dict) -> dict:
        raise NotImplementedError

    def get_from_date(self, from_date: datetime.datetime) -> Optional[datetime.datetime]:
        first_transient = self.model.objects.filter(
            created_at__gte=from_date, status__in=self.model.STATUSES_TRANSIENT
        ).aggregate(date=Min('created_at'))['date']
        return first_transient


class SaveDailyDepositsV1(SaveDailyMixin, CronJob):
    # It's refactored for convenience
    schedule = Schedule(run_at_times=['00:30'])
    code = 'SaveDailyJibitDepositWithdraw'

    guard_duration = datetime.timedelta(0)
    filter_duration = datetime.timedelta(days=1)
    api_func = JibitHandler.fetch_deposits
    model = DailyShetabDeposit

    @staticmethod
    def get_items(response: Optional[dict]) -> list:
        return response['elements'] if response else []

    @staticmethod
    def has_next(response: Optional[dict]) -> bool:
        return parse_bool(response and response['hasNext'])

    @classmethod
    def parse_item(cls, deposit_data: dict) -> dict:
        return {
            'broker': DailyShetabDeposit.BROKER.jibit,
            'gateway_pk': deposit_data.get('id'),
            'amount': parse_money(deposit_data.get('amount')),
            'reference_number': deposit_data.get('referenceNumber'),
            'user_identifier': deposit_data.get('userIdentifier'),
            'description': deposit_data.get('description'),
            'additional_data': deposit_data.get('additionalData', '{}'),
            'expiration_date': parse_iso_date(deposit_data.get('expirationDate')),
            'deposit': cls.get_deposit(
                deposit_data.get('referenceNumber'), deposit_data.get('userIdentifier'), deposit_data.get('amount')
            ),
            'defaults': {
                'status': parse_daily_shetab_deposit_status(deposit_data.get('status')),
                'modified_at': parse_iso_date(deposit_data.get('modifiedAt')),
                'created_at': parse_iso_date(deposit_data.get('createdAt')),
                'payer_card': deposit_data.get('payerCard'),
                'national_code': deposit_data.get('nationalCode'),
            },
        }

    @staticmethod
    def get_deposit(reference_number: str, user_identifier: str, amount: str) -> ShetabDeposit:
        try:
            pk = parse_jibit_reference_number(reference_number)
            user_id = parse_int(user_identifier, required=True)
        except ParseError:
            return None
        return ShetabDeposit.objects.filter(
            pk=pk, broker=ShetabDeposit.BROKER.jibit_v2, user_id=user_id, amount=amount
        ).first()


class SaveDailyDepositsV2(SaveDailyMixin, CronJob):
    schedule = Schedule(run_every_mins=120)
    code = 'SaveDailyJibitDeposit'

    guard_duration = datetime.timedelta(hours=1)
    filter_duration = datetime.timedelta(hours=6)
    api_func = JibitHandlerV2.fetch_deposits
    model = DailyShetabDeposit

    @staticmethod
    def get_items(response: Optional[dict]) -> list:
        return response['elements'] if response else []

    @staticmethod
    def has_next(response: Optional[dict]) -> bool:
        return parse_bool(response and response['hasNext'])

    @classmethod
    def parse_item(cls, deposit_data: dict) -> dict:
        return {
            'broker': DailyShetabDeposit.BROKER.jibit_v2,
            'gateway_pk': deposit_data.get('purchaseId'),
            'amount': parse_money(deposit_data.get('amount')),
            'reference_number': deposit_data.get('clientReferenceNumber'),
            'user_identifier': deposit_data.get('userIdentifier'),
            'description': deposit_data.get('description'),
            'additional_data': deposit_data.get('additionalData'),
            'expiration_date': parse_iso_date(deposit_data.get('expirationDate')),
            'deposit': cls.get_deposit(
                deposit_data.get('clientReferenceNumber'),
                deposit_data.get('userIdentifier'),
                deposit_data.get('amount'),
            ),
            'defaults': {
                'status': parse_daily_shetab_deposit_status(deposit_data.get('state')),
                'modified_at': parse_iso_date(deposit_data.get('verifiedAt')),
                'created_at': parse_iso_date(deposit_data.get('createdAt')),
                'payer_card': deposit_data.get('payerCardNumber'),
                'national_code': deposit_data.get('payerNationalCode'),
            },
        }

    @staticmethod
    def get_deposit(reference_number: str, user_identifier: str, amount: str) -> Optional[ShetabDeposit]:
        try:
            pk = parse_jibit_reference_number(reference_number)
            user_id = parse_int(user_identifier, required=True)
        except ParseError:
            return None
        return ShetabDeposit.objects.filter(
            pk=pk, broker=ShetabDeposit.BROKER.jibit_v2, user_id=user_id, amount=amount
        ).first()


class SaveDailyDirectDeposits(SaveDailyMixin, CronJob):
    schedule = Schedule(run_every_mins=60 if not settings.IS_TESTNET else 10)
    code = 'SaveDailyFaraboomDirectDeposit'
    guard_duration = datetime.timedelta(minutes=10)
    filter_duration = datetime.timedelta(hours=3)
    api_func = FaraboomHandler.fetch_deposits
    model = DailyDirectDeposit
    max_page = 1000

    SENTINEL_NAME = 'daily_direct_debit_sentinel_v4'

    last_object_check = False

    def run(self):
        to_date = ir_now() - self.guard_duration
        from_date = to_date - self.filter_duration
        if self.last_object_check:
            last_object = self.model.objects.aggregate(date=Max('created_at'))['date']
            from_date = last_object if (last_object and last_object > from_date) else from_date
        from_date = self.get_from_date(from_date) or from_date
        self.update_items(from_date, to_date)

    @classmethod
    def update_items(cls, from_date, to_date):
        has_next = True
        page = 1
        banks = None
        while has_next and page < cls.max_page:

            # Due to the implementation of the function (cls.api_func), in subsequent calls we will send
            # only the banks that were included in the first call, in order to reduce redundant requests
            response = cls.api_func(from_date, to_date, page, only_banks=banks)
            banks = {deposit.get('source_bank') for deposit in response}

            for item in cls.get_items(response):
                try:
                    data = cls.parse_item(item)
                    record, created = cls.model.objects.get_or_create(**data)
                    if created:
                        continue

                    changed_fields = {key for key, value in data['defaults'].items() if getattr(record, key) != value}
                    if changed_fields:
                        cls.model.objects.filter(pk=record.pk).update(**data['defaults'])
                except:
                    report_exception()
            has_next = cls.has_next(response)
            page += 1

        to_date = to_date if to_date < ir_now() else ir_now()
        Settings.set_datetime(
            cls.SENTINEL_NAME,
            to_date.astimezone(pytz.utc),
        )

    @staticmethod
    def get_items(response: Optional[list]) -> list:
        return response or []

    @staticmethod
    def has_next(response: Optional[dict]) -> bool:
        """
        If the length of the response is less than the page_size, it means that there are no other deposits
        """
        return len(response) >= PAGE_SIZE_IN_FETCH_DEPOSITS

    @classmethod
    def parse_item(cls, deposit_data: dict) -> dict:
        return {
            'trace_id': deposit_data.get('trace_id'),
            'defaults': {
                'status': cls._parse_status(deposit_data.get('status'), deposit_data.get('error_type', '')),
                'transaction_amount': parse_money(deposit_data.get('transaction_amount')),
                'description': deposit_data.get('description'),
                'reference_id': deposit_data.get('reference_id') or '',
                'contract_id': deposit_data.get('payman_id'),
                'transaction_type': deposit_data.get('transaction_type'),
                'destination_bank': deposit_data.get('destination_bank'),
                'source_bank': deposit_data.get('source_bank'),
                'server_date': cls.parse_iso_date(deposit_data.get('server_date')),
                'client_date': cls.parse_iso_date(deposit_data.get('client_date')),
                'deposit': cls.get_deposit(
                    deposit_data.get('trace_id'),
                    deposit_data.get('transaction_amount'),
                ),
            },
        }

    @classmethod
    def _parse_status(cls, value: str, error_type: str):
        status = parse_choices(DailyDirectDeposit.STATUS, value.lower())
        if error_type == 'BALANCE_FAILED' and status == DailyDirectDeposit.STATUS.failed:
            return DailyDirectDeposit.STATUS.insufficient_balance
        return status


    @staticmethod
    def parse_iso_date(date: str) -> datetime:
        fmt = '%Y-%m-%dT%H:%M:%S'
        return pytz.timezone('Asia/Tehran').localize(datetime.datetime.strptime(date, fmt))

    @staticmethod
    def get_deposit(trace_id: str, amount: str) -> Optional[ShetabDeposit]:
        return DirectDeposit.objects.filter(trace_id=trace_id, amount=amount).first()

    def get_from_date(self, from_date: datetime.datetime) -> Optional[datetime.datetime]:
        default_from_date = make_aware(datetime.datetime(2024, 3, 1, 0, 0, 0))
        from_date = Settings.get_datetime(self.SENTINEL_NAME, default_from_date)
        return from_date - self.filter_duration


class SaveDailyWithdrawsV1(SaveDailyMixin, CronJob):
    # It's refactored for convenience
    schedule = Schedule(run_at_times=['00:30'])
    code = 'SaveDailyJibitDepositWithdraw'

    guard_duration = datetime.timedelta(0)
    filter_duration = datetime.timedelta(days=1)
    api_func = JibitHandler.fetch_withdraws
    model = DailyWithdraw

    @staticmethod
    def get_items(response: Optional[dict]) -> list:
        return (response['elements'] or []) if response else []

    @staticmethod
    def has_next(response: Optional[dict]) -> bool:
        return bool(response and response['elements'])

    @classmethod
    def parse_item(cls, withdraw_data: dict) -> dict:
        return {
            'broker': DailyWithdraw.BROKER.jibit,
            'transfer_pk': withdraw_data.get('transferID'),
            'transfer_mode': withdraw_data.get('transferMode'),
            'destination': withdraw_data.get('destination'),
            'amount': parse_money(withdraw_data.get('amount')),
            'description': withdraw_data.get('description'),
            'gateway_fee': 0,
            'defaults': {
                'status': parse_daily_withdraw_status(withdraw_data.get('state')),
                'bank_transfer': parse_str(
                    withdraw_data.get('bankTransferID') or f'jibit_{withdraw_data.get("transferID")}', max_length=50
                ),
                'created_at': parse_iso_date(withdraw_data.get('createdAt')),
                'destination_first_name': withdraw_data.get('destinationFirstName'),
                'destination_last_name': withdraw_data.get('destinationLastName'),
                'withdraw': cls.get_withdraw(
                    withdraw_data.get('transferID'), withdraw_data.get('destination'), withdraw_data.get('amount')
                ),
            }
        }

    @staticmethod
    def get_withdraw(transfer_pk: str, destination: str, amount: str) -> Optional[WithdrawRequest]:
        try:
            pk = parse_int(transfer_pk, required=True)
        except ParseError:
            return None
        withdraw = WithdrawRequest.objects.filter(pk=pk, target_account__shaba_number=destination).first()
        if withdraw and JibitSettlementV2(withdraw).net_amount != Decimal(amount):
            return None
        return withdraw


class SaveDailyWithdrawsV2(SaveDailyMixin, CronJob):
    schedule = Schedule(run_every_mins=120)
    code = 'SaveDailyJibitWithdraw'

    guard_duration = datetime.timedelta(hours=1)
    filter_duration = datetime.timedelta(hours=8)
    api_func = JibitSettlementV2.fetch_withdraws
    model = DailyWithdraw

    @staticmethod
    def get_items(response: list) -> list:
        return response

    @staticmethod
    def has_next(response: list) -> bool:
        return bool(response)

    @classmethod
    def parse_item(cls, withdraw_data: dict) -> dict:
        return {
            'broker': DailyWithdraw.BROKER.jibit_v2,
            'transfer_pk': withdraw_data.get('transferID'),
            'transfer_mode': withdraw_data.get('transferMode'),
            'destination': withdraw_data.get('destination'),
            'amount': parse_money(withdraw_data.get('amount')),
            'description': withdraw_data.get('description'),
            'defaults': {
                'status': parse_daily_withdraw_status(withdraw_data.get('state')),
                'bank_transfer': parse_str(
                    withdraw_data.get('bankTransferID') or f'jibit_{withdraw_data.get("transferID")}', max_length=50
                ),
                'created_at': parse_iso_date(withdraw_data.get('createdAt')),
                'destination_first_name': parse_str(withdraw_data.get('destinationFirstName'), max_length=50),
                'destination_last_name': parse_str(withdraw_data.get('destinationLastName'), max_length=50),
                'gateway_fee': withdraw_data.get('feeAmount'),
                'withdraw': cls.get_withdraw(
                    withdraw_data.get('transferID'),
                    withdraw_data.get('destination'),
                    withdraw_data.get('amount'),
                    withdraw_data.get('paymentID'),
                ),
            }
        }

    @staticmethod
    def get_withdraw(
        transfer_pk: str, destination: str, amount: str, payment_id: Optional[str] = None
    ) -> Optional[WithdrawRequest]:
        try:
            pk = parse_int(transfer_pk, required=True)
        except ParseError:
            return None
        possible_shaba = [destination] if payment_id is None else [destination, payment_id]
        withdraw = WithdrawRequest.objects.filter(pk=pk, target_account__shaba_number__in=possible_shaba).first()
        if withdraw and JibitSettlementV2(withdraw).net_amount != Decimal(amount):
            return None
        return withdraw

class OldDataUpdateDailyWithdraws(SaveDailyWithdrawsV2):
    """Getting all old and new data from Jibit in one cron, has been facing (Too Many Iterations) error lately.
    And we have not been able to obtain new Data, because each time we face the error and on each run, we get data for more than 3 days ago
    In order to fix the problem, we are breaking the getting data into 2 different crons.
    One will get the data for the past day, and the other (this one) for all the old data.
    """
    schedule = Schedule(run_every_mins=240)
    code = 'OldDataUpdateDailyWithdraws'

    guard_duration = datetime.timedelta(days=1)
    filter_duration = datetime.timedelta(days=6)
    last_object_check = False


class DailyWithdrawsManuallyFailedV2(SaveDailyWithdrawsV2):
    schedule = Schedule(run_every_mins=60)
    code = 'SaveDailyJibitWithdrawManuallyFailed'

    guard_duration = datetime.timedelta(minutes=20)
    filter_duration = datetime.timedelta(days=20)

    def run(self):
        to_date = ir_now() - self.guard_duration
        from_date = to_date - self.filter_duration
        self.update_items(from_date, to_date)

    @classmethod
    def update_items(cls, from_date, to_date):
        has_next = True
        page = 1

        ids = []
        while has_next and page < 25:
            response = cls.api_func(from_date, to_date, page, manually_failed=True)
            for item in cls.get_items(response):
                try:
                    data = cls.parse_item(item)
                    status = data.pop('defaults').get('status')  # Always equals to Manually Failed
                    try:
                        record = cls.model.objects.get(**data)
                    except cls.model.DoesNotExist:
                        continue
                    if status != record.status:
                        ids.append(record.id)
                except:
                    report_exception()
            has_next = cls.has_next(response)
            page += 1
        run_admin_task('admin.daily_withdraw_manually_failed', daily_withdraw_ids=ids)
        if has_next:
            report_event(
                'Too many iterations', extras={'from': from_date, 'to': to_date, 'api': cls.api_func.__qualname__}
            )


class SaveBanksGatewayStatsCron(CronJob):
    schedule = Schedule(run_at_times=['{}:00'.format(str(i).zfill(2)) for i in range(24)])
    code = 'save_banks_gateway_stats'

    def run(self):
        print('[CRON] save_banks_gateway_stats')
        nw = ir_now()

        jibit_balances = JibitSettlementV2.get_balance()
        vandar_balances = VandarP2P.get_balance()
        payir_balances = PayIrHandler.get_wallet_balances()

        if jibit_balances:
            balance = jibit_balances['balance'] + jibit_balances['settleableBalance']
            stat = BanksGatewayStats.get(nw, BanksGatewayStats.gateway_choices.jibit)
            stat.balance = balance
            stat.save()
        if vandar_balances:
            stat = BanksGatewayStats.get(nw, BanksGatewayStats.gateway_choices.vandar)
            stat.balance = vandar_balances
            stat.save()
        if payir_balances:
            stat = BanksGatewayStats.get(nw, BanksGatewayStats.gateway_choices.pey)
            stat.balance = payir_balances
            stat.save()


class SaveJibitBankDeposits(SaveDailyMixin, CronJob):
    schedule = Schedule(run_every_mins=120)
    code = 'SaveJibitBankDeposits'
    model = DailyJibitDeposit

    guard_duration = datetime.timedelta(hours=1)
    filter_duration = datetime.timedelta(days=3)
    api_func = JibitPip.fetch_deposits

    @staticmethod
    def get_items(response: Optional[dict]) -> list:
        return (response.get('content') or []) if response else []

    @staticmethod
    def has_next(response: Optional[dict]) -> bool:
        return not bool(response.get('last'))

    @classmethod
    def parse_item(cls, item: dict) -> dict:
        external_reference_number = item.get('externalReferenceNumber')
        bank_reference_number = item.get('bankReferenceNumber')
        payment_id = item.get('paymentId')
        jibit_deposit = cls.get_jibit_deposit(external_reference_number, payment_id)
        bank_deposit = cls.get_bank_deposit(jibit_deposit=jibit_deposit, receipt_id=bank_reference_number)
        return {
            'external_reference_number': external_reference_number,
            'bank': item.get('bank'),
            'bank_reference_number': bank_reference_number,
            'payment_id': payment_id,
            'merchant_reference_number': item.get('merchantReferenceNumber'),
            'amount': parse_money(item.get('amount')),
            'source_identifier': item.get('sourceIdentifier'),
            'destination_account_identifier': item.get('destinationAccountIdentifier'),
            'defaults': {
                'status': parse_daily_bank_deposit_status(item.get('status')),
                'jibit_deposit': jibit_deposit,
                'bank_deposit': bank_deposit,
                'bank_raw_timestamp': item.get('rawBankTimestamp'),
            }
        }

    @staticmethod
    def get_bank_deposit(jibit_deposit: JibitDeposit, receipt_id) -> Optional[BankDeposit]:
        if not jibit_deposit:
            return None
        deposit = jibit_deposit.bank_deposit
        if deposit and deposit.receipt_id == receipt_id:
            return deposit
        return None

    @staticmethod
    def get_jibit_deposit(external_reference_number, payment_id):
        return JibitDeposit.objects.filter(
            external_reference_number=external_reference_number,
            payment_id__payment_id=payment_id,
        ).first()


class SendPeriodicMetricsToKafkaCron(CronJob):
    schedule = Schedule(run_every_mins=0.25)
    code = 'reports.metrics.periodic_metrics'
    celery_beat = True
    task_name = 'reports.metrics.send_periodic_metrics_to_kafka'

    def run(self):
        periodic_metric_calculator = PeriodicMetricsCalculator(target='kafka')
        periodic_metric_calculator.set_metrics()
        periodic_metric_calculator.send_metrics()
