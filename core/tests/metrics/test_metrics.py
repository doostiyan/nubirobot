from django.test import TestCase, override_settings

from exchange.accounts.models import User
from exchange.metrics.exporter import Counter, Gauge


@override_settings(MONITORING_USERNAME='user', MONITORING_PASSWORD='pass')  # noqa: S106
class TestMetrics(TestCase):
    def setUp(self) -> None:
        self.counter_metric_args = ['accounts', 'successful_login', 'counter for successful logins']
        self.counter_metric = Counter(*self.counter_metric_args)
        self.gauge_metric = Gauge('accounts', 'unsuccessful_login', 'counter for unsuccessful logins')

    def test_counter_metric(self):
        assert self.counter_metric.get_value() == 0
        self.counter_metric.inc()
        assert self.counter_metric.get_value() == 1
        self.counter_metric.inc(10)
        assert self.counter_metric.get_value() == 11
        metric = Counter(*self.counter_metric_args)
        assert metric.get_value() == 11

    def test_gauge_metric(self):
        assert self.gauge_metric.get_value() == 0
        self.gauge_metric.set(10)
        assert self.gauge_metric.get_value() == 10

    def test_monitoring_view_and_authentication(self):
        response = self.client.get('/bitex/prometheus')
        assert response.status_code == 404
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Basic dXNlcjpwYXNz'
        response = self.client.get('/bitex/prometheus')
        assert response.status_code == 200
        assert b'HELP' in response.content

    def get_metrics_from_response(self, response):
        assert response.status_code == 200
        return [line.strip() for line in response.content.decode('utf8').split('\n')]

    def test_nobitex_metrics(self):
        response = self.client.get('/bitex/metrics')
        assert response.status_code == 404
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Basic dXNlcjpwYXNz'
        # we are not testings timings,counters,blockchain modules because test runners cache does not support keys()
        response = self.client.get('/bitex/metrics?modules=userLevels,importantPrices,emails,celery,marketPrices')
        metrics = self.get_metrics_from_response(response)
        assert f'nobitex_registered_users_count {User.objects.count()}' in metrics
