from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.accounts.models import User
from exchange.broker.broker.client.decorators import ack_on_success
from exchange.broker.broker.client.django_utils import DjangoSchemaConsumerCommand
from exchange.broker.broker.schema.notification import TelegramNotificationSchema
from exchange.broker.broker.topics import Topics
from exchange.notification.models import InAppNotification as Notification


@transaction.atomic
@ack_on_success
def callback(data: TelegramNotificationSchema, *args, **kwargs):
    user = User.objects.filter(uid=data.user_id).only('id').first()
    if not user:
        return
    Notification(user=user, message=data.message).send_to_telegram_conversation(
        save=False, title=data.title if data.title else '🔵 Notification'
    )


class Command(DjangoSchemaConsumerCommand, BaseCommand):
    topic = Topics.FAST_TELEGRAM_NOTIFICATION.value
    config = settings.KAFKA_CONSUMER_CONFIG
    group_id = 'fast_telegram_notification.creator'
    schema = TelegramNotificationSchema
    callback = callback
    poll_rate = 0.01
    auto_ack = False
