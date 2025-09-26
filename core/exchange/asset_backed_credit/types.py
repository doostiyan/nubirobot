from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum, IntEnum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import UUID4, BaseModel, ConfigDict, Field, PlainSerializer, conlist, field_validator, model_validator
from pydantic.alias_generators import to_camel
from typing_extensions import Annotated

from exchange.asset_backed_credit.currencies import ABCCurrencies
from exchange.asset_backed_credit.exceptions import (
    InvalidMarginDstWalletCurrency,
    InvalidWithdrawDestinationWallet,
    WalletValidationError,
)
from exchange.asset_backed_credit.models.wallet import Transaction, Wallet
from exchange.base.api import ParseError
from exchange.base.constants import MONETARY_DECIMAL_PLACES, ZERO
from exchange.base.helpers import get_symbol_from_currency_code
from exchange.base.parsers import parse_currency, parse_money
from exchange.config.config.derived_data import DST_CURRENCIES, MARGIN_CURRENCIES
from exchange.wallet.constants import TRANSACTION_MAX, TRANSACTION_MAX_DIGITS

DEBIT_FEATURE_FLAG = 'abc_debit'

FeeDecimal = Annotated[Decimal, PlainSerializer(lambda x: f'{x:.1f}', return_type=str)]


class MTI(Enum):
    REQUESTED = '0200'
    CONFIRMED = '0220'
    REJECTED = '0400'

    @classmethod
    def from_value(cls, value):
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f'No member of {cls.__name__} has value {value}')


@dataclass
class TransactionRequest:
    mti: MTI
    pan: str
    rrn: str
    trace_id: str
    date: str
    time: str
    process_code: str
    terminal_id: str
    terminal_owner: str
    amount: Decimal
    rid: str
    description: str
    additional_data: str


@dataclass
class TransactionResponse:
    status: str
    pan: str = None
    rid: str = None
    rrn: str = None
    trace: str = None


bank_switch_status_code_mapping = {
    'SUCCESS': '00',
    'DUPLICATE_TRANSACTION': '02',
    'BALANCE_NOT_ENOUGH': '51',
    'UNAUTHORIZED_TRANSACTION': '57',
    'AMOUNT_LIMIT_EXCEEDED': '61',
    'CARD_RESTRICTED': '62',
    'CARD_EXPIRED': '54',
    'CARD_INACTIVE': '78',
}


@dataclass
class CreditWalletBulkWithdrawCreateRequest:
    dst_type: int
    src_type: int
    transfers: Dict[int, Decimal]


@dataclass
class AssetPriceData:
    total_mark_price: Decimal
    total_nobitex_price: Decimal
    weighted_avg: Optional[Decimal] = None


@dataclass
class MarginCallCandidate:
    user_id: int
    internal_user_id: int
    margin_call_id: int
    total_debt: Decimal
    total_assets: AssetPriceData = 0
    is_rial_only: bool = False
    ratio: Decimal = None


class ProviderFeeType(str, Enum):
    PRE_PAID = 'PRE_PAID'
    ON_INSTALLMENTS = 'ON_INSTALLMENTS'


@dataclass
class ProviderBasedLoanCalculationData:
    principal: int
    installment_amount: int
    period: int
    interest_rate: Decimal
    provider_fee_percent: Decimal
    provider_fee_amount: int
    provider_fee_type: ProviderFeeType
    total_installments_amount: int
    extra_info: dict = dict


class LoanCalculationData(BaseModel):
    principal: int
    installment_amount: int
    period: int
    interest_rate: int
    collateral_fee_percent: FeeDecimal
    collateral_fee_amount: int
    provider_fee_percent: FeeDecimal
    provider_fee_amount: int
    provider_fee_type: ProviderFeeType
    total_repayment_amount: int
    initial_debt_amount: int
    collateral_amount: int
    extra_info: Optional[dict] = None


@dataclass
class DebitCardEnableData:
    user_id: UUID
    pan: str


@dataclass
class LoanServiceOptions:
    min_principal_limit: int
    max_principal_limit: int
    periods: List[int]
    provider_fee: Optional[Decimal] = None
    punishment_rate: Optional[Decimal] = None
    forced_liquidation_period: Optional[int] = None
    no_punishment_period: Optional[int] = None
    debt_to_grant_ratio: Optional[Decimal] = None

    def __iter__(self):
        yield 'min_principal_limit', self.min_principal_limit
        yield 'max_principal_limit', self.max_principal_limit
        yield 'periods', self.periods
        yield 'provider_fee', str(self.provider_fee)
        yield 'punishment_rate', str(self.punishment_rate) if self.punishment_rate is not None else None
        yield 'forced_liquidation_period', (
            self.forced_liquidation_period if self.forced_liquidation_period is not None else None
        )
        yield 'no_punishment_period', self.no_punishment_period if self.no_punishment_period is not None else None
        yield 'debt_to_grant_ratio', str(self.debt_to_grant_ratio) if self.debt_to_grant_ratio is not None else None


