from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.base.decorators import measure_consumer_execution
from exchange.broker.broker.client.decorators import ack_on_success
from exchange.broker.broker.client.django_utils import DjangoSchemaConsumerCommand
from exchange.broker.broker.schema.sms import SMSSchema
from exchange.broker.broker.topics import Topics
from exchange.notification.models import Sms
from exchange.notification.switches import NotificationConfig
from exchange.notification.tasks import task_send_sms


@measure_consumer_execution('sms', metrics_flush_interval=30)
@transaction.atomic
@ack_on_success
def callback(sms_data: SMSSchema, *args, **kwargs):
    sms = Sms.create(sms_data=sms_data)
    if not NotificationConfig.is_sms_broker_enabled():
        return
    task_send_sms.delay(sms_id=sms.id, is_fast=False)


class Command(DjangoSchemaConsumerCommand, BaseCommand):
    topic = Topics.SMS.value
    config = settings.KAFKA_CONSUMER_CONFIG
    group_id = 'sms.creator'
    schema = SMSSchema
    callback = callback
    poll_rate = 0.01
    auto_ack = False
