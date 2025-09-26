from unittest import TestCase
from unittest.mock import MagicMock, patch

import requests

from exchange.integrations.finnotech import (
    FINNOTECH_API_ACCESS_TOKEN_KEY,
    FINNOTECH_API_REFRESH_TOKEN_KEY,
    FinnotechTokenAPI,
)


class TestFinnotechGetTokenService(TestCase):
    @patch('exchange.integrations.finnotech.Settings.set')
    @patch('exchange.integrations.finnotech.requests.post')
    def test_get_token_success(self, mock_post, mock_settings_set):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'DONE',
            'result': {'value': 'mock_access_token', 'refreshToken': 'mock_refresh_token'},
        }
        mock_post.return_value = mock_response

        result = FinnotechTokenAPI.get_token()

        assert result['result']
        assert result['accesstoken'] == 'mock_access_token'
        assert result['refreshtoken'] == 'mock_refresh_token'

        mock_settings_set.assert_any_call(FINNOTECH_API_ACCESS_TOKEN_KEY, 'mock_access_token')
        mock_settings_set.assert_any_call(FINNOTECH_API_REFRESH_TOKEN_KEY, 'mock_refresh_token')

    @patch('exchange.integrations.finnotech.Settings.set')
    @patch('exchange.integrations.finnotech.requests.post')
    def test_get_token_api_error(self, mock_post, mock_settings_set):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {'status': 'FAILED', 'error': 'Some error message'}
        mock_post.return_value = mock_response

        result = FinnotechTokenAPI.get_token()
        assert not result['result']
        mock_settings_set.assert_not_called()

    @patch('exchange.integrations.finnotech.Settings.set')
    @patch('exchange.integrations.finnotech.requests.post')
    def test_get_token_request_exception(self, mock_post, mock_settings_set):
        mock_post.side_effect = requests.exceptions.RequestException()

        result = FinnotechTokenAPI.get_token()

        assert not result['result']
        mock_settings_set.assert_not_called()

    @patch('exchange.integrations.finnotech.Settings.set')
    @patch('exchange.integrations.finnotech.requests.post')
    def test_get_token_missing_tokens(self, mock_post, mock_settings_set):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'DONE', 'result': {'value': None, 'refreshToken': None}}
        mock_post.return_value = mock_response
        result = FinnotechTokenAPI.get_token()

        assert not result['result']
        mock_settings_set.assert_not_called()
