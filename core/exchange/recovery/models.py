from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from model_utils import Choices

from exchange.base.calendar import ir_now
from exchange.market.models import Order
from exchange.usermanagement.models import BlockedOrderLog
from exchange.wallet.models import Transaction, ManualDepositRequest


class RecoveryCurrency(models.Model):
    name = models.CharField(max_length=50, verbose_name='نام رمز‌ارز')
    created_at = models.DateTimeField(default=timezone.now, verbose_name="زمان ایجاد")

    class Meta:
        verbose_name = 'رمزارز بازیابی'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class RecoveryNetwork(models.Model):
    name = models.CharField(max_length=50, verbose_name='نام شبکه', unique=True)
    fee = models.DecimalField(max_digits=20, decimal_places=10, verbose_name='کارمزد شبکه')
    created_at = models.DateTimeField(default=timezone.now, verbose_name="زمان ایجاد")
    url_hash = models.URLField(null=True, blank=True)
    url_address = models.URLField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'شبکه بازیابی'
        verbose_name_plural = verbose_name


class RecoveryRequest(models.Model):
    STATUS = Choices(
        (1, 'new', 'New'),
        (2, 'initial_approval', 'InitialApproval'),
        (3, 'confirmed', 'Confirmed'),
        (4, 'ready', 'Ready'),
        (5, 'done', 'Done'),
        (6, 'rejected', 'Rejected'),
        (7, 'unrecoverable', 'Unrecoverable'),
        (8, 'canceled', 'Canceled'),
        (9, 'charging_wallet', 'ChargingWallet'),
        (10, 'recheck', 'Recheck'),
    )
    STATUSES_CANCELABLE = [
        STATUS.new,
        STATUS.initial_approval,
        STATUS.confirmed,
    ]  # Can be cancel by user

    block_order = models.OneToOneField(Order, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.TextField(null=True, blank=True, verbose_name='توضیحات')
    updated_at = models.DateTimeField(default=timezone.now, verbose_name='آخرین تغییر وضعیت')
    contract = models.CharField(max_length=200, verbose_name='قرارداد')
    currency = models.ForeignKey(
        'RecoveryCurrency', on_delete=models.SET_NULL, null=True, blank=False, verbose_name='رمز ارز'
    )
    network = models.ForeignKey(
        'RecoveryNetwork', on_delete=models.SET_NULL, null=True, blank=False, verbose_name='نام شبکه'
    )
    user = models.ForeignKey(
        to=get_user_model(),
        on_delete=models.PROTECT,
        verbose_name='کاربر',
        related_name='recoveries',
        related_query_name='recoveries',
    )
    status = models.PositiveSmallIntegerField(choices=STATUS, default=STATUS.new)
    amount = models.DecimalField(max_digits=30, decimal_places=10, verbose_name='مقدار')
    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='زمان ایجاد')
    # deposit data
    deposit_address = models.CharField(max_length=200)
    deposit_tag = models.CharField(max_length=200, null=True, blank=True, verbose_name='تگ')
    deposit_hash = models.CharField(max_length=200, verbose_name='هش تراکنش')
    # Return data
    return_address = models.CharField(max_length=200, verbose_name='آدرس بازگشت')
    return_tag = models.CharField(max_length=200, null=True, blank=True, verbose_name='تگ بازگشت')
    recovery_link = models.CharField(max_length=200, null=True, blank=True, verbose_name='لینک بازیابی')
    recovery_hash = models.CharField(max_length=200, null=True, blank=True, verbose_name='هش بازیابی')
    # Transaction
    transactions = models.ManyToManyField(Transaction, through='RecoveryTransaction', verbose_name='تراکنش‌ها')

    class Meta:
        verbose_name = 'درخواست بازیابی'
        verbose_name_plural = verbose_name
        constraints = (
            models.UniqueConstraint(
                fields=['user', 'deposit_hash'],
                name='unique_user_deposit_hash',
                condition=~Q(status__in=[6, 8])
            ),
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_status = self.status

    def cancel_by_user(self):
        """
        This method handles cancel_recovery_request action by user
        """
        if self.status not in self.STATUSES_CANCELABLE:
            return False
        with transaction.atomic():
            if self.block_order:
                self.block_order.do_cancel()
            self.status = RecoveryRequest.STATUS.canceled
            self.save(update_fields=['status'])
            BlockedOrderLog.cancel_blocked_order_log(self.block_order)
        return True

    def save(self, *args, **kwargs):
        created = True if not self.pk else False
        if not created and self.__original_status != self.status:
            self.updated_at = ir_now()
            update_fields = kwargs.get('update_fields', None)
            if update_fields:
                kwargs['update_fields'] = list(set(update_fields) | {'updated_at'})
        super().save(*args, **kwargs)


class RecoveryTransaction(models.Model):
    TYPES = Choices(
        (1, 'user_fee_deduction', 'کسر کارمزد کاربر'),
        (2, 'system_fee_addition', 'افزایش کارمزد سیستم'),
        (3, 'user_fee_addition', 'افزایش کارمزد کاربر'),
        (4, 'system_fee_deduction', 'کاهش کارمزد سیستم'),
    )
    transaction = models.OneToOneField(Transaction, on_delete=models.PROTECT, related_name='+', verbose_name='تراکنش')
    recovery_request = models.ForeignKey(RecoveryRequest, on_delete=models.PROTECT, related_name='recovery_transactions',
                                         verbose_name='درخواست بازیابی')
    tp = models.PositiveSmallIntegerField(choices=TYPES, default=TYPES.user_fee_deduction)
    amount = models.DecimalField(max_digits=20, decimal_places=10, verbose_name='مقدار')

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=['recovery_request', 'tp'],
                name='unique_recovery_request_tp',
            ),
        )


class ManualDepositRequestReInquiryLog(models.Model):
    manual_deposit_request = models.ForeignKey(ManualDepositRequest, null=False,on_delete=models.PROTECT, verbose_name='واریز دستی')
    description = models.TextField(verbose_name='توضیحات', null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    admin_user = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)


class RejectReason(models.Model):
    title = models.CharField(max_length=35, null=False, blank=False, unique=True, verbose_name='موضوع')
    description = models.TextField(null=True, verbose_name='توضیحات برای نمایش به کاربر')

    allocated_by = models.ForeignKey('accounts.User', null=True, verbose_name='ایجاد کننده', on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    def __str__(self) -> str:
        return self.title


class RecoveryRejectReasons(models.Model):
    reasons = models.ManyToManyField(to=RejectReason)
    recovery = models.OneToOneField(RecoveryRequest, null=True, on_delete=models.SET_NULL, related_name='reject_reason')

    allocated_by = models.ForeignKey('accounts.User', null=True, verbose_name='ایجاد کننده', on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
