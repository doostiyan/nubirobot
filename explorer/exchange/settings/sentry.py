import sentry_sdk
from django.conf import settings
from sentry_sdk.integrations.django import DjangoIntegration

from .main import env

ENABLE_SENTRY = env.bool('ENABLE_SENTRY', False)
METRICS_BACKEND = 'sentry' if ENABLE_SENTRY else 'logger'

if ENABLE_SENTRY:
    sentry_sdk.init(
        dsn='https://cd52a945e8b47b4f3b104eae328414eb@sentry.hamravesh.com/7008',
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=0.003,
        sample_rate=0.1,
        integrations=[DjangoIntegration(transaction_style='function_name')],
        environment=settings.ENV,
        send_default_pii=True,
    )
