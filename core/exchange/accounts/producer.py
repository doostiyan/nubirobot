from django.conf import settings

from exchange.base.lazy_var import LazyVar
from exchange.broker.broker.client.producer import EventProducer

notification_producer = LazyVar(lambda: EventProducer(config=settings.KAFKA_PRODUCER_CONFIG))
