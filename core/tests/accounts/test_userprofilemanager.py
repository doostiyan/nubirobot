from django.conf import settings
from django.db import connection
from django.test import Client, TestCase, override_settings

from exchange.accounts.models import User
from exchange.accounts.userprofile import UserProfileManager
from exchange.security.models import LoginAttempt


class UserProfileManagerTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client = Client(
            HTTP_AUTHORIZATION='Token user201token',
        )
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)

    def test_property_getter_setter(self):
        uid = self.user.id
        # First property
        assert UserProfileManager.get_user_property(uid, 'regCh') is None
        UserProfileManager.set_user_property(uid, 'regCh', 'w')
        assert UserProfileManager.get_user_property(uid, 'regCh') == 'w'
        UserProfileManager.set_user_property(uid, 'regCh', 'a')
        assert UserProfileManager.get_user_property(uid, 'regCh') == 'a'
        # Another property
        assert UserProfileManager.get_user_property(uid, 'father') is None
        UserProfileManager.set_user_property(uid, 'father', 'حجّت')
        assert UserProfileManager.get_user_property(uid, 'regCh') == 'a'
        assert UserProfileManager.get_user_property(uid, 'father') == 'حجّت'
        # Client properties
        UserProfileManager.set_client_version(uid, 'Android', '3.7.2')
        assert UserProfileManager.get_client_version(uid, 'android') == 372
        assert UserProfileManager.get_user_property(uid, 'vA') == 372
        assert UserProfileManager.get_user_property(uid, 'regCh') == 'a'
        assert UserProfileManager.get_user_property(uid, 'father') == 'حجّت'

    def test_user_set_profile_property(self):
        self.user.set_profile_property('regCh', 'w')
        assert UserProfileManager.get_user_property(self.user.id, 'regCh') == 'w'

    def test_properties_field_format_backward_compatibility(self):
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO accounts_userprofile (user_ptr_id, properties) VALUES (%s, %s::jsonb)',
                [self.user.id, '{"vA": 400, "vI": 140}'],
            )
        assert UserProfileManager.get_client_version(self.user, 'android') == 400
        assert UserProfileManager.get_client_version(self.user, 'ios') == 140
        assert UserProfileManager.get_user_property(self.user, 'regCh') is None

    def test_parse_client_params(self):
        assert UserProfileManager._parse_client_params(1, 'android', '3.8.0') == (1, 'vA', 380)
        assert UserProfileManager._parse_client_params(2, 'ios', '1.0') == (2, 'vI', 100)
        assert UserProfileManager._parse_client_params(self.user, 'iOSApp', None) == (201, 'vI', None)

    def test_client_version(self):
        u = self.user
        assert UserProfileManager.get_client_version(u, 'android') is None
        assert UserProfileManager.get_client_version(u, 'ios') is None
        # Set Android
        assert UserProfileManager.set_client_version(u, 'Android', '3.7.2')
        assert UserProfileManager.get_client_version(u, 'android') == 372
        assert UserProfileManager.get_client_version(u, 'ios') is None
        # Set iOS
        assert UserProfileManager.set_client_version(u, 'ios', '1.1')
        assert UserProfileManager.get_client_version(u, 'android') == 372
        assert UserProfileManager.get_client_version(u, 'ios') == 110
        # Set iOS again
        assert UserProfileManager.set_client_version(u, 'ios', '1.1')
        assert UserProfileManager.get_client_version(u, 'android') == 372
        assert UserProfileManager.get_client_version(u, 'ios') == 110
        # Update Android
        assert UserProfileManager.set_client_version(u, 'Android', '3.8.0')
        assert UserProfileManager.get_client_version(u, 'android') == 380
        assert UserProfileManager.get_client_version(u, 'ios') == 110
        # Set by UA
        assert UserProfileManager.set_client_version_from_ua(u, 'iOSApp/1.0 (iPhone; iOS 15.2.1; Scale/2.00)')
        assert UserProfileManager.get_client_version(u, 'ios') == 100
        assert UserProfileManager.set_client_version_from_ua(u, 'Android/3.7.0-testnet (HUAWEI P7-L10)')
        assert UserProfileManager.set_client_version_from_ua(u, 'Mozilla/5.0 (Linux; Android 9; SM-J530F)') is False
        assert UserProfileManager.set_client_version_from_ua(u, 'python-requests/2.25.1') is False
        assert UserProfileManager.get_client_version(u, 'android') == 370
        assert UserProfileManager.get_client_version(u, 'ios') == 100

    @override_settings(SET_USER_PROPERTIES_PR=1)
    def test_set_client_version_in_api(self):
        version = settings.LAST_SUPPORTED_ANDROID_VERSION
        r = self.client.get('/users/markets/favorite', HTTP_USER_AGENT=f'Android/{version} (RNE-L21)').json()
        assert r['status'] == 'ok'
        assert UserProfileManager.get_client_version(self.user, 'android') == int(version.replace('.', ''))
        r = self.client.get(
            '/users/markets/favorite',
            HTTP_USER_AGENT='iOSApp/1.0 (iPhone; iOS 15.2.1; Scale/2.00)',
        ).json()
        assert r['status'] == 'ok'
        assert UserProfileManager.get_client_version(self.user, 'ios') == 100