@dataclass
class ReconTransactionData:
    date: str
    time: str
    pos_condition_code: str
    trace_id: str
    account_number: str
    amount: int
    amount_type: str
    pr_code: str
    terminal_id: str
    acquirer_institution_code: str
    pan: str
    acquirer_institution: str
    issuer_institution: str


@dataclass
class UserServiceLimit:
    min_limit: int
    max_limit: int


class WalletType(str, Enum):
    SPOT = 'spot'
    MARGIN = 'margin'
    CREDIT = 'credit'  # for backward compatibility
    COLLATERAL = 'collateral'
    DEBIT = 'debit'


class WalletTransferItem(BaseModel):
    currency: str
    amount: Decimal

    @field_validator('amount', mode='before')
    @classmethod
    def validate_amount(cls, value: Decimal):
        if value is None or value == '':
            raise ParseError('Missing monetary value')
        try:
            if Decimal(value) == ZERO:
                raise WalletValidationError(code='InvalidAmount', description='Amount can not be zero')
            if Decimal(value) < ZERO:
                raise WalletValidationError(code='InvalidAmount', description='Amount can not be less than zero')
        except InvalidOperation:
            raise ParseError(f'Invalid monetary value: "{value}"')

        parse_money(value, required=True)
        return value


class WalletDepositInput(BaseModel):
    src_type: WalletType
    dst_type: WalletType
    transfers: conlist(WalletTransferItem, min_length=1, max_length=19)

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    @model_validator(mode='before')
    @classmethod
    def validate_before(cls, data: dict):
        if data['srcType'] == data['dstType']:
            raise WalletValidationError('SameDestination', 'Dst wallet must be different from src wallet')
        return data

    @field_validator('src_type', mode='before')
    @classmethod
    def validate_src_type(cls, src_type: str):
        valid_src_types = [WalletType.SPOT, WalletType.MARGIN]
        if src_type not in valid_src_types:
            raise WalletValidationError(
                code='InvalidSrcType', description=f'Source wallet should be spot or margin wallets'
            )
        return src_type

    @field_validator('dst_type', mode='before')
    @classmethod
    def validate_dst_type(cls, dst_type: str):
        valid_dst_types = [WalletType.COLLATERAL, WalletType.DEBIT]
        if dst_type not in valid_dst_types:
            raise WalletValidationError(
                code='InvalidDstType', description=f'Destination wallet should be collateral or debit wallets'
            )
        return dst_type

    @model_validator(mode="after")
    def validate_wallets(self):
        self._validate_transfers()
        return self

    def _validate_transfers(self):
        currencies = set()
        for item in self.transfers:
            currency_id = self._parse_currency(item.currency)
            currencies.add(currency_id)
            self._check_valid_collateral_currency(currency_id)
            self._check_valid_margin_currency(currency_id)
            self._check_valid_debit_currency(currency_id)

        if len(currencies) < len(self.transfers):
            raise WalletValidationError('DuplicateCurrencies', "Same currencies in the transfers set")

    def _parse_currency(self, currency: str) -> int:
        try:
            currency_id = parse_currency(currency)
        except ParseError as _:
            raise WalletValidationError(code='UnsupportedCoin', description=f'Currency {currency} is invalid')
        return currency_id

    def _check_valid_collateral_currency(self, currency_id: int):
        if self.dst_type == WalletType.COLLATERAL and currency_id not in ABCCurrencies.get_active_currencies():
            raise WalletValidationError(
                'UnsupportedCoin',
                f'Cannot transfer {get_symbol_from_currency_code(currency_id)} to credit wallet',
            )

    def _check_valid_margin_currency(self, currency_id: int):
        if self.src_type == WalletType.MARGIN and currency_id not in MARGIN_CURRENCIES:
            raise WalletValidationError(
                'UnsupportedCoin',
                f'Cannot transfer {get_symbol_from_currency_code(currency_id)} from margin wallet',
            )

    def _check_valid_debit_currency(self, currency_id: int):
        if self.dst_type == WalletType.DEBIT and currency_id not in ABCCurrencies.get_active_currencies(
            Wallet.WalletType.DEBIT
        ):
            raise WalletValidationError(
                'UnsupportedCoin',
                f'Cannot transfer {get_symbol_from_currency_code(currency_id)} to debit wallet',
            )


