from django.core.cache import cache
from django.test import TestCase

from exchange.base.models import Settings


class SettingsTest(TestCase):
    def test_get_cached_json(self):
        # Sample flag
        v = Settings.get_cached_json('test_settings1', default=False)
        assert v is False
        assert Settings.objects.get(key='test_settings1').value == 'false'
        assert cache.get('settings_test_settings1') is False
        assert Settings.get_cached_json('test_settings1', default=True) is False
        # Sample str
        v = Settings.get_cached_json('test_settings2', default='test')
        assert v == 'test'
        assert Settings.objects.get(key='test_settings2').value == '"test"'
        assert cache.get('settings_test_settings2') == 'test'
        # Check cache usage
        Settings.objects.filter(key='test_settings2').delete()
        assert Settings.get_cached_json('test_settings2') == 'test'
        # Sample dict
        v = Settings.get_cached_json('test_settings3', default={'x': 2})
        assert v == {'x': 2}
        assert Settings.objects.get(key='test_settings3').value == '{"x": 2}'
        assert cache.get('settings_test_settings3') == {'x': 2}
        assert Settings.get_cached_json('test_settings3') == {'x': 2}
        # Sample list
        v = Settings.get_cached_json('test_settings4', default=['a', 'b'])
        assert v == ['a', 'b']
        assert Settings.objects.get(key='test_settings4').value == '["a", "b"]'
        assert cache.get('settings_test_settings4') == ['a', 'b']
        # Default None
        assert Settings.get_cached_json('test_settings5') is None
        assert Settings.objects.get(key='test_settings5').value == 'null'
        assert Settings.get_cached_json('test_settings5', default='1') == '1'
        assert Settings.get_cached_json('test_settings5', default='2') == '2'
        Settings.objects.filter(key='test_settings5').update(value='"3"')
        assert Settings.get_cached_json('test_settings5', default='2') == '3'
