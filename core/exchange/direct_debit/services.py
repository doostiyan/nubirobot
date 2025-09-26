import datetime
import json
from dataclasses import asdict
from typing import Tuple

from django.db import IntegrityError
from requests import HTTPError
from rest_framework.exceptions import status as http_status

from exchange.base.logging import report_exception
from exchange.base.parsers import parse_choices
from exchange.direct_debit.exceptions import DiffResolverError
from exchange.direct_debit.integrations.faraboom import FaraboomHandler
from exchange.direct_debit.models import DailyDirectDeposit, DirectDeposit
from exchange.direct_debit.types import (
    DirectDepositTraceObject,
    get_deposit_dto_from_object,
    get_deposit_dto_from_response,
)
from exchange.wallet.models import Transaction


class DirectDebitUpdateDeposit:

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.daily_deposit = DailyDirectDeposit.objects.select_related('deposit').filter(trace_id=trace_id).first()
        self.deposit = DirectDeposit.objects.filter(trace_id=trace_id).select_related('contract__bank').first()
        self._validate_deposit_existence()

    def resolve_diff(self):
        try:
            is_daily_deposit_created = self._ensure_daily_deposit()
            contract = self._get_contract()
            self._ensure_direct_deposit(contract)
            self._connect_deposit_to_daily()

            if not self._is_diff_case():
                return

            if not is_daily_deposit_created or self.daily_deposit.status != DailyDirectDeposit.STATUS.succeed:
                response = self._inquiry(
                    bank_id=contract.bank.bank_id,
                    trace_id=self.daily_deposit.trace_id,
                    server_date=self.daily_deposit.server_date,
                )
                faraboom_response = get_deposit_dto_from_response(response)
                self._update_daily_deposit(faraboom_response)
            else:
                faraboom_response = get_deposit_dto_from_object(self.daily_deposit)

            status = parse_choices(DirectDeposit.STATUS, faraboom_response.status)

            if status == DirectDeposit.STATUS.in_progress:
                return

            if status == DirectDeposit.STATUS.succeed:
                self._run_succeed_case(data=faraboom_response)
                return

            if (
                status in [DirectDeposit.STATUS.failed, DirectDeposit.STATUS.reversed, DirectDeposit.STATUS.timeout]
                and not self.deposit.transaction_id
            ):
                self._run_failed_case(data=faraboom_response)
        except HTTPError as e:
            if e.response.status_code == http_status.HTTP_400_BAD_REQUEST:
                self._run_not_found_case()
        except IntegrityError:
            if self.deposit and not self.deposit.transaction_id:
                _transaction = Transaction.objects.filter(
                    ref_module=Transaction.REF_MODULES['DirectDebitUserTransaction'],
                    ref_id=self.deposit.id,
                ).first()
                if _transaction:
                    self.daily_deposit = DailyDirectDeposit.objects.filter(trace_id=self.deposit.trace_id).first()
                    if self.daily_deposit:
                        self.deposit.reference_id = self.daily_deposit.reference_id
                    self.deposit.transaction = _transaction
                    self.deposit.status = DirectDeposit.STATUS.succeed
                    self.deposit.deposited_at = _transaction.created_at
                    self.deposit.save(update_fields=['transaction', 'reference_id', 'status', 'deposited_at'])
                    return
            report_exception()
            return
        except Exception:
            report_exception()
            return

    def _validate_deposit_existence(self):
        if not self.daily_deposit and not self.deposit:
            raise DiffResolverError(f'direct deposit not found - trace_id={self.trace_id}')

    def _ensure_daily_deposit(self) -> bool:
        if not self.daily_deposit:
            self.daily_deposit = self._create_daily_deposit()
            return True
        return False

    def _ensure_direct_deposit(self, contract: 'DirectDebitContract'):
        if not self.deposit:
            self.deposit = self._get_or_create_deposit(contract)

    def _connect_deposit_to_daily(self):
        if not self.daily_deposit.deposit:
            self.daily_deposit.deposit = self.deposit
            self.daily_deposit.save(update_fields=['deposit'])

    def _create_daily_deposit(self) -> 'DailyDirectDeposit':
        from exchange.direct_debit.models import DailyDirectDeposit
        from exchange.direct_debit.types import get_deposit_dto_from_response

        response = self._inquiry(
            trace_id=self.trace_id,
            bank_id=self.deposit.contract.bank.bank_id,
            server_date=self.deposit.created_at,
        )
        daily_object = get_deposit_dto_from_response(response)
        data = daily_object.prepare_for_create()
        data['contract_id'] = self.deposit.contract.contract_id
        data['deposit_id'] = self.deposit.id
        daily_deposit = DailyDirectDeposit.objects.create(**data)
        return daily_deposit

    def _get_or_create_deposit(self, contract: 'DirectDebitContract') -> 'DirectDeposit':
        from exchange.direct_debit.models import DirectDeposit

        if self.daily_deposit.deposit:
            return self.daily_deposit.deposit

        deposit, created = DirectDeposit.objects.get_or_create(
            trace_id=self.daily_deposit.trace_id,
            defaults={'contract': contract},
        )
        return deposit

    def _inquiry(self, bank_id: str, trace_id: str, server_date: datetime):
        return FaraboomHandler().fetch_deposit_stats(
            trace_id=trace_id,
            date=server_date,
            bank_id=bank_id,
        )

    def _run_failed_case(self, data: DirectDepositTraceObject):
        self.deposit.amount = data.transaction_amount
        self.deposit.reference_id = data.reference_id
        self.deposit.batch_id = data.batch_id
        if self.deposit.status != self.deposit.STATUS.insufficient_balance:
            self.deposit.status = parse_choices(self.deposit.STATUS, data.status)
        self.deposit.third_party_response = asdict(data)
        self.deposit.save()

    def _run_succeed_case(self, data: DirectDepositTraceObject):

        if self.deposit.transaction_id:
            self.deposit.third_party_response = asdict(data)
            self.deposit.save()
            return  # must handle manually

        data_for_update = data.prepare_for_update()
        data_for_update['third_party_response'] = asdict(data)
        self.deposit.contract._finalize_deposit(self.deposit, data_for_update)

    def _run_not_found_case(self):
        if not self.deposit:
            return
        self.deposit.status = self.deposit.STATUS.failed
        self._update_third_party_response('Not found this trace_id in faraboom')

    def _is_diff_case(self):
        if (
            self.daily_deposit.deposit
            and self.daily_deposit.deposit.transaction_id
            and self.daily_deposit.deposit.status == self.daily_deposit.status
            and self.daily_deposit.deposit.amount == self.daily_deposit.transaction_amount
        ):
            self._update_third_party_response('It is not a diff case')
            return False
        return True

    def _get_contract(self):
        from exchange.direct_debit.models import DirectDebitContract

        contract = (
            DirectDebitContract.objects.filter(
                contract_id=self.daily_deposit.contract_id,
            )
            .select_related('bank')
            .first()
        )
        if not contract:
            self._update_third_party_response(
                f'Contract {self.daily_deposit.contract_id} not found',
            )
            raise DiffResolverError(f'Contract {self.daily_deposit.contract_id} not found')
        return contract

    def _update_third_party_response(self, third_party_response):
        if not isinstance(self.deposit.third_party_response, dict):
            self.deposit.third_party_response = (
                {'error_response': self.deposit.third_party_response}
                if isinstance(self.deposit.third_party_response, str)
                else {}
            )

        self.deposit.third_party_response['diff_try_response'] = third_party_response
        self.deposit.save()

    def _update_daily_deposit(self, data: DirectDepositTraceObject):
        self.daily_deposit.deposit = self.deposit
        for key, value in data.prepare_for_create().items():
            if value:
                setattr(self.daily_deposit, key, value)
        self.daily_deposit.save()
