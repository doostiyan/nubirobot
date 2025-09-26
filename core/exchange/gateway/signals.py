from django.db.models.signals import post_save
from django.dispatch import receiver

from exchange.accounts.models import Notification
from exchange.base.formatting import f_m
from exchange.gateway.gateway import create_gateway_order, create_gateway_transaction
from exchange.gateway.models import PendingWalletRequest


@receiver(post_save, sender=PendingWalletRequest, dispatch_uid='pending_wallet_request_after_save')
def pending_wallet_request_after_save(sender, instance, created, **kwargs):
    if created:
        Notification.notify_admins('*RequestID:* #{}\n*Gateway:* {}\n*Amount:* {}({})'.format(
            instance.pk,
            instance.pg_req.pg_user.site_name,
            f_m(instance.exact_crypto_amount, c=instance.tp, show_c=True),
            f_m(instance.pg_req.amount, c=instance.pg_req.settle_tp, show_c=True),
        ), title='فاکتور درگاه رمزارزی')
    if instance.status in [PendingWalletRequest.STATUS.unconfirmed, PendingWalletRequest.STATUS.paid] and not instance.create_order:
        Notification.notify_admins('واریز مربوط به فاکتور {} درگاه رمزارزی {} در شبکه {} ثبت اولیه شد.'.format(
            instance.pk,
            instance.pg_req.pg_user.site_name,
            instance.get_tp_display(),
        ))
        create_gateway_order(instance)
    if instance.status == PendingWalletRequest.STATUS.paid and not instance.settle:
        create_gateway_transaction(instance)
        Notification.notify_admins('واریز مربوط به فاکتور {} درگاه رمزارزی {} در شبکه {} تایید شد.'.format(
            instance.pk,
            instance.pg_req.pg_user.site_name,
            instance.get_tp_display(),
        ))
