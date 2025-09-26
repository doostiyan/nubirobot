from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings

from exchange.accounts.models import User
from exchange.accounts.serializers import serialize_user
from exchange.accounts.userstats import UserStatsManager
from exchange.base.serializers import serialize
from exchange.market.constants import SYSTEM_USERS_VIP_LEVEL
from exchange.market.models import UserTradeStatus
from exchange.security.models import LoginAttempt

USER_ID = 1001

class TradingFeesTest(TestCase):
    def setUp(self):
        self.user, _ = User.objects.get_or_create(pk=USER_ID)
        self.user.email = f'test_{USER_ID}@nobitex.ir'
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)

    def tearDown(self):
        cache.clear()

    def set_user_trade_volume(self, user, volume, trader_volume=None):
        try:
            u = UserTradeStatus.objects.get(user=user)
        except UserTradeStatus.DoesNotExist:
            u = UserTradeStatus(user=user)
        u.month_trades_total = Decimal(volume)
        u.month_trades_total_trader = Decimal(trader_volume or '0')
        u.save()

    def test_vip_level(self):
        status = UserTradeStatus()
        # Some special cases first
        assert status.vip_level == 0
        status.month_trades_total = Decimal('0')
        assert status.vip_level == 0
        status.month_trades_total = Decimal('-1_000_000_0')
        assert status.vip_level == 0
        # Low volumes check
        status.month_trades_total = Decimal('60_000_000_0')
        assert status.vip_level == 0
        status.month_trades_total = Decimal('100_000_000_0')
        assert status.vip_level == 1
        status.month_trades_total_trader = Decimal('10_000_000_0')
        assert status.vip_level == 1
        status.month_trades_total = Decimal('110_000_000_0')
        assert status.vip_level == 1
        status.month_trades_total_trader = Decimal('0')
        assert status.vip_level == 1
        # More checks for each level
        for volume, level in [
            ['299_000_000_0', 1],
            ['300_000_000_0', 2],
            ['500_000_000_0', 2],
            ['999_999_999_9', 2],
            ['1_000_000_000_0', 3],
            ['4_000_000_000_0', 3],
            ['5_000_000_000_0', 4],
            ['10_000_000_000_0', 4],
            ['19_999_999_999_9', 4],
            ['20_000_000_000_0', 5],
            ['50_000_000_000_0', 5],
            ['80_000_000_000_0', 6],
            ['100_000_000_000_0', 6],
            ['1_000_000_000_000_0', 6],
            ['1_000_000_000_000_000_0', 6],
        ]:
            status.month_trades_total = Decimal(volume)
            assert status.vip_level == level
        # Some more checks (downgrade with real trader volume)
        status.month_trades_total = Decimal('1_210_324_543_8')
        status.month_trades_total_trader = Decimal('233_222_111_1')
        assert status.vip_level == 3
        status.month_trades_total_trader = Decimal('33_222_321_9')
        assert status.vip_level == 3
        status.month_trades_total_trader = Decimal('33_222_321_9')
        assert status.vip_level == 3
        status.month_trades_total_trader = Decimal('1_333_222_321_9')
        assert status.vip_level == 3

    def test_get_user_vip_level(self):
        u = self.user
        assert UserStatsManager.get_user_vip_level(u.id, force_update=True) == 0
        self.set_user_trade_volume(u, '100_000_000_0')
        assert UserStatsManager.get_user_vip_level(u.id) == 0  # uses cache
        assert UserStatsManager.get_user_vip_level(u.id, force_update=True) == 1
        self.set_user_trade_volume(u, '90_000_000_0')
        assert UserStatsManager.get_user_vip_level(u.id) == 1  # uses cache
        assert UserStatsManager.get_user_vip_level(u.id, force_update=True) == 0
        # Check cache usage
        cache.set(f'user_{USER_ID}_vipLevel', 5)
        assert UserStatsManager.get_user_vip_level(u.id) == 5  # uses cache
        # Check cache invalidation by deleting the key
        self.set_user_trade_volume(u, '1_000_000_000_0')
        cache.delete(f'user_{USER_ID}_vipLevel')
        assert UserStatsManager.get_user_vip_level(u.id) == 3
        assert cache.get(f'user_{USER_ID}_vipLevel') == 3
        # Invalid cache value results in cache invalidation
        self.set_user_trade_volume(u, '299_000_000_0')
        cache.set(f'user_{USER_ID}_vipLevel', 7)
        assert UserStatsManager.get_user_vip_level(u.id) == 1
        # Test some other steps
        self.set_user_trade_volume(u, '500_000_000_0')
        assert UserStatsManager.get_user_vip_level(u.id, force_update=True) == 2
        self.set_user_trade_volume(u, '5_000_000_000_0')
        assert UserStatsManager.get_user_vip_level(u.id, force_update=True) == 4
        self.set_user_trade_volume(u, '80_000_000_000_0')
        assert UserStatsManager.get_user_vip_level(u.id, force_update=True) == 6
        self.set_user_trade_volume(u, '20_000_000_000_0')
        assert UserStatsManager.get_user_vip_level(u.id, force_update=True) == 5

    @override_settings(CACHE_VIP_LEVEL=False)
    def test_get_user_fee(self):
        user, _ = User.objects.get_or_create(pk=USER_ID)
        stats = UserTradeStatus.objects.get_or_create(user=user)[0]
        # Generic fees
        assert UserStatsManager.get_user_fee() == Decimal('0.0025')
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.0025')
        assert UserStatsManager.get_user_fee(is_maker=True) == Decimal('0.0025')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0025')

        # USDT Fees
        assert UserStatsManager.get_user_fee(is_usdt=True) == Decimal('0.0013')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0013')
        assert UserStatsManager.get_user_fee(is_maker=True, is_usdt=True) == Decimal('0.001')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True, is_usdt=True) == Decimal('0.001')
        # User-specific fees
        user.base_fee = Decimal('0.123')
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.00123')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.00123')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0013')
        user.base_maker_fee = Decimal('0.15')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0015')
        user.base_maker_fee = Decimal('0.09')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0009')
        # User-specific USDT fees
        user.base_fee_usdt = Decimal('0.11')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0011')
        user.base_fee_usdt = Decimal('0.10')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True, is_usdt=True) == Decimal('0.0010')
        user, _ = User.objects.get_or_create(pk=USER_ID)
        # Step 0
        stats.month_trades_total = Decimal('10_000_000_0')
        stats.save()
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.0025')
        assert UserStatsManager.get_user_fee(is_maker=True) == Decimal('0.0025')
        stats.month_trades_total = Decimal('99_999_999_9')
        stats.save()
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.0025')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0025')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0013')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.001')
        # Step 1
        stats.month_trades_total = Decimal('100_000_000_0')
        stats.save()
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.002')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0017')
        stats.month_trades_total = Decimal('290_000_000_0')
        stats.save()
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.002')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0017')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0012')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.00095')
        # Step 2
        stats.month_trades_total = Decimal('300_000_000_0')
        stats.save()
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.0019')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0015')
        stats.month_trades_total = Decimal('999_999_999_9')
        stats.save()
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.0019')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0015')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0011')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.0009')
        # Step 3
        stats.month_trades_total = Decimal('1_000_000_000_0')
        stats.save()
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.00175')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.00125')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.001')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.0008')
        # Step 4
        stats.month_trades_total = Decimal('5_000_000_000_0')
        stats.save()
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.00155')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.001')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.001')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.0007')

    @override_settings(CACHE_VIP_LEVEL=False)
    def test_get_trader_fee(self):
        user, _ = User.objects.get_or_create(pk=USER_ID)
        user.user_type = User.USER_TYPES.trader

        stats = UserTradeStatus.objects.get_or_create(user=user)[0]
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.0025')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0025')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0013')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True, is_usdt=True) == Decimal('0.001')

        # USDT Fees
        assert UserStatsManager.get_user_fee(is_usdt=True) == Decimal('0.0013')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0013')
        assert UserStatsManager.get_user_fee(is_maker=True, is_usdt=True) == Decimal('0.001')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True, is_usdt=True) == Decimal('0.001')

        # User-specific fees
        user.base_fee = Decimal('0.123')
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.00123')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.00123')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0013')
        user.base_maker_fee = Decimal('0.15')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0015')
        user.base_maker_fee = Decimal('0.09')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0009')

        # User-specific USDT fees
        user.base_fee_usdt = Decimal('0.11')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0011')
        user.base_fee_usdt = Decimal('0.10')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True, is_usdt=True) == Decimal('0.0010')
        user, _ = User.objects.get_or_create(pk=USER_ID)
        user.user_type = User.USER_TYPES.trader

        # Step 0 (<100M)
        for volume in (Decimal('10_000_000_0'), Decimal('99_999_999_9')):
            stats.month_trades_total = volume
            stats.save()
            assert UserStatsManager.get_user_fee(user=user) == Decimal('0.0025')
            assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0025')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0013')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.001')

        # Step 1 (100M-300M)
        for volume in (Decimal('100_000_000_0'), Decimal('299_999_999_9')):
            stats.month_trades_total = volume
            stats.save()
            assert UserStatsManager.get_user_fee(user=user) == Decimal('0.002')
            assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0017')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0012')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.00095')

        # Step 2 (300M-1B)
        for volume in (Decimal('300_000_000_0'), Decimal('999_999_999_9')):
            stats.month_trades_total = volume
            stats.save()
            assert UserStatsManager.get_user_fee(user=user) == Decimal('0.0019')
            assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0015')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0011')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.0009')

        # Step 3 (1B-5B)
        for volume in (Decimal('1_000_000_000_0'), Decimal('4_999_999_999_9')):
            stats.month_trades_total = volume
            stats.save()
            assert UserStatsManager.get_user_fee(user=user) == Decimal('0.00175')
            assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.00125')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.001')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.0008')

        # Step 4 (5B-20B)
        for volume in (Decimal('5_000_000_000_0'), Decimal('19_999_999_999_9')):
            stats.month_trades_total = volume
            stats.save()
            assert UserStatsManager.get_user_fee(user=user) == Decimal('0.00155')
            assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.001')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.001')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.0007')

        # Step 5 (20-80B)
        for volume in (Decimal('20_000_000_000_0'), Decimal('79_999_999_999_9')):
            stats.month_trades_total = volume
            stats.save()
            assert UserStatsManager.get_user_fee(user=user) == Decimal('0.00145')
            assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0009')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.00095')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.00065')

        # Step 6 (>80B)
        for volume in (Decimal('80_000_000_000_0'), Decimal('81_000_000_000_0')):
            stats.month_trades_total = volume
            stats.save()
            assert UserStatsManager.get_user_fee(user=user) == Decimal('0.00135')
            assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0008')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0009')
            assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.0006')

    @override_settings(CACHE_VIP_LEVEL=True)
    def test_get_user_fee_cached(self):
        user, _ = User.objects.get_or_create(pk=USER_ID)
        stats = UserTradeStatus.objects.get_or_create(user=user)[0]
        UserStatsManager.get_user_vip_level(user.id, force_update=True)
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.0025')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0025')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0013')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.001')
        # Trade stats update should not be reflected immediately
        stats.month_trades_total = Decimal('100_000_000_0')
        stats.save()
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.0025')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0025')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0013')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.001')
        # Update caches
        UserStatsManager.get_user_vip_level(user.id, force_update=True)
        assert UserStatsManager.get_user_fee(user=user) == Decimal('0.002')
        assert UserStatsManager.get_user_fee(user=user, is_maker=True) == Decimal('0.0017')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True) == Decimal('0.0012')
        assert UserStatsManager.get_user_fee(user=user, is_usdt=True, is_maker=True) == Decimal('0.00095')

    def _test_serialize_user(self, user_type):
        self.user.user_type = user_type
        self.set_user_trade_volume(self.user, '5_000_000_000_0')
        assert UserStatsManager.get_user_vip_level(self.user.id, force_update=True) == 4
        options = serialize(serialize_user(self.user, {'level': 2})['options'])
        assert options['fee'] == '0.155'
        assert options['feeUsdt'] == '0.1'
        assert options['makerFee'] == '0.1'
        assert options['makerFeeUsdt'] == '0.07'
        assert options['isManualFee'] is False
        assert options['vipLevel'] == 4
        assert options['discount'] is None
        # Manual maker fee
        self.user.base_maker_fee = Decimal('0.09')
        self.user.base_maker_fee_usdt = Decimal('0.05')
        options = serialize(serialize_user(self.user, {'level': 2})['options'])
        assert options['fee'] == '0.155'
        assert options['feeUsdt'] == '0.1'
        assert options['makerFee'] == '0.09'
        assert options['makerFeeUsdt'] == '0.05'
        assert options['isManualFee'] is False
        assert options['vipLevel'] == 4
        assert options['discount'] is None
        # Manual maker & taker fee
        self.user.base_fee = Decimal('0.15')
        self.user.base_fee_usdt = Decimal('0.09')
        self.user.base_maker_fee_usdt = None
        options = serialize(serialize_user(self.user, {'level': 2})['options'])
        assert options['fee'] == '0.15'
        assert options['feeUsdt'] == '0.09'
        assert options['makerFee'] == '0.09'
        assert options['makerFeeUsdt'] == '0.07'
        assert options['isManualFee'] is True
        assert options['vipLevel'] == 4
        assert options['discount'] is None
        # Manual fee greater than user vip level
        self.user.base_fee = Decimal('0.16')
        self.user.base_maker_fee_usdt = Decimal('0.08')
        options = serialize(serialize_user(self.user, {'level': 2})['options'])
        assert options['fee'] == '0.155'
        assert options['makerFeeUsdt'] == '0.07'

    def test_serialize_user_non_trader(self):
        self._test_serialize_user(User.USER_TYPES.level2)

    def test_serialize_user_trader(self):
        self._test_serialize_user(User.USER_TYPES.trader)

    def test_pool_manager_vip_level(self):
        user = User.objects.get(pk=202)
        user.user_type = User.USER_TYPES.system
        user.save()

        self.set_user_trade_volume(user, '80_000_000_000_0')
        assert UserStatsManager.get_user_vip_level(user.id, force_update=True) == SYSTEM_USERS_VIP_LEVEL
