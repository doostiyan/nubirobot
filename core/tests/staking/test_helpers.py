from decimal import Decimal

import pytest
from django.test import TestCase, override_settings

from exchange.accounts.models import User
from exchange.config.config.models import Currencies
from exchange.staking.errors import InsufficientWalletBalance
from exchange.staking.helpers import check_wallet_balance, env_aware_ratelimit
from exchange.wallet.models import Wallet


class SystemUsersLoginTest(TestCase):
    """As users with the usersname 'system-staking' and 'system-staking-rewards' are meant to be used
        by their user panel (hence they cannot be defined in a fixture), we have to make sure that their
        primary keys aren't re-assigned in any fixture.
    """

    def test_staking_user(self):
        assert User.objects.filter(pk=995).first() is None

    def test_staking_rewards_user(self):
        assert User.objects.filter(pk=993).first() is None


class CheckWalletBalanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.first()
        self.wallet = Wallet.get_user_wallet(user=self.user, currency=Currencies.usdt)
        self.wallet.balance = 10
        self.wallet.save(update_fields=['balance'])

    def test_when_user_has_balance_then_no_error_is_raised(self):
        check_wallet_balance(self.user.id, Currencies.usdt, Decimal('10'))

    def test_when_user_has_low_balance_then_insufficient_balance_error_is_raised(self):
        with pytest.raises(InsufficientWalletBalance):
            check_wallet_balance(self.user.id, Currencies.usdt, Decimal('10.1'))

    def test_when_user_no_wallet_instance_then_insufficient_balance_error_is_raised(self):
        assert Wallet.get_user_wallet(user=self.user.id, currency=Currencies.xrp, create=False) is None
        with pytest.raises(InsufficientWalletBalance):
            check_wallet_balance(self.user.id, Currencies.xrp, Decimal('7.1'))


class EnvAwareRateLimitTests(TestCase):
    @override_settings(IS_TESTNET=True)
    def test_when_environment_is_testnet_then_default_testnet_ratelimit_is_returned(self):
        assert env_aware_ratelimit('123/4s') == '150/1m'

    @override_settings(IS_TESTNET=False)
    def test_when_environment_is_not_testnet_then_input_limit_is_returned(self):
        assert env_aware_ratelimit('5/1m') == '5/1m'
