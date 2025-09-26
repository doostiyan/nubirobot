import json
from dataclasses import dataclass
from typing import Optional, Tuple, Union

import redis
from django.conf import settings
from typing_extensions import TypeAlias


@dataclass
class HealthCheckPublish:
    channel: str
    message: dict


IS_OK: TypeAlias = bool
Error: TypeAlias = str

HealthCheck: TypeAlias = Tuple[IS_OK, Union[HealthCheckPublish, Error]]


def healthcheck_publisher(channel_postfix: str = '', message: Optional[dict] = None) -> HealthCheck:
    if message is None:
        message = {'debug': 'heartbeat'}

    serialized_message = json.dumps(message)
    channel = f'public:healthcheck{channel_postfix}'
    try:
        redis.Redis.from_url(settings.PUBLISHER_REDIS_URL).publish(
            channel=channel,
            message=serialized_message,
        )
        return True, HealthCheckPublish(channel=channel, message=message)
    except Exception as e:
        return False, str(e)
