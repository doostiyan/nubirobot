import datetime

from django.contrib.postgres.fields import ArrayField
from django.db import IntegrityError, models, transaction
from django.db.models import CheckConstraint, F, JSONField, Q
from django.utils.timezone import now
from model_utils import Choices

from exchange.accounts.models import UploadedFile, User
from exchange.base.logging import report_event
from exchange.base.models import Currencies
from exchange.market.models import Order
from exchange.promotions.exceptions import CreateNewUserDiscountBudgetLimit
from exchange.wallet.models import Transaction


class FeeDiscount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feediscounts')
    discounted_fee = models.DecimalField(decimal_places=2, max_digits=5, help_text='درصد')
    total_discount = models.IntegerField(null=True, blank=True, help_text='﷼')
    used_discount = models.IntegerField(default=0, help_text='﷼')
    date_from = models.DateTimeField(null=True, blank=True)
    date_to = models.DateTimeField(null=True, blank=True)
    description = models.CharField(
        max_length=500, null=True, blank=True, verbose_name='توضیحات', help_text='علت اعمال تخفیف'
    )
    is_finished = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'تخفیف کارمزد'
        verbose_name_plural = verbose_name

    @property
    def is_active_now(self):
        nw = now()
        if self.date_from and nw < self.date_from:
            return False
        if self.date_to and nw >= self.date_to:
            return False
        return True

    def check_is_finished(self):
        is_expired = self.date_to and now() >= self.date_to
        is_used = self.total_discount is not None and self.used_discount >= self.total_discount
        if is_expired or is_used:
            self.is_finished = True
            self.save(update_fields=['is_finished'])
            return True
        return False

    def commit_discount_use(self, used_discount):
        used_discount = int(used_discount)
        FeeDiscount.objects.filter(pk=self.pk).update(used_discount=F('used_discount') + used_discount)


def default_trade_types():
    return [Order.TRADE_TYPES.spot]


class Discount(models.Model):
    STATUS = Choices(
        (0, 'inactive', 'Inactive'),
        (1, 'active', 'Active'),
        (2, 'finished', 'Finished'),
        (3, 'disabled', 'Disabled'),
    )
    name = models.CharField(max_length=500, null=False, blank=False, verbose_name='نام تخفیف')
    description = models.TextField(null=True, blank=True, verbose_name='توضیحات', help_text='توضیحات')
    webengage_campaign_id = models.CharField(max_length=60, db_index=True, unique=True, null=True, blank=True,
                                             verbose_name='شناسه‌ی کمپین در webengage')
    status = models.SmallIntegerField(choices=STATUS, default=0, null=False, blank=False, verbose_name='وضعیت')
    currency = models.IntegerField(choices=Currencies, verbose_name='ارز هدف', blank=True, null=True)
    start_date = models.DateField(null=True, blank=True, verbose_name='تاریخ شروع')
    end_date = models.DateField(null=True, blank=True, verbose_name='تاریخ پایان')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    percent = models.IntegerField(null=True, blank=True, default=100, verbose_name='درصد تخفیف')
    amount_rls = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, default=0,
                                     verbose_name='مقدار ریالی تخفیف')
    duration = models.IntegerField(default=0, verbose_name='مدت زمان')
    budget = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='بودجه‌ی کمپین تخفیفی')
    budget_remain = models.DecimalField(max_digits=15, decimal_places=0, default=0,
                                        verbose_name='بودجه‌ی باقی‌مانده‌ی کمپین تخفیفی')
    trade_types = ArrayField(
        models.PositiveSmallIntegerField(choices=Order.TRADE_TYPES, default=Order.TRADE_TYPES.spot),
        default=default_trade_types,
    )
    disabled_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ توقف فعالیت')

    class Meta:
        constraints = [
            CheckConstraint(
                check=(Q(budget_remain__gte=0) & Q(budget_remain__lte=F('budget'))),
                name='check_budget_remain',
            ),
        ]

    def __str__(self):
        return f'{self.name} - {self.webengage_campaign_id}'


class UserDiscountBatch(models.Model):
    file = models.OneToOneField(UploadedFile, verbose_name='فایل', on_delete=models.DO_NOTHING)
    discount = models.ForeignKey(Discount, on_delete=models.CASCADE, verbose_name='تخفیف')
    details = JSONField(verbose_name='جزئیات', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ ویرایش')

    @property
    def is_applied(self):
        return self.details is not None


class UserDiscount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='کاربر')
    discount = models.ForeignKey(Discount, related_name='user_discount', on_delete=models.CASCADE, verbose_name='تخفیف')
    amount_rls = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, default=0,
                                     verbose_name='مقدار ریالی تخفیف')
    activation_date = models.DateField(null=True, blank=True, verbose_name='تاریخ فعال شدن تخفیف')
    end_date = models.DateField(null=True, blank=True, verbose_name='تاریخ پایان')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    discount_batch = models.ForeignKey(UserDiscountBatch, related_name='user_discounts', on_delete=models.DO_NOTHING,
                                       null=True, blank=True)

    @classmethod
    def create_new_user_discount_with_webengage_campaign_id(cls, user_id: int, discount: Discount,
                                                            activation_date: datetime.date = None,
                                                            end_date: datetime.date = None,
                                                            discount_batch_id: int = None):
        with transaction.atomic():
            try:
                Discount.objects.filter(id=discount.id).update(budget_remain=F('budget_remain') - discount.amount_rls)
            except IntegrityError:
                report_event('CreateNewUserDiscountBudgetError', extras={'src': 'CreateUserDiscount'})
                raise CreateNewUserDiscountBudgetLimit()
            user_discount = cls.objects.create(user_id=user_id, discount=discount, amount_rls=discount.amount_rls,
                                               activation_date=activation_date, end_date=end_date,
                                               discount_batch_id=discount_batch_id)
        return user_discount

    def get_user_status(self):
        """
        This function returns user discount status
        """
        if self.discount.status == Discount.STATUS.disabled:
            if self.end_date >= self.discount.disabled_at.date():
                return Discount.STATUS[Discount.STATUS.disabled].lower()
            return Discount.STATUS[Discount.STATUS.finished].lower()

        if self.end_date >= now().date():
            return Discount.STATUS[Discount.STATUS.active].lower()

        return Discount.STATUS[Discount.STATUS.finished].lower()


class DiscountTransactionLog(models.Model):
    user_discount = models.ForeignKey(UserDiscount, related_name='discount_transaction_log',
                                      on_delete=models.CASCADE, verbose_name='تخفیفات کاربر')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    amount = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='مبلغ تراکنش')
    transaction = models.OneToOneField(
        Transaction, on_delete=models.SET_NULL, related_name="+", null=True, blank=True, verbose_name="تراکنش"
    )
