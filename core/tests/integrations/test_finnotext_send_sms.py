from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import MagicMock, patch

from exchange.integrations.errors import APICallException
from exchange.integrations.finnotext import FinnotextSMSService


class TestFinnotextSendSmsService(TestCase):
    @staticmethod
    @contextmanager
    def does_not_raise_error():
        yield

    @patch('exchange.integrations.finnotext.settings.IS_PROD', True)
    @patch('exchange.integrations.finnotext.get_finnotech_access_token')
    @patch('exchange.integrations.finnotext.requests.post')
    def test_send_sms_with_duplicated_track_id_success(self, mock_post, mock_token):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'responseCode': 'FN-BRFH-40001210001',
            'trackId': '16385572-6dc8-4d37-ab20-b170014781c6',
            'status': 'FAILED',
            'error': {'code': 'VALIDATION_ERROR', 'message': 'trackId is duplicated'},
        }
        mock_post.return_value = mock_response
        mock_token.return_value = 'sample-token'

        body = ['Hello']
        phone_numbers = ['09123456789']
        track_id = 'sample-track-id'
        from_number = '3000125'

        result = FinnotextSMSService.send_sms(body, phone_numbers, track_id, from_number)
        assert result is None

    @patch('exchange.integrations.finnotext.settings.IS_PROD', True)
    @patch('exchange.integrations.finnotext.get_finnotech_access_token')
    @patch('exchange.integrations.finnotext.requests.post')
    def test_send_sms_with_timeout_error_failed(self, mock_post, mock_token):
        # given->
        mock_response = MagicMock()
        mock_response.status_code = 408
        mock_response.json.return_value = {
            'responseCode': 'FN-BRFH-40801210008',
            'trackId': '16385572-6dc8-4d37-ab20-b170014781c6',
            'status': 'FAILED',
            'error': {'code': 'REQUEST_TIME_OUT', 'message': 'timeout of 40000ms exceeded'},
        }
        mock_post.return_value = mock_response
        mock_token.return_value = 'sample-token'

        body = ['Hello']
        phone_numbers = ['09123456789']
        track_id = 'sample-track-id'
        from_number = '3000125'

        # when->
        with self.assertRaises(APICallException) as context:
            FinnotextSMSService.send_sms(body, phone_numbers, track_id, from_number)

        # then->
        assert context.exception.status_code == 408
