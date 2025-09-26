from decimal import Decimal
from time import time
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from rest_framework.test import APITestCase

from exchange.broker.broker.client.health_check import HealthStatus


class BaseViewsTest(APITestCase):
    def setUp(self):
        cache.set('market_4_last_price', Decimal(60_000_0))
        cache.set('current_time', time() * 1000)

    @patch('exchange.base.views.check_kafka_health')
    def test_check_health(self, mock_check_kafka_health: MagicMock):
        mock_check_kafka_health.return_value = HealthStatus(
            is_producer_healthy=True,
            is_consumer_healthy=True,
            e2e_latency=100,
        )

        response = self.client.post('/check/health')
        assert response.status_code == 200
        status = response.json()
        assert status['status'] == 'ok'
        assert status['health'] == 'ok'
        assert status['db'] == 'ok'
        assert status['cache'] == 'ok'
        assert status['kafka'] == 'ok'
        assert status['kafkaLatency'] == '100'

    @patch('exchange.base.views.check_kafka_health')
    def test_check_health_kafka_failed(self, mock_check_kafka_health: MagicMock):
        mock_check_kafka_health.return_value = HealthStatus(
            is_producer_healthy=True,
            is_consumer_healthy=True,
            e2e_latency=2000,
        )
        response = self.client.post('/check/health')
        status = response.json()
        assert status['health'] == 'degraded'
        assert status['kafka'] == 'degraded'
        assert status['kafkaLatency'] == '2000'

        mock_check_kafka_health.return_value = HealthStatus(
            is_producer_healthy=True,
            is_consumer_healthy=False,
        )
        response = self.client.post('/check/health')
        status = response.json()
        assert status['health'] == 'degraded'
        assert status['kafka'] == 'consumerFailed'
        assert status['kafkaLatency'] is None

        mock_check_kafka_health.return_value = HealthStatus(
            is_producer_healthy=False,
            is_consumer_healthy=False,
        )
        response = self.client.post('/check/health')
        status = response.json()
        assert status['health'] == 'degraded'
        assert status['kafka'] == 'failed'
        assert status['kafkaLatency'] is None
