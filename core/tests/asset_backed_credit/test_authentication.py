import uuid
from unittest.mock import patch

import pytest
import responses
from django.conf import settings
from django.http import HttpRequest
from django.test import TestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed

from exchange.accounts.models import User
from exchange.asset_backed_credit.api.authentication import InternalTokenAuthentication
from exchange.asset_backed_credit.externals.user import UserProfileAPI
from exchange.asset_backed_credit.models import InternalUser
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import INTERNAL_TEST_JWT_TOKEN


class InternalTokenAuthenticationTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.internal_user = InternalUser.objects.create(uid=self.user.uid, user_type=self.user.user_type)
        Settings.set('abc_use_internal_user_profile_api', 'yes')

    @patch('rest_framework.authentication.TokenAuthentication.authenticate')
    def test_core_user_authentication_enabled_success(self, mock_authenticate):
        mock_authenticate.return_value = (self.user, None)

        authentication = InternalTokenAuthentication()
        request = HttpRequest()
        user, token = authentication.authenticate(request=request)

        assert user == self.user
        assert user.is_authenticated
        assert not token
        assert request.internal_user == self.internal_user
        assert request.internal_user.id
        assert request.internal_user.id == self.internal_user.id

    @patch('rest_framework.authentication.TokenAuthentication.authenticate_credentials')
    def test_core_user_authentication_enabled_auth_header_not_found_return_none(self, mock_authenticate):
        mock_authenticate.return_value = (self.user, None)

        authentication = InternalTokenAuthentication()
        request = HttpRequest()
        user_and_token = authentication.authenticate(request=request)

        assert not user_and_token

    @override_settings(ABC_AUTHENTICATION_INTERNAL_USER_ENABLED=True)
    @patch('rest_framework.authentication.TokenAuthentication.authenticate')
    def test_internal_user_authentication_enabled_success(self, mock_authenticate):
        assert settings.ABC_AUTHENTICATION_INTERNAL_USER_ENABLED

        mock_authenticate.return_value = (self.user, None)

        authentication = InternalTokenAuthentication()
        request = HttpRequest()
        user, token = authentication.authenticate(request=request)

        assert user == self.internal_user
        assert user.is_authenticated
        assert not token
        assert user.id
        assert user.id == self.internal_user.id

    @override_settings(
        ABC_AUTHENTICATION_INTERNAL_USER_ENABLED=True, ABC_INTERNAL_API_JWT_TOKEN=INTERNAL_TEST_JWT_TOKEN
    )
    @patch('rest_framework.authentication.TokenAuthentication.authenticate')
    @patch('exchange.asset_backed_credit.externals.user.UserProfileAPI._request')
    def test_internal_user_authentication_enabled_internal_user_not_found_call_user_api_create_success(
        self, mock_user_profile, mock_authenticate
    ):
        user = User.objects.get(pk=202)

        assert settings.ABC_AUTHENTICATION_INTERNAL_USER_ENABLED

        mock_authenticate.return_value = (user, None)

        user_id = user.uid

        mock_user_profile.return_value.json.return_value = {
            'uid': str(user_id),
            'username': 'siavash',
            'email': 'siavash.at.work@gmail.com',
            'nationalCode': '1231233331',
            'mobile': '09180001122',
            'verificationStatus': 10,
            'userType': 10,
            "birthdateShamsi": "1403/10/15",
            "fatherName": "test",
            "gender": 1,
            "requires2fa": True,
            'verificationProfile': {
                'emailConfirmed': True,
                'mobileConfirmed': True,
                'identityConfirmed': False,
                'mobileIdentityConfirmed': False,
            },
        }

        authentication = InternalTokenAuthentication()
        request = HttpRequest()
        user, token = authentication.authenticate(request=request)

        assert user
        internal_user = InternalUser.objects.get(uid=user_id)
        assert user == internal_user
        assert user.is_authenticated
        assert not token
        mock_user_profile.assert_called_once()
        assert internal_user.id
        assert user.id == internal_user.id
        assert internal_user.email_confirmed == True
        assert internal_user.mobile_confirmed == True
        assert internal_user.identity_confirmed == False
        assert internal_user.mobile_identity_confirmed == False
        assert internal_user.birthdate_shamsi == "1403/10/15"
        assert internal_user.father_name == "test"
        assert internal_user.gender == 1
        assert internal_user.requires_2fa == True

    @override_settings(
        ABC_AUTHENTICATION_INTERNAL_USER_ENABLED=True, ABC_INTERNAL_API_JWT_TOKEN=INTERNAL_TEST_JWT_TOKEN
    )
    @patch('rest_framework.authentication.TokenAuthentication.authenticate')
    @patch('exchange.asset_backed_credit.externals.user.UserProfileAPI._request')
    def test_internal_user_authentication_when_mobile_identity_confirm_is_none_in_internal_api_response(
        self, mock_user_profile, mock_authenticate
    ):
        user = User.objects.get(pk=202)
        mock_authenticate.return_value = (user, None)
        user_id = user.uid
        mock_user_profile.return_value.json.return_value = {
            'uid': str(user_id),
            'username': 'siavash',
            'email': 'siavash.at.work@gmail.com',
            'nationalCode': '1231233331',
            'mobile': '09180001122',
            'verificationStatus': 10,
            'userType': 10,
            'gender': 0,
            'requires2fa': False,
            'verificationProfile': {
                'mobileIdentityConfirmed': None,
                'emailConfirmed': True,
                'mobileConfirmed': False,
                'identityConfirmed': False,
            },
        }

        authentication = InternalTokenAuthentication()
        request = HttpRequest()
        user, token = authentication.authenticate(request=request)

        assert user
        internal_user = InternalUser.objects.get(uid=user_id)
        assert user == internal_user
        assert user.is_authenticated
        assert not token
        mock_user_profile.assert_called_once()
        assert internal_user.id
        assert user.id == internal_user.id
        assert internal_user.email_confirmed == True
        assert internal_user.mobile_confirmed == False
        assert internal_user.identity_confirmed == False
        assert internal_user.mobile_identity_confirmed == False
        assert internal_user.birthdate_shamsi is None
        assert internal_user.father_name is None
        assert internal_user.gender == 0
        assert internal_user.requires_2fa == False

    @responses.activate
    @override_settings(
        ABC_AUTHENTICATION_INTERNAL_USER_ENABLED=True, ABC_INTERNAL_API_JWT_TOKEN=INTERNAL_TEST_JWT_TOKEN
    )
    @patch('rest_framework.authentication.TokenAuthentication.authenticate')
    def test_internal_user_authentication_enabled_invalid_user_id_authentication_failed(self, mock_authenticate):
        responses.reset()

        user = User.objects.get(pk=202)

        assert settings.ABC_AUTHENTICATION_INTERNAL_USER_ENABLED

        mock_authenticate.return_value = (user, None)

        user_id = user.uid

        url = UserProfileAPI.url % user_id
        responses.get(
            url=url,
            json={'message': 'User not found', 'error': 'NotFound'},
            status=404,
        )

        authentication = InternalTokenAuthentication()
        request = HttpRequest()
        with pytest.raises(AuthenticationFailed):
            authentication.authenticate(request=request)

    @override_settings(ABC_AUTHENTICATION_ENABLED=False)
    def test_authentication_disabled_success(self):
        assert not settings.ABC_AUTHENTICATION_ENABLED

        authentication = InternalTokenAuthentication()
        request = HttpRequest()
        request.META['HTTP_USER-ID'] = self.user.uid
        user, token = authentication.authenticate(request=request)

        assert user == self.internal_user
        assert user.id
        assert user.id == self.internal_user.id
        assert user.is_authenticated
        assert not token

    @override_settings(ABC_AUTHENTICATION_ENABLED=False)
    def test_authentication_disabled_authentication_failed(self):
        assert not settings.ABC_AUTHENTICATION_ENABLED

        authentication = InternalTokenAuthentication()
        request = HttpRequest()
        request.META['HTTP_USER-ID'] = 'invalid-id'

        with pytest.raises(AuthenticationFailed):
            authentication.authenticate(request=request)

    @override_settings(ABC_AUTHENTICATION_INTERNAL_USER_ENABLED=True)
    @patch('rest_framework.authentication.TokenAuthentication.authenticate')
    def test_internal_user_authentication_when_internal_profile_api_is_disabled_and_internal_user_exists(
        self, mock_authenticate
    ):
        Settings.set('abc_use_internal_user_profile_api', 'no')
        assert settings.ABC_AUTHENTICATION_INTERNAL_USER_ENABLED

        mock_authenticate.return_value = (self.user, None)

        authentication = InternalTokenAuthentication()
        request = HttpRequest()
        user, token = authentication.authenticate(request=request)

        assert user == self.internal_user
        assert user.is_authenticated
        assert not token
        assert user.id
        assert user.id == self.internal_user.id

    @override_settings(ABC_AUTHENTICATION_INTERNAL_USER_ENABLED=True)
    @patch('rest_framework.authentication.TokenAuthentication.authenticate')
    def test_internal_user_authentication_when_internal_profile_api_is_disabled_and_internal_user_does_not_exist(
        self, mock_authenticate
    ):
        Settings.set('abc_use_internal_user_profile_api', 'no')
        assert settings.ABC_AUTHENTICATION_INTERNAL_USER_ENABLED

        user = User.objects.get(id=202)
        mock_authenticate.return_value = (user, None)

        authentication = InternalTokenAuthentication()
        request = HttpRequest()
        internal_user, token = authentication.authenticate(request=request)

        expected_internal_user = InternalUser.objects.get(uid=user.uid)
        assert internal_user == expected_internal_user
        assert internal_user.is_authenticated
        assert not token
        assert internal_user.id
        assert internal_user.id == expected_internal_user.id
        assert internal_user.email_confirmed == False
        assert internal_user.mobile_confirmed == False
        assert internal_user.identity_confirmed == False
        assert internal_user.mobile_identity_confirmed == False
        assert internal_user.birthdate_shamsi == user.birthday_shamsi
        assert internal_user.father_name == user.father_name
        assert internal_user.gender == user.gender
        assert internal_user.requires_2fa == user.requires_2fa

    @override_settings(ABC_AUTHENTICATION_INTERNAL_USER_ENABLED=True)
    @patch('rest_framework.authentication.TokenAuthentication.authenticate')
    def test_internal_user_authentication_when_internal_profile_api_is_disabled_and_user_does_not_exists(
        self, mock_authenticate
    ):
        Settings.set('abc_use_internal_user_profile_api', 'no')
        assert settings.ABC_AUTHENTICATION_INTERNAL_USER_ENABLED

        user = User(uid=uuid.uuid4())
        mock_authenticate.return_value = (user, None)

        authentication = InternalTokenAuthentication()
        request = HttpRequest()
        with pytest.raises(AuthenticationFailed):
            authentication.authenticate(request=request)
