import uuid
from unittest.mock import patch

from django.test import override_settings
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Card, CardSetting, Service, UserService, UserServicePermission
from exchange.asset_backed_credit.types import DEBIT_FEATURE_FLAG
from exchange.base.calendar import ir_now
from exchange.base.internal.services import Services
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import ABCMixins, APIHelper
from tests.features.utils import BetaFeatureTestMixin
from tests.helpers import APITestCaseWithIdempotency, create_internal_token, mock_internal_service_settings


class DebitCardEnableInternalViewTest(APIHelper, ABCMixins, APITestCaseWithIdempotency):
    URL = '/internal/asset-backed-credit/debit/cards/enable'

    @classmethod
    def setUpTestData(cls) -> None:
        Settings.set('abc_debit_card_creation_enabled', 'yes')
        cls.user = User.objects.get(pk=201)
        cls.user.user_type = User.USER_TYPES.level1
        cls.user.mobile = '09120000000'
        cls.user.national_code = '0010000000'
        cls.user.first_name = 'Siavash'
        cls.user.last_name = 'Kavousi'
        cls.user.save(update_fields=('user_type', 'mobile', 'national_code', 'first_name', 'last_name'))

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ADMIN.value)}')
        self.internal_user = self.create_internal_user(self.user)

    def _add_user_eligibility(self):
        self._add_user_mobile_confirmed()
        self._add_user_level1_confirmed()

    def _add_user_mobile_confirmed(self):
        self._change_parameters_in_object(
            self.user.get_verification_profile(),
            {'mobile_identity_confirmed': True},
        )

    def _add_user_level1_confirmed(self):
        self._change_parameters_in_object(
            self.user.get_verification_profile(),
            {'mobile_confirmed': True, 'identity_confirmed': True},
        )

    @override_settings(RATELIMIT_ENABLE=True)
    @mock_internal_service_settings
    def test_ratelimit_error(self):
        for _ in range(4):
            response = self.client.post(path=self.URL, data=None, content_type='application/json', headers={})

        assert response.status_code == 429
        assert response.json() == {
            'status': 'failed',
            'message': 'تعداد درخواست شما بیش از حد معمول تشخیص داده شده. لطفا کمی صبر نمایید.',
            'code': 'TooManyRequests',
        }

    @mock_internal_service_settings
    def test_no_data_error(self):
        self._add_user_eligibility()
        self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        response = self.client.post(path=self.URL, data={'data': []}, content_type='application/json', headers={})

        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_400_BAD_REQUEST,
            code='ParseError',
            message='Missing list value',
        )
        assert not UserService.objects.all().exists()
        assert not Card.objects.all().exists()

    @mock_internal_service_settings
    def test_no_user_id_error(self):
        response = self.client.post(
            path=self.URL, data={'data': [{'pan': '5041721000001111'}]}, content_type='application/json', headers={}
        )
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_400_BAD_REQUEST,
            code='ParseError',
            message='Missing uuid value',
        )
        assert not UserService.objects.all().exists()
        assert not Card.objects.all().exists()

    @mock_internal_service_settings
    def test_no_pan_error(self):
        response = self.client.post(
            path=self.URL, data={'data': [{'userId': str(self.user.uid)}]}, content_type='application/json', headers={}
        )
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_400_BAD_REQUEST,
            code='ParseError',
            message='Missing string value',
        )
        assert not UserService.objects.all().exists()
        assert not Card.objects.all().exists()

    @mock_internal_service_settings
    def test_data_too_large_error(self):
        self._add_user_eligibility()
        self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        response = self.client.post(
            path=self.URL,
            data={'data': [{'userId': str(self.user.uid), 'pan': '6037991810102020'} for _ in range(1001)]},
            content_type='application/json',
            headers={},
        )
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_400_BAD_REQUEST,
            code='ParseError',
            message='data is too large',
        )
        assert not UserService.objects.all().exists()
        assert not Card.objects.all().exists()

    @mock_internal_service_settings
    def test_user_not_found_error(self):
        response = self.client.post(
            path=self.URL,
            data={'data': [{'userId': str(uuid.uuid4()), 'pan': '6037991810102020'}]},
            content_type='application/json',
            headers={},
        )
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='UserNotFound',
            message='User not found! invalid user_id',
        )
        assert not UserService.objects.all().exists()
        assert not Card.objects.all().exists()

    @mock_internal_service_settings
    def test_user_is_not_verified_error(self):
        response = self.client.post(
            path=self.URL,
            data={'data': [{'userId': str(self.user.uid), 'pan': '6037991810102020'}]},
            content_type='application/json',
            headers={},
        )
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_400_BAD_REQUEST,
            code='UserLevelRestriction',
            message='User is not verified as level 1.',
        )

        assert not UserService.objects.all().exists()
        assert not Card.objects.all().exists()

    @mock_internal_service_settings
    def test_user_has_no_confirmed_mobile_error(self):
        self._add_user_level1_confirmed()
        response = self.client.post(
            path=self.URL,
            data={'data': [{'userId': str(self.user.uid), 'pan': '6037991810102020'}]},
            content_type='application/json',
            headers={},
        )
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_400_BAD_REQUEST,
            code='UserLevelRestriction',
            message='User has no confirmed mobile number.',
        )
        assert not UserService.objects.all().exists()
        assert not Card.objects.all().exists()

    @mock_internal_service_settings
    def test_service_not_found_error(self):
        self._add_user_eligibility()
        response = self.client.post(
            path=self.URL,
            data={'data': [{'userId': str(self.user.uid), 'pan': '6037991810102020'}]},
            content_type='application/json',
            headers={},
        )
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ServiceNotFoundError',
            message='No active debit service found!',
        )
        assert not UserService.objects.all().exists()
        assert not Card.objects.all().exists()

    @mock_internal_service_settings
    def test_service_already_activated_error(self):
        self._add_user_eligibility()
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.create_user_service(user=self.user, service=service)
        response = self.client.post(
            path=self.URL,
            data={'data': [{'userId': str(self.user.uid), 'pan': '6037991810102020'}]},
            content_type='application/json',
            headers={},
        )
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ServiceAlreadyActivated',
        )

    @mock_internal_service_settings
    def test_card_already_exists_error(self):
        pan = '6037991810102020'
        self._add_user_eligibility()
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        user_service = self.create_user_service(user=self.user, service=service)
        self.create_card(pan=pan, user_service=user_service)
        response = self.client.post(
            path=self.URL,
            data={'data': [{'userId': str(self.user.uid), 'pan': pan}]},
            content_type='application/json',
            headers={},
        )
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='CardAlreadyExists',
        )

    @mock_internal_service_settings
    def test_success(self):
        default_setting = self.create_card_setting(level=CardSetting.DEFAULT_CARD_LEVEL)
        self._add_user_eligibility()
        self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        pan = '6037991810102020'
        response = self.client.post(
            path=self.URL,
            data={'data': [{'userId': str(self.user.uid), 'pan': pan}]},
            content_type='application/json',
            headers={},
        )
        self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )

        user_service = UserService.objects.filter(user=self.user).first()
        assert user_service is not None
        assert user_service.account_number == ''

        user_service_permission = user_service.user_service_permission
        assert user_service_permission is not None
        assert user_service_permission.created_at is not None

        card = Card.objects.filter(pan=pan, user=self.user).first()
        assert card is not None
        assert card.user_service == user_service
        assert card.status == card.STATUS.activated
        assert card.setting == default_setting

    @mock_internal_service_settings
    def test_use_existing_user_service_permission_success(self):
        self._add_user_eligibility()
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        pan = '6037991810102020'

        user_service_permission_1 = UserServicePermission.objects.create(
            user=self.user, service=service, created_at=ir_now()
        )
        UserServicePermission.objects.create(user=self.user, service=service, created_at=ir_now(), revoked_at=ir_now())

        response = self.client.post(
            path=self.URL,
            data={'data': [{'userId': str(self.user.uid), 'pan': pan}]},
            content_type='application/json',
            headers={},
        )
        self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )

        user_service = UserService.objects.filter(user=self.user).first()
        assert user_service is not None
        assert user_service.account_number == ''

        card = Card.objects.filter(pan=pan, user=self.user).first()
        assert card is not None
        assert card.user_service == user_service
        assert card.status == card.STATUS.activated

        user_service_permission_2 = user_service.user_service_permission
        assert user_service_permission_2 is not None
        assert user_service_permission_2.created_at is not None
        assert user_service_permission_2.id == user_service_permission_1.id

    @mock_internal_service_settings
    def test_enable_api_fails_when_when_card_creation_flag_is_not_enabled(self):
        Settings.set('abc_debit_card_creation_enabled', 'no')
        self._add_user_eligibility()
        self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        pan = '6037991810102020'
        response = self.client.post(
            path=self.URL,
            data={'data': [{'userId': str(self.user.uid), 'pan': pan}]},
            content_type='application/json',
            headers={},
        )
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='DebitCardCreationServiceTemporaryUnavailable',
        )


@patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
@patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
class DebitCardActivateView(BetaFeatureTestMixin, APIHelper, ABCMixins):
    URL = '/asset-backed-credit/debit/cards/{id}/activate'

    feature = DEBIT_FEATURE_FLAG

    def setUp(self) -> None:
        self.user = self.create_user()
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()
        self.client.force_authenticate(user=self.user)

    def test_feature_is_not_activated(self):
        response = self.client.post(path=self.URL.format(id=1), format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'status': 'failed',
            'code': 'FeatureUnavailable',
            'message': 'abc_debit feature is not available for your user',
        }

    def test_failure_user_2fa_is_not_activated(self):
        self.user.requires_2fa = False
        self.user.save()
        self.request_feature(self.user, 'done')

        url = self.URL.format(id=1)
        response = self.client.post(path=url, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'UserLevelRestrictionError'
        assert response.json()['message'] == 'User 2FA is not activated.'

    def test_failure_user_is_not_level2(self):
        self.user.user_type = User.USER_TYPES.level1
        self.user.save()
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.save()

        url = self.URL.format(id=2)
        response = self.client.post(path=url, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'UserLevelRestrictionError'
        assert response.json()['message'] == 'User is not level-2.'

    def test_success(self):
        self.request_feature(self.user, 'done')

        pan = '6063909010102323'
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        user_service = self.create_user_service(user=self.user, service=service)
        card = self.create_card(pan=pan, user_service=user_service, status=Card.STATUS.disabled)

        response = self.client.post(path=self.URL.format(id=card.id))

        self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )

        card = Card.objects.filter(user=self.user, id=card.id).first()
        assert card.status == Card.STATUS.activated

    def test_registered_status_card_not_found_error(self):
        self.request_feature(self.user, 'done')

        pan = '6063909010102323'
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        user_service = self.create_user_service(user=self.user, service=service)
        card = self.create_card(pan=pan, user_service=user_service, status=Card.STATUS.registered)

        response = self.client.post(path=self.URL.format(id=card.id))

        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='CardInvalidStatus',
            message='Card status is invalid!',
        )

        card = Card.objects.filter(user=self.user, id=card.id).first()
        assert card.status == Card.STATUS.registered

    def test_expired_status_card_not_found_error(self):
        self.request_feature(self.user, 'done')

        pan = '6063909010102323'
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        user_service = self.create_user_service(user=self.user, service=service)
        card = self.create_card(pan=pan, user_service=user_service, status=Card.STATUS.expired)

        response = self.client.post(path=self.URL.format(id=card.id))

        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='CardInvalidStatus',
            message='Card status is invalid!',
        )

        card = Card.objects.filter(user=self.user, id=card.id).first()
        assert card.status == Card.STATUS.expired

    def test_issued_card_does_not_belong_to_user_error(self):
        self.request_feature(self.user, 'done')

        pan = '6063909010102323'
        user = User.objects.get(pk=202)
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        user_service = self.create_user_service(user=user, service=service)
        card = self.create_card(pan=pan, user_service=user_service)

        response = self.client.post(path=self.URL.format(id=card.id))

        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='CardNotFound',
            message='card not found.',
        )

        card = Card.objects.filter(user=user, id=card.id).first()
        assert card.status == Card.STATUS.activated


@patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
@patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
class DebitCardDisableView(BetaFeatureTestMixin, APIHelper, ABCMixins):
    URL = '/asset-backed-credit/debit/cards/{id}/disable'

    feature = DEBIT_FEATURE_FLAG

    def setUp(self) -> None:
        self.user = self.create_user()
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()
        self.client.force_authenticate(user=self.user)

    def test_feature_is_not_activated(self):
        response = self.client.post(path=self.URL.format(id=1), format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'status': 'failed',
            'code': 'FeatureUnavailable',
            'message': 'abc_debit feature is not available for your user',
        }

    def test_failure_user_2fa_is_not_activated(self):
        self.user.requires_2fa = False
        self.user.save()
        self.request_feature(self.user, 'done')

        url = self.URL.format(id=1)
        response = self.client.post(path=url, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'UserLevelRestrictionError'
        assert response.json()['message'] == 'User 2FA is not activated.'

    def test_failure_user_is_not_level2(self):
        self.user.user_type = User.USER_TYPES.level1
        self.user.save()
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.save()

        url = self.URL.format(id=2)
        response = self.client.post(path=url, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'UserLevelRestrictionError'
        assert response.json()['message'] == 'User is not level-2.'

    def test_success(self):
        self.request_feature(self.user, 'done')

        pan = '6063909010102323'
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        user_service = self.create_user_service(user=self.user, service=service)
        card = self.create_card(pan=pan, user_service=user_service)

        response = self.client.post(path=self.URL.format(id=card.id))

        self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )

        card = Card.objects.filter(user=self.user, id=card.id).first()
        assert card.status == Card.STATUS.disabled

    def test_registered_status_card_not_found_error(self):
        self.request_feature(self.user, 'done')

        pan = '6063909010102323'
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        user_service = self.create_user_service(user=self.user, service=service)
        card = self.create_card(pan=pan, user_service=user_service, status=Card.STATUS.registered)

        response = self.client.post(path=self.URL.format(id=card.id))

        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='CardInvalidStatus',
            message='Card status is invalid!',
        )

        card = Card.objects.filter(user=self.user, id=card.id).first()
        assert card.status == Card.STATUS.registered

    def test_expired_status_card_not_found_error(self):
        self.request_feature(self.user, 'done')

        pan = '6063909010102323'
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        user_service = self.create_user_service(user=self.user, service=service)
        card = self.create_card(pan=pan, user_service=user_service, status=Card.STATUS.expired)

        response = self.client.post(path=self.URL.format(id=card.id))

        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='CardInvalidStatus',
            message='Card status is invalid!',
        )

        card = Card.objects.filter(user=self.user, id=card.id).first()
        assert card.status == Card.STATUS.expired

    def test_issued_card_does_not_belong_to_user_error(self):
        self.request_feature(self.user, 'done')

        pan = '6063909010102323'
        user = User.objects.get(pk=202)
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        user_service = self.create_user_service(user=user, service=service)
        card = self.create_card(pan=pan, user_service=user_service)

        response = self.client.post(path=self.URL.format(id=card.id))

        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='CardNotFound',
            message='card not found.',
        )

        card = Card.objects.filter(user=user, id=card.id).first()
        assert card.status == Card.STATUS.activated
