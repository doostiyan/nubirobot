from abc import abstractmethod

from exchange.explorer.basis.message_broker.ports.message_broker_config import MessageBrokerConfig


class RabbitmqBindingConfig(MessageBrokerConfig):

    @abstractmethod
    def routing_key(self) -> str:
        pass

    @abstractmethod
    def queue(self) -> str:
        pass
