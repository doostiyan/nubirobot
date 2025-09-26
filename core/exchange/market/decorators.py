import functools
import random

import sentry_sdk

from exchange.base.logging import report_exception
from exchange.base.models import Settings


def capture_marketmaker_sentry_api_transaction(func):
    """
    This decorator is to be used with view functions to analyze performance for marketmaker transactions.
    """

    def should_be_sampled():
        try:
            sample_rate = float(Settings.get_value('marketmaker_sentry_transactions_capture_sample_rate', default='0'))
        except ValueError:
            report_exception()
            return False

        sampling_chance = random.uniform(0, 1)
        return sampling_chance < sample_rate

    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        is_user_marketmaker = request.user.is_authenticated and request.user.is_system_trader_bot

        if is_user_marketmaker and should_be_sampled():
            with sentry_sdk.start_transaction(op='function', name=f'marketmaker-{request.path}', sampled=True):
                return func(request, *args, **kwargs)
        else:
            return func(request, *args, **kwargs)

    return wrapper
