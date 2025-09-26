import unittest
from time import sleep
from unittest.mock import patch

from django.http import HttpRequest, HttpResponse

from exchange.base.internal.services import Services
from exchange.base.logstash_logging.loggers import logstash_logger


class LogApiDecoratorTestCase(unittest.TestCase):
    def create_mock_request(self, path='/test', method='GET', ip='127.0.0.1'):
        request = HttpRequest()
        request.META['PATH_INFO'] = path
        request.META['REQUEST_METHOD'] = method
        request.META['REMOTE_ADDR'] = ip
        return request

    @patch.object(logstash_logger, 'info')
    def test_log_api_decorator_logs_correctly(self, mock_logstash_logger):
        from exchange.base.api_logger import log_api

        @log_api(is_internal=False)
        def mock_view(request):
            return HttpResponse(status=200)

        request = self.create_mock_request()
        response = mock_view(request)

        assert response.status_code == 200

        mock_logstash_logger.assert_called_once()
        args, kwargs = mock_logstash_logger.call_args

        logged_message = args[0] % args[1:]
        logged_params = kwargs['extra']['params']
        assert logged_message == 'GET /test'
        assert logged_params['method'] == 'GET'
        assert logged_params['src_ip'] == '127.0.0.1'
        assert logged_params['status'] == '200'
        assert logged_params['is_internal'] is False

    @patch.object(logstash_logger, 'info')
    def test_log_api_decorator_with_internal_request(self, mock_logstash_logger):
        from exchange.base.api_logger import log_api

        @log_api(is_internal=True)
        def mock_view(request):
            return HttpResponse(status=200)

        request = self.create_mock_request()
        request.service = Services.ABC.value
        response = mock_view(request)

        assert response.status_code == 200

        mock_logstash_logger.assert_called_once()
        args, kwargs = mock_logstash_logger.call_args

        logged_params = kwargs['extra']['params']
        assert logged_params['src_service'] == ''
        assert logged_params['is_internal'] is True

    @patch.object(logstash_logger, 'info')
    def test_log_api_decorator_logs_process_time(self, mock_logstash_logger):
        from exchange.base.api_logger import log_api

        @log_api(is_internal=False)
        def mock_view(request):
            sleep(0.1)
            return HttpResponse(status=200)

        request = self.create_mock_request()
        response = mock_view(request)

        assert response.status_code == 200

        mock_logstash_logger.assert_called_once()
        args, kwargs = mock_logstash_logger.call_args

        logged_params = kwargs['extra']['params']
        assert logged_params['process_time'] >= 100