class WalletWithdrawInput(BaseModel):
    src_type: WalletType = WalletType.CREDIT
    dst_type: WalletType
    transfers: conlist(WalletTransferItem, min_length=1, max_length=19)

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    @field_validator('src_type', mode='before')
    @classmethod
    def validate_src_type(cls, src_type: str):
        valid_src_types = [WalletType.CREDIT, WalletType.COLLATERAL, WalletType.DEBIT]
        if src_type not in valid_src_types:
            raise ParseError('Source wallet should be one of collateral or debit wallets')
        return src_type

    @field_validator('dst_type', mode='before')
    @classmethod
    def validate_dst_type(cls, dst_type: str):
        valid_dst_types = [WalletType.SPOT, WalletType.MARGIN]
        if dst_type not in valid_dst_types:
            raise InvalidWithdrawDestinationWallet
        return dst_type

    @model_validator(mode="after")
    def validate_wallets(self):
        for transfer in self.transfers:
            currency_id = parse_currency(transfer.currency)
            if self.dst_type == WalletType.MARGIN and not currency_id in DST_CURRENCIES:
                raise InvalidMarginDstWalletCurrency()
        return self


class RequestFilters(BaseModel):
    page: int
    page_size: int
    from_date: Optional[date] = None
    to_date: Optional[date] = None


class WalletSchema(BaseModel):
    id: Optional[int] = None
    currency: str
    type: int
    type_str: str
    balance: Decimal
    active_balance: Decimal
    blocked_balance: Decimal
    rial_balance: int
    rial_balance_sell: int

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class TransactionInput(BaseModel):
    # wallet data
    user_id: UUID4
    wallet_type: Wallet.WalletType
    exchange_wallet_type: Optional[WalletType] = None
    currency: str

    amount: Decimal = Field(
        max_digits=TRANSACTION_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        ge=-TRANSACTION_MAX,
        le=TRANSACTION_MAX,
        allow_inf_nan=False,
    )

    description: str = Field(min_length=1, max_length=256)
    tp: Transaction.Type
    ref_module: Optional[Transaction.RefModule] = None
    ref_id: Optional[int] = None

    @property
    def wallet_key(self) -> str:
        return f'{self.user_id}-{self.int_currency}-{self.wallet_type}'

    @field_validator('currency')
    @classmethod
    def currency_validator(cls, value: str) -> str:
        try:
            parse_currency(value, required=True)
        except ParseError as e:
            raise ValueError(f'Invalid currency: {value}') from e
        return value

    @property
    def int_currency(self) -> int:
        return parse_currency(self.currency, required=True)


class UserServiceProviderMessage(IntEnum):
    FAILED = 10

    # DIGIPAY
    BLACKLISTED = 11
    INVALID_MOBILE_NUMBER = 12
    INVALID_IDENTITY = 13
    UNPROCESSABLE_REQUEST = 14
    # USER_HAS_DEBT_ERROR = 15
    USER_HAS_ANOTHER_CREDIT_ERROR = 16
    USER_HAS_IN_CLOSURE_CREDIT_ERROR = 17
    USER_HAS_ACTIVE_CREDIT_ERROR = 18
    ALREADY_CLOSED_CREDIT_ERROR = 19
    INVALID_REQUEST = 20
    USER_HAS_DEBT_CREATE_ERROR = 26
    USER_HAS_DEBT_CLOSE_ERROR = 27  # LAST ID

    # AZKI
    USER_HAS_ONGOING_REQUEST_ERROR = 21
    USER_HAS_OVERDUE_PAYMENT_ERROR = 22
    USER_HAS_OVERDUE_PAYMENT_IN_BANKING_SYSTEM_ERROR = 23
    USER_HAS_BOUNCED_CHECK_ERROR = 24
    USER_HAS_ACTIVE_LOAN_ERROR = 25


@dataclass
class UserServiceCreateResponse:
    class Status(IntEnum):
        SUCCEEDED = 1
        REQUESTED = 2
        FAILED = 3

    status: Status
    message: Optional[UserServiceProviderMessage] = None
    provider_tracking_id: str = None
    amount: Decimal = None
    options: dict = None


