from exchange.explorer.basis.message_broker.ports.message_broker_config import MessageBrokerConfig
from exchange.explorer.basis.message_broker.ports.message_broker_interface import MessageBrokerInterface
from exchange.explorer.basis.message_broker.ports.subscriber_interface import SubscriberInterface


class MockMessageBroker(MessageBrokerInterface):
    def add_custom_config(self, *config: MessageBrokerConfig) -> None:
        pass

    def publish(self, topic: str, message: str) -> None:
        pass

    def register_subscriber(self, subscriber: SubscriberInterface) -> None:
        pass

    def start_subscribing_threads(self) -> None:
        pass

    def stop_subscribing_threads(self) -> None:
        pass
