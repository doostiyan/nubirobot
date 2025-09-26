import hashlib
import time
from typing import Optional
from uuid import UUID

import jwt
from django.conf import settings


def create_ws_authentication_param(user_uid: UUID) -> str:
    hash_of_user_uid = hashlib.sha256(user_uid.bytes).hexdigest()
    return hash_of_user_uid[:32]


def generate_connection_token(user_uid: UUID, meta: Optional[dict] = None) -> str:
    if meta is None:
        meta = {}
    now_second = int(time.time())

    payload = {
        'sub': create_ws_authentication_param(user_uid),
        'exp': now_second + 1200,
        'iat': now_second,
        'meta': meta,
    }
    token = jwt.encode(payload, settings.WEBSOCKET_AUTH_SECRET, algorithm='ES512')
    return token
