import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.utils.timezone import now

from exchange.accounts.models import User
from exchange.accounts.userstats import UserStatsManager
from exchange.base.models import Currencies
from exchange.wallet.models import Wallet


class UserStatsTest(TestCase):
    """
    Tests for USerStats class.

    Note: Tests for fee-related methods are in TradingFeesTest
    """

    def test_last_activity(self):
        user = User.objects.get(pk=201)
        last_activity = now()
        assert UserStatsManager.get_last_activity(user) < last_activity
        UserStatsManager.update_last_activity(user, last_activity)
        assert UserStatsManager.get_last_activity(user) == last_activity

    def test_is_online(self):
        user = User.objects.get(pk=201)
        UserStatsManager.update_last_activity(user, last_activity=now() - datetime.timedelta(minutes=11))
        assert not user.is_online
        UserStatsManager.update_last_activity(user)
        assert user.is_online

    def test_get_user_total_balance_irr(self):
        user = User.objects.get(pk=201)
        assert UserStatsManager.get_user_total_balance_irr(user) == Decimal('0')
        wallet_rls = Wallet.get_user_wallet(user, Currencies.rls)
        wallet_rls.balance = Decimal('100_000_0')
        wallet_rls.save(update_fields=['balance'])
        assert UserStatsManager.get_user_total_balance_irr(user) == Decimal('100_000_0')
        # Add ETH balance
        wallet_eth = Wallet.get_user_wallet(user, Currencies.eth)
        wallet_eth.balance = Decimal('0.11')
        wallet_eth.save(update_fields=['balance'])
        cache.set('orderbook_ETHIRT_best_buy', Decimal('35_500_200_0'))
        assert UserStatsManager.get_user_total_balance_irr(user) == Decimal('4_005_022_0')
        # Reduce balances
        wallet_rls.balance = Decimal('10_000_0')
        wallet_rls.save(update_fields=['balance'])
        assert UserStatsManager.get_user_total_balance_irr(user) == Decimal('3_915_022_0')
