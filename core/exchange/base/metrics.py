import random
from typing import Callable, Dict, List, Optional, Tuple, Union

from cachetools import TTLCache, cached

from exchange.base.producers import metric_producer
from exchange.broker.broker.schema.metric import MetricSchema
from exchange.broker.broker.topics import Topics
from exchange.report.metrics import COUNTER_METRICS_WITH_LABELS, TIME_METRICS_WITH_LABELS

METRIC_LABEL_MAPPING: Dict[str, List[str]] = {**TIME_METRICS_WITH_LABELS, **COUNTER_METRICS_WITH_LABELS}
HISTOGRAM_BUCKET_MILLISECONDS = [0.1, 1, 2, 5, 10, 20, 50, 75, 100, 250, 500, 750, 1000, 2000, 5000, 10000, 20000]

def broker_on_error(*args, **kwargs):
    from exchange.base.logging import report_exception

    report_exception()


def _send_metric(
    metric: str,
    metric_type: str,
    operation: str,
    value: Union[int, float] = None,
    buckets: Optional[List[Union[float, str]]] = None,
    sample_rate: float = 1,
    sample_func: Optional[Callable[..., float]] = None,
    on_error: Callable[[Exception], None] = broker_on_error,
    **labels,
) -> None:
    """
    Common helper function to send metrics to the metric producer.

    Args:
        metric (str): The metric string.
        metric_type (str): The type of metric ('counter', 'gauge', 'summary', 'histogram').
        operation (str): The operation to perform ('inc', 'set', 'reset').
        value (Union[int, float], optional): The metric value.
        buckets (Optional[List[Union[float, str]]], optional): Histogram buckets.
        sample_rate (float, optional): The sample rate. Defaults to 1.
        sample_func (Optional[Callable[..., float]], optional): Dynamic sample rate function.
        on_error (Callable[[Exception], None], optional): Error handler function.
        **labels: Label key-value pairs.
    """
    if not should_be_sampled(sample_rate, sample_func):
        return

    if metric_type in ['counter', 'gauge'] and metric.startswith('metric_'):
        metric = metric[7:]

    validate_metric(metric, labels)

    if not labels:
        metric, labels = extract_labels_from_metric(metric)

    # Prevent invalid characters in metric key
    metric = metric.replace('.', '_').replace('-', '_').replace('\n', '_')

    metric_data = {
        'type': metric_type,
        'name': metric,
        'labels': labels,
        'operation': operation,
    }

    if value is not None:
        metric_data['value'] = value

    if buckets is not None:
        metric_data['buckets'] = buckets

    _metric = MetricSchema(**metric_data)
    metric_producer.write_event(Topics.METRIC, event=_metric.serialize(), key=metric, on_error=on_error)


def _metric_reset(
    metric: str,
    sample_rate: float = 1,
    sample_func: Optional[Callable[..., float]] = None,
    on_error: Callable[[Exception], None] = broker_on_error,
    **labels,
) -> None:
    """
    Reset a counter metric (Not Recommended!)

    Args:
        metric (str): The metric string. If no explicit labels are provided, it should be in the format
                      'metricName__value1_value2_...'.
        sample_rate (float, optional): The sample rate of the histogram. Defaults to 1.
        sample_func (Optional[Callable[..., float]], optional): A function that dynamically returns sample rate
        on_error (Callable[[Exception], None], optional): A function that handles exceptions raised
        **labels: Arbitrary keyword arguments representing label values.

    Raises:
        ValueError: If both embedded labels in the metric and keyword labels are provided, or if label
                    extraction fails.
    """

    _send_metric(
        metric=metric,
        metric_type='counter',
        operation='reset',
        sample_rate=sample_rate,
        sample_func=sample_func,
        on_error=on_error,
        **labels,
    )

