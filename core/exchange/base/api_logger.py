import contextlib
from functools import wraps
from time import time

import jwt
from django.http import HttpRequest, HttpResponse
from ipware import get_client_ip
from rest_framework.authentication import get_authorization_header
from rest_framework.request import Request

from exchange.base.logging import report_exception
from exchange.base.logstash_logging.loggers import logstash_logger


def log_api(*, is_internal=False):
    """
    Decorator to log API requests and responses.

    This decorator wraps a view function to log details about incoming API requests and responses,
    including the request path, method, source IP, processing time, and response status. The log is
    sent to a message broker using the `log_to_broker` function.

    This decorator will inject api_log into the request object, so you can add thing into extras in the body of api.

    NOTE: Put it ABOVE all other decorators (except @wraps)

    Example:
        @log_api(is_internal=True)
        @api_view
        def my_view_function(request):
            ...
    """

    def outer_wrapper(f):
        @wraps(f)
        def inner_wrapper(*args, **kwargs):
            request = args[0] if isinstance(args[0], (HttpRequest, Request)) else args[1]

            path = request.META['PATH_INFO']
            method = request.META['REQUEST_METHOD']
            ip = get_client_ip(request)[0]
            log = dict(
                path=path,
                method=method,
                src_ip=ip,
                status='404',
                is_internal=is_internal,
                extras={},
                src_service='',
            )
            start_time = time()
            request.api_log = log

            response: HttpResponse = f(*args, **kwargs)

            log['process_time'] = round((time() - start_time) * 1000)
            log['status'] = str(response.status_code)

            with contextlib.suppress(Exception):
                log['src_service'] = jwt.decode(
                    get_authorization_header(request).split()[1].decode(),
                    options={'verify_signature': False},
                )['service']

            try:
                logstash_logger.info('%s %s', method, path, extra={'params': log, 'index_name': 'api_logger'})
            except:  # noqa: BLE001
                report_exception()

            return response

        return inner_wrapper

    return outer_wrapper
