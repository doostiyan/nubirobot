from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sessions.models import Session
from django.test import RequestFactory, TestCase

from exchange.base.middlewares import DisableSessionForAPIsMiddleware


class DisableSessionForAPIsMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        def get_response(request):
            return None

        self.session_middleware = SessionMiddleware(get_response)
        self.disable_session_middleware = DisableSessionForAPIsMiddleware(get_response)

    def process_request_with_middleware(self, path):
        request = self.factory.get(path)

        self.session_middleware.process_request(request)
        self.disable_session_middleware.process_request(request)

        return request

    def test_session_disabled_for_apis(self):
        request = self.process_request_with_middleware('/api/some-endpoint/')
        request.session.save()
        assert Session.objects.count() == 0

    def test_session_enabled_for_admin(self):
        request = self.process_request_with_middleware('/bitex/admin/')
        request.session.save()
        assert Session.objects.count() == 1
