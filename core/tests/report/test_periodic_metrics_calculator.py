import pytest

from exchange.broker.broker.schema import MetricSchema
from exchange.report.periodic_metrics_calculator import PeriodicMetricsCalculator


class TestPeriodicMetricsCalculator:
    @pytest.fixture
    def calculator(self):
        return PeriodicMetricsCalculator()

    def test_transform_metric_with_labels(self):
        metric = MetricSchema(
            type='gauge',
            name='price',
            operation='set',
            value=123,
            labels={'currency': 'btc', 'exchange': 'binance'},
        )
        result = PeriodicMetricsCalculator.transform_metric(metric)
        assert result == {'price{currency="btc",exchange="binance"}': 123}

    def test_transform_metric_without_labels(self):
        metric = MetricSchema(type='gauge', name='price_usdt_irr', operation='set', value=50000)
        result = PeriodicMetricsCalculator.transform_metric(metric)
        assert result == {'price_usdt_irr': 50000}

    def test_add_metric(self, calculator):
        calculator.add_metric(name='test', type='gauge', value=1, operation='set')
        assert len(calculator._metrics) == 1
        assert calculator._metrics[0].name == 'test'

    def test_is_module_selected_all_selected(self, calculator):
        calculator.selected_modules = None
        assert calculator.is_module_selected('marketPrices') is True

    def test_is_module_selected_with_list(self, calculator):
        calculator.selected_modules = ['emails', 'marketPrices']
        assert calculator.is_module_selected('emails') is True
        assert calculator.is_module_selected('celery') is False

    def test_celery_queues_list(self, calculator):
        assert {'celery', 'telegram', 'telegram_admin', 'notif'}.issubset(calculator.CELERY_QUEUES)
