from abc import ABC, abstractmethod

from exchange.explorer.basis.message_broker.ports.message_broker_config import MessageBrokerConfig
from exchange.explorer.basis.message_broker.ports.subscriber_interface import SubscriberInterface


class MessageBrokerInterface(ABC):
    @abstractmethod
    def publish(self, topic: str, message: str) -> None:
        """
        Publish a message to a specific topic.

        Args:
            topic (str): The name of the topic.
            message (str): The message to be published.

        """

    @abstractmethod
    def register_subscriber(self, subscriber: SubscriberInterface) -> None:
        """
        Register a subscriber to a topic. When a message is received, the execute method will be invoked.

        :param subscriber (SubscriberInterface)
        """

    @abstractmethod
    def start_subscribing_threads(self) -> None:
        """Start subscribing on all registered subscribers."""

    @abstractmethod
    def stop_subscribing_threads(self) -> None:
        """Stop all subscribers and close their connections."""

    @abstractmethod
    def add_custom_config(self, *config: MessageBrokerConfig) -> None:
        """Stop all subscribers and close their connections."""
