import datetime
import functools
from decimal import Decimal
from typing import List, Optional, Union

from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils.functional import cached_property
from model_utils import Choices

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import (
    AmountIsLargerThanDebtOnUpdateUserService,
    InsuranceFundAccountLowBalance,
    InvalidAmountError,
    SettlementError,
    SettlementNeedsLiquidation,
    SettlementReverseError,
    UnexpectedSettlementLowLiquidity,
)
from exchange.asset_backed_credit.models.service import Service
from exchange.asset_backed_credit.models.user_service import UserService
from exchange.asset_backed_credit.models.wallet import Wallet
from exchange.asset_backed_credit.services.price import PricingService
from exchange.asset_backed_credit.services.providers.provider import Provider
from exchange.asset_backed_credit.services.providers.provider_manager import ProviderManager
from exchange.asset_backed_credit.services.wallet.wallet import WalletService
from exchange.base.calendar import ir_now
from exchange.base.constants import ZERO
from exchange.base.models import RIAL
from exchange.base.money import money_is_zero
from exchange.base.validators import validate_transaction_is_atomic
from exchange.market.models import Order
from exchange.wallet.models import Transaction as ExchangeTransaction
from exchange.wallet.models import Wallet as ExchangeWallet
from exchange.wallet.models import WithdrawRequest as ExchangeWithdrawRequest


