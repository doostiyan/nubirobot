import uuid

from django.conf import settings

from exchange.accounts.models import User


def is_valid_uuid(uuid_string):
    try:
        uuid.UUID(uuid_string)
    except ValueError:
        return False

    return True
