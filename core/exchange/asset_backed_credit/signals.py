from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from exchange.asset_backed_credit.externals.restriction import UserRestrictionType
from exchange.asset_backed_credit.models import DebtChangeLog, Service, SettlementTransaction, UserService
from exchange.asset_backed_credit.tasks import remove_user_restriction_task, task_settlement_settle_user
from exchange.base.constants import ZERO
from exchange.base.models import has_changed_field


@receiver(post_save, sender=UserService, dispatch_uid='user_service_post_save')
def user_service_post_save(sender, instance: UserService, **kwargs):
    log_debt_change(instance, 'current_debt')
    log_debt_change(instance, 'initial_debt')

    # remove restriction for mobile on finished tara services
    if instance.service.provider == Service.PROVIDERS.tara and instance.status in [
        UserService.STATUS.settled,
        UserService.STATUS.closed,
    ]:
        remove_user_restriction_task.delay(
            user_service_id=instance.id, restriction=UserRestrictionType.CHANGE_MOBILE.value
        )


def log_debt_change(instance: UserService, field_name: str):
    if has_changed_field(instance.tracker.changed(), field_name, None):
        pre_current_debt = instance.tracker.changed()[field_name] or ZERO
        current_debt_diff = getattr(instance, field_name) - pre_current_debt
        if current_debt_diff != ZERO:
            DebtChangeLog.objects.create(
                user_service=instance, amount=current_debt_diff, type=getattr(DebtChangeLog.TYPE, field_name)
            )


@receiver(post_save, sender=SettlementTransaction, dispatch_uid='user_settlement_called')
def call_settle_user_task(sender, instance: SettlementTransaction, created, **_):
    if created and instance.should_settle:
        transaction.on_commit(lambda: task_settlement_settle_user.delay(instance.pk))
