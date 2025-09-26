from functools import partial

from django.conf import settings
from django.db import transaction

from exchange.accounts.models import User
from exchange.base.consumer import register_consumer
from exchange.base.decorators import measure_consumer_execution
from exchange.broker.broker.client.decorators import ack_on_success
from exchange.broker.broker.schema import (
    AdminTelegramNotificationSchema,
    EmailSchema,
    NotificationSchema,
    SMSSchema,
    TelegramNotificationSchema,
)
from exchange.broker.broker.topics import Topics
from exchange.notification.email.email_manager import EmailManager
from exchange.notification.models import EmailInfo
from exchange.notification.models import InAppNotification as Notification
from exchange.notification.models import Sms
from exchange.notification.switches import NotificationConfig
from exchange.notification.tasks import task_send_sms

register_notification_consumers = partial(
    register_consumer,
    scope='notification',
    config=settings.KAFKA_CONSUMER_CONFIG,
    poll_rate=0.01,
    auto_ack=False,
)


@register_notification_consumers(
    topic=Topics.NOTIFICATION.value,
    group_id='notification.creator',
    schema=NotificationSchema,
    num_processes=5 if settings.IS_PROD else 2,
)
@measure_consumer_execution('notification', metrics_flush_interval=30)
@ack_on_success
@transaction.atomic
def notif_callback(notification_data: NotificationSchema, *args, **kwargs):
    user = User.objects.filter(uid=notification_data.user_id).only('id').first()
    if not user:
        return
    admin = User.objects.filter(uid=notification_data.admin).first() if notification_data.admin else None
    Notification(
        user_id=user.id,
        message=notification_data.message,
        admin=admin,
        sent_to_telegram=notification_data.sent_to_telegram,
        sent_to_fcm=notification_data.sent_to_fcm,
    ).create()


@register_notification_consumers(
    topic=Topics.EMAIL.value,
    group_id='email.creator',
    schema=EmailSchema,
    num_processes=1,
)
@measure_consumer_execution('email', metrics_flush_interval=30)
@ack_on_success
@transaction.atomic
def email_callback(email_data: EmailSchema, *args, **kwargs):
    if NotificationConfig.is_email_logging_enabled():
        EmailInfo.objects.create(
            to=email_data.to,
            template=email_data.template,
            context=email_data.context,
            priority=email_data.priority,
            backend=email_data.backend,
            scheduled_time=email_data.scheduled_time,
        )

    if NotificationConfig.is_email_broker_enabled():
        EmailManager.send_email(
            email=email_data.to,
            template=email_data.template,
            data=email_data.context,
            backend=email_data.backend,
            scheduled_time=email_data.scheduled_time,
            priority=email_data.priority,
        )


@register_notification_consumers(
    topic=Topics.ADMIN_TELEGRAM_NOTIFICATION.value,
    group_id='admin_telegram_notification.creator',
    schema=AdminTelegramNotificationSchema,
    num_processes=1,
)
@ack_on_success
@transaction.atomic
def admin_telegram_callback(data: AdminTelegramNotificationSchema, *args, **kwargs):
    Notification.notify_admins(
        data.message,
        data.title,
        data.channel,
        data.message_id,
        data.codename,
        data.pin,
        data.cache_key,
        data.cache_timeout,
    )


@register_notification_consumers(
    topic=Topics.SMS.value,
    group_id='sms.creator',
    schema=SMSSchema,
    num_processes=1,
)
@measure_consumer_execution('sms', metrics_flush_interval=30)
@ack_on_success
@transaction.atomic
def sms_callback(sms_data: SMSSchema, *args, **kwargs):
    handle_sms_callback(sms_data, is_fast=False)


@register_notification_consumers(
    topic=Topics.FAST_SMS.value,
    group_id='fast_sms.creator',
    schema=SMSSchema,
    num_processes=1,
)
@measure_consumer_execution('fastSms', metrics_flush_interval=30)
@ack_on_success
@transaction.atomic
def fast_sms_callback(sms_data: SMSSchema, *args, **kwargs):
    handle_sms_callback(sms_data, is_fast=True)


@register_notification_consumers(
    topic=Topics.TELEGRAM_NOTIFICATION.value,
    group_id='telegram_notification.creator',
    schema=TelegramNotificationSchema,
    num_processes=1,
)
@ack_on_success
@transaction.atomic
def telegram_callback(data: TelegramNotificationSchema, *args, **kwargs):
    handle_telegram_callback(data)


@register_notification_consumers(
    topic=Topics.FAST_TELEGRAM_NOTIFICATION.value,
    group_id='fast_telegram_notification.creator',
    schema=TelegramNotificationSchema,
    num_processes=1,
)
@ack_on_success
@transaction.atomic
def fast_telegram_callback(data: TelegramNotificationSchema, *args, **kwargs):
    handle_telegram_callback(data)


def handle_sms_callback(sms_data: SMSSchema, is_fast: bool):
    sms = Sms.create(sms_data=sms_data)
    if not NotificationConfig.is_sms_broker_enabled():
        return
    task_send_sms.delay(sms_id=sms.id, is_fast=is_fast)  # TODO Use different celery task to separate the SMS queue


def handle_telegram_callback(data: TelegramNotificationSchema):
    user = User.objects.filter(uid=data.user_id).only('id').first()
    if not user:
        return
    Notification(user=user, message=data.message).send_to_telegram_conversation(
        save=False, title=data.title if data.title else '🔵 Notification'
    )