@dataclass
class UserServiceCloseResponse:
    class Status(IntEnum):
        SUCCEEDED = 1
        REQUESTED = 2
        FAILED = 3

    status: Status
    message: Optional[UserServiceProviderMessage] = None


@dataclass
class UserServiceRestriction:
    tp: str
    description: str
    consideration: str


USER_SERVICE_PROVIDER_MESSAGE_MAPPING = {
    UserServiceProviderMessage.FAILED: 'سرویس‌دهنده در دسترس نیست. کمی بعد دوباره تلاش کنید.',
    # DIGIPAY
    UserServiceProviderMessage.BLACKLISTED: 'فعالسازی اعتبار از طرف سرویس‌دهنده برای شما امکان‌پذیر نیست.',
    UserServiceProviderMessage.INVALID_MOBILE_NUMBER: 'فعالسازی اعتبار به دلیل مطابقت نداشتن کد ملی و شماره موبایل در سرویس‌دهنده امکان‌پذیر نیست.',
    UserServiceProviderMessage.INVALID_IDENTITY: 'فعالسازی اعتبار به‌دلیل اطلاعات هویتی اشتباه  در سرویس‌دهنده امکان‌پذیر نیست.',
    UserServiceProviderMessage.UNPROCESSABLE_REQUEST: 'مشکلی پیش آمده است. با پشتیبانی نوبیتکس تماس بگیرید.',
    UserServiceProviderMessage.USER_HAS_ANOTHER_CREDIT_ERROR: 'فعالسازی اعتبار به دلیل فعال بودن یک اعتبار دیگر در سرویس‌دهنده امکان‌پذیر نیست.',
    UserServiceProviderMessage.USER_HAS_IN_CLOSURE_CREDIT_ERROR: 'لطفا برای فعالسازی اعتبار، تا غیرفعال شدن اعتبار قبلی در سرویس‌دهنده صبر کنید.',
    UserServiceProviderMessage.USER_HAS_ACTIVE_CREDIT_ERROR: 'فعالسازی اعتبار به دلیل فعال بودن یک اعتبار دیگر در سرویس‌دهنده امکان‌پذیر نیست.',
    UserServiceProviderMessage.ALREADY_CLOSED_CREDIT_ERROR: 'این اعتبار قبلا لغو شده‌است.',
    UserServiceProviderMessage.INVALID_REQUEST: 'در حال حاضر لغو اعتبار امکان‌پذیر نیست.',
    UserServiceProviderMessage.USER_HAS_DEBT_CREATE_ERROR: 'فعالسازی اعتبار به دلیل بدهی در سرویس‌دهنده امکان‌پذیر نیست.',
    UserServiceProviderMessage.USER_HAS_DEBT_CLOSE_ERROR: 'لغو اعتبار به دلیل بدهی در سرویس‌دهنده امکان‌پذیر نیست.',
    # AZKI
    UserServiceProviderMessage.USER_HAS_ONGOING_REQUEST_ERROR: 'درخواست قبلی شما در حال انجام است. لطفا کمی صبر کنید.',
    UserServiceProviderMessage.USER_HAS_OVERDUE_PAYMENT_ERROR: 'فعالسازی وام شما به‌دلیل بدهی در سرویس‌دهنده امکان‌پدیر نیست.',
    UserServiceProviderMessage.USER_HAS_OVERDUE_PAYMENT_IN_BANKING_SYSTEM_ERROR: 'فعالسازی وام شما به‌دلیل قسط معوق در سامانه‌ی اعتبارسنجی امکان‌پدیر نیست.',
    UserServiceProviderMessage.USER_HAS_BOUNCED_CHECK_ERROR: 'فعالسازی وام شما به‌دلیل چک برگشتی امکان‌پذیر نیست.',
    UserServiceProviderMessage.USER_HAS_ACTIVE_LOAN_ERROR: 'فعالسازی وام به‌دلیل فعال بودن یک وام دیگر در سرویس‌دهنده امکان‌پذیر نیست.',
}


class UserServiceCloseStatus(IntEnum):
    CLOSEABLE = 1
    NOT_CLOSEABLE = 2
    ALREADY_CLOSED = 3


class UserInfo(BaseModel):
    national_code: str
    mobile: str
    first_name: str
    last_name: str
    birthday_shamsi: str


class UserServiceCreateRequest(BaseModel):
    unique_id: str
    user_info: UserInfo
    amount: int
    period: Optional[int] = None
    extra_info: Optional[dict] = None


class StoreSchema(BaseModel):
    title: str
    url: str
