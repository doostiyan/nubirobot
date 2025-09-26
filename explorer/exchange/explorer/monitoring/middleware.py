from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django_prometheus.middleware import Metrics
from django_prometheus.utils import PowersOf, Time, TimeSince
from prometheus_client import Counter, Histogram

from exchange.explorer.utils.prometheus import labelnames, get_request_info


class ExplorerMetrics(Metrics):
    _instance = None

    def register(self):
        self.requests_latency_by_app_view_method_network_provider = self.register_metric(
            Histogram,
            "explorer_http_requests_latency_seconds_by_app_view_method_network_provider",
            "Histogram of request processing time.",
            labelnames=labelnames,
            buckets=settings.PROMETHEUS_LATENCY_BUCKETS,
        )

        # Set in process_response
        self.responses_by_status_app_view_method_network_provider = self.register_metric(
            Counter,
            "explorer_http_responses_by_status_app_view_method_network_provider",
            "Count of responses.",
            labelnames=labelnames + ['status'],
        )
        self.responses_body_bytes_by_app_view_method_network_provider = self.register_metric(
            Histogram,
            "explorer_http_responses_body_bytes_by_app_view_method_network_provider",
            "Histogram of responses by body size.",
            labelnames=labelnames,
            buckets=PowersOf(2, 30),
        )


class ExplorerPrometheusAfterMiddleware(MiddlewareMixin):
    metrics_cls = ExplorerMetrics

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics = self.metrics_cls.get_instance()

    def _method(self, request):
        m = request.method
        if m not in (
                "GET",
                "HEAD",
                "POST",
                "PUT",
                "DELETE",
                "TRACE",
                "OPTIONS",
                "CONNECT",
                "PATCH",
        ):
            return "<invalid method>"
        return m

    def label_metric(self, metric, request, response=None, **labels):
        return metric.labels(**labels) if labels else metric

    def process_request(self, request):
        request.prometheus_after_middleware_event = Time()

    def process_response(self, request, response):
        labels = get_request_info(request)
        status = str(response.status_code)
        self.label_metric(self.metrics.responses_by_status_app_view_method_network_provider, request, response,
                          status=status, **labels).inc()

        if hasattr(response, "content"):
            self.label_metric(
                self.metrics.responses_body_bytes_by_app_view_method_network_provider, request, response,
                **labels).observe(len(response.content))
        if hasattr(request, "prometheus_after_middleware_event"):
            self.label_metric(
                self.metrics.requests_latency_by_app_view_method_network_provider, request, response, **labels).observe(
                TimeSince(request.prometheus_after_middleware_event))

        return response
