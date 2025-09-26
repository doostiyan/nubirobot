import unittest
from unittest.mock import patch

from django.core.cache import cache
from requests import ConnectTimeout

from exchange.base.helpers import deterministic_hash
from exchange.staking.admin_notifier import notify_or_raise_exception
from exchange.staking.errors import CallSupport


class NotifyOrRaiseExceptionTest(unittest.TestCase):
    def setUp(self):
        self.suspicion_exception = ConnectTimeout()
        self.suspicion_exception_cache_key = (
            f'staking_suspicious_exception_{deterministic_hash(str(self.suspicion_exception))}'
        )

    def test_with_exception_that_might_be_a_system_fail(self):
        notify_or_raise_exception(self.suspicion_exception)

        assert cache.get(self.suspicion_exception_cache_key) == 1

    @patch('django.core.cache.cache.set')
    def test_with_exception_that_has_a_cache_but_the_cache_expires_when_gets_cache(self, *_):
        notify_or_raise_exception(ConnectTimeout())

        assert cache.get(self.suspicion_exception_cache_key) is None

    @patch('exchange.accounts.models.Notification.notify_admins')
    def test_that_special_exceptions_notifies_admins(self, mock_notify_admins):
        exception = CallSupport(message='test message')
        notify_or_raise_exception(exception)

        mock_notify_admins.assert_called_once()
