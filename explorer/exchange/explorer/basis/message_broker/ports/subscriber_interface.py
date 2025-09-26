from abc import ABC, abstractmethod


class SubscriberInterface(ABC):
    @abstractmethod
    def callback(self, message: str) -> None:
        pass

    @abstractmethod
    def topic(self) -> str:
        pass

    def threads(self) -> int:
        return 1
