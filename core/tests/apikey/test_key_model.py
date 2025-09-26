import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from exchange.accounts.models import User
from exchange.apikey.models import Key, Permission


class TestKeyPermissions(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)

    def test_save_and_load(self):
        k = Key(
            key='fyqRCbsAixItOzMSRAHcN7Q02jCKtVH6tktWBoBSUrA=',
            owner=self.user,
            expiration_date=None,
            name='test',
            description='test',
            ip_addresses_whitelist=[],
            permission_bits=Permission.READ | Permission.WITHDRAW,
        )
        k.save()

        k = Key.objects.get(key='fyqRCbsAixItOzMSRAHcN7Q02jCKtVH6tktWBoBSUrA=')
        assert k.name == 'test'
        assert Permission.READ in k.permissions
        assert Permission.TRADE not in k.permissions
        assert Permission.WITHDRAW in k.permissions

    def test_save_and_load_using_property(self):
        k = Key(
            key='fyqRCbsAixItOzMSRAHcN7Q02jCKtVH6tktWBoBSUrA=',
            owner=self.user,
            expiration_date=None,
            name='test',
            description='test',
            ip_addresses_whitelist=[],
        )
        k.permissions = Permission.READ | Permission.WITHDRAW
        k.save()

        k = Key.objects.get(key='fyqRCbsAixItOzMSRAHcN7Q02jCKtVH6tktWBoBSUrA=')
        assert k.name == 'test'
        assert Permission.READ in k.permissions
        assert Permission.TRADE not in k.permissions
        assert Permission.WITHDRAW in k.permissions

    def test_max_keys_per_user(self):
        another_user = User.objects.get(pk=202)

        for i in range(Key.MAX_KEYS_PER_USER):
            k = Key(
                key=f'public_key_{i}',
                owner=self.user,
                expiration_date=None,
                name='test',
                description='test',
                ip_addresses_whitelist=[],
                permission_bits=Permission.READ | Permission.WITHDRAW,
            )
            k.save()

        k = Key(
            key='public_key_last',
            owner=self.user,
            expiration_date=None,
            name='test',
            description='test',
            ip_addresses_whitelist=[],
            permission_bits=Permission.READ | Permission.WITHDRAW,
        )
        with pytest.raises(expected_exception=ValidationError):
            k.save()

        k = Key(
            key='public_key_last',
            owner=another_user,
            expiration_date=None,
            name='test',
            description='test',
            ip_addresses_whitelist=[],
            permission_bits=Permission.READ | Permission.WITHDRAW,
        )
        k.save()

    def test_max_ip_per_key(self):
        k = Key(
            key='public_key',
            owner=self.user,
            expiration_date=None,
            name='test',
            description='test',
            ip_addresses_whitelist=[],
            permission_bits=Permission.READ | Permission.WITHDRAW,
        )
        assert isinstance(k.ip_addresses_whitelist, list)
        assert hasattr(k.ip_addresses_whitelist, 'append')

        for i in range(Key.MAX_IPS_PER_KEY):
            k.ip_addresses_whitelist.append(f'192.168.73.{i}')
            k.save()

        k.ip_addresses_whitelist.append('192.168.73.254')
        with pytest.raises(expected_exception=ValidationError):
            k.save()
