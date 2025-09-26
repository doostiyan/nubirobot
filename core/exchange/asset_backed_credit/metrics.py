import enum
import functools

import sentry_sdk


class Metrics(enum.Enum):
    # Waiting for DB lock Metrics:
    USER_LOCK_WAIT_TIME = ('db_lock_wait', 'user')

    def __str__(self) -> str:
        metric, labels = self.value
        return f'abc_{metric}__{labels}'


def sentry_transaction(name, predicate=lambda: True):
    """
    Decorator to wrap a function in a Sentry transaction if the predicate is met.

    :param name: The name of the Sentry transaction.
    :param predicate: A boolean or callable that returns a boolean.
                      If True, the transaction is started.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if predicate():
                with sentry_sdk.start_transaction(op='function', name=name):
                    return func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator
