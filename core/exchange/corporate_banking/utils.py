from functools import wraps
from time import time

from exchange.base.logging import log_time, metric_incr


class ObjectBasedMetricMeasurement:
    """
    This class helps monitor another class's methods when the class or the object has an attribute called "metric_name".
    For each method two count and time metrics will be calculated.
    See example for correct naming of the labels and how to use this class.
    Note that the class or the object must define "metric_name" attribute.
    You should define the metrics in exchange/report/views/views.py

    Example:
        >>> class SampleClassToBeMonitored:
        >>>     metric_name: str = 'class_metric_name__'
        >>>
        >>>     @ObjectBasedMetricMeasurement.measure_execution_metrics
        >>>     def some_method_to_be_monitored(self):
        >>>         # Metrics for this method will be:
        >>>         # 'class_metric_name__success' for time metric
        >>>         #  and 'metric_class_metric_name__success' for counter metric
        >>>         return 'normal_result'
        >>>
        >>>     @ObjectBasedMetricMeasurement.measure_execution_metrics
        >>>     def another_method_to_be_monitored(self):
        >>>         # Metrics for this method will be:
        >>>         # 'class_metric_name__aMethodSpecificLabel_success' for time metric
        >>>         #  and 'metric_class_metric_name__aMethodSpecificLabel_success' for counter metric
        >>>         self.metric_name = 'class_metric_name__aMethodSpecificLabel_'
        >>>         return 'normal_result'
        >>>
        >>>     @ObjectBasedMetricMeasurement.measure_execution_metrics
        >>>     def some_method_that_raises_exception(self):
        >>>         # Metrics for this method will be:
        >>>         # 'class_metric_name__anotherMethodName_ValueError' for time metric
        >>>         #  and 'metric_class_metric_name__anotherMethodName_ValueError' for counter metric
        >>>         self.metric_name = 'class_metric_name__anotherMethodName_'
        >>>         raise ValueError('something went wrong')
    """

    @staticmethod
    def measure_execution_metrics(func):
        @wraps(func)
        def inner_decorator(self, *args, **kwargs):
            start_time = time()
            result_label = 'success'
            try:
                result = func(self, *args, **kwargs)
            except Exception as e:
                result_label = getattr(e, 'code', e.__class__.__name__)
                raise
            finally:
                execution_time = time() - start_time
                ObjectBasedMetricMeasurement._submit_metrics(
                    self.metric_name, round(execution_time * 1000), result_label
                )

            return result

        return inner_decorator

    @classmethod
    def _submit_metrics(cls, metric_name, execution_time, result_label):
        metric_name_parts = metric_name.split('__')
        time_metric = f'{metric_name_parts[0]}_time__{metric_name_parts[1]}'
        count_metric = f'{metric_name_parts[0]}_count__{metric_name_parts[1]}'
        log_time(f'{time_metric}{result_label}', execution_time)
        metric_incr(f'metric_{count_metric}{result_label}')

