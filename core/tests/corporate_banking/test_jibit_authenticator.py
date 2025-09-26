from unittest.mock import patch

import pytest
import requests
import responses
from django.test import TestCase

from exchange.base.models import Settings
from exchange.corporate_banking.exceptions import ThirdPartyAuthenticationException
from exchange.corporate_banking.integrations.jibit.authenticator import CobankJibitAuthenticator


class TestCobankJibitAuthenticator(TestCase):
    def setUp(self):
        self.authenticator = CobankJibitAuthenticator()
        self.jibit_auth_url = 'https://napi.jibit.ir/cobank/v1/tokens/generate'
        self.jibit_refresh_url = 'https://napi.jibit.ir/cobank/v1/tokens/refresh'
        self.sample_successful_jibit_response = {
            'accessToken': '5OGgq1FQS7jPITItICRwlDYZv5P91A',
            'refreshToken': 'upTFapSZfpJISYeo0YsZVjf8X29SBy',
            'scopes': ['ACCOUNTS'],
        }
        self.sample_invalid_scope_jibit_response = {
            'fingerprint': '843070',
            'errors': [{'code': 'invalid.enum.value', 'message': 'Invalid enum value on *Type field.'}],
        }
        self.sample_invalid_client_jibit_response = {
            'fingerprint': '443638',
            'errors': [{'code': 'unauthorized.access', 'message': 'Invalid api/secret key'}],
        }

    @responses.activate
    @patch('exchange.corporate_banking.integrations.jibit.authenticator.Settings.set')
    @patch('exchange.corporate_banking.integrations.jibit.authenticator.Settings.get_value')
    def test_get_auth_token_success(self, mock_settings_get, mock_settings_set):
        responses.add(responses.POST, self.jibit_auth_url, json=self.sample_successful_jibit_response, status=200)

        access_token = self.authenticator.get_auth_token()

        # Verify the call to the Jibit Auth URL actually happened
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == self.jibit_auth_url
        assert access_token == '5OGgq1FQS7jPITItICRwlDYZv5P91A'

        mock_settings_set.assert_any_call('cobank_jibit_access_token', '5OGgq1FQS7jPITItICRwlDYZv5P91A')
        mock_settings_set.assert_any_call('cobank_jibit_refresh_token', 'upTFapSZfpJISYeo0YsZVjf8X29SBy')
        mock_settings_get.assert_not_called()

    @responses.activate
    @patch('exchange.corporate_banking.integrations.jibit.authenticator.Settings.set')
    def test_get_auth_token_timeout(self, mock_settings_set):
        """
        Test get_auth_token if a request timeout occurs:
         - Should re-raise the Timeout exception
        """
        responses.add(responses.POST, self.jibit_auth_url, body=requests.Timeout('Connection timed out'))

        # The code should raise requests.Timeout and schedule a retry
        with self.assertRaises(requests.Timeout):
            self.authenticator.get_auth_token()

        mock_settings_set.assert_not_called()

    @responses.activate
    @patch('exchange.corporate_banking.integrations.jibit.authenticator.Settings.set')
    def test_get_auth_token_error_in_response(self, mock_settings_set):
        """
        Test get_auth_token if an error object is present in the token_response.
        Should raise HTTPError (due to .raise_for_status()) or
        ThordPartyAuthenticationException (depending on code flow).
        """
        for res, code in (
            (self.sample_invalid_scope_jibit_response, 400),
            (self.sample_invalid_client_jibit_response, 401),
        ):
            responses.add(responses.POST, self.jibit_auth_url, json=res, status=code)

            with self.assertRaises(requests.HTTPError):
                self.authenticator.get_auth_token()

            mock_settings_set.assert_not_called()

    @responses.activate
    @patch('exchange.corporate_banking.integrations.jibit.authenticator.Settings.set')
    def test_get_auth_token_error_in_response_with_200_code(self, mock_settings_set):
        """
        Test get_auth_token if an error object is present in the token_response.
        Should raise HTTPError (due to .raise_for_status()) or
        ThordPartyAuthenticationException (depending on code flow).
        """
        for res, code in (
            (self.sample_invalid_scope_jibit_response, 200),
            (self.sample_invalid_client_jibit_response, 200),
        ):
            responses.add(responses.POST, self.jibit_auth_url, json=res, status=code)

            with pytest.raises(ThirdPartyAuthenticationException):
                self.authenticator.get_auth_token()

            mock_settings_set.assert_not_called()

    @responses.activate
    @patch('exchange.corporate_banking.integrations.jibit.authenticator.Settings.set')
    @patch('exchange.corporate_banking.integrations.jibit.authenticator.Settings.get_value')
    def test_refresh_token_success(self, mock_settings_get, mock_settings_set):
        """
        Test refresh_token with a successful response from the server.
         - If refresh token is found in DB (Settings),
         - We call the refresh flow
         - We store new tokens in Settings
         - We schedule refresh again
        """
        # Mock that we have a refresh_token
        mock_settings_get.return_value = 'existing-refresh-token'

        # Register a mock 200 response for the POST request
        responses.add(responses.POST, self.jibit_refresh_url, json=self.sample_successful_jibit_response, status=200)

        self.authenticator.refresh_token()

        # Verify one HTTP call
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == self.jibit_refresh_url

        # Check that new tokens are set
        mock_settings_get.assert_any_call('cobank_jibit_refresh_token')
        mock_settings_get.assert_any_call('cobank_jibit_access_token')
        mock_settings_set.assert_any_call('cobank_jibit_access_token', '5OGgq1FQS7jPITItICRwlDYZv5P91A')
        mock_settings_set.assert_any_call('cobank_jibit_refresh_token', 'upTFapSZfpJISYeo0YsZVjf8X29SBy')

    @responses.activate
    def test_jibit_refresh_token_401(self):
        access_key = 'cobank_jibit_access_token'
        refresh_key = 'cobank_jibit_refresh_token'

        Settings.set(access_key, 'invalid-access-token')
        Settings.set(refresh_key, 'invalid-refresh-token')

        responses.add(responses.POST, self.jibit_auth_url, json=self.sample_successful_jibit_response, status=200)
        responses.add(responses.POST, self.jibit_refresh_url, json={}, status=401)
        responses.post(
            url=self.jibit_refresh_url,
            json=self.sample_successful_jibit_response,
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'accessToken': self.sample_successful_jibit_response['accessToken'],
                        'refreshToken': self.sample_successful_jibit_response['refreshToken'],
                    },
                ),
            ],
        )

        self.authenticator.refresh_token()

        assert len(responses.calls) == 2

        assert Settings.get(access_key) == self.sample_successful_jibit_response['accessToken']
        assert Settings.get(refresh_key) == self.sample_successful_jibit_response['refreshToken']

    @patch('exchange.corporate_banking.integrations.jibit.authenticator.CobankJibitAuthenticator.get_auth_token')
    @patch('exchange.corporate_banking.integrations.jibit.authenticator.Settings.get_value')
    def test_refresh_token_no_existing_refresh_token(self, mock_settings_get, mock_get_auth_token):
        """
        Test refresh_token if no refresh_token is stored:
        - Should call get_auth_token
        - Should not call refresh (since it doesn't have a token to refresh)
        """
        mock_settings_get.return_value = None  # No refresh token in DB

        self.authenticator.refresh_token()

        # Expect the authenticator to fall back to the full auth flow
        mock_get_auth_token.assert_called_once()

    @responses.activate
    def test_send_request_retry_logic(self):
        """
        Test the _send_request method's retry logic when an error occurs and retry > 0.
        We expect it to reattempt the request the specified number of times,
        then succeed or raise after exhausting retries.
        """
        # We'll simulate a 500 error on the first call, then a 200 success on the second.
        responses.add(responses.POST, self.jibit_auth_url, json={'detail': 'Server Error'}, status=500)
        responses.add(responses.POST, self.jibit_auth_url, json={'key': 'value'}, status=200)

        response_data = self.authenticator._send_request(headers={}, payload={}, retry=1)

        # We expect two total calls
        assert len(responses.calls) == 2
        # The final response should be the successful JSON
        assert response_data == {'key': 'value'}

    @responses.activate
    def test_send_request_no_retry_left(self):
        """
        Test _send_request with no retry left. Should raise the exception on failure.
        """
        # A single 500 response; we have retry=0, so it shouldn't retry again.
        responses.add(responses.POST, self.jibit_auth_url, json={'error': 'Some server error'}, status=500)

        with self.assertRaises(requests.HTTPError):
            self.authenticator._send_request({}, {}, retry=0)

        # Only one call is made
        assert len(responses.calls) == 1

    @patch('exchange.corporate_banking.integrations.jibit.authenticator.report_event')
    def test_handle_error_function(self, mock_report_event):
        authenticator = CobankJibitAuthenticator()
        error_code = self.sample_invalid_client_jibit_response.get('errors')[0]['code']
        error_message = self.sample_invalid_client_jibit_response.get('errors')[0]['message']

        with self.assertRaises(ThirdPartyAuthenticationException) as e:
            authenticator.handle_error(self.sample_invalid_client_jibit_response)
            assert e.code == error_code
            assert e.message == error_message

            mock_report_event.assert_called_once_with(
                message='CobankJibitClient_failed_to_get_auth_token',
                extras={
                    'error_code': error_code,
                    'error_message': error_message,
                    'errors': self.sample_invalid_client_jibit_response.get('errors'),
                },
            )
