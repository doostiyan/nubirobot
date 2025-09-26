import contextlib
from unittest import mock

from django.test.testcases import TestCase

from exchange.web_engage.externals.web_engage import web_engage_event_api


class WebEngageCallTest(TestCase):

    @mock.patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=False)
    @mock.patch('exchange.web_engage.externals.web_engage.requests.post')
    def test_webengage_conditional_call_must_not_call(self, mock_post, mock_condition):
        web_engage_event_api.send(dict())
        mock_post.assert_not_called()

    @mock.patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=True)
    @mock.patch('exchange.web_engage.externals.web_engage.requests.post')
    def test_webengage_conditional_call_must_call_success(self, mock_post, mock_condition):
        with contextlib.suppress(TypeError):
            web_engage_event_api.send(dict())
        mock_post.assert_called_once()