def _metric_incr(
    metric: str,
    amount: int = 1,
    sample_rate: float = 1,
    sample_func: Optional[Callable[..., float]] = None,
    on_error: Callable[[Exception], None] = broker_on_error,
    **labels,
) -> None:
    """
    Increment a counter metric by a specified amount.

    This function validates the metric input and either extracts labels from the metric string
    (if no explicit labels are provided) or uses the provided labels. It then creates a metric
    event of type 'counter' and writes the event via the metric producer.

    Args:
        metric (str): The metric string. If no explicit labels are provided, it should be in the format
                      'metricName__value1_value2_...'.
        amount (int, optional): The increment amount. A negative amount indicates a decrement.
                                Defaults to 1.
        sample_rate (float, optional): The sample rate of the histogram. Defaults to 1.
        sample_func (Optional[Callable[..., float]], optional): A function that dynamically returns sample rate
        on_error (Callable[[Exception], None], optional): A function that handles exceptions raised
        **labels: Arbitrary keyword arguments representing label values.

    Raises:
        ValueError: If both embedded labels in the metric and keyword labels are provided, or if label
                    extraction fails.
    """

    if amount < 1:
        # Return early if the amount is less than 1, as counters only support positive increments.
        return

    _send_metric(
        metric=metric,
        metric_type='counter',
        operation='inc',
        value=amount,
        sample_rate=sample_rate,
        sample_func=sample_func,
        on_error=on_error,
        **labels,
    )

def _gauge_meter(
    metric: str,
    amount: int,
    sample_rate: float = 1,
    sample_func: Optional[Callable[..., float]] = None,
    on_error: Callable[[Exception], None] = broker_on_error,
    **labels,
) -> None:
    """
    Set a gauge metric and sends it to the metric producer.

    Args:
        metric (str): The name of the metric.
        amount (int): The value to set gauge metric.
        on_error (Callable[[Exception], None], optional): A function that handles exceptions raised
        **labels: Additional label key-value pairs for the metric.

    Raises:
        ValueError: If both embedded labels in the metric and keyword labels are provided, or if label
                    extraction fails.
    """

    _send_metric(
        metric=metric,
        metric_type='gauge',
        operation='set',
        value=amount,
        sample_rate=sample_rate,
        sample_func=sample_func,
        on_error=on_error,
        **labels,
    )


def _gauge_meter_incr(
    metric: str,
    amount: int = 1,
    sample_rate: float = 1,
    sample_func: Optional[Callable[..., float]] = None,
    on_error: Callable[[Exception], None] = broker_on_error,
    **labels,
) -> None:
    """
    Increments or decrements a gauge metric and sends it to the metric producer.

    Args:
        metric (str): The name of the metric.
        amount (int, optional): The value to increment (positive) or decrement (negative). Defaults to 1.
        on_error (Callable[[Exception], None], optional): A function that handles exceptions raised
        **labels: Additional label key-value pairs for the metric.

    Raises:
        ValueError: If both embedded labels in the metric and keyword labels are provided, or if label
                    extraction fails.
    """

    if amount == 0:
        # Return early if the amount is zero
        return

    _send_metric(
        metric=metric,
        metric_type='gauge',
        operation='inc',
        value=amount,
        sample_rate=sample_rate,
        sample_func=sample_func,
        on_error=on_error,
        **labels,
    )


def _summary_meter(
    metric: str,
    amount: int = 1,
    sample_rate: float = 1,
    sample_func: Optional[Callable[..., float]] = None,
    on_error: Callable[[Exception], None] = broker_on_error,
    **labels,
):
    """
    Increments or decrements a gauge metric and sends it to the metric producer.

    Args:
        metric (str): The name of the metric.
        amount (int, optional): The value to increment (positive) or decrement (negative). Defaults to 1.
        on_error (Callable[[Exception], None], optional): A function that handles exceptions raised
        **labels: Additional label key-value pairs for the metric.

    Raises:
        ValueError: If both embedded labels in the metric and keyword labels are provided, or if label
                    extraction fails.
    """

    _send_metric(
        metric=metric,
        metric_type='summary',
        operation='set',
        value=amount,
        sample_rate=sample_rate,
        sample_func=sample_func,
        on_error=on_error,
        **labels,
    )


