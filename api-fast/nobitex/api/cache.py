import pickle
from typing import Any, Optional, Iterable

from flask import Flask

from flask_redis import FlaskRedis

rc: FlaskRedis


def init(app: Flask):
    global rc
    rc = FlaskRedis(app)


def _decode_value(encoded_value):
    try:
        return int(encoded_value)
    except ValueError:
        return pickle.loads(encoded_value)


def get(key: str, default: Optional[Any] = None) -> Optional[Any]:
    value = rc.get(':1:' + key)
    if value is None:
        return default
    return _decode_value(value)


def set(key: str, value: Any, timeout: int):
    rc.set(':1:' + key, pickle.dumps(value), ex=timeout)


def keys(regex: str) -> list:
    return [key[3:].decode() for key in rc.keys(':1:' + regex)]


def get_many(keys: Iterable) -> dict:
    values = rc.mget(':1:' + key for key in keys)
    return {key: _decode_value(value) for key, value in zip(keys, values) if value}
