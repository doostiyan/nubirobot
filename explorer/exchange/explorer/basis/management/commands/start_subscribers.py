import logging

from django.core.management.base import BaseCommand
from sentry_sdk import capture_exception

from exchange.explorer.basis.message_broker.factory import MessageBrokerFactory


class Command(BaseCommand):
    help = "Start MessageBroker subscriber threads"
    logger = logging.getLogger("default")

    def handle(self, *_: list, **__: dict) -> None:
        self.logger.info("Starting MessageBroker subscribers...")
        message_broker = MessageBrokerFactory.get_instance()
        try:
            message_broker.start_subscribing_threads()
        except KeyboardInterrupt:
            message_broker.stop_subscribing_threads()
        except Exception as e:
            capture_exception(e)
            message_broker.stop_subscribing_threads()
