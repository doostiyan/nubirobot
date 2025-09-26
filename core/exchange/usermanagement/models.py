from typing import Union

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from model_utils import Choices

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.market.models import Order


class BlockedOrderLog(models.Model):
    STATUS = Choices(
        (1, 'active', 'Active'),
        (3, 'canceled', 'Canceled'),
    )
    ORDER_TYPES = Choices(
        (1, 'sell', 'Sell'),
        (2, 'buy', 'Buy'),
    )
    admin_user = models.ForeignKey(get_user_model(), on_delete=models.PROTECT, related_name='+', verbose_name='کارشناس')
    src_currency = models.IntegerField(choices=Currencies, verbose_name='ارز مبدا')
    dst_currency = models.IntegerField(choices=Currencies, verbose_name='ارز مقصد')
    amount = models.DecimalField(max_digits=25, decimal_places=10, verbose_name='مقدار ارز')
    status = models.IntegerField(choices=STATUS, default=STATUS.active, db_index=True, verbose_name='وضعیت')
    user = models.ForeignKey(get_user_model(), on_delete=models.PROTECT, verbose_name='کاربر')
    order_type = models.IntegerField(choices=ORDER_TYPES, verbose_name='نوع')
    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='تاریخ ایجاد')
    canceled_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ لغو‌شدن')
    order_id = models.BigIntegerField(null=True, blank=True)
    description = models.TextField(null=True, blank=True, verbose_name='توضیحات')

    @staticmethod
    def add_blocked_order_log(blocked_order: Order, admin_user: User = None) -> Union['BlockedOrderLog', None]:
        """
            Add a blocked order log based on a blocked order.
        """
        blocked_order_log = None
        if blocked_order:
            blocked_order_log = BlockedOrderLog.objects.create(
                admin_user=admin_user or blocked_order.user,
                user=blocked_order.user,
                src_currency=blocked_order.src_currency,
                dst_currency=blocked_order.dst_currency,
                order_type=blocked_order.order_type,
                status=BlockedOrderLog.STATUS.active,
                amount=blocked_order.amount,
                order_id=blocked_order.id,
            )
        return blocked_order_log

    @staticmethod
    def cancel_blocked_order_log(blocked_order: Order, description=None) -> Union['BlockedOrderLog', None]:
        """
            Update the blocked order log based on a blocked order. Update
            the status and canceled_at fields.
        """
        blocked_order_log = None
        if blocked_order:
            blocked_order_log = BlockedOrderLog.objects.filter(order_id=blocked_order.id).first()
            if blocked_order_log:
                blocked_order_log.description = description
                blocked_order_log.status = BlockedOrderLog.STATUS.canceled
                blocked_order_log.canceled_at = timezone.now()
                blocked_order_log.save(update_fields=['status', 'canceled_at', 'description'])
        return blocked_order_log
