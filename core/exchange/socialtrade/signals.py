from datetime import timedelta

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from exchange.base.calendar import get_earliest_time, ir_now
from exchange.socialtrade.models import Leader


@receiver(pre_save, sender=Leader, dispatch_uid='socialtrade_leader_pre_save')
def socialtrade_leader_pre_save(sender, instance: Leader, update_fields, **_):
    if not instance.activates_at:
        instance.activates_at = get_earliest_time(ir_now()) + timedelta(days=1)
        if update_fields:
            update_fields = (*update_fields, 'activates_at')

@receiver(post_save, sender=Leader, dispatch_uid='socialtrade_leader_post_save')
def socialtrade_leader_post_save(sender, instance: Leader, created, **_):
    if created:
        instance.update_profits()
