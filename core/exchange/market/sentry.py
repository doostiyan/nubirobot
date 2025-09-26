from exchange.base.decorators import ram_cache
from exchange.base.models import Settings


@ram_cache(timeout=60)
def capture_matcher_sentry_transaction():
    return not Settings.is_disabled('capture_matcher_sentry_transaction')
