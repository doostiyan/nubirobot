import datetime
import uuid
from decimal import Decimal
from typing import Optional

from exchange import settings
from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.crypto import random_string, unique_random_string
from exchange.base.models import Settings
from exchange.direct_debit.models import DirectDebitBank, DirectDebitContract, DirectDeposit
from tests.features.utils import BetaFeatureTestMixin


class DirectDebitMixins(BetaFeatureTestMixin):
    feature = 'direct_debit'

    @property
    def base_url(self):
        return (
            settings.FARABOOM_APIS_BASE_URL
            if settings.IS_PROD
            else Settings.get_value('direct_debit_testnet_base_url', 'https://payman2.sandbox.faraboom.co')
        )

    def create_bank(
        self,
        bank_id: Optional[str] = None,
        max_daily_transaction_amount: Optional[Decimal] = None,
        max_daily_transaction_count: Optional[int] = None,
        name: Optional[str] = None,
        max_transaction_amount: Optional[Decimal] = None,
    ) -> DirectDebitBank:
        return DirectDebitBank.objects.create(
            bank_id=bank_id or random_string(6).upper(),
            name=name or random_string(15),
            daily_max_transaction_amount=max_daily_transaction_amount or Decimal('10_000_000_0'),
            daily_max_transaction_count=max_daily_transaction_count or 5,
            max_transaction_amount=max_transaction_amount or 0,
        )

    def create_contract(
        self,
        user: User,
        status: int = DirectDebitContract.STATUS.active,
        start_date: datetime = None,
        expire_date: datetime = None,
        bank: DirectDebitBank = None,
        count: int = 0,
        amount: Optional[Decimal] = None,
        contract_code: Optional[str] = None,
    ) -> DirectDebitContract:
        count = count or 5
        amount = amount or Decimal('10_000_000_0')
        bank = bank or self.create_bank()

        return DirectDebitContract.objects.create(
            status=status,
            user=user,
            bank=bank,
            contract_code=contract_code or random_string(10),
            contract_id=random_string(10),
            trace_id=unique_random_string(),
            started_at=start_date or ir_now(),
            expires_at=expire_date or ir_now() + datetime.timedelta(days=10),
            daily_max_transaction_count=count,
            max_transaction_amount=count * amount,
        )

    def create_deposit(
        self,
        user: User,
        contract: DirectDebitContract = None,
        amount: Decimal = Decimal('10_000_000_0'),
        status: int = DirectDeposit.STATUS.succeed,
        trace_id: Optional[str] = None,
        reference_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        deposited_at: datetime = None,
    ) -> DirectDeposit:
        return DirectDeposit.objects.create(
            trace_id=trace_id or uuid.uuid4().hex,
            deposited_at=deposited_at or ir_now() + datetime.timedelta(minutes=15),
            contract=contract or self.create_contract(user),
            amount=amount,
            fee=DirectDeposit.calculate_fee(amount),
            reference_id=reference_id if reference_id is not None else uuid.uuid4().hex,
            batch_id=batch_id or uuid.uuid4().hex,
            status=status,
        )


class MockResponse:
    def __init__(self, json_data, status_code, headers=None):
        self.json_data = json_data
        self.status_code = status_code
        self.headers = headers

    def json(self):
        return self.json_data
