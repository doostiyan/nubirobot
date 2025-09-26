import datetime
from decimal import Decimal

import pytz
from django.db import models
from django.db.models import JSONField
from django.utils.timezone import now
from model_utils import Choices

from exchange.accounts.models import ApiUsage, User, VerificationProfile
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.shetab.models import JibitDeposit, ShetabDeposit
from exchange.wallet.models import BankDeposit, ConfirmedWalletDeposit, WithdrawRequest


class WalletsStats(models.Model):
    date = models.DateField()
    hour = models.IntegerField()
    currency = models.IntegerField(choices=Currencies)
    balance_user = models.DecimalField(max_digits=25, decimal_places=10, default=Decimal('0'))
    balance_bot = models.DecimalField(max_digits=25, decimal_places=10, default=Decimal('0'))
    balance_system = models.DecimalField(max_digits=25, decimal_places=10, default=Decimal('0'))
    balance_hot = models.DecimalField(max_digits=25, decimal_places=10, default=Decimal('0'))
    balance_cold = models.DecimalField(max_digits=25, decimal_places=10, default=Decimal('0'))
    balance_cold_system = models.DecimalField(max_digits=25, decimal_places=10, default=Decimal('0'))
    balance_binance = models.DecimalField(max_digits=25, decimal_places=10, default=Decimal('0'))
    balance_kraken = models.DecimalField(max_digits=25, decimal_places=10, default=Decimal('0'))

    class Meta:
        unique_together = ['date', 'hour', 'currency']
        ordering = ['-date', '-hour', 'currency']
        verbose_name = 'آمار موجودی والت‌ها'
        verbose_name_plural = verbose_name

    @classmethod
    def get(cls, dt, currency):
        dt = dt.astimezone(pytz.timezone('Asia/Tehran'))
        return cls.objects.get_or_create(currency=currency, date=dt.date(), hour=dt.hour)[0]


class AdoptionStats(models.Model):
    date = models.DateField(db_index=True, verbose_name='روز')
    registered_users = models.IntegerField(default=0, help_text='تعداد کاربران ثبت‌نام شده')
    verified_users = models.IntegerField(default=0, help_text='تعداد کاربران تایید شده')
    verified_users_identity = models.IntegerField(default=0, help_text='تعداد کاربران تایید شده(هویت)')
    monthly_active_trade_users = models.IntegerField(default=0, help_text='تعداد کاربران فعال ماهانه‌(معامله)')
    daily_active_trade_users = models.IntegerField(default=0, help_text='تعداد کاربران فعال روزانه‌(معامله)')
    monthly_active_login_users = models.IntegerField(default=0, help_text='تعداد کاربران فعال ماهانه‌(لاگین)')
    daily_active_login_users = models.IntegerField(default=0, help_text='تعداد کاربران فعال روزانه‌(لاگین)')

    class Meta:
        verbose_name = 'آمار روزانه فعالیت‌های کاربران'
        verbose_name_plural = verbose_name

    def reset_stats(self):
        self.registered_users = 0
        self.verified_users = 0
        self.verified_users_identity = 0
        self.monthly_active_trade_users = 0
        self.daily_active_trade_users = 0
        self.monthly_active_login_users = 0
        self.daily_active_login_users = 0

    def update_stats(self, is_yesterday=False):
        nw = ir_now()
        day = nw.replace(hour=0, minute=0, second=0, microsecond=0)
        if is_yesterday:
            day = day - datetime.timedelta(1)
        month = day.month
        year = day.year
        # TODO: filter based on last 30 days, not the month
        self.registered_users = User.objects.count()
        self.verified_users = User.objects.filter(user_type__gte=User.USER_TYPES.level2).count()
        self.verified_users_identity = VerificationProfile.objects.filter(identity_confirmed=True).count()
        self.monthly_active_trade_users = ApiUsage.objects.filter(last_trade__year=year, last_trade__month=month).count()
        self.daily_active_trade_users = ApiUsage.objects.filter(last_trade__gte=day).count()
        self.monthly_active_login_users = ApiUsage.objects.filter(last_activity__year=year, last_activity__month=month).count()
        self.daily_active_login_users = ApiUsage.objects.filter(last_activity__gte=day).count()
        self.save()

    @classmethod
    def get(cls, dt):
        return cls.objects.get_or_create(date=dt)[0]


