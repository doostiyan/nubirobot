from unittest.mock import patch

import pytest

from exchange.corporate_banking.utils import (
    ObjectBasedMetricMeasurement,
)


class SampleClassToBeMonitored:
    metric_name: str = 'class_metric_name__'

    @ObjectBasedMetricMeasurement.measure_execution_metrics
    def some_method_to_be_monitored(self):
        # Metrics for this method will be:
        # 'class_metric_name__success' for time metric
        #  and 'metric_class_metric_name__success' for counter metric
        return 'normal_result'

    @ObjectBasedMetricMeasurement.measure_execution_metrics
    def another_method_to_be_monitored(self):
        # Metrics for this method will be:
        # 'class_metric_name__aMethodSpecificLabel_success' for time metric
        #  and 'metric_class_metric_name__aMethodSpecificLabel_success' for counter metric
        self.metric_name = 'class_metric_name__aMethodSpecificLabel_'
        return 'normal_result'

    @ObjectBasedMetricMeasurement.measure_execution_metrics
    def some_method_that_raises_exception(self):
        # Metrics for this method will be:
        # 'class_metric_name__anotherMethodName_ValueError' for time metric
        #  and 'metric_class_metric_name__anotherMethodName_ValueError' for counter metric
        self.metric_name = 'class_metric_name__anotherMethodName_'
        raise ValueError('something went wrong')


class TestMeasureExecutionMetrics:
    def setup_method(self):
        # Create a client instance for each test
        self.client = SampleClassToBeMonitored()

    @patch('exchange.corporate_banking.utils.log_time')
    @patch('exchange.corporate_banking.utils.metric_incr')
    def test_success_scenario(self, mock_metric_incr, mock_log_time):
        """
        Test that when the method returns normally,
        the metrics are logged with a 'success' label.
        """
        result = self.client.some_method_to_be_monitored()

        assert result == 'normal_result'
        assert mock_log_time.call_count == 1
        assert mock_metric_incr.call_count == 1

        # Validate the arguments passed to log_time
        (log_time_metric_label, log_time_execution_time), _ = mock_log_time.call_args
        assert log_time_metric_label == 'class_metric_name_time__success'
        assert isinstance(log_time_execution_time, int)

        # Validate the arguments passed to metric_incr
        (metric_incr_name,), _ = mock_metric_incr.call_args
        assert metric_incr_name == 'metric_class_metric_name_count__success'

    @patch('exchange.corporate_banking.utils.log_time')
    @patch('exchange.corporate_banking.utils.metric_incr')
    def test_success_scenario_with_a_method_specific_metric_name(self, mock_metric_incr, mock_log_time):
        """
        Test that when the method returns normally,
        the metrics are logged with a 'success' label.
        """
        result = self.client.another_method_to_be_monitored()

        assert result == 'normal_result'
        assert mock_log_time.call_count == 1
        assert mock_metric_incr.call_count == 1

        # Validate the arguments passed to log_time
        (log_time_metric_label, log_time_execution_time), _ = mock_log_time.call_args
        assert log_time_metric_label == 'class_metric_name_time__aMethodSpecificLabel_success'
        assert isinstance(log_time_execution_time, int)

        # Validate the arguments passed to metric_incr
        (metric_incr_name,), _ = mock_metric_incr.call_args
        assert metric_incr_name == 'metric_class_metric_name_count__aMethodSpecificLabel_success'

    @patch('exchange.corporate_banking.utils.log_time')
    @patch('exchange.corporate_banking.utils.metric_incr')
    def test_exception_scenario(self, mock_metric_incr, mock_log_time):
        """
        Test that when the method raises an exception,
        the metrics are logged with the exception's class name as the label,
        and the exception is re-raised.
        """
        with pytest.raises(ValueError) as exc_info:
            self.client.some_method_that_raises_exception()

        assert 'something went wrong' in str(exc_info.value)

        assert mock_log_time.call_count == 1
        assert mock_metric_incr.call_count == 1

        # Validate the arguments passed to log_time
        (log_time_metric_label, log_time_execution_time), _ = mock_log_time.call_args
        assert log_time_metric_label == 'class_metric_name_time__anotherMethodName_ValueError'
        assert isinstance(log_time_execution_time, int)

        # Validate the arguments passed to metric_incr
        (metric_incr_name,), _ = mock_metric_incr.call_args
        assert metric_incr_name == 'metric_class_metric_name_count__anotherMethodName_ValueError'

