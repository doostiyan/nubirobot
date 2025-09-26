from django.conf import settings

from .common import *

if settings.IS_VIP:
    from .vip import *
else:
    from .non_vip import *