class BanksGatewayStats(models.Model):
    gateway_choices = Choices(
        (1, 'jibit', 'جیبیت'),
        (2, 'vandar', 'وندار'),
        (3, 'pey', 'پی'),
    )
    date = models.DateField()
    hour = models.IntegerField()
    gateway = models.IntegerField(choices=gateway_choices)
    balance = models.BigIntegerField(verbose_name='موجودی', default=0)
    balance_user = models.BigIntegerField(verbose_name='موجودی کاربران', default=0)
    deposit = models.BigIntegerField(verbose_name='واریز', default=0)
    withdraw = models.BigIntegerField(verbose_name='برداشت', default=0)

    class Meta:
        unique_together = ['date', 'hour', 'gateway']
        ordering = ['-date', '-hour', 'gateway']
        verbose_name = 'آمار درگاه‌های بانکی'
        verbose_name_plural = verbose_name

    @classmethod
    def get(cls, dt, gateway):
        dt = dt.astimezone(pytz.timezone('Asia/Tehran'))
        return cls.objects.get_or_create(gateway=gateway, date=dt.date(), hour=dt.hour)[0]


class ReportResult(models.Model):
    REPORTS = Choices(
        (0, 'other', 'سایر'),
        (1, 'user_referral', 'گزارش درآمد کاربران از معرفی دوستان'),
        (2, 'total_commission', 'گزارش کارمزد کل'),
        (3, 'daily_commission', 'گزارش کارمزد روزانه'),
        (4, 'users_commission', 'گزارش کارمزد کاربران'),
        (5, 'gateway_performance', 'گزارش عملکرد درگاهها'),
        (6, 'month_users', 'گزارش کاربران ماه'),
        (7, 'bots_notifications', '‌اعلانات معاملات بات‌ها'),
        (8, 'customer_segmentation', 'گزارش تفکیک کاربران'),
        (9, 'commission_explain', 'گزارش درصد کارمزد پله ای'),
    )
    REPORT_TYPES = Choices(
        (0, 'default', 'Default'),
        (1, 'splitted', 'Splitted'),
        (2, 'overall', 'Overall'),
        (3, 'export', 'Export'),
        (4, 'pending', 'Pending'),
    )
    from_date = models.DateField(db_index=True)
    to_date = models.DateField(db_index=True)
    report = models.IntegerField(choices=REPORTS, default=REPORTS.other, db_index=True)
    report_type = models.IntegerField(choices=REPORT_TYPES, default=REPORT_TYPES.default)
    result = JSONField()
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'تاریخچه گزارشات'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(fields=['from_date', 'to_date', 'report', 'report_type'], name='unique_report')
        ]


class DailyShetabDeposit(models.Model):
    BROKER = Choices(
        (1, 'jibit', 'Jibit'),
        (2, 'jibit_v2', 'JibitV2'),
    )

    STATUS = Choices(
        (0, 'unknown', 'Unknown'),
        (1, 'in_progress', 'In progress'),
        (2, 'ready_to_verify', 'Ready to verify'),
        (3, 'failed', 'Failed'),
        (4, 'success', 'Success'),
        (5, 'expired', 'Expired'),
        (6, 'reversed', 'Reversed'),
    )

    STATUSES_TRANSIENT = (STATUS.unknown, STATUS.in_progress, STATUS.ready_to_verify)
    INTERNAL_FIELDS = {'deposit'}

    broker = models.IntegerField(choices=BROKER, verbose_name='درگاه')
    gateway_pk = models.CharField(max_length=70, verbose_name='شناسه درگاه')
    amount = models.BigIntegerField(verbose_name='مبلغ')
    reference_number = models.CharField(max_length=50, unique=True, verbose_name='شناسه مرجع')
    deposit = models.ForeignKey(ShetabDeposit, null=True, blank=True, on_delete=models.SET_NULL)
    user_identifier = models.CharField(max_length=50, verbose_name='هویت کاربر')
    description = models.CharField(max_length=300, null=True, blank=True, verbose_name='توضیحات')
    additional_data = models.CharField(max_length=300, null=True, blank=True, verbose_name='اطلاعات اضافه شده')
    status = models.PositiveSmallIntegerField(choices=STATUS, default=STATUS.unknown, verbose_name='وضیعت پرداخت')
    created_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ ایجاد')
    modified_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ تغییر')
    expiration_date = models.DateTimeField(verbose_name='تاریخ انفضا')
    payer_card = models.CharField(max_length=16, null=True, blank=True, verbose_name='شماره کارت پرداخت کننده')
    national_code = models.CharField(max_length=12, null=True, blank=True, verbose_name='کد ملی')

    class Meta:
        verbose_name = 'واریزی‌های روزانه'
        verbose_name_plural = verbose_name
        unique_together = ('broker', 'gateway_pk')


