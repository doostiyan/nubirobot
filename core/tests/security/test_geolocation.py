import pytest
from django.test import TestCase

from exchange.security.models import KnownIP


class GeoLocationTest(TestCase):
    def test_ip_geolocation_local_db(self):
        KnownIP.objects.create(ip_range='127.0.0', country='IR')
        geo = KnownIP.inspect_ip('127.0.0.1')
        assert geo['country'] == 'IR'
        assert geo['city'] == 'UN'

    @pytest.mark.slow
    def test_ip_geolocation_generic(self):
        geo = KnownIP.inspect_ip('8.8.8.8')
        assert geo['country'] == 'US'
        assert geo['city'] and geo['city'] != 'UN'

    @pytest.mark.slow
    def test_ip_geolocation_ipinfo_fallback(self):
        geo = KnownIP.inspect_ip('204.18.170.1')
        assert geo['response'].get('city') == 'Tehran'
        assert geo['country'] == 'IR'
        assert geo['city'] == 'Tehran'
