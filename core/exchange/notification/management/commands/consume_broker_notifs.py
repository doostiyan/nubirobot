from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.accounts.models import User
from exchange.base.decorators import measure_consumer_execution
from exchange.broker.broker.client.decorators import ack_on_success
from exchange.broker.broker.client.django_utils import DjangoSchemaConsumerCommand
from exchange.broker.broker.schema.notification import NotificationSchema
from exchange.broker.broker.topics import Topics
from exchange.notification.models import InAppNotification as Notification


@measure_consumer_execution('notification', metrics_flush_interval=30)
@transaction.atomic
@ack_on_success
def callback(notification_data: NotificationSchema, *args, **kwargs):
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


class Command(DjangoSchemaConsumerCommand, BaseCommand):
    topic = Topics.NOTIFICATION.value
    config = settings.KAFKA_CONSUMER_CONFIG
    group_id = 'notification.creator'
    schema = NotificationSchema
    callback = callback
    poll_rate = 0.01
    auto_ack = False
