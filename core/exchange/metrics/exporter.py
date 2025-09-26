from django.core.cache import cache
from django.utils.functional import cached_property


class MetricManager:
    metrics = set()

    @classmethod
    def register(cls, metric):
        cls.metrics.add(metric)


def _metric_method(func):
    def wrapper(*args, **kwargs):
        self = args[0]
        self._add
        return  func(*args, **kwargs)
    return wrapper


class Metric:
    """
    Parent class for different type of metrics.
    """

    def __init__(self, app: str, name: str, description: str, metric_type: str, labels: list = None):
        self.name = app + '_' + name
        self.description = description
        self.type = metric_type
        self.labels = labels
        MetricManager.register(self)

    @property
    def cache_key(self):
        return f'metric_{self.name}'

    @_metric_method
    def get_value(self):
        return cache.get(self.cache_key)

    @cached_property
    def _add(self):
        if cache.get(self.cache_key) is None:
            cache.set(self.cache_key, 0)

    def remove(self):
        cache.delete(self.cache_key)


class Counter(Metric):
    def __init__(self, app: str, name: str, description: str):
        super().__init__(app, name, description, 'counter', None)

    @_metric_method
    def inc(self, amount: int = 1):
        if amount < 0:
            raise ValueError
        cache.incr(self.cache_key, amount)


class Gauge(Metric):
    def __init__(self, app: str, name: str, description: str):
        super().__init__(app, name, description, 'gauge', None)

    @_metric_method
    def set(self, amount: int):
        cache.incr(self.cache_key, amount)


class Summary(Metric):
    def __init__(self, app: str, name: str, description: str, labels: list = None):
        self.counts = {label: 0 for label in labels}
        super().__init__(app, name, description, 'summary', labels)

    @_metric_method
    def observe(self, amount: int, label: str = None):
        pass


class Histogram(Metric):
    def __init__(self, app: str, name: str, description: str, labels: list = None):
        self.counts = {label: 0 for label in labels}
        super().__init__(app, name, description, 'histogram', labels)

    @_metric_method
    def observe(self, amount: int, label: str = None):
        pass
