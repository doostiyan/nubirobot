import time
from collections import defaultdict
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test.utils import override_settings

from exchange.base.decorators import cached_method, measure_consumer_execution, measure_internal_bot_api_execution
from exchange.base.sentry import sentry_transaction_sample_rate, traces_sampler
from exchange.broker.broker.client.consumer import EventConsumer
from exchange.broker.broker.client.testing import mock_consumer_raw_events


class CacheDecoratorTest(TestCase):
    def setUp(self):
        class Sample:
            def __init__(self):
                self.access = 0

            @cached_method
            def heavy_action(self, arg, kwarg=None):
                self.access += 1
                return arg, kwarg

            @cached_method(timeout=0.5)
            def heavy_action_timeout(self, arg):
                self.access += 1
                return arg

        self.sample = Sample()

    def test_cached_method(self):
        assert self.sample.access == 0
        assert self.sample.heavy_action('hello') == ('hello', None)
        assert self.sample.access == 1
        assert self.sample.heavy_action('hello') == ('hello', None)
        assert self.sample.access == 1
        assert self.sample.heavy_action('hello', 5) == ('hello', 5)
        assert self.sample.access == 2
        assert self.sample.heavy_action('hello', 6) == ('hello', 6)
        assert self.sample.access == 3
        assert self.sample.heavy_action('hi', 5) == ('hi', 5)
        assert self.sample.access == 4
        self.sample.heavy_action('hi', kwarg=5)
        assert self.sample.access == 4
        self.sample.heavy_action(arg='hi', kwarg=5)
        assert self.sample.access == 4
        self.sample.heavy_action('hi', 5, skip_cache=True)
        assert self.sample.access == 5

    @pytest.mark.slow
    def test_cached_method_default_timeout(self):
        assert self.sample.access == 0
        self.sample.heavy_action('hello')
        assert self.sample.access == 1
        time.sleep(59)
        self.sample.heavy_action('hello')
        assert self.sample.access == 1
        time.sleep(1)
        self.sample.heavy_action('hello')
        assert self.sample.access == 2

    def test_cached_method_custom_timeout(self):
        assert self.sample.access == 0
        assert self.sample.heavy_action_timeout('hello') == 'hello'
        assert self.sample.access == 1
        assert self.sample.heavy_action_timeout('hello') == 'hello'
        assert self.sample.access == 1
        time.sleep(0.5)
        self.sample.heavy_action_timeout('hello')
        assert self.sample.access == 2


class TestConsumerMetrics:
    @staticmethod
    def get_callback(log_every_seconds=30, sleep_=0):
        @measure_consumer_execution('test_topic', log_every_seconds)
        def callback(msg, ack, e2e_latency):
            time.sleep(sleep_)

        return callback

    @patch.object(cache, 'set')
    @mock_consumer_raw_events(['msg1', 'msg2', 'msg3'])
    def test_consumer_metrics_cache_not_called(self, mock_cache_set: MagicMock):
        mock_cache_set.reset_mock()
        measure_consumer_execution.counter_metrics_store = defaultdict(int)
        measure_consumer_execution.last_commit_time = time.time()

        with EventConsumer({}, 'test') as c:
            c.read_raw_events('test', callback=self.get_callback(30))

        mock_cache_set.assert_not_called()

    @patch.object(cache, 'set')
    @mock_consumer_raw_events(['msg1', 'msg2', 'msg3'], e2e_latency=30)
    def test_consumer_metrics_cache_called(self, mock_cache_set: MagicMock):
        mock_cache_set.reset_mock()
        measure_consumer_execution.counter_metrics_store = defaultdict(int)
        measure_consumer_execution.last_commit_time = time.time()

        with EventConsumer({}, 'test') as c:
            c.read_raw_events('test', callback=self.get_callback(0))

        assert mock_cache_set.call_count == 9
        for i in range(3):
            calls = {call.args[0]: call.args[1] for call in mock_cache_set.call_args_list[i * 3 : (i + 1) * 3]}
            assert calls['metric_consumer_process_count__test_topic'] == 1
            assert calls['time_consumer_process_time__test_topic_avg'] >= 0
            assert calls['time_consumer_e2e_latency__test_topic_avg'] >= 30

    @patch.object(cache, 'set')
    @mock_consumer_raw_events(['msg1', 'msg2', 'msg3'], e2e_latency=30)
    def test_consumer_metrics_cache_called_once(self, mock_cache_set: MagicMock):
        mock_cache_set.reset_mock()
        measure_consumer_execution.counter_metrics_store = defaultdict(int)
        measure_consumer_execution.last_commit_time = time.time()

        with EventConsumer({}, 'test') as c:
            c.read_raw_events('test', callback=self.get_callback(log_every_seconds=0.3, sleep_=0.1))

        assert mock_cache_set.call_count == 3
        calls = {call.args[0]: call.args[1] for call in mock_cache_set.call_args_list}
        assert calls['metric_consumer_process_count__test_topic'] >= 3
        assert calls['time_consumer_process_time__test_topic_avg'] >= 100
        assert calls['time_consumer_e2e_latency__test_topic_avg'] >= 30


