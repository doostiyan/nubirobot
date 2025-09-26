from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.base.decorators import measure_consumer_execution
from exchange.broker.broker.client.decorators import ack_on_success
from exchange.broker.broker.client.django_utils import DjangoSchemaConsumerCommand
from exchange.broker.broker.schema import EmailSchema
from exchange.broker.broker.topics import Topics
from exchange.notification.email.email_manager import EmailManager
from exchange.notification.models import EmailInfo
from exchange.notification.switches import NotificationConfig


@measure_consumer_execution('email', metrics_flush_interval=30)
@transaction.atomic
@ack_on_success
def callback(email_data: EmailSchema, *args, **kwargs):
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


class Command(DjangoSchemaConsumerCommand, BaseCommand):
    topic = Topics.EMAIL.value
    config = settings.KAFKA_CONSUMER_CONFIG
    group_id = 'email.creator'
    schema = EmailSchema
    callback = callback
    poll_rate = 0.01
    auto_ack = False
