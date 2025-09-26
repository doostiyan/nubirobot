from random import choices
from unittest.mock import patch

import responses
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.providers.parsian.api import (
    PARSIAN,
    ParsianAPI,
)
from exchange.asset_backed_credit.models import (
    Card,
    Service,
    UserFinancialServiceLimit,
    UserService,
    UserServicePermission,
)
from exchange.asset_backed_credit.types import DEBIT_FEATURE_FLAG
from exchange.base.calendar import ir_now
from tests.asset_backed_credit.helper import MockCacheValue
from tests.features.utils import BetaFeatureTestMixin


class TestDebitCardSuspendAPI(BetaFeatureTestMixin, APITestCase):
    URL = '/asset-backed-credit/debit/cards/{id}/suspend'

    feature = DEBIT_FEATURE_FLAG

    @classmethod
    def setUpTestData(cls):
        user, _ = User.objects.get_or_create(username='user')
        another_user, _ = User.objects.get_or_create(username='another_user')
        service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit, is_active=True
        )
        UserFinancialServiceLimit.set_service_limit(service=service, min_limit=1_000_000, max_limit=100_000_000)

        cls.user = user
        cls.another_user = another_user
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
    def test_failure_user_2fa_is_not_activated(self):
        self.request_feature(self.user, 'done')

        url = self.URL.format(id=1)
        response = self.client.post(path=url, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'UserLevelRestrictionError'
        assert response.json()['message'] == 'User 2FA is not activated.'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_user_is_not_level2(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.save()

        url = self.URL.format(id=2)
        response = self.client.post(path=url, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'UserLevelRestrictionError'
        assert response.json()['message'] == 'User is not level-2.'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_card_not_found_error(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        url = self.URL.format(id=3)
        response = self.client.post(path=url, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'CardNotFoundError'
        assert response.json()['message'] == 'card not found.'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_card_not_found_error_user_has_card(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        _ = self._create_card(user=self.user)
        another_card = self._create_card(user=self.another_user)

        url = self.URL.format(id=another_card.id)
        response = self.client.post(path=url, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'CardNotFoundError'
        assert response.json()['message'] == 'card not found.'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_card_is_not_active_or_disabled(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        card = self._create_card(user=self.user)
        _ = self._create_card(user=self.another_user)

        url = self.URL.format(id=card.id)
        response = self.client.post(path=url, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'CardInvalidStatusError'
        assert response.json()['message'] == 'card is not active or disabled.'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_service_not_found(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        card = self._create_card(user=self.user, card_status=Card.STATUS.disabled)
        _ = self._create_card(user=self.another_user)

        with patch('exchange.asset_backed_credit.models.service.Service.get_matching_active_service', lambda **_: None):
            url = self.URL.format(id=card.id)
            response = self.client.post(path=url, format='json')

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'ServiceNotFoundError'
        assert response.json()['message'] == 'ServiceNotFoundError'

    @responses.activate
    @patch.object(PARSIAN, 'username', 'test-username')
    @patch.object(PARSIAN, 'password', 'test-password')
    @patch.object(ParsianAPI, 'PARENT_CARD_NUMBER', '100020003004000')
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_third_party_error_bad_request(self):
        self.request_feature(self.user, 'done')

        responses.post(
            url='https://issuer.pec.ir/pec/api/Issuer/SuspendChildCard',
            status=400,
            json={'IsSuccess': False, 'ErrorCode': 22, 'Message': 'Invalid pan.'},
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'ParentCardNumber': '100020003004000',
                        'ChildCardNumber': '6063100020003000',
                        'SuspendIdentifier': 1,
                        'Description': 'درخواست مشتری',
                    },
                ),
                responses.matchers.header_matcher({'Authorization': 'Basic dGVzdC11c2VybmFtZTp0ZXN0LXBhc3N3b3Jk'}),
            ],
        )
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        card = self._create_card(user=self.user, card_status=Card.STATUS.activated, pan='6063100020003000')
        _ = self._create_card(user=self.another_user, card_status=Card.STATUS.activated)

        url = self.URL.format(id=card.id)
        response = self.client.post(path=url, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'ThirdPartyError'
        assert response.json()['message'] == 'failed to suspend card.'

    @responses.activate
    @patch.object(PARSIAN, 'username', 'test-username')
    @patch.object(PARSIAN, 'password', 'test-password')
    @patch.object(ParsianAPI, 'PARENT_CARD_NUMBER', '100020003004000')
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_third_party_error_is_success_false(self):
        self.request_feature(self.user, 'done')

        responses.post(
            url='https://issuer.pec.ir/pec/api/Issuer/SuspendChildCard',
            status=20,
            json={'IsSuccess': False, 'ErrorCode': 4, 'Message': 'دلیل انسداد معتبر نمی‌باشد'},
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'ParentCardNumber': '100020003004000',
                        'ChildCardNumber': '6063100020003000',
                        'SuspendIdentifier': 1,
                        'Description': 'درخواست مشتری',
                    },
                ),
                responses.matchers.header_matcher({'Authorization': 'Basic dGVzdC11c2VybmFtZTp0ZXN0LXBhc3N3b3Jk'}),
            ],
        )
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        card = self._create_card(user=self.user, card_status=Card.STATUS.activated, pan='6063100020003000')
        current_status = card.status
        _ = self._create_card(user=self.another_user, card_status=Card.STATUS.activated)

        url = self.URL.format(id=card.id)
        response = self.client.post(path=url, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'ThirdPartyError'
        assert response.json()['message'] == 'failed to suspend card.'

        card.refresh_from_db()
        assert card.status == current_status

    @responses.activate
    @patch.object(PARSIAN, 'username', 'username')
    @patch.object(PARSIAN, 'password', 'password')
    @patch.object(ParsianAPI, 'PARENT_CARD_NUMBER', '100020003004000')
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_success(self):
        self.request_feature(self.user, 'done')

        responses.post(
            url='https://issuer.pec.ir/pec/api/Issuer/SuspendChildCard',
            status=200,
            json={'IsSuccess': True, 'ErrorCode': None, 'Message': 'Success.'},
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'ParentCardNumber': '100020003004000',
                        'ChildCardNumber': '6063100020003000',
                        'SuspendIdentifier': 1,
                        'Description': 'درخواست مشتری',
                    },
                ),
                responses.matchers.header_matcher({'Authorization': 'Basic dXNlcm5hbWU6cGFzc3dvcmQ='}),
            ],
        )
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        card = self._create_card(user=self.user, card_status=Card.STATUS.activated, pan='6063100020003000')
        _ = self._create_card(user=self.another_user, card_status=Card.STATUS.activated)

        url = self.URL.format(id=card.id)
        response = self.client.post(path=url, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'

        card.refresh_from_db()
        assert card.status == Card.STATUS.suspended

    def test_feature_is_not_activated(self):
        url = self.URL.format(id='10')
        resp = self.client.post(path=url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {
            'status': 'failed',
            'code': 'FeatureUnavailable',
            'message': 'abc_debit feature is not available for your user',
        }

    def _create_card(self, user, card_status=Card.STATUS.requested, pan=None):
        permission = UserServicePermission.objects.create(user=user, service=self.service, created_at=ir_now())
        user_service = UserService.objects.create(
            user=user, user_service_permission=permission, service=self.service, current_debt=1000, initial_debt=1000
        )
        if not pan:
            pan = '6063' + ''.join(choices(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'], k=12))

        return Card.objects.create(user=user, user_service=user_service, status=card_status, pan=pan)
