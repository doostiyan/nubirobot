from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Type

from django.conf import settings

from exchange.broker.broker.schema.base import Model


@dataclass
class ConsumerBlueprint:
    scope: str
    topic: str
    group_id: str
    callback: Callable
    poll_rate: float
    auto_ack: bool
    num_processes: int
    config: dict
    schema: Optional[Type[Model]] = None
    on_error_callback: Optional[Callable] = None

    def __str__(self) -> str:
        return f'Scope: {self.scope}, Topic: {self.topic}, GroupId: {self.group_id}'


class ConsumerRegistry:
    consumer_blueprints: Dict[str, List[ConsumerBlueprint]] = defaultdict(list)

    @classmethod
    def register_consumer(
        cls,
        scope: str,
        topic: str,
        group_id: str,
        callback: Callable,
        poll_rate: float,
        num_processes: int,
        config: dict,
        *,
        auto_ack: bool,
        schema: Optional[Type[Model]] = None,
        on_error_callback: Optional[Callable] = None,
    ):
        cls.consumer_blueprints[scope].append(
            ConsumerBlueprint(
                scope=scope,
                topic=topic,
                group_id=group_id,
                callback=callback,
                poll_rate=poll_rate,
                auto_ack=auto_ack,
                num_processes=num_processes,
                config=config,
                schema=schema,
                on_error_callback=on_error_callback,
            ),
        )


def register_consumer(
    scope: str,
    topic: str,
    group_id: str,
    poll_rate=0.1,
    num_processes=1,
    config=settings.KAFKA_CONSUMER_CONFIG,
    *,
    auto_ack=True,
    schema: Optional[Type[Model]] = None,
    on_error_callback: Optional[Callable] = None,
):
    def decorator(f):
        ConsumerRegistry.register_consumer(
            scope=scope,
            topic=topic,
            group_id=group_id,
            callback=f,
            poll_rate=poll_rate,
            auto_ack=auto_ack,
            num_processes=num_processes,
            config=config,
            schema=schema,
            on_error_callback=on_error_callback,
        )
        return f

    return decorator
