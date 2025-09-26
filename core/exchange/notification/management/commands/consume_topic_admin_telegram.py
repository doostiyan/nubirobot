from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.broker.broker.client.decorators import ack_on_success
from exchange.broker.broker.client.django_utils import DjangoSchemaConsumerCommand
from exchange.broker.broker.schema.notification import AdminTelegramNotificationSchema
from exchange.broker.broker.topics import Topics
from exchange.notification.models import InAppNotification as Notification


@transaction.atomic
@ack_on_success
def callback(data: AdminTelegramNotificationSchema, *args, **kwargs):
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


class Command(DjangoSchemaConsumerCommand, BaseCommand):
    topic = Topics.ADMIN_TELEGRAM_NOTIFICATION.value
    config = settings.KAFKA_CONSUMER_CONFIG
    group_id = 'admin_telegram_notification.creator'
    schema = AdminTelegramNotificationSchema
    callback = callback
    poll_rate = 0.01
    auto_ack = False
