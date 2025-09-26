from unittest.mock import patch

from django.core.cache import cache

from exchange.base.logging import log_time
from exchange.base.metrics import HISTOGRAM_BUCKET_MILLISECONDS, MetricHandler


def test_log_time_with_redis_metric_handler():
    log_time('test1', 150)
    assert cache.get('time_test1_avg') == 150
    log_time('test1', 200)
    assert cache.get('time_test1_avg') == 190
    log_time('test1', 180)
    assert cache.get('time_test1_avg') == 190  # 182 is ignored as similar value
    log_time('test1', 170)
    assert cache.get('time_test1_avg') == 174
    cache.delete('time_test1_avg')


@patch.object(MetricHandler, 'is_redis', return_value=False)
@patch.object(MetricHandler, 'is_kafka', return_value=True)
@patch('exchange.base.logging._log_time')
def test_log_time_with_kafka_metric_handler(mock_kafka_log_time, *mocks):
    log_time('test1', 150, ('lv1', 'lv2'))
    mock_kafka_log_time.assert_called_with('test1__lv1_lv2', 150, buckets=HISTOGRAM_BUCKET_MILLISECONDS)


@patch.object(MetricHandler, 'is_redis', return_value=True)
@patch.object(MetricHandler, 'is_kafka', return_value=True)
@patch('exchange.base.logging._log_time')
def test_log_time_with_both_redis_and_kafka_metric_handlers(mock_kafka_log_time, *mocks):
    log_time('test1', 150)
    assert cache.get('time_test1_avg') == 150
    mock_kafka_log_time.assert_called_with('test1', 150, buckets=HISTOGRAM_BUCKET_MILLISECONDS)
    cache.delete('time_test1_avg')
