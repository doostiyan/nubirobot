from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from exchange.accounts.models import Notification
from exchange.base.calendar import to_shamsi_date
from exchange.base.emailmanager import EmailManager
from exchange.base.models import Settings
from exchange.base.templatetags.nobitex import shamsidateformat
from exchange.security.functions import get_emergency_cancel_url
from exchange.security.models import IPBlackList, KnownDevice, LoginAttempt


@receiver(post_save, sender=LoginAttempt, dispatch_uid='new_login_attempt')
def new_login_attempt(sender, instance, created, **kwargs):
    # Check if this is an attempt for a registered user
    if not created:
        return
    user = instance.user
    if not user:
        return

    # Send notification email for logins from new devices
    send_email_notif = user.is_email_verified
    if settings.IS_TESTNET:
        send_email_notif = False
    if instance.is_successful or not Settings.get_flag('email_send_unsuccessful_login_notification'):
        send_email_notif = False
    if send_email_notif:
        EmailManager.send_email(
            email=user.email,
            template='login_notif',
            data={
                'successful': instance.is_successful,
                'username': instance.username,
                'ip': instance.ip,
                'date': to_shamsi_date(instance.created_at),
                'device': instance.get_device_name(),
            },
            priority='high',
        )

    # Send Telegram notification
    Notification(
        user=user,
        message='لاگین {} از آدرس: {}'.format('موفق' if instance.is_successful else 'ناموفق', instance.ip),
    ).send_to_telegram_conversation(save=False)


@receiver((post_save, post_delete), sender=IPBlackList, dispatch_uid='clear_blacklist_cache')
def clear_blacklist_cache(**kwargs):
    cache.delete(IPBlackList.CACHE_KEY)


@receiver(post_save, sender=KnownDevice, dispatch_uid='send_new_device_notification')
def send_new_device_notification(sender, instance, created, **kwargs):
    if not created:
        return
    user = instance.user
    if user is None:
        return

    def send_mail():
        login_datetime = shamsidateformat(instance.last_activity)
        login_date, login_time = login_datetime.split(' ')
        EmailManager.send_email(
            email=user.email,
            template='new_device_notif',
            data={
                'user_full_name': user.get_full_name(),
                'device_name': instance.name,
                'login_date': login_date,
                'login_time': login_time,
                'emergency_cancel_url': get_emergency_cancel_url(user),
            },
            priority='high',
        )

    if (
        user.is_email_verified and
        Settings.get_flag('send_new_device_email_notification')
    ):
        send_mail()
