import functools
import time
import prometheus_client

from prometheus_client import Counter
from prometheus_client import Histogram

from exchange.blockchain.apis_conf import APIS_CONF, APIS_CLASSES
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.explorer.networkproviders.models import Operation
from exchange.explorer.utils.blockchain import is_network_ready
from exchange.settings.prometheus import PROMETHEUS_LATENCY_BUCKETS

prometheus_client.REGISTRY.unregister(prometheus_client.PROCESS_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)

labelnames = ['app', 'view', 'method', 'network', 'provider']

exceptions_counter = Counter(
    'explorer_exceptions_by_{}_type'.format('_'.join(labelnames)),
    'Total number of django exceptions',
    labelnames + ['type'],
)

RESPONSE_TIME = Histogram('explorer_http_response_time_seconds_by_{}'.format('_'.join(labelnames)),
                          'Histogram of response time',
                          buckets=PROMETHEUS_LATENCY_BUCKETS,
                          labelnames=labelnames)


def histogram_observer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        request = args[1]
        labels = get_request_info(request)
        start_time = time.time()
        result = func(*args, **kwargs)
        response_time = time.time() - start_time
        RESPONSE_TIME.labels(**labels).observe(
            response_time)
        return result

    return wrapper


def get_request_info(request):
    app = view = network = provider = None
    if hasattr(request, "resolver_match"):
        if request.resolver_match is not None:
            app = request.resolver_match.app_name
            view = request.resolver_match.view_name
            network = request.resolver_match.kwargs.get('network', '').upper()
    method = request.method
    return dict(app=app, view=view, method=method, network=network, provider=None)