class SettlementTransaction(models.Model):
    STATUS = Choices(
        (1, 'initiated', 'initiated'),
        (2, 'confirmed', 'confirmed'),
        (3, 'unknown_rejected', 'unknown_rejected'),
        (4, 'unknown_confirmed', 'unknown_confirmed'),
        (5, 'reversed', 'reversed'),
    )

    created_at = models.DateTimeField(default=ir_now, verbose_name='تاریخ ایجاد')
    amount = models.DecimalField(max_digits=30, decimal_places=10, verbose_name='مقدار تراکنش')
    fee_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0, verbose_name='مقدار کارمزد تراکنش')
    remaining_rial_wallet_balance = models.BigIntegerField(
        blank=True, null=True, verbose_name='موجودی ریالی ولت بعد از انجام تراکنش'
    )
    status = models.SmallIntegerField(choices=STATUS, default=STATUS.confirmed, verbose_name='وضعیت تسویه')
    transaction_datetime = models.DateTimeField(null=True, verbose_name='تاریخ تسویه')

    user_service = models.ForeignKey(
        UserService,
        related_name='settlement_transactions',
        on_delete=models.PROTECT,
        verbose_name='سرویس اعتباری',
    )

    # Transactions
    user_withdraw_transaction = models.OneToOneField(
        ExchangeTransaction,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='تراکنش تسویه با کاربر',
    )
    user_reverse_transaction = models.OneToOneField(
        ExchangeTransaction,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='تراکنش برگشت‌ به کاربر',
    )
    user_fee_withdraw_transaction = models.OneToOneField(
        ExchangeTransaction,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='تراکنش برداشت کارمزد از کاربر',
    )
    user_fee_reverse_transaction = models.OneToOneField(
        ExchangeTransaction,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='تراکنش برگشت کارمزد به کاربر',
    )
    provider_deposit_transaction = models.OneToOneField(
        ExchangeTransaction,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='تراکنش تسویه با سرویس‌دهنده',
    )
    provider_reverse_transaction = models.OneToOneField(
        ExchangeTransaction,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='تراکنش برگشت تسویه با سرویس‌دهنده',
    )
    insurance_withdraw_transaction = models.OneToOneField(
        ExchangeTransaction,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='تراکنش کسر از اکانت بیمه‌ی نوبیتکس',
    )
    insurance_reverse_transaction = models.OneToOneField(
        ExchangeTransaction,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='تراکنش برگشت کسر از اکانت بیمه‌ی نوبیتکس',
    )
    fee_deposit_transaction = models.OneToOneField(
        ExchangeTransaction, null=True, on_delete=models.PROTECT, related_name='+', verbose_name='تراکنش کارمزد'
    )
    fee_reverse_transaction = models.OneToOneField(
        ExchangeTransaction, null=True, on_delete=models.PROTECT, related_name='+', verbose_name='تراکنش برگشت کارمزد'
    )

    # Provider Withdraw
    provider_withdraw_requests = models.ManyToManyField(
        ExchangeWithdrawRequest,
        related_name='+',
        verbose_name='درخواست‌های برداشت سرویس‌دهنده',
    )
    provider_withdraw_request_log = models.ForeignKey(
        to='ProviderWithdrawRequestLog',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='settlement_transactions',
    )

    # Liquidation
    liquidation_run_at = models.DateTimeField(null=True, blank=True)
    liquidation_retry = models.SmallIntegerField(default=0)
    orders = models.ManyToManyField(Order, related_name='+', blank=True)

    class Meta:
        verbose_name = 'تراکنش تسویه'
        verbose_name_plural = 'تراکنش‌های تسویه'
        constraints = (
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name='amount_positivity',
            ),
        )

    @property
    def user_rial_wallet(self) -> Union[Wallet, ExchangeWallet]:
        return WalletService.get_user_wallet(
            user=self.user_service.user,
            currency=RIAL,
            wallet_type=Service.get_related_wallet_type(self.user_service.service.tp),
        )

    @property
    def should_settle(self) -> bool:
        return (
            self.status == SettlementTransaction.STATUS.confirmed
            or self.status == SettlementTransaction.STATUS.unknown_confirmed
        )

    @cached_property
    def provider(self) -> Provider:
        return ProviderManager.get_provider_by_id(self.user_service.service.provider)

    @property
    def liquidated_amount(self) -> Decimal:
        return self.orders.aggregate(
            total_liquidated=Coalesce(models.Sum(models.F('matched_total_price') - models.F('fee')), ZERO),
        )['total_liquidated']

    @property
    def pending_liquidation_amount(self) -> Decimal:
        if self.user_withdraw_transaction_id:
            return ZERO
        return max(self.amount + self.fee_amount - self.user_rial_wallet.balance, ZERO)

    @cached_property
    def should_use_insurance_fund(self) -> bool:
        pricing_service = PricingService(
            user=self.user_service.user, wallet_type=Service.get_related_wallet_type(self.user_service.service.tp)
        )
        required_collateral = pricing_service.get_required_collateral(keep_ratio=False)
        if required_collateral > ZERO and not money_is_zero(self.pending_liquidation_amount):
            return True
        return False

    @classmethod
    @functools.lru_cache(maxsize=1)
    def get_insurance_fund_account(cls):
        return User.objects.get(pk=settings.ABC_INSURANCE_FUND_ACCOUNT_ID)

    @classmethod
    def get_insurance_fund_rial_wallet(cls):
        return WalletService.get_user_wallet(
            user=cls.get_insurance_fund_account(), currency=RIAL, wallet_type=Wallet.WalletType.SYSTEM
        )

    @classmethod
    @functools.lru_cache(maxsize=1)
    def get_fee_account(cls):
        return User.objects.get(pk=settings.ABC_FEE_ACCOUNT_ID)

    @classmethod
    def get_fee_rial_wallet(cls):
        return WalletService.get_user_wallet(
            user=cls.get_fee_account(), currency=RIAL, wallet_type=Wallet.WalletType.SYSTEM
        )

    @classmethod
    def get_pending_user_settlements(cls):
        return cls.objects.filter(
            status__in=[SettlementTransaction.STATUS.confirmed, SettlementTransaction.STATUS.unknown_confirmed],
            user_withdraw_transaction__isnull=True,
        )

    @classmethod
    def has_pending_transaction(cls, user: User, service_types: List[int] = None) -> bool:
        service_type_query = Q()
        if service_types is not None:
            service_type_query = Q(user_service__service__tp__in=service_types)

        return cls.get_pending_user_settlements().filter(service_type_query, user_service__user=user).exists()

    @classmethod
    def unknown_confirm_initiated_user_settlements(cls) -> None:
        cls.objects.filter(
            status=SettlementTransaction.STATUS.initiated, created_at__lte=ir_now() - datetime.timedelta(minutes=5)
        ).update(status=SettlementTransaction.STATUS.unknown_confirmed)

    def create_user_transaction(self) -> ExchangeTransaction:
        def get_description():
            service_name = self.user_service.service.get_tp_display()
            provider_name = self.user_service.service.get_provider_display()
            dst_name = 'نوبی‌کارت' if self.user_service.service.tp == Service.TYPES.debit else 'کیف وثیقه'
            return f'تسویه {service_name} با {provider_name} از {dst_name}'

        validate_transaction_is_atomic()
        if self.user_withdraw_transaction:
            return self.user_withdraw_transaction

        if not money_is_zero(self.pending_liquidation_amount) and not self.should_use_insurance_fund:
            raise SettlementNeedsLiquidation()

        user_withdraw_transaction = self.user_rial_wallet.create_transaction(
            tp='asset_backed_credit',
            amount=-self.amount + self.pending_liquidation_amount,
            description=get_description(),
        )

        if user_withdraw_transaction is None:
            # If this happens, we have a serious bug in the system
            raise UnexpectedSettlementLowLiquidity()

        user_withdraw_transaction.commit(ref=ExchangeTransaction.Ref('AssetBackedCreditUserSettlement', self.pk))
        self.user_withdraw_transaction = user_withdraw_transaction
        self.transaction_datetime = user_withdraw_transaction.created_at
        self.save(update_fields=('transaction_datetime', 'user_withdraw_transaction'))
        return self.user_withdraw_transaction

    def create_reverse_user_transaction(self) -> ExchangeTransaction:
        def get_description():
            service_name = self.user_service.service.get_tp_display()
            provider_name = self.user_service.service.get_provider_display()
            dst_name = 'نوبی‌کارت' if self.user_service.service.tp == Service.TYPES.debit else 'کیف وثیقه'
            return f'تراکنش اصلاحی {service_name} با {provider_name} از {dst_name}'

        validate_transaction_is_atomic()
        if self.user_reverse_transaction:
            return self.user_reverse_transaction

        if not self.user_withdraw_transaction or self.is_provider_withdraw_exists():
            raise SettlementReverseError

        user_reverse_transaction = self.user_rial_wallet.create_transaction(
            tp='asset_backed_credit', amount=-self.user_withdraw_transaction.amount, description=get_description()
        )
        if user_reverse_transaction is None:
            raise SettlementReverseError

        user_reverse_transaction.commit(ref=ExchangeTransaction.Ref('AssetBackedCreditUserSettlementReverse', self.pk))
        self.user_reverse_transaction = user_reverse_transaction
        self.status = SettlementTransaction.STATUS.reversed
        self.save(update_fields=('user_reverse_transaction', 'status'))
        return self.user_reverse_transaction

    def create_user_fee_transaction(self) -> Optional[ExchangeTransaction]:
        def get_description():
            dst_name = 'نوبی‌کارت' if self.user_service.service.tp == Service.TYPES.debit else 'کیف وثیقه'
            return f'کسر کارمزد خرید از {dst_name}'

        validate_transaction_is_atomic()
        if self.user_fee_withdraw_transaction:
            return self.user_fee_withdraw_transaction

        if money_is_zero(self.fee_amount):
            return None

        user_fee_withdraw_transaction = self.user_rial_wallet.create_transaction(
            tp='asset_backed_credit',
            amount=-self.fee_amount,
            description=get_description(),
        )
        if user_fee_withdraw_transaction is None:
            raise UnexpectedSettlementLowLiquidity()
        user_fee_withdraw_transaction.commit(ref=ExchangeTransaction.Ref('AssetBackedCreditUserFeeSettlement', self.pk))
        self.user_fee_withdraw_transaction = user_fee_withdraw_transaction
        self.save(update_fields=('user_fee_withdraw_transaction',))
        return self.user_fee_withdraw_transaction

    def create_reverse_user_fee_transaction(self) -> Optional[ExchangeTransaction]:
        def get_description():
            dst_name = 'نوبی‌کارت' if self.user_service.service.tp == Service.TYPES.debit else 'کیف وثیقه'
            return f'اصلاح کسر کارمزد خرید از {dst_name}'

        validate_transaction_is_atomic()
        if self.user_fee_reverse_transaction:
            return self.user_fee_reverse_transaction

        if money_is_zero(self.fee_amount):
            return None

        if not self.user_fee_withdraw_transaction or self.is_provider_withdraw_exists():
            raise SettlementReverseError

        user_fee_reverse_transaction = self.user_rial_wallet.create_transaction(
            tp='asset_backed_credit',
            amount=-self.user_fee_withdraw_transaction.amount,
            description=get_description(),
        )
        if user_fee_reverse_transaction is None:
            raise SettlementReverseError

        user_fee_reverse_transaction.commit(
            ref=ExchangeTransaction.Ref('AssetBackedCreditUserFeeSettlementReverse', self.pk)
        )
        self.user_fee_reverse_transaction = user_fee_reverse_transaction
        self.save(update_fields=('user_fee_reverse_transaction',))
        return user_fee_reverse_transaction

    def is_provider_withdraw_exists(self):
        return self.provider_withdraw_requests.exists() or self.provider_withdraw_request_log

    def create_provider_transaction(self) -> ExchangeTransaction:
        validate_transaction_is_atomic()
        if self.provider_deposit_transaction:
            return self.provider_deposit_transaction

        provider_deposit_transaction = self.provider.rial_wallet.create_transaction(
            tp='asset_backed_credit',
            amount=self.amount,
            description=f'واریز وجه تسویه طرح {self.user_service_id}',
        )
        provider_deposit_transaction.commit(ref=ExchangeTransaction.Ref('AssetBackedCreditProviderSettlement', self.pk))
        self.provider_deposit_transaction = provider_deposit_transaction
        self.save(update_fields=('provider_deposit_transaction',))
        return self.provider_deposit_transaction

    def create_reverse_provider_transaction(self) -> ExchangeTransaction:
        def get_description():
            return f'تراکنش اصلاحی تسویه طرح {self.user_service_id}'

        validate_transaction_is_atomic()
        if self.provider_reverse_transaction:
            return self.provider_reverse_transaction

        if not self.provider_deposit_transaction or self.is_provider_withdraw_exists():
            raise SettlementReverseError

        provider_reverse_transaction = self.provider.rial_wallet.create_transaction(
            tp='asset_backed_credit',
            amount=-self.provider_deposit_transaction.amount,
            description=get_description(),
        )
        provider_reverse_transaction.commit(
            ref=ExchangeTransaction.Ref('AssetBackedCreditProviderSettlementReverse', self.pk)
        )
        self.provider_reverse_transaction = provider_reverse_transaction
        self.save(update_fields=('provider_reverse_transaction',))
        return self.provider_reverse_transaction

    def create_insurance_fund_transaction(self) -> Optional[ExchangeTransaction]:
        validate_transaction_is_atomic()
        if self.insurance_withdraw_transaction:
            return self.insurance_withdraw_transaction

        if not self.should_use_insurance_fund or money_is_zero(self.pending_liquidation_amount):
            return None

        insurance_withdraw_transaction = self.get_insurance_fund_rial_wallet().create_transaction(
            tp='asset_backed_credit',
            amount=-self.pending_liquidation_amount,
            description=f'برداشت وجه کسری مربوط به تسویه طرح {self.user_service_id}',
        )
        if insurance_withdraw_transaction is None:
            raise InsuranceFundAccountLowBalance()

        insurance_withdraw_transaction.commit(
            ref=ExchangeTransaction.Ref('AssetBackedCreditInsuranceSettlement', self.pk)
        )
        self.insurance_withdraw_transaction = insurance_withdraw_transaction
        self.save(update_fields=('insurance_withdraw_transaction',))
        return self.insurance_withdraw_transaction

    def create_reverse_insurance_fund_transaction(self) -> Optional[ExchangeTransaction]:
        def get_description():
            return f'تراکنش اصلاحی کسری مربوط به تسویه طرح {self.user_service_id}'

        validate_transaction_is_atomic()
        if self.insurance_reverse_transaction:
            return self.insurance_reverse_transaction

        if self.is_provider_withdraw_exists():
            raise SettlementReverseError

        if not self.insurance_withdraw_transaction:
            return None

        insurance_reverse_transaction = self.get_insurance_fund_rial_wallet().create_transaction(
            tp='asset_backed_credit',
            amount=-self.insurance_withdraw_transaction.amount,
            description=get_description(),
        )
        insurance_reverse_transaction.commit(
            ref=ExchangeTransaction.Ref('AssetBackedCreditInsuranceSettlementReverse', self.pk)
        )
        self.insurance_reverse_transaction = insurance_reverse_transaction
        self.save(update_fields=('insurance_reverse_transaction',))
        return self.insurance_reverse_transaction

    def create_fee_transaction(self) -> Optional[ExchangeTransaction]:
        def get_description():
            dst_name = 'نوبی‌کارت' if self.user_service.service.tp == Service.TYPES.debit else 'کیف وثیقه'
            return f'انتقال کارمزد خرید از {dst_name}'

        validate_transaction_is_atomic()
        if self.fee_deposit_transaction:
            return self.fee_deposit_transaction

        if money_is_zero(self.fee_amount):
            return None

        fee_deposit_transaction = self.get_fee_rial_wallet().create_transaction(
            tp='asset_backed_credit',
            amount=self.fee_amount,
            description=get_description(),
        )
        fee_deposit_transaction.commit(ref=ExchangeTransaction.Ref('AssetBackedCreditFeeSettlement', self.pk))
        self.fee_deposit_transaction = fee_deposit_transaction
        self.save(update_fields=('fee_deposit_transaction',))
        return self.fee_deposit_transaction

    def create_reverse_fee_transaction(self) -> Optional[ExchangeTransaction]:
        def get_description():
            dst_name = 'نوبی‌کارت' if self.user_service.service.tp == Service.TYPES.debit else 'کیف وثیقه'
            return f'اصلاح انتقال کارمزد خرید از {dst_name}'

        validate_transaction_is_atomic()
        if self.fee_reverse_transaction:
            return self.fee_reverse_transaction

        if money_is_zero(self.fee_amount):
            return None

        if not self.fee_deposit_transaction or self.is_provider_withdraw_exists():
            raise SettlementReverseError

        fee_reverse_transaction = self.get_fee_rial_wallet().create_transaction(
            tp='asset_backed_credit',
            amount=-self.fee_deposit_transaction.amount,
            description=get_description(),
        )
        if fee_reverse_transaction is None:
            raise SettlementReverseError

        fee_reverse_transaction.commit(ref=ExchangeTransaction.Ref('AssetBackedCreditFeeSettlementReverse', self.pk))
        self.fee_reverse_transaction = fee_reverse_transaction
        self.save(update_fields=('fee_reverse_transaction',))
        return fee_reverse_transaction

    @transaction.atomic
    def create_transactions(self):
        if self.status == SettlementTransaction.STATUS.reversed:
            raise SettlementError

        self.create_insurance_fund_transaction()
        self.create_user_transaction()
        self.create_user_fee_transaction()
        self.create_provider_transaction()
        self.create_fee_transaction()
        self.user_service.update_current_debt(-(self.amount + self.fee_amount))
        self.user_service.finalize(UserService.STATUS.settled)
        WalletService.invalidate_user_wallets_cache(user_id=self.user_service.user.uid)

    @transaction.atomic
    def create_reverse_transactions(self):
        if self.status == SettlementTransaction.STATUS.confirmed:
            raise SettlementReverseError

        self.create_reverse_provider_transaction()
        self.create_reverse_fee_transaction()
        self.create_reverse_insurance_fund_transaction()
        self.create_reverse_user_transaction()
        self.create_reverse_user_fee_transaction()
        self.user_service.update_current_debt(self.amount + self.fee_amount)
        WalletService.invalidate_user_wallets_cache(user_id=self.user_service.user.uid)

    @classmethod
    @transaction.atomic
    def create(
        cls, user_service: UserService, amount: Decimal, fee_amount: Decimal = 0, status: int = STATUS.confirmed
    ):
        """
        Creates a settlement record.
        Args:
            user_service(UserService)
            amount (Decimal)
            fee_amount (Decimal)
            status (int)
        Returns:
            SettlementTransaction

        Raises:
            AmountIsLargerThanDebtOnUpdateUserService: when amount bigger than user current debt.
            SettlementError: when an active settlement record exists for user service.

        """
        if (
            cls.objects.filter(user_service=user_service, transaction_datetime__isnull=True)
            .exclude(status=SettlementTransaction.STATUS.unknown_rejected)
            .exists()
        ):
            raise SettlementError()

        if user_service.current_debt < amount:
            raise AmountIsLargerThanDebtOnUpdateUserService()

        return cls.objects.create(user_service=user_service, amount=amount, fee_amount=fee_amount, status=status)

    def confirm(self, amount: Decimal):
        """
        Confirms a settlement record.
        Args:
            amount (Decimal)

        Returns:
            SettlementTransaction

        Raises:
            SettlementError: when a settlement record exists for user service.

        """
        if self.amount != amount:
            raise InvalidAmountError()

        self.status = SettlementTransaction.STATUS.confirmed
        self.save(update_fields=['status'])

    def reject(self, amount: Decimal):
        """
        rejects a settlement record.
        Args:
            amount (Decimal)

        Returns:
            SettlementTransaction

        Raises:
            SettlementError: when a settlement record exists for user service.

        """
        if self.amount != amount:
            raise InvalidAmountError()

        self.status = SettlementTransaction.STATUS.unknown_rejected
        self.save(update_fields=['status'])

    def cancel_active_orders(self):
        active_orders = (
            self.orders.exclude(status__in=[Order.STATUS.done, Order.STATUS.canceled])
            .select_for_update(no_key=True)
            .all()
        )
        for active_order in active_orders:
            active_order.do_cancel()

    def update_remaining_rial_wallet_balance(self, rial_balance: int):
        if self.remaining_rial_wallet_balance is None:
            self.remaining_rial_wallet_balance = rial_balance
            self.save(update_fields=['remaining_rial_wallet_balance'])
