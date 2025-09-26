import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.conf import settings
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import InvalidIPError, InvalidSignatureError
from exchange.asset_backed_credit.models import IncomingAPICallLog, Service, UserFinancialServiceLimit, UserService
from exchange.asset_backed_credit.models.service import UserServicePermission
from exchange.asset_backed_credit.services.price import get_ratios
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider
from exchange.base.calendar import ir_now
from tests.asset_backed_credit.helper import ABCMixins, APIHelper
from tests.base.utils import check_response


class TestUnlockAPI(APIHelper, ABCMixins):
    url = '/asset-backed-credit/v1/unlock'

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.get(pk=201)
        cls.user.national_code = '0921234562'
        cls.user.save()
        cls.provider = SignSupportProvider('tara', ['127.0.0.1'], 1, 1, 'public_key')
        cls.collateral_ratio = get_ratios().get('collateral')

    def setUp(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.service = self.create_service(contract_id='123456')
        self.permission = self.create_user_service_permission(self.user, self.service)
        self.service_limit = UserFinancialServiceLimit.set_service_limit(
            self.service,
            max_limit=10_000_000_0,
        )
        patch(
            'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
            return_value=self.provider,
        ).start()

    def tearDown(self) -> None:
        patch.stopall()

    def unlock(self, data=None):
        return self.client.post(
            path=self.url,
            data=data,
            content_type='application/json',
        )

    @patch('exchange.asset_backed_credit.api.views.api_utils.is_ratelimited', return_value=True)
    def test_unlock_rate_limit_error(self, *_):
        response = self.unlock()
        check_response(
            response=response,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            status_data='failed',
            code='TooManyRequests',
            message='Too many requests',
        )

    def test_unlock_empty_body(self):
        response = self.unlock()
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            status_data='failed',
            code='ValidationError',
            message='Invalid or empty JSON in the request body',
        )

    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        side_effect=InvalidIPError(),
    )
    def test_unlock_not_verified_ip(self, *_):
        response = self.unlock(
            {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
                'trackId': str(uuid.uuid4()),
                'amount': '19230768',
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unlock_missing_signature(self):
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.unlock(request_data)
        expected_result = {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'x-request-signature parameter is required!',
        }
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )
        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_invalid_signature(self, verify_signature_mock):
        verify_signature_mock.side_effect = InvalidSignatureError('The signature is not valid!')
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.unlock(request_data)
        expected_result = {
            'status': 'failed',
            'code': 'AuthorizationError',
            'message': 'The signature is not valid!',
        }
        check_response(
            response=response,
            status_code=status.HTTP_401_UNAUTHORIZED,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )
        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            response_code=status.HTTP_401_UNAUTHORIZED,
            provider=self.provider.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_invalid_json_body(self, *_):
        request_data = {'invalid_json'}
        response = self.unlock(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Invalid or empty JSON in the request body',
        }
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        self.check_incoming_log(
            api_url=self.url,
            request_body=str(request_data),
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_invalid_national_code(self, *_):
        request_data = {
            'nationalCode': '092',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.unlock(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Invalid nationalCode format.',
        }
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_invalid_service_type(self, *_):
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'crediit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.unlock(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'The serviceType is not valid!',
        }
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_service_unavailable(self, *_):
        self.service.delete()
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.unlock(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'ServiceUnavailable',
            'message': 'The service is not currently active',
        }
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_user_not_found(self, _):
        self.user.national_code = ''
        self.user.save()

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.unlock(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'UserNotActivated',
            'message': 'User has not activated',
        }
        check_response(
            response=response,
            status_code=status.HTTP_404_NOT_FOUND,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_404_NOT_FOUND,
            service=self.service.tp,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_zero_amount(self, _):
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '0',
        }

        response = self.unlock(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'The amount must be greater than zero',
        }
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        with pytest.raises(UserService.DoesNotExist):
            UserService.objects.get(user=self.user)

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_400_BAD_REQUEST,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_missing_amount(self, *_):
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
        }

        response = self.unlock(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'The amount is required!',
        }
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        with pytest.raises(UserService.DoesNotExist):
            UserService.objects.get(user=self.user)

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_400_BAD_REQUEST,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_user_service_not_exists(self, *_):
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '1000000',
        }

        response = self.unlock(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'UserServiceUnavailable',
            'message': 'Service is not active for this user',
        }
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        with pytest.raises(UserService.DoesNotExist):
            UserService.objects.get(user=self.user)

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            user=self.user,
            service=self.service.tp,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_permission_user_not_exists(self, *_):
        for _ in [
            UserServicePermission.objects.update(revoked_at=ir_now()),
            UserServicePermission.objects.all().delete(),
        ]:
            request_data = {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
                'trackId': str(uuid.uuid4()),
                'amount': '1000000',
            }
            response = self.unlock(request_data)

            expected_result = {
                'status': 'failed',
                'code': 'UserNotActivated',
                'message': 'User has not activated',
            }
            check_response(
                response=response,
                status_code=status.HTTP_404_NOT_FOUND,
                status_data=expected_result['status'],
                code=expected_result['code'],
                message=expected_result['message'],
            )

            with pytest.raises(UserService.DoesNotExist):
                UserService.objects.get(user=self.user)

            self.check_incoming_log(
                api_url=self.url,
                request_body=request_data,
                response_body=expected_result,
                log_status=1,
                provider=self.provider.id,
                response_code=status.HTTP_404_NOT_FOUND,
                user=self.user,
                service=self.service.tp,
            )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_insufficient_debt(self, *_):
        user_service = self.create_user_service(self.user, initial_debt=100_000_0)

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '1000010',
        }

        response = self.unlock(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'InappropriateAmount',
            'message': 'Requested unblock amount exceeds user balance.',
        }
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        user_service.refresh_from_db()
        assert user_service.current_debt == user_service.initial_debt == 100_000_0
        assert user_service.closed_at is None

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            user=self.user,
            service=self.service.tp,
            user_service=user_service,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_insufficient_debt_duplicate_request(self, *_):
        user_service = self.create_user_service(self.user, initial_debt=100_000_0)

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '1000010',
        }

        response = self.unlock(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'InappropriateAmount',
            'message': 'Requested unblock amount exceeds user balance.',
        }
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        user_service.refresh_from_db()
        assert user_service.current_debt == user_service.initial_debt == 100_000_0
        assert user_service.closed_at is None

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            user=self.user,
            service=self.service.tp,
            user_service=user_service,
        )

        UserService.objects.filter(pk=user_service.pk).update(initial_debt=200_000_0, current_debt=200_000_0)

        log_count = IncomingAPICallLog.objects.count()

        response = self.unlock(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'InappropriateAmount',
            'message': 'Requested unblock amount exceeds user balance.',
        }
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        assert log_count == IncomingAPICallLog.objects.count()

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_insufficient_debt_duplicate_request_different_body(self, *_):
        user_service = self.create_user_service(self.user, initial_debt=100_000_0)

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '1000010',
        }

        response = self.unlock(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'InappropriateAmount',
            'message': 'Requested unblock amount exceeds user balance.',
        }
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        user_service.refresh_from_db()
        assert user_service.current_debt == user_service.initial_debt == 100_000_0
        assert user_service.closed_at is None

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            user=self.user,
            service=self.service.tp,
            user_service=user_service,
        )

        UserService.objects.filter(pk=user_service.pk).update(initial_debt=200_000_0, current_debt=200_000_0)

        log_count = IncomingAPICallLog.objects.count()

        request_data.update({'amount': '1100000'})
        response = self.unlock(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'DuplicateRequestError',
            'message': 'track-id key reused with different payload',
        }
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        assert log_count == IncomingAPICallLog.objects.count()

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_on_closed_but_not_revoked(self, *_):
        self.create_user_service(
            self.user,
            self.service,
            self.permission,
            closed_at=ir_now(),
        )

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '5000000',
        }

        response = self.unlock(request_data)
        expected_result = {
            'status': 'failed',
            'code': 'UserServiceUnavailable',
            'message': 'Service is not active for this user',
        }
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        user_service = UserService.objects.get(user=self.user)
        assert user_service.current_debt != Decimal(request_data['amount'])

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            user=self.user,
            service=self.service.tp,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_on_another_service(self, *_):
        UserServicePermission.objects.all().delete()
        other_service = self.create_service(tp=Service.TYPES.debit)
        self.create_user_service(
            self.user,
            other_service,
            self.create_user_service_permission(self.user, other_service),
            closed_at=ir_now(),
        )

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '50',
        }

        response = self.unlock(request_data)
        expected_result = {
            'status': 'failed',
            'code': 'UserNotActivated',
            'message': 'User has not activated',
        }
        check_response(
            response=response,
            status_code=status.HTTP_404_NOT_FOUND,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        user_service = UserService.objects.get(user=self.user)
        assert user_service.current_debt != Decimal(request_data['amount'])

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_404_NOT_FOUND,
            user=self.user,
            service=self.service.tp,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_unlock_success_partial(self, *_):
        user_service = self.create_user_service(self.user, initial_debt=100_000_0)

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '800000',
        }

        response = self.unlock(request_data)
        expected_result = {
            'status': 'ok',
        }
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data=expected_result['status'],
        )

        user_service.refresh_from_db()
        assert user_service.service == self.service
        assert user_service.closed_at is None
        assert user_service.current_debt == 20_000_0
        assert user_service.initial_debt == 100_000_0
        assert UserService.get_total_active_debt(self.user) == 20_000_0

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=0,
            provider=self.provider.id,
            response_code=status.HTTP_200_OK,
            user=self.user,
            service=self.service.tp,
            user_service=user_service,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_unlock_successful(self, mock_restriction_task, *_):
        user_service = self.create_user_service(self.user, initial_debt=100_000_0)

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '1000000',
        }

        response = self.unlock(request_data)
        expected_result = {
            'status': 'ok',
        }
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data=expected_result['status'],
        )

        user_service.refresh_from_db()
        user_service.user_service_permission.refresh_from_db()
        assert user_service.service == self.service
        assert user_service.closed_at is not None
        assert user_service.current_debt == 0
        assert user_service.initial_debt == 100_000_0
        assert user_service.user_service_permission.revoked_at is not None
        assert UserService.get_total_active_debt(self.user) == 0

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=0,
            provider=self.provider.id,
            response_code=status.HTTP_200_OK,
            user=self.user,
            service=self.service.tp,
            user_service=user_service,
        )
        mock_restriction_task.assert_called_once()

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_unlock_successful_duplicate_request(self, mock_restriction_task, *_):
        user_service = self.create_user_service(self.user, initial_debt=100_000_0)

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '1000000',
        }

        response = self.unlock(request_data)
        expected_result = {
            'status': 'ok',
        }
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data=expected_result['status'],
        )

        user_service.refresh_from_db()
        user_service.user_service_permission.refresh_from_db()
        assert user_service.service == self.service
        assert user_service.closed_at is not None
        assert user_service.current_debt == 0
        assert user_service.initial_debt == 100_000_0
        assert user_service.user_service_permission.revoked_at is not None
        assert UserService.get_total_active_debt(self.user) == 0

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=0,
            provider=self.provider.id,
            response_code=status.HTTP_200_OK,
            user=self.user,
            service=self.service.tp,
            user_service=user_service,
        )
        mock_restriction_task.assert_called_once()

        log_count = IncomingAPICallLog.objects.count()
        mock_restriction_task.reset_mock()

        response = self.unlock(request_data)
        expected_result = {
            'status': 'ok',
        }
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data=expected_result['status'],
        )

        assert log_count == IncomingAPICallLog.objects.count()
        mock_restriction_task.assert_not_called()

        user_service.refresh_from_db()
        user_service.user_service_permission.refresh_from_db()
        assert user_service.service == self.service
        assert user_service.closed_at is not None
        assert user_service.current_debt == 0
        assert user_service.initial_debt == 100_000_0
        assert user_service.user_service_permission.revoked_at is not None
        assert UserService.get_total_active_debt(self.user) == 0

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_unlock_successful_duplicate_request_different_body(self, mock_restriction_task, *_):
        user_service = self.create_user_service(self.user, initial_debt=100_000_0)

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '1000000',
        }

        response = self.unlock(request_data)
        expected_result = {
            'status': 'ok',
        }
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data=expected_result['status'],
        )

        user_service.refresh_from_db()
        user_service.user_service_permission.refresh_from_db()
        assert user_service.service == self.service
        assert user_service.closed_at is not None
        assert user_service.current_debt == 0
        assert user_service.initial_debt == 100_000_0
        assert user_service.user_service_permission.revoked_at is not None
        assert UserService.get_total_active_debt(self.user) == 0

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=0,
            provider=self.provider.id,
            response_code=status.HTTP_200_OK,
            user=self.user,
            service=self.service.tp,
            user_service=user_service,
        )
        mock_restriction_task.assert_called_once()

        log_count = IncomingAPICallLog.objects.count()
        mock_restriction_task.reset_mock()

        request_data.update({'amount': '900000'})
        response = self.unlock(request_data)
        expected_result = {
            'status': 'failed',
            'code': 'DuplicateRequestError',
            'message': 'track-id key reused with different payload',
        }
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        assert log_count == IncomingAPICallLog.objects.count()
        mock_restriction_task.assert_not_called()

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_has_pending_settlement_prevent_unlock(self, *_):
        user_service = self.create_user_service(self.user, initial_debt=100_000_0)
        self.create_settlement(amount='100', user_service=user_service)
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '1000000',
        }

        response = self.unlock(request_data)
        expected_result = {
            'status': 'failed',
            'code': 'SettlementError',
            'message': 'Settlement process is running!',
        }
        check_response(
            response=response,
            status_code=status.HTTP_423_LOCKED,
            status_data=expected_result['status'],
        )

        user_service.refresh_from_db()
        user_service.user_service_permission.refresh_from_db()
        assert user_service.service == self.service
        assert user_service.closed_at is None
        assert user_service.current_debt == 100_000_0
        assert user_service.initial_debt == 100_000_0
        assert user_service.user_service_permission.revoked_at is None

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_423_LOCKED,
            user=self.user,
            service=self.service.tp,
            user_service=user_service,
        )
