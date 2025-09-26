from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.security.models import IPBlackList


class TestIPBlacklist(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username='test_user')

    def setUp(self):
        cache.clear()

    @classmethod
    def add_black_ip(cls, ip, is_active):
        return IPBlackList.objects.create(ip=ip, is_active=is_active, allocated_by=cls.user)

    def test_no_blacklist_ip(self):
        assert not IPBlackList.contains('1.1.1.1')
        assert not IPBlackList.contains('2.2.2.2')

    def test_inactive_blacklist_ip(self):
        self.add_black_ip('1.1.1.1', is_active=False)
        assert not IPBlackList.contains('1.1.1.1')
        assert not IPBlackList.contains('2.2.2.2')

    def test_active_blacklist_ip(self):
        self.add_black_ip('1.1.1.1', is_active=True)
        assert IPBlackList.contains('1.1.1.1')
        assert not IPBlackList.contains('2.2.2.2')

    def test_blacklist_ips_cache(self):
        self.add_black_ip('1.1.1.1', is_active=True)
        with self.assertNumQueries(1):
            assert IPBlackList.contains('1.1.1.1')
            assert not IPBlackList.contains('2.2.2.2')
            assert IPBlackList.contains('1.1.1.1')

    def test_blacklist_ips_cache_on_change(self):
        black_ip = self.add_black_ip('1.1.1.1', is_active=True)
        with self.assertNumQueries(1):
            assert IPBlackList.contains('1.1.1.1')
            assert not IPBlackList.contains('2.2.2.2')
        black_ip.is_active = False
        black_ip.save(update_fields=('is_active',))
        with self.assertNumQueries(1):
            assert not IPBlackList.contains('1.1.1.1')
            assert not IPBlackList.contains('2.2.2.2')

    def test_blacklist_ips_cache_on_new(self):
        self.add_black_ip('1.1.1.1', is_active=True)
        with self.assertNumQueries(1):
            assert IPBlackList.contains('1.1.1.1')
            assert not IPBlackList.contains('2.2.2.2')
        self.add_black_ip('2.2.2.2', is_active=True)
        with self.assertNumQueries(1):
            assert IPBlackList.contains('1.1.1.1')
            assert IPBlackList.contains('2.2.2.2')

    def test_blacklist_ips_cache_on_delete(self):
        black_ip = self.add_black_ip('1.1.1.1', is_active=True)
        with self.assertNumQueries(1):
            assert IPBlackList.contains('1.1.1.1')
            assert not IPBlackList.contains('2.2.2.2')
        black_ip.delete()
        with self.assertNumQueries(1):
            assert not IPBlackList.contains('1.1.1.1')
            assert not IPBlackList.contains('2.2.2.2')