class DailyJibitDeposit(models.Model):
    """
    A Django model representing all data retrieved from jibit API.
    Data in this model will be fetched regularly from Jibit API Service, Keeping all JibitDeposit Data.
    Considering we also have a JibitDeposit Model, This model does not include in transaction and charging user wallet
    But is used to keep what Bank Deposits Jibit claims belong to Nobitex System


    STATUSES_TRANSIENT (tuple):
        Statuses that can be changed and are not yet final.

    INTERNAL_FIELDS (set):
        Fields that are Foreign Keys to our deposit objects and can be changed, even after final statuses
    """
    STATUS = Choices(
        (0, 'in_progress', 'IN_PROGRESS'),
        (1, 'waiting_for_merchant_verify', 'WAITING_FOR_MERCHANT_VERIFY'),
        (2, 'failed', 'FAILED'),
        (3, 'successful', 'SUCCESSFUL'),
        (4, 'account_processing', 'ACCOUNT_PROCESSING'),
    )

    STATUSES_TRANSIENT = (STATUS.in_progress, STATUS.waiting_for_merchant_verify, STATUS.account_processing)
    INTERNAL_FIELDS = {'bank_deposit', 'jibit_deposit'}

    bank_deposit = models.ForeignKey(to=BankDeposit, null=True, blank=True, on_delete=models.SET_NULL)
    jibit_deposit = models.ForeignKey(to=JibitDeposit, null=True, blank=True, on_delete=models.SET_NULL)

    status = models.PositiveSmallIntegerField(choices=STATUS, default=STATUS.in_progress, verbose_name='وضعیت')
    bank = models.CharField(max_length=15, verbose_name='بانک')
    external_reference_number = models.CharField(max_length=50, verbose_name='شناسه یکتای جیبیت')
    bank_reference_number = models.CharField(
        max_length=255, verbose_name='کد رهگیری بانک', help_text='شناسه رسید بانکی، receipt_id'
    )
    payment_id = models.CharField(max_length=40, verbose_name='شناسه واریز جیبیت')
    merchant_reference_number = models.CharField(
        max_length=50, verbose_name='آیدی نوبیتکس', help_text='NA.bank_account_id, آیدی حساب بانکی کاربر در نوبیتکس'
    )
    source_identifier = models.CharField(max_length=50, verbose_name='شبای کاربر')
    amount = models.BigIntegerField(verbose_name='مبلغ واریزی', help_text='ریال')
    destination_account_identifier = models.CharField(max_length=50, verbose_name='شبای جیبیت')
    bank_raw_timestamp = models.CharField(max_length=50, verbose_name='تاریخ ایجاد در بانک')

    created_at = models.DateTimeField(default=now, db_index=True)


