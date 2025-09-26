from django.conf import settings

if settings.IS_PROD:
    from .prod import *
else:
    from .debug import *
