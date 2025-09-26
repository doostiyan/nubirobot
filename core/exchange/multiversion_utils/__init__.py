__all__ = [
    'multiversion_JSONField',
    'is_ratelimited',
    'ratelimit',
    'Ratelimited',
]


from django import VERSION
from django.db.models import JSONField

multiversion_JSONField = JSONField


if VERSION[0] == 4:
    DJANGO_4 = True
elif VERSION[0] == 3:
    DJANGO_4 = False
else:
    raise Exception('This version of Django is not supported')


if DJANGO_4:
    from django_ratelimit.core import is_ratelimited
    from django_ratelimit.decorators import ratelimit
    from django_ratelimit.exceptions import Ratelimited
else:
    from ratelimit.core import is_ratelimited
    from ratelimit.decorators import ratelimit
    from ratelimit.exceptions import Ratelimited
