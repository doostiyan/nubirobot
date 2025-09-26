import sys
import traceback


def handle_exception(function=None):
    def decorator(func):
        def _wrapped(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as error:
                traceback.print_exception(*sys.exc_info())
        return _wrapped
    if function:
        return decorator(function)
    return decorator