def _log_time(
    metric: str,
    value: Union[int, float] = 1,
    buckets: Optional[List[Union[float, str]]] = None,
    sample_rate: float = 1,
    sample_func: Optional[Callable[..., float]] = None,
    on_error: Callable[[Exception], None] = broker_on_error,
    **labels,
) -> None:
    """
    Record a timing metric (histogram) with an optional set of buckets.

    This function validates the metric input and either extracts labels from the metric string
    (if no explicit labels are provided) or uses the provided labels. It creates a metric event of type
    'histogram' and writes the event via the metric producer.

    Args:
        metric (str): The metric string. If no explicit labels are provided, it should be in the format
                      'metricName__value1_value2_...'.
        value (Union[int, float], optional): The recorded value (e.g., duration or count). Defaults to 1.
        buckets (Optional[List[Union[float, str]]], optional): A list of buckets for the histogram.
                                                               Defaults to None.
                                                               Example: [0.1, 0.5, 1.0, 'Inf'].
        sample_rate (float, optional): The sample rate of the histogram. Defaults to 1.
        sample_func (Optional[Callable[..., float]], optional): A function that dynamically returns sample rate
        on_error (Callable[[Exception], None], optional): A function that handles exceptions raised
        **labels: Arbitrary keyword arguments representing label values.

    Raises:
        ValueError: If both embedded labels in the metric and keyword labels are provided, or if label
                    extraction fails.
    """

    _send_metric(
        metric=metric,
        metric_type='histogram',
        operation='set',
        value=value,
        buckets=buckets,
        sample_rate=sample_rate,
        sample_func=sample_func,
        on_error=on_error,
        **labels,
    )


def get_labels_from_metric(metric: str) -> Tuple[str, Optional[List[str]]]:
    """
    Parse a metric string and extract the metric name and its label values.

    The metric string is expected to contain a double underscore '__' separating the metric name
    and the concatenated label values, which are then split by single underscores '_'.

    Args:
        metric (str): The metric string in the format 'metricName__value1_value2'.

    Returns:
        Tuple[str, List[str]]: A tuple where the first element is the metric name and the second element
        is a list of label values.

    Raises:
        ValueError: If the metric string does not contain the '__' delimiter.
    """

    if '__' not in metric:
        return metric, None

    metric_name, labels = metric.split('__', 1)
    return metric_name, labels.split('_')


def extract_labels_from_metric(metric: str) -> Tuple[str, Optional[dict]]:
    """
    Extract metric labels from a metric string using the global METRIC_LABEL_MAPPING.

    The metric string should be in the format 'metricName__value1_value2_...'. The function
    retrieves the expected label names for the given metric from METRIC_LABEL_MAPPING and zips them
    together with the provided label values.

    Args:
        metric (str): The metric string in the format 'metricName__value1_value2_...'.

    Returns:
        Tuple[str, dict]: A tuple containing the metric name and a dictionary mapping each label name
        to its corresponding value.

    Raises:
        KeyError: If the metric name is not defined in METRIC_LABEL_MAPPING.
        ValueError: If the number of label values does not match the number of expected label names.
    """
    metric, label_values = get_labels_from_metric(metric)
    if label_values is None:
        return metric, None

    try:
        label_names = METRIC_LABEL_MAPPING[metric]
    except KeyError as ex:
        raise KeyError("Metric's labels should be defined in METRIC_LABEL_MAPPING") from ex

    if len(label_names) != len(label_values):
        raise ValueError(f'invalid labels for metric {metric}!')

    labels = dict(zip(label_names, label_values))
    return metric, labels


def validate_metric(metric: str, labels: dict) -> None:
    """
    Validate that the metric string and provided labels do not conflict.

    This function ensures that if explicit label arguments are provided, the metric string
    should not also include embedded label values (i.e. it should not contain the '__' delimiter).

    Args:
        metric (str): The metric name, which may include embedded labels.
        labels (dict): A dictionary of label values provided as keyword arguments.

    Raises:
        ValueError: If both embedded labels in the metric and keyword labels are provided.
    """
    if labels and '__' in metric:
        raise ValueError('Labels should be set only in metric or labels args')


def should_be_sampled(sample_rate: float = 1, sample_func: Optional[Callable[..., float]] = None) -> bool:
    sample_rate = sample_func() if sample_func is not None else sample_rate
    return not (sample_rate != 1 and random.random() >= sample_rate)  # noqa: S311


class MetricHandler:
    """Metrics Backend Handler"""

    _settings_module = None

    @classmethod
    def _get_settings(cls):
        if cls._settings_module is None:
            from exchange.base.models import Settings

            cls._settings_module = Settings
        return cls._settings_module

    @classmethod
    @cached(cache=TTLCache(maxsize=1, ttl=60), key=lambda cls: ('metric_handler_get_value', MetricHandler))
    def get_value(cls):
        return cls._get_settings().get_value('metrics_handler', default='redis')

    @classmethod
    def is_redis(cls):
        return cls.get_value() in ['redis', 'redis_and_kafka']

    @classmethod
    def is_kafka(cls):
        return cls.get_value() in ['kafka', 'redis_and_kafka']
