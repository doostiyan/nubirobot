from typing import Callable

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from exchange.base.calendar import ir_now
from exchange.staking.helpers import OperationTime
from exchange.staking.models import ExternalEarningPlatform, StakingTransaction
from exchange.staking.notifier import ContextInfo, Notifier, StakingNotifTopic
from exchange.staking.service.staking import get_staking_extended_amount, get_user_stakings


@receiver(post_save, sender=StakingTransaction, dispatch_uid='send_user_staking_notifications')
def send_user_staking_notifications(sender, instance: StakingTransaction, created, **_):
    if not created:
        return

    transaction.on_commit(get_notif_func(instance))


def get_notif_func(instance) -> Callable:
    def notify():
        context = ContextInfo(
            currency=instance.plan.currency,
            amount=instance.amount,
            platform=instance.plan.fa_description,
            platform_code=ExternalEarningPlatform.get_type_machine_display(instance.plan.external_platform.tp),
            realized_apr=instance.plan.realized_apr,
        )

        if instance.tp == StakingTransaction.TYPES.create_request:
            Notifier.notify(StakingNotifTopic.CREATE_REQUEST, instance.user_id, context)

        if instance.tp == StakingTransaction.TYPES.end_request:
            Notifier.notify(StakingNotifTopic.END_REQUEST, instance.user_id, context)

        if instance.tp == StakingTransaction.TYPES.release:
            Notifier.notify(StakingNotifTopic.RELEASE, instance.user_id, context)

        if instance.tp == StakingTransaction.TYPES.stake:
            Notifier.notify(StakingNotifTopic.STAKED, instance.user_id, context)

        if instance.tp == StakingTransaction.TYPES.give_reward:
            extended_amount = get_staking_extended_amount(user_id=instance.user_id, plan_id=instance.plan_id)
            if extended_amount and extended_amount > 0:
                Notifier.notify(StakingNotifTopic.REWARD_DEPOSIT_AND_EXTEND, instance.user_id, context)
            else:
                Notifier.notify(StakingNotifTopic.REWARD_DEPOSIT_NO_EXTEND, instance.user_id, context)

        if instance.tp == StakingTransaction.TYPES.instant_end_request:
            context['release_day'] = 'امروز' if ir_now().date() == OperationTime.get_next().date() else 'فردا'
            Notifier.notify(StakingNotifTopic.INSTANT_END_REQUEST, instance.user_id, context)

    return notify
