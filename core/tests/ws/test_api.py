import json
from unittest.mock import MagicMock, patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from websocket import WebSocketTimeoutException

from exchange.accounts.models import User
from exchange.ws.healthcheck import HealthCheckPublish


class HealthCheckWsPublishTests(APITestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    @override_settings(IS_TESTNET=False, DEBUG=False)
    @patch('exchange.ws.views.healthcheck_publisher')
    def test_auth_failure(self, mock_healthcheck_publisher):
        publish_obj = HealthCheckPublish(channel='public:healthcheck', message={"debug": "heartbeat"})
        mock_healthcheck_publisher.return_value = (True, publish_obj)
        response = self.client.post(
            '/ws/healthcheck/publish', data=json.dumps(publish_obj.message), content_type='application/json'
        )
        response_content = response.json()
        assert response.status_code == 404
        assert response_content['error'] == 'NotFound'

    @override_settings(IS_TESTNET=True)
    @patch('exchange.ws.views.healthcheck_publisher')
    def test_healthcheck_ws_publish_success(self, mock_healthcheck_publisher: MagicMock):
        publish_obj = HealthCheckPublish(channel=f'public:healthcheck{self.user.id}', message={"debug": "heartbeat"})
        mock_healthcheck_publisher.return_value = (True, publish_obj)
        response = self.client.post(
            '/ws/healthcheck/publish', data=json.dumps(publish_obj.message), content_type='application/json'
        )

        mock_healthcheck_publisher.assert_called_once_with(channel_postfix='#201', message={'debug': 'heartbeat'})

        response_content = response.json()
        assert response_content['status'] == 'ok'
        assert response_content['published_message'] == {"debug": "heartbeat"}
        assert response_content['channel'] == f'public:healthcheck{self.user.id}'

    @override_settings(IS_TESTNET=True)
    @patch('exchange.ws.views.healthcheck_publisher')
    def test_healthcheck_ws_publish_failure(self, mock_healthcheck_publisher):
        mock_healthcheck_publisher.return_value = (False, 'Some error')
        response = self.client.post(
            '/ws/healthcheck/publish', data='{"debug": "heartbeat"}', content_type='application/json'
        )
        response_content = response.json()
        assert response_content['status'] == 'failed'
        assert response_content['error'] == 'Some error'


class MockUUID:
    hex = 'random'


class WsStatusTests(APITestCase):

    @patch('exchange.ws.views.healthcheck_publisher')
    @patch('websocket.WebSocket')
    @patch('exchange.ws.views.uuid4', MockUUID)
    def test_ws_status_success(self, mock_websocket, mock_healthcheck_publisher):
        expected_message = {'status': f'expected_message random'}
        mock_healthcheck_publisher.return_value = (
            True,
            HealthCheckPublish(
                channel='public:healthcheck-status-check',
                message=expected_message,
            ),
        )
        mock_ws_instance = mock_websocket.return_value

        messages = [
            json.dumps({'type': 'connected'}),
            json.dumps({'type': 'subscribed'}),
            json.dumps({'push': {'pub': {'data': expected_message}}}),
        ]

        recv_generator = (msg for msg in messages)
        mock_ws_instance.recv.side_effect = lambda: next(recv_generator, '')

        response = self.client.get('/ws/status')
        response_content = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert response_content['status'] == 'ok'

    @patch('websocket.WebSocket')
    def test_ws_status_connection_refused(self, mock_websocket):
        mock_ws_instance = mock_websocket.return_value
        mock_ws_instance.connect.side_effect = ConnectionRefusedError

        response = self.client.get('/ws/status')
        response_content = response.json()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response_content['status'] == 'failed'
        assert 'connection refused' in response_content['error']

    @patch('websocket.WebSocket')
    def test_ws_status_timeout_on_recv(self, mock_websocket):
        mock_ws_instance = mock_websocket.return_value
        mock_ws_instance.recv.side_effect = WebSocketTimeoutException

        response = self.client.get('/ws/status')
        response_content = response.json()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response_content['status'] == 'failed'
        assert 'connection timed out' in response_content['error']

    @patch('exchange.ws.views.uuid4', MockUUID)
    @patch('exchange.ws.views.healthcheck_publisher')
    @patch('websocket.WebSocket')
    def test_ws_status_invalid_push_data(self, mock_websocket, mock_healthcheck_publisher):
        expected_message = {'status': 'expected_message random'}
        mock_healthcheck_publisher.return_value = (
            True,
            HealthCheckPublish(
                channel='public:healthcheck-status-check',
                message=expected_message,
            ),
        )
        mock_ws_instance = mock_websocket.return_value

        messages = [
            json.dumps({'type': 'connected'}),
            json.dumps({'type': 'subscribed'}),
            json.dumps({'push': {'pub': {'data': {'status': 'unexpected_message'}}}}),
        ]

        recv_generator = (msg for msg in messages)
        mock_ws_instance.recv.side_effect = lambda: next(recv_generator, '')

        response = self.client.get('/ws/status')
        response_content = response.json()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response_content['status'] == 'failed'
        assert 'invalid push data' in response_content['error']

    @patch('exchange.ws.views.healthcheck_publisher')
    @patch('websocket.WebSocket')
    def test_ws_status_publish_error(self, mock_websocket, mock_healthcheck_publisher):
        mock_healthcheck_publisher.return_value = (False, 'publish error')
        mock_ws_instance = mock_websocket.return_value

        messages = [
            json.dumps({'type': 'connected'}),
            json.dumps({'type': 'subscribed'}),
        ]

        recv_generator = (msg for msg in messages)
        mock_ws_instance.recv.side_effect = lambda: next(recv_generator, '')

        response = self.client.get('/ws/status')
        response_content = response.json()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response_content['status'] == 'failed'
        assert 'publish error' in response_content['error']
