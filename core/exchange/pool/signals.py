from django.db.models.signals import post_save
from django.db import transaction
from django.dispatch import receiver

from exchange.base.constants import ZERO
from exchange.pool.models import DelegationTransaction, DelegationRevokeRequest
from exchange.pool.tasks import task_check_settle_delegation_revoke_request


@receiver(post_save, sender=DelegationTransaction, dispatch_uid='pool_user_delegation_update')
def update_user_delegation_after_pool_delegation(sender, instance: DelegationTransaction, created, **_):
    if created:
        instance.user_delegation.update_balance(instance.amount)

    else:
        if instance.amount > ZERO and instance.transaction:
            instance.notify_on_delegation()


@receiver(post_save, sender=DelegationRevokeRequest, dispatch_uid='delegation_revoke_request_update')
def update_pool_revoke_capacity(sender, instance: DelegationRevokeRequest, created, **_):
    if created:
        instance.user_delegation.pool.update_revoke_capacity(instance.amount)
        transaction.on_commit(
            lambda: task_check_settle_delegation_revoke_request.delay(instance.user_delegation.pool_id)
        )
    else:
        instance.notify_on_paid()
