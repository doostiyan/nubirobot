import functools
import traceback

from ..logging import get_logger


def catch_all_exceptions(log_level='error'):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger = get_logger('local')
                log_method = getattr(logger, log_level)
                log_method("func={} args={} kwargs={} message={} traceback={}".format(func,
                                                                                      args,
                                                                                      kwargs,
                                                                                      e,
                                                                                      traceback.format_exc()
                                                                                      if log_level == 'error' else ''))

        return wrapper

    return decorator
