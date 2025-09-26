from unittest.mock import patch

import responses
from django.core.cache import cache
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.providers.parsian.api import (
    DebitCardHashPanAPI,
    DebitCardOTPRequestAPI,
    DebitCardOTPVerifyAPI,
)
from exchange.asset_backed_credit.models import (
    Card,
    CardRequestAPISchema,
    InternalUser,
    Service,
    UserFinancialServiceLimit,
    UserServicePermission,
)
from exchange.asset_backed_credit.services.debit.card import create_debit_card
from exchange.asset_backed_credit.types import DEBIT_FEATURE_FLAG
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import MockCacheValue
from tests.features.utils import BetaFeatureTestMixin


class TestDebitCardOtpVerify(BetaFeatureTestMixin, APITestCase):
    URL = '/asset-backed-credit/debit/cards/otp/verify'

    feature = DEBIT_FEATURE_FLAG

    @classmethod
    def setUpTestData(cls):
        Settings.set('abc_debit_card_creation_enabled', 'yes')
        user, _ = User.objects.get_or_create(username='user')
        internal_user = InternalUser.objects.create(uid=user.uid, user_type=user.user_type)
        Token.objects.create(user=user, key='sample-token')
        service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit, is_active=True, is_available=True
        )
        UserFinancialServiceLimit.set_service_limit(service=service, min_limit=100_000, max_limit=100_000_000)

        cls.nobifi_service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.nobifi, tp=Service.TYPES.debit, is_active=True
        )

        cls.user = user
        cls.internal_user = internal_user
        cls.service = service

    def setUp(self):
        self.client.force_authenticate(user=self.user)
        cache.clear()
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_invalid_pan(self):
        self.request_feature(self.user, 'done')

        data = {'pan': '5678', 'code': '12345'}
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'ParseError'
        assert response.json()['message'] == 'Invalid string value'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_invalid_code(self):
        self.request_feature(self.user, 'done')

        data = {'pan': '5041001100120013', 'code': 'abcde'}
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'ParseError'
        assert response.json()['message'] == 'Invalid string value'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_user_2fa_is_not_activated(self):
        self.request_feature(self.user, 'done')

        data = {'pan': '5041001100120013', 'code': '12345'}
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'UserLevelRestrictionError'
        assert response.json()['message'] == 'User 2FA is not activated.'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_user_not_level_2(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.save()

        data = {'pan': '5041001100120013', 'code': '12345'}
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'UserLevelRestrictionError'
        assert response.json()['message'] == 'User is not level-2'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_user_is_limited(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        UserFinancialServiceLimit.set_user_service_limit(user=self.user, service=self.service, max_limit=0)

        data = {'pan': '5041001100120013', 'code': '12345'}
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'UserLevelRestrictionError'
        assert response.json()['message'] == 'User is restricted to use this service'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_user_is_limited_and_level_3(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.verified
        self.user.save()

        UserFinancialServiceLimit.set_user_service_limit(user=self.user, service=self.service, max_limit=0)

        data = {'pan': '5041001100120013', 'code': '12345'}
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'UserLevelRestrictionError'
        assert response.json()['message'] == 'User is restricted to use this service'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_user_has_no_card(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        data = {'pan': '5041001100120013', 'code': '12345'}
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'UserServiceNotFoundError'
        assert response.json()['message'] == 'User-Service not found'

    @responses.activate
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_user_has_no_issued_card(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=ir_now())
        card = create_debit_card(
            user=self.user,
            internal_user=self.internal_user,
            card_info=CardRequestAPISchema(firstName='john', lastName='doe', birthCertNo='1234', color=1),
        )
        card.status = Card.STATUS.registered
        card.save()

        data = {'pan': '5041001100120013', 'code': '12345'}
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'UserServiceNotFoundError'
        assert response.json()['message'] == 'User-Service not found'

    @responses.activate
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_third_party_response_with_error(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=ir_now())
        card = create_debit_card(
            user=self.user,
            internal_user=self.internal_user,
            card_info=CardRequestAPISchema(firstName='john', lastName='doe', birthCertNo='1234', color=2),
        )
        card.status = Card.STATUS.issued
        card.save()

        responses.post(
            url=DebitCardHashPanAPI.url,
            json={
                'GetHashCardsRequest': {'CardNumber': '5041001100120013', 'HashCode': '5041998899879986'},
                'IsSuccess': True,
                'ErrorCode': None,
                'Message': 'success',
            },
            status=200,
            match=[responses.matchers.json_params_matcher({'CardNumber': '5041001100120013'})],
        )

        responses.post(
            url=DebitCardOTPVerifyAPI.url,
            json={'IsSuccess': False, 'ErrorCode': 'code', 'Message': 'failure'},
            status=200,
            match=[responses.matchers.json_params_matcher({'CardNumberHash': '5041998899879986', 'OTPCode': '12345'})],
        )

        data = {'pan': '5041001100120013', 'code': '12345'}
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'

    @responses.activate
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_success(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=ir_now())
        card = create_debit_card(
            user=self.user,
            internal_user=self.internal_user,
            card_info=CardRequestAPISchema(firstName='john', lastName='doe', birthCertNo='1234', color=3),
        )
        card.status = Card.STATUS.issued
        card.save()

        responses.post(
            url=DebitCardHashPanAPI.url,
            json={
                'GetHashCardsRequest': {'CardNumber': '5041001100120013', 'HashCode': '5041998899879986'},
                'IsSuccess': True,
                'ErrorCode': None,
                'Message': 'success',
            },
            status=200,
            match=[responses.matchers.json_params_matcher({'CardNumber': '5041001100120013'})],
        )

        responses.post(
            url=DebitCardOTPVerifyAPI.url,
            json={'IsSuccess': True, 'ErrorCode': None, 'Message': 'success'},
            status=200,
            match=[responses.matchers.json_params_matcher({'CardNumberHash': '5041998899879986', 'OTPCode': '12345'})],
        )

        data = {'pan': '5041001100120013', 'code': '12345'}
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'

        card.refresh_from_db()
        assert card.pan == '5041001100120013'
        assert card.status == Card.STATUS.verified

    def test_feature_is_not_activated(self):
        resp = self.client.post(path=self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {
            'status': 'failed',
            'code': 'FeatureUnavailable',
            'message': 'abc_debit feature is not available for your user',
        }
