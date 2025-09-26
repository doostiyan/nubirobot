from django.conf import settings

from exchange.explorer.basis.message_broker.adapters.mock_message_broker import MockMessageBroker
from exchange.explorer.basis.message_broker.adapters.rabbitmq import RabbitMQService
from exchange.explorer.basis.message_broker.ports.message_broker_interface import MessageBrokerInterface
from exchange.settings import IS_PROD


class MessageBrokerFactory:
    _instance = None

    @classmethod
    def get_instance(cls) -> MessageBrokerInterface:
        if not cls._instance:
            cls._instance = cls._create_message_broker()
        return cls._instance

    @classmethod
    def _create_message_broker(cls) -> MessageBrokerInterface:
        if not IS_PROD:
            return MockMessageBroker()

        message_broker_setting = settings.MESSAGE_BROKERS.get("rabbitmq")

        return RabbitMQService(
            message_broker_setting.get("HOST"),
            message_broker_setting.get("PORT"),
            message_broker_setting.get("USERNAME"),
            message_broker_setting.get("PASSWORD"),
            message_broker_setting.get("USE_PROXY")
        )
