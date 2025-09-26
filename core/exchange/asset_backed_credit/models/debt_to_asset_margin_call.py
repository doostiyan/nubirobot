from django.db import models
from django.utils import timezone
from model_utils import Choices

from exchange.accounts.models import User
from exchange.asset_backed_credit.models.user import InternalUser
from exchange.market.models import Order


class AssetToDebtMarginCall(models.Model):
    ACTION = Choices(
        (10, 'noop', 'noop'),
        (20, 'discharged', 'discharged'),
        (30, 'liquidated', 'liquidated'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='کاربر')
    internal_user = models.ForeignKey(
        InternalUser,
        on_delete=models.CASCADE,
        verbose_name='کاربر',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='تاریخ ایجاد')
    total_debt = models.DecimalField(max_digits=25, decimal_places=10, verbose_name='میزان بدهی')
    total_assets = models.DecimalField(max_digits=25, decimal_places=10, verbose_name='میزان دارایی')
    is_margin_call_sent = models.BooleanField(default=False, verbose_name='نوتیف مارجین کال ارسال شده؟')
    is_liquidation_notif_sent = models.BooleanField(default=False, verbose_name='نوتیف لیکویدشن ارسال شده؟')
    is_adjustment_notif_sent = models.BooleanField(default=False, verbose_name='نوتیف اجاستمنت ارسال شده؟')
    is_solved = models.BooleanField(default=False, verbose_name='برطرف شده؟')
    last_action = models.SmallIntegerField(choices=ACTION, default=ACTION.noop, verbose_name='آخرین اقدام سیستمی')
    orders = models.ManyToManyField(Order, related_name='+', blank=True)

    class Meta:
        verbose_name = 'اعلان هشدار مارجین‌کال نسبت دارایی به بدهی'
        verbose_name_plural = 'اعلان‌های هشدار مارجین‌کال نسبت دارایی به بدهی'

    def cancel_active_orders(self):
        active_orders = (
            self.orders.exclude(status__in=[Order.STATUS.done, Order.STATUS.canceled])
            .select_for_update(no_key=True)
            .all()
        )
        for active_order in active_orders:
            active_order.do_cancel()

    @classmethod
    def user_has_active_liquidation_order(cls, user_id) -> bool:
        active_margin_call = cls.objects.filter(user_id=user_id, is_solved=False).first()
        if not active_margin_call:
            return False
        return active_margin_call.orders.filter(status=Order.STATUS.active).exists()
