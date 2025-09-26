from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from sentry_sdk import Hub
from sentry_sdk.tracing import Transaction


class DisableSessionForAPIsMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not request.path.startswith('/bitex/admin') and hasattr(request, 'session'):
            request.session.save = lambda: None


class SentryContextMiddleware(MiddlewareMixin):
    def process_request(self, request):
        sentry_trace = request.headers.get('Sentry-Trace')
        if settings.ENABLE_SENTRY and sentry_trace:
            try:
                trace_id, span_id, sampled = sentry_trace.split('-')
                context = Transaction(trace_id=trace_id, span_id=span_id, parent_sampled=(sampled == '1'))
                Hub.current.start_transaction(context)
            except Exception:
                pass
