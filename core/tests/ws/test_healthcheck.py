import json
from unittest.mock import patch

from django.test import TestCase

from exchange.ws.healthcheck import HealthCheckPublish, healthcheck_publisher


class HealthCheckPublisherTests(TestCase):

    @patch('redis.Redis.from_url')
    def test_healthcheck_publisher_success(self, mock_redis_from_url):
        mock_redis_instance = mock_redis_from_url.return_value
        mock_redis_instance.publish.return_value = 1

        is_ok, data = healthcheck_publisher()
        assert is_ok is True
        assert isinstance(data, HealthCheckPublish)
        assert data.channel == 'public:healthcheck'
        assert data.message == {'debug': 'heartbeat'}

        mock_redis_instance.publish.assert_called_with(
            channel='public:healthcheck',
            message=json.dumps({'debug': 'heartbeat'}),
        )

    @patch('redis.Redis.from_url')
    def test_healthcheck_publisher_custom_message(self, mock_redis_from_url):
        mock_redis_instance = mock_redis_from_url.return_value
        mock_redis_instance.publish.return_value = 1

        custom_message = {'test': 'message'}

        is_ok, data = healthcheck_publisher(channel_postfix='-test', message=custom_message)
        assert is_ok is True
        assert isinstance(data, HealthCheckPublish)
        assert data.channel == 'public:healthcheck-test'
        assert data.message == custom_message

        mock_redis_instance.publish.assert_called_with(
            channel='public:healthcheck-test',
            message=json.dumps(custom_message),
        )

    @patch('redis.Redis.from_url')
    def test_healthcheck_publisher_exception(self, mock_redis_from_url):
        mock_redis_instance = mock_redis_from_url.return_value
        mock_redis_instance.publish.side_effect = Exception('Redis error')

        is_ok, data = healthcheck_publisher()
        assert is_ok is False
        assert data == 'Redis error'