class TestMeasureInternalBotAPIExecution(TestCase):
    def setUp(self):
        self.mock_request = MagicMock()
        self.mock_request.META = {'REMOTE_ADDR': '127.0.0.1'}
        self.mock_response = MagicMock()
        self.count_metric = f'metric_api_process_count__testInBotMetric_{settings.SERVER_NAME}_200'
        self.time_metric = f'api_process_time__testInBotMetric_{settings.SERVER_NAME}_200'

        @measure_internal_bot_api_execution(api_label='testInBotMetric', metrics_flush_interval=0)
        def api_function(request):
            time.sleep(0.001)
            return self.mock_response

        self.api_function = api_function

    @patch('exchange.base.decorators.is_internal_ip', return_value=True)
    @patch('exchange.base.decorators.metric_incr')
    @patch('exchange.base.decorators.log_time_without_avg')
    def test_decorator_with_internal_ip(
        self,
        mock_log_time: MagicMock,
        mock_metric_incr: MagicMock,
        mock_is_internal_ip: MagicMock,
    ):
        self.mock_response.status_code = 200
        response = self.api_function(self.mock_request)
        assert response == self.mock_response
        mock_is_internal_ip.assert_called_once_with('127.0.0.1')

        assert mock_metric_incr.call_count == 1
        mock_metric_incr.assert_called_with(self.count_metric, amount=1)
        assert mock_log_time.call_count == 1
        assert mock_log_time.call_args_list[0][0][1] >= 1

    @patch('exchange.base.decorators.is_internal_ip', return_value=False)
    @patch('exchange.base.decorators.metric_incr')
    @patch('exchange.base.decorators.log_time_without_avg')
    def test_decorator_without_internal_ip(self, mock_log_time, mock_metric_incr, mock_is_internal_ip):
        self.mock_response.status_code = 200
        self.api_function(self.mock_request)
        mock_is_internal_ip.assert_called_once_with('127.0.0.1')
        mock_metric_incr.assert_not_called()
        mock_log_time.assert_not_called()


class TestSentryTransactionSampleRateDecorator:
    def test_sentry_transaction_sample_rate(self):
        sentry_transaction_sample_rate.API_MAPPING_TRANSACTION_SAMPLE_RATE_MAPPING = {}

        class MockRequest:
            def __init__(self, path, method='GET'):
                self.path = path
                self.method = method

        @sentry_transaction_sample_rate(rate=0.125)
        def sample_view(request):
            pass

        request = MockRequest(path='/api/test', method='GET')
        sample_view(request)
        assert sentry_transaction_sample_rate.API_MAPPING_TRANSACTION_SAMPLE_RATE_MAPPING[('GET', '/api/test')] == 0.125

    @override_settings(SENTRY_TRACES_SAMPLE_RATE=0.001)
    def test_sentry_traces_sampler(self):
        sentry_transaction_sample_rate.API_MAPPING_TRANSACTION_SAMPLE_RATE_MAPPING[('GET', '/api/test')] = 0.125

        # transaction sample rate is overridden for this view, so the rate should be the value is set by decorator
        sampling_context = {
            'wsgi_environ': {
                'REQUEST_METHOD': 'GET',
                'PATH_INFO': '/api/test',
            }
        }
        sample_rate = traces_sampler(sampling_context)
        assert sample_rate == 0.125

        # transaction sample rate is not overridden for this view, so the sample rate should be default value
        sampling_context = {
            'wsgi_environ': {
                'REQUEST_METHOD': 'POST',
                'PATH_INFO': '/api/test',
            }
        }
        sample_rate = traces_sampler(sampling_context)
        assert sample_rate == settings.SENTRY_TRACES_SAMPLE_RATE

        # not using wsgi, so the sample rate should be default value
        sample_rate = traces_sampler({})
        assert sample_rate == settings.SENTRY_TRACES_SAMPLE_RATE
