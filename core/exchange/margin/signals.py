from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from exchange.accounts.models import Notification
from exchange.liquidator.models import LiquidationRequest
from exchange.margin.log_functions import log_margin_order_cancel
from exchange.margin.models import MarginOrderChange, Position
from exchange.margin.tasks import (
    task_bulk_update_position_on_order_change,
    task_update_position_on_liquidation_request_change,
)
from exchange.market.models import Order


@receiver(post_save, sender=Order, dispatch_uid='log_margin_order_change')
def log_margin_order_change(sender, instance: Order, created, **_):
    if instance.is_margin:
        if not created:
            MarginOrderChange.objects.create(order=instance)
        if instance.status == Order.STATUS.canceled:
            log_margin_order_cancel(instance, inside_matcher=False)


@receiver(post_save, sender=MarginOrderChange, dispatch_uid='margin_order_position_update')
def update_position_after_order_change(sender, instance: MarginOrderChange, **_):
    transaction.on_commit(lambda: task_bulk_update_position_on_order_change.delay([instance.order_id]))


@receiver(post_save, sender=LiquidationRequest, dispatch_uid='track_margin_liquidation_request_change')
def update_position_after_liquidation_request_change(sender, instance: LiquidationRequest, created, **_):
    if not created:
        transaction.on_commit(lambda: task_update_position_on_liquidation_request_change.delay(instance.id))


@receiver(post_save, sender=Position, dispatch_uid='margin_position_notif')
def send_position_notifications(sender, instance: Position, update_fields, **_):
    if update_fields and 'pnl' in update_fields:
        instance.notify_on_complete()