class DailyWithdraw(models.Model):
    BROKER = Choices(
        (1, 'jibit', 'Jibit'),
        (2, 'jibit_v2', 'JibitV2'),
    )

    STATUS = Choices(
        (0, 'initialized', 'Initialized'),
        (1, 'cancelling', 'Cancelling'),
        (2, 'cancelled', 'Cancelled'),
        (3, 'in_progress', 'In progress'),
        (4, 'transferred', 'Transferred'),
        (5, 'failed', 'Failed'),
        (6, 'manually_failed', 'Manually Failed'),
    )

    STATUSES_TRANSIENT = (STATUS.initialized, STATUS.cancelling, STATUS.in_progress)
    INTERNAL_FIELDS = {'withdraw'}

    broker = models.IntegerField(choices=BROKER, verbose_name='درگاه')
    transfer_pk = models.CharField(max_length=70, unique=True, verbose_name='شناسه درگاه')
    transfer_mode = models.CharField(max_length=10, verbose_name='روش انتقال')
    destination = models.CharField(max_length=30, verbose_name='شبا مقصد')
    withdraw = models.ForeignKey(WithdrawRequest, null=True, blank=True, on_delete=models.SET_NULL)
    destination_first_name = models.CharField(max_length=50, null=True, blank=True, verbose_name='نام صاحب شبا')
    destination_last_name = models.CharField(max_length=50, null=True, blank=True, verbose_name='نام‌خانوادگی صاحب شبا')
    amount = models.BigIntegerField(verbose_name='مبلغ')
    description = models.CharField(max_length=300, null=True, blank=True, verbose_name='توضیحات')
    bank_transfer = models.CharField(max_length=50, verbose_name='شناسه انتقال')
    status = models.PositiveSmallIntegerField(choices=STATUS, default=STATUS.initialized, verbose_name='وضعیت')
    gateway_fee = models.IntegerField(null=True, blank=True, verbose_name='کارمزد درگاه')
    created_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ ایجاد')

    class Meta:
        verbose_name = 'برداشت‌های روزانه'
        verbose_name_plural = verbose_name


class DailyAccountingReport(models.Model):
    date = models.DateField()
    currency = models.IntegerField(choices=Currencies)
    trade_fees = models.DecimalField(verbose_name='کارمزدهای معاملات', max_digits=25, decimal_places=10)
    deposits = models.DecimalField(verbose_name='برداشت‌ها', max_digits=25, decimal_places=10)
    withdraws = models.DecimalField(verbose_name='واریزها', max_digits=25, decimal_places=10)
    wallet_balances_sum = models.DecimalField(verbose_name='مجموع موجودی کیف‌های پول', max_digits=25, decimal_places=10)

    class Meta:
        verbose_name = 'گزارش سند روزانه'
        verbose_name_plural = verbose_name


class WithdrawDepositDiff(models.Model):
    deposit = models.ForeignKey(to=ConfirmedWalletDeposit, on_delete=models.CASCADE, verbose_name='برداشت', null=True)
    currency = models.IntegerField(choices=Currencies, verbose_name='ارز')
    network = models.CharField(max_length=200, null=True, blank=True, verbose_name='شبکه')
    created_at = models.DateTimeField(auto_now_add=True, null=False, blank=True, verbose_name='تاریخ ایجاد')
    hash = models.CharField(max_length=200, verbose_name='هش تراکنش')
    system_amount = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal('0'),
                                        verbose_name='مقدار سیستم', null=True, blank=True)
    network_amount = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal('0'),
                                         verbose_name='مقدار شبکه', null=True, blank=True)
    address = models.CharField(max_length=200, verbose_name='آدرس', null=True)
    resolved = models.BooleanField(default=False, verbose_name='رفع شده')

    @property
    def type(self):
        return 'withdraw' if self.deposit == None else 'deposit'

    class Meta:
        verbose_name = 'گزارش تفاوت تراکنش'
        verbose_name_plural = verbose_name


class CeleryTaskLog(models.Model):
    LOG_LEVEL = Choices(
        (0, 'info', 'INFO'),
        (1, 'warning', 'WARNING'),
        (2, 'error', 'ERROR'),
        (3, 'critical', 'CRITICAL'),
    )

    task = models.CharField(max_length=200, verbose_name='نام تسک')
    level = models.PositiveSmallIntegerField(choices=LOG_LEVEL, default=LOG_LEVEL.info, verbose_name='نوع لاگ')
    message = models.TextField(blank=True, null=True, verbose_name='پیام لاگ')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='تاریخ ایجاد')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'لاگ تسک های سلری'
        verbose_name_plural = verbose_name
