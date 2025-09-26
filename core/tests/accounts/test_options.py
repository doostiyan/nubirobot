from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import Client, TestCase
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.accounts.views.profile import get_options_v2
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.models import Currencies, Settings


class OptionsTest(TestCase):

    def setUp(self):
        self.client = Client()


    def test_get_options_v2(self):
        options_map = get_options_v2(new_version=True, set_db_defaults=False)
        options = list(options_map.values())
        assert len(options) == len(CURRENCY_INFO)
        btc = options_map[Currencies.btc]
        assert btc['coin'] == 'btc'
        assert btc['name'] == 'Bitcoin'
        assert btc['defaultNetwork'] == 'BTC'
        btc_btc = btc['networkList']['BTC']
        assert btc_btc['withdrawMin'] == '0.00200000'
        assert btc_btc['withdrawMax'] == '0.10000000'
        assert btc_btc['withdrawFee'] == '0.0003500000'
        self.assertTrue(btc_btc['withdrawEnable'])
        self.assertTrue(btc_btc['depositEnable'])
        btc_ln = btc['networkList']['BTCLN']
        assert btc_ln['withdrawMin'] == '0.00000100'
        assert btc_ln['withdrawMax'] == '0.00700000'
        assert btc_ln['withdrawFee'] == '0.00000050'
        # Manually set some settings in DB
        Settings.set('withdraw_fee_btc_btcln', '0.00000020')
        Settings.set('withdraw_enabled_btc_btc', 'no')
        Settings.set('deposit_enabled_btc_btc', 'no')
        # Recheck
        options_map = get_options_v2(new_version=True, set_db_defaults=False)
        btc = options_map[Currencies.btc]
        btc_btc = btc['networkList']['BTC']
        assert btc_btc['withdrawMin'] == '0.00200000'
        assert btc_btc['withdrawMax'] == '0.10000000'
        assert btc_btc['withdrawFee'] == '0.0003500000'
        self.assertFalse(btc_btc['withdrawEnable'])
        self.assertFalse(btc_btc['depositEnable'])
        btc_ln = btc['networkList']['BTCLN']
        assert btc_ln['withdrawMin'] == '0.00000100'
        assert btc_ln['withdrawMax'] == '0.00700000'
        assert btc_ln['withdrawFee'] == '0.00000020'

    def test_v2_options_api(self):
        r = self.client.get('/v2/options').json()
        assert r['status'] == 'ok'
        assert 'btc' in r['nobitex']['allCurrencies']
        assert r['nobitex']['amountPrecisions']['BTCIRT'] == '0.000001'
        assert r['nobitex']['amountPrecisions']['BTCUSDT'] == '0.000001'
        assert r['nobitex']['pricePrecisions']['BTCIRT'] == '10'
        assert r['nobitex']['pricePrecisions']['BTCUSDT'] == '0.01'
        assert r['nobitex']['pricePrecisions']['DOGEUSDT'] == '0.0000001'
        assert r['nobitex']['minOrders']['rls'] == "500000"
        assert r['nobitex']['minOrders'][str(Currencies.usdt)] == "5"
        assert r['nobitex']['withdrawLimits']["level2"] == r['nobitex']['withdrawLimits'][str(User.USER_TYPES.level2)]

        assert r['nobitex']['depositLimits']["level0"] == r['nobitex']['depositLimits'][str(User.USER_TYPES.level0)]
        assert r['nobitex']['depositLimits']["level1"] == r['nobitex']['depositLimits'][str(User.USER_TYPES.level1)]
        assert r['nobitex']['depositLimits']["trader"] == r['nobitex']['depositLimits'][str(User.USER_TYPES.trader)]
        assert r['nobitex']['depositLimits']["level2"] == r['nobitex']['depositLimits'][str(User.USER_TYPES.level2)]
        assert r['nobitex']['depositLimits']["verified"] == r['nobitex']['depositLimits'][str(User.USER_TYPES.verified)]
        assert (
            r['nobitex']['depositLimitsWithIdentifiedMobile']["level2"]
            == r['nobitex']['depositLimitsWithIdentifiedMobile'][str(User.USER_TYPES.level2)]
        )

        assert r['nobitex']['depositLimits']["level0"] == str(0)
        assert r['nobitex']['depositLimits']["level1"] == str(25_000_000_0)
        assert r['nobitex']['depositLimits']["trader"] == str(25_000_000_0)
        assert r['nobitex']['depositLimits']["level2"] == str(25_000_000_0)
        assert r['nobitex']['depositLimits']["verified"] == str(25_000_000_0)

        assert r['nobitex']['depositLimitsWithIdentifiedMobile']["level0"] == str(0)
        assert r['nobitex']['depositLimitsWithIdentifiedMobile']["level1"] == str(25_000_000_0)
        assert r['nobitex']['depositLimitsWithIdentifiedMobile']["trader"] == str(25_000_000_0)
        assert r['nobitex']['depositLimitsWithIdentifiedMobile']["level2"] == str(25_000_000_0)
        assert r['nobitex']['depositLimitsWithIdentifiedMobile']["verified"] == str(25_000_000_0)

        assert r['features']['fcmEnabled'] == True
        assert r['nobitex']['vandarDepositId']['feeRate'] == "0.0002"
        assert r['nobitex']['shetabFee']['max'] == 4000_0
        assert r['nobitex']['shetabFee']['min'] == 120_0
        assert r['nobitex']['shetabFee']['rate'] == '0.0002'
        btc = [coin_info for coin_info in r['coins'] if coin_info['coin'] == 'btc'][0]
        assert btc['name'] == 'Bitcoin'
        assert btc['defaultNetwork'] == 'BTC'
        assert btc['displayPrecision'] == '0.000001'
        btc_btc = btc['networkList']['BTC']
        assert btc_btc['withdrawMin'] == '0.00200000'
        assert btc_btc['withdrawMax'] == '0.10000000'
        assert btc_btc['withdrawFee'] == '0.0003500000'
        btc_ln = btc['networkList']['BTCLN']
        assert btc_ln['withdrawMin'] == '0.00000100'
        assert btc_ln['withdrawMax'] == '0.00700000'
        assert btc_ln['withdrawFee'] == '0.00000050'

        for user_type, user_name in r['nobitex']['userLevelNames'].items():
            assert settings.NOBITEX_OPTIONS['userTypes'][int(user_type)] == user_name

        assert r['nobitex']['rialDepositGatewayLimit'] == str(25_000_000_0)

    def test_v2_options_feature_setting_status(self):
        cache_key = f'is_{Settings.FEATURE_AUTO_KYC}_feature_enabled'
        cache.set(cache_key, True)
        r = self.client.get('/v2/options').json()
        assert r['features']['autoKYC'] is True
        cache.set(cache_key, False)
        r = self.client.get('/v2/options').json()
        assert r['features']['autoKYC'] is False
        cache.delete(cache_key)
        Settings.objects.update_or_create(key=f'{Settings.FEATURE_AUTO_KYC}_feature_status',
                                          defaults=dict(value='enabled'))
        r = self.client.get('/v2/options').json()
        assert r['features']['autoKYC'] is True
        cache.delete(cache_key)
        Settings.objects.update_or_create(key=f'{Settings.FEATURE_AUTO_KYC}_feature_status',
                                          defaults=dict(value='disabled'))
        r = self.client.get('/v2/options').json()
        assert r['features']['autoKYC'] is False
        cache.delete(cache_key)
        Settings.objects.filter(key=f'{Settings.FEATURE_AUTO_KYC}_feature_status').delete()
        r = self.client.get('/v2/options').json()
        assert r['features']['autoKYC'] is True

    def test_v2_withdraw_limits(self):
        Settings.set('max_rial_withdrawal', '5_000_000_000_0.00000000')
        r = self.client.get('/v2/options').json()
        assert r['nobitex']['rialWithdrawConfigs']['maxRialWithdrawal'] == '50000000000'
        assert r['nobitex']['rialWithdrawConfigs']['minRialWithdrawal'] == '150000'


class TestUserPreferences(APITestCase):

    def setUp(self):
        self.client = Client()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

    @patch.dict(settings.NOBITEX_OPTIONS, currencies=['1b_babydoge'])
    def test_preference_for_none_applications(self):
        url = '/users/preferences'
        r = self.client.post(url, data={}).json()
        assert r['status'] == 'ok'
        assert '1b_babydoge' in r['options']['currencies']

    @patch.dict(settings.NOBITEX_OPTIONS, currencies=['1b_babydoge'])
    def test_preference_for_applications(self):
        url = '/users/preferences'
        r = self.client.post(url, HTTP_USER_AGENT='Android/4.8.0 (RNE-L21)', data={}).json()
        assert r['status'] == 'ok'
        assert '1b_babydoge' in r['options']['currencies']

        r = self.client.post(url, HTTP_USER_AGENT='iOSApp/1.9.0 (iPhone; iOS 15.2.1; Scale/2.00)', data={}).json()
        assert r['status'] == 'ok'
        assert '1b_babydoge' in r['options']['currencies']

        r = self.client.post(url, HTTP_USER_AGENT='Android/5.0.1 (RNE-L21)', data={}).json()
        assert r['status'] == 'ok'
        assert '1b_babydoge' in r['options']['currencies']
