import datetime
import os
import traceback
import jsonpickle
from django_redis.serializers.base import BaseSerializer
from typing import Any
from datetime import datetime
from django.db.models import Model
import json


class CustomJSONSerializer(BaseSerializer):

    def dumps(self, value: Any) -> bytes:
        if value:
            return jsonpickle.dumps(value)

    def loads(self, value: bytes) -> Any:
        if value:
            return jsonpickle.loads(value)
