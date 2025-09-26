import json
import os
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import responses
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import InvalidSignatureError
from exchange.asset_backed_credit.externals.providers import VENCY
from exchange.asset_backed_credit.externals.providers.vency import (
    VENCY_REDIRECT_URL,
    VencyCalculatorAPI,
    VencyGetOrderAPI,
    VencyRenewTokenAPI,
)
from exchange.asset_backed_credit.models import (
    IncomingAPICallLog,
    OutgoingAPICallLog,
    Service,
    UserFinancialServiceLimit,
    UserService,
)
from exchange.asset_backed_credit.services.loan.create import LoanCreateService
from exchange.asset_backed_credit.services.logging import process_abc_outgoing_api_logs
from exchange.asset_backed_credit.services.price import get_ratios
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
from tests.asset_backed_credit.helper import ABCMixins, APIHelper, MockCacheValue, sign_mock
from tests.base.utils import check_response


class TestLockAPI(APIHelper, ABCMixins):
    fixtures = ['test_data']

    @classmethod
    def setUpTestData(cls) -> None:
        cls.url = reverse('abc_lock_url')
        cls.user = User.objects.get(pk=201)
        cls.user.national_code = '0101010109'
        cls.user.birthday = date(year=1993, month=11, day=15)
        cls.user.mobile = '99800000012'
        cls.user.save()
        cls.provider = SignSupportProvider('tara', ['127.0.0.1'], 1, 1, 'public_key')
        cls.vency_provider = SignSupportProvider('vency', ['127.0.0.1'], 3, 3, 'public_key')
        cls.baloan_provider = SignSupportProvider('baloan', ['127.0.0.1'], 6, 6, 'public_key')
        cls.collateral_ratio = get_ratios().get('collateral')

    def setUp(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.service = self.create_service(contract_id='123456')
        self.loan_service = self.create_service(
            provider=Service.PROVIDERS.vency,
            tp=Service.TYPES.loan,
            contract_id='123456789',
        )
        self.permission = self.create_user_service_permission(self.user, self.service)
        self.loan_permission = self.create_user_service_permission(self.user, self.loan_service)
        self.service_limit = UserFinancialServiceLimit.set_service_limit(self.service, max_limit=100_000_000)
        self.loan_service_limit = UserFinancialServiceLimit.set_service_limit(self.loan_service, max_limit=200_000_000)

        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.credit, min_limit=10_000_000)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.loan, min_limit=10_000_000)

        cache.clear()
        self.mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=self.mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=self.mock_cache).start()
        Settings.set_cached_json('scrubber_sensitive_fields', [])

    def tearDown(self):
        cache.clear()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=self.mock_cache
        ).stop()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=self.mock_cache).stop()

    def lock(self, data=None):
        return self.client.post(
            path=self.url,
            data=data,
            content_type='application/json',
        )

    @patch('exchange.asset_backed_credit.api.views.api_utils.is_ratelimited', return_value=True)
    def test_lock_rate_limit_error(self, _):
        response = self.lock()
        check_response(
            response=response,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            status_data='failed',
            code='TooManyRequests',
            message='Too many requests',
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_empty_body(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        response = self.lock()
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            status_data='failed',
            code='ValidationError',
            message='Invalid or empty JSON in the request body',
        )

    def test_lock_not_verified_ip(self):
        response = self.lock(
            {
                'nationalCode': '0101010109',
                'serviceType': 'credit',
                'trackId': str(uuid.uuid4()),
                'amount': '19230768',
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_missing_signature(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.lock(request_data)
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
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_invalid_signature(self, get_provider_mock, verify_signature_mock):
        get_provider_mock.return_value = self.provider
        verify_signature_mock.side_effect = InvalidSignatureError('The signature is not valid!')
        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.lock(request_data)
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
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_invalid_json_body(self, get_provider_mock, _):
        get_provider_mock.return_value = self.provider

        request_data = {'invalid_json'}
        response = self.lock(request_data)

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
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_invalid_national_code(self, get_provider_mock, _):
        get_provider_mock.return_value = self.provider
        request_data = {
            'nationalCode': '092',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.lock(request_data)

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
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_invalid_service_type(self, get_provider_mock, _):
        get_provider_mock.return_value = self.provider
        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'crediit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.lock(request_data)

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
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_service_unavailable(self, get_provider_mock, _):
        self.service.delete()
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.lock(request_data)

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
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_user_not_found(self, get_provider_mock, _):
        self.user.national_code = ''
        self.user.save()
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.lock(request_data)

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
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_zero_amount(self, get_provider_mock, _):
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'debit',
            'trackId': str(uuid.uuid4()),
            'amount': '0',
        }

        response = self.lock(request_data)

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

        with self.assertRaises(UserService.DoesNotExist):
            UserService.objects.get(user=self.user)

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_400_BAD_REQUEST,
        )

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_wrong_minimum_init_debt(self, get_provider_mock, _):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '100',
        }

        response = self.lock(json.dumps(request_data))

        expected_result = {
            'status': 'failed',
            'code': 'MinimumInitialDebtError',
            'message': f'Amount is less than {10_000_000} rls',
        }
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        with self.assertRaises(UserService.DoesNotExist):
            UserService.objects.get(user=self.user)

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            service=self.service.tp,
            user=self.user,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_missing_amount(self, get_provider_mock, _):
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
        }

        response = self.lock(request_data)

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

        with self.assertRaises(UserService.DoesNotExist):
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
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_zero_collateral(self, get_provider_mock, _):
        get_provider_mock.return_value = self.provider
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.credit, min_limit=1000)
        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '1000000',
        }

        response = self.lock(json.dumps(request_data))

        expected_result = {
            'status': 'failed',
            'code': 'InsufficientBalance',
            'message': 'Amount cannot exceed active balance',
        }
        check_response(
            response=response,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        with self.assertRaises(UserService.DoesNotExist):
            UserService.objects.get(user=self.user)

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_402_PAYMENT_REQUIRED,
            user=self.user,
            service=self.service.tp,
        )

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_insufficient_collateral(self, get_provider_mock, _):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '26000000',
        }

        response = self.lock(json.dumps(request_data))

        expected_result = {
            'status': 'failed',
            'code': 'InsufficientBalance',
            'message': 'Amount cannot exceed active balance',
        }
        check_response(
            response=response,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        with self.assertRaises(UserService.DoesNotExist):
            UserService.objects.get(user=self.user)

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_402_PAYMENT_REQUIRED,
            user=self.user,
            service=self.service.tp,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_zero_collateral(self, get_provider_mock, _):
        get_provider_mock.return_value = self.provider
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.credit, min_limit=1000)
        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '1000000',
        }

        response = self.lock(json.dumps(request_data))

        expected_result = {
            'status': 'failed',
            'code': 'InsufficientBalance',
            'message': 'Amount cannot exceed active balance',
        }
        check_response(
            response=response,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        with self.assertRaises(UserService.DoesNotExist):
            UserService.objects.get(user=self.user)

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_402_PAYMENT_REQUIRED,
            user=self.user,
            service=self.service.tp,
        )

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_insufficient_collateral_duplicate_request(self, get_provider_mock, _):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '26000000',
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'failed',
            'code': 'InsufficientBalance',
            'message': 'Amount cannot exceed active balance',
        }
        check_response(
            response=response,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        with self.assertRaises(UserService.DoesNotExist):
            UserService.objects.get(user=self.user)

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_402_PAYMENT_REQUIRED,
            user=self.user,
            service=self.service.tp,
        )

        log_count = IncomingAPICallLog.objects.count()

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'failed',
            'code': 'InsufficientBalance',
            'message': 'Amount cannot exceed active balance',
        }
        check_response(
            response=response,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        assert log_count == IncomingAPICallLog.objects.count()

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_insufficient_collateral_duplicate_request_different_body(self, get_provider_mock, _):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '26000000',
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'failed',
            'code': 'InsufficientBalance',
            'message': 'Amount cannot exceed active balance',
        }
        check_response(
            response=response,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        with self.assertRaises(UserService.DoesNotExist):
            UserService.objects.get(user=self.user)

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_402_PAYMENT_REQUIRED,
            user=self.user,
            service=self.service.tp,
        )

        log_count = IncomingAPICallLog.objects.count()

        request_data.update({'amount': '28000000'})

        response = self.lock(json.dumps(request_data))
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

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_activation_error_duplication(self, get_provider_mock, _):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.credit, min_limit=5_000_000)

        self.create_user_service(
            self.user,
            self.service,
            self.permission,
            current_debt=Decimal('1_000_000_0'),
            initial_debt=Decimal('1_000_000_0'),
        )
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '5000000',
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'failed',
            'code': 'ServiceAlreadyActivated',
            'message': 'Service is already activated.',
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

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_invalid_collateral_ratio_policy(self, get_provider_mock, _):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '25000000',
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'failed',
            'code': 'InsufficientBalance',
            'message': 'Amount cannot exceed active balance',
        }
        check_response(
            response=response,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        with self.assertRaises(UserService.DoesNotExist):
            UserService.objects.get(user=self.user)

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_402_PAYMENT_REQUIRED,
            user=self.user,
            service=self.service.tp,
        )

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_success(self, get_provider_mock, _):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'ok',
        }
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data=expected_result['status'],
        )

        user_service = UserService.objects.get(user=self.user)
        assert user_service.service == self.service
        assert user_service.user == self.user
        assert user_service.internal_user.uid == self.user.uid
        assert user_service.user_service_permission == self.permission
        assert user_service.closed_at is None
        assert user_service.current_debt == Decimal(request_data['amount'])
        assert user_service.initial_debt == Decimal(request_data['amount'])
        assert UserService.get_total_active_debt(self.user) == Decimal(request_data['amount'])

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

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_success_duplicate_request(self, get_provider_mock, _):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'ok',
        }
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data=expected_result['status'],
        )

        user_service = UserService.objects.get(user=self.user)
        assert user_service.service == self.service
        assert user_service.user == self.user
        assert user_service.internal_user.uid == self.user.uid
        assert user_service.user_service_permission == self.permission
        assert user_service.closed_at is None
        assert user_service.current_debt == Decimal(request_data['amount'])
        assert user_service.initial_debt == Decimal(request_data['amount'])
        assert UserService.get_total_active_debt(self.user) == Decimal(request_data['amount'])

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

        log_count = IncomingAPICallLog.objects.count()

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'ok',
        }
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data=expected_result['status'],
        )

        user_service = UserService.objects.get(user=self.user)
        assert user_service.current_debt == Decimal(request_data['amount'])
        assert user_service.initial_debt == Decimal(request_data['amount'])
        assert UserService.get_total_active_debt(self.user) == Decimal(request_data['amount'])

        assert log_count == IncomingAPICallLog.objects.count()

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_success_duplicate_request_different_body(self, get_provider_mock, _):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'ok',
        }
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data=expected_result['status'],
        )

        user_service = UserService.objects.get(user=self.user)
        assert user_service.service == self.service
        assert user_service.user == self.user
        assert user_service.internal_user.uid == self.user.uid
        assert user_service.user_service_permission == self.permission
        assert user_service.closed_at is None
        assert user_service.current_debt == Decimal(request_data['amount'])
        assert user_service.initial_debt == Decimal(request_data['amount'])
        assert UserService.get_total_active_debt(self.user) == Decimal(request_data['amount'])

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

        log_count = IncomingAPICallLog.objects.count()

        request_data.update({'amount': '19000000'})
        response = self.lock(json.dumps(request_data))
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

        user_service = UserService.objects.get(user=self.user)
        amount = Decimal('19230768')
        assert user_service.current_debt == Decimal(amount)
        assert user_service.initial_debt == Decimal(amount)
        assert UserService.get_total_active_debt(self.user) == Decimal(amount)

        assert log_count == IncomingAPICallLog.objects.count()

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_success_int_amount(self, get_provider_mock, _):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': 19230768,
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'ok',
        }
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data=expected_result['status'],
        )

        user_service = UserService.objects.get(user=self.user)
        assert user_service.service == self.service
        assert user_service.user == self.user
        assert user_service.internal_user.uid == self.user.uid
        assert user_service.user_service_permission == self.permission
        assert user_service.closed_at is None
        assert user_service.current_debt == Decimal(request_data['amount'])
        assert user_service.initial_debt == Decimal(request_data['amount'])
        assert UserService.get_total_active_debt(self.user) == Decimal(request_data['amount'])

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

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_user_limit_exceeded(self, get_provider_mock, _):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        get_provider_mock.return_value = self.provider
        UserFinancialServiceLimit.set_user_limit(self.user, max_limit=15000000)
        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'failed',
            'code': 'LimitExceededError',
            'message': 'The user limit exceeded',
        }
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        with self.assertRaises(UserService.DoesNotExist):
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
            user_service=None,
        )

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_user_limit_exceeded_with_another_service(self, get_provider_mock, _):
        get_provider_mock.return_value = self.provider

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('10000'))  # '500_000_000_0' rial

        service2 = self.create_service(tp=Service.TYPES.loan, contract_id='2345')
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.credit, min_limit=500)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.loan, min_limit=500)

        UserFinancialServiceLimit.set_service_limit(service2, max_limit=10_000_000_0)
        UserFinancialServiceLimit.set_user_service_limit(self.user, self.service, max_limit=8_000_000_0)
        UserFinancialServiceLimit.set_user_limit(self.user, max_limit=15_000_000_0)

        permission_service_2 = self.create_user_service_permission(self.user, service2)
        self.create_user_service(
            self.user,
            service2,
            permission_service_2,
            current_debt=Decimal('10_000_000_0'),
            initial_debt=Decimal('10_000_000_0'),
        )
        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': str(Decimal('5_000_000_1')),
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'failed',
            'code': 'LimitExceededError',
            'message': 'The user limit exceeded',
        }
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        with self.assertRaises(UserService.DoesNotExist):
            UserService.objects.get(user=self.user, service=self.service)

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            user=self.user,
            service=self.service.tp,
            user_service=None,
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_loan_success(self, get_provider_mock, *_):
        unique_id = str(uuid.uuid4())

        responses.post(
            url=VencyRenewTokenAPI.url,
            json={
                'access_token': 'ACCESS_TOKEN',
                'expires_in': 599,
                'scope': VencyRenewTokenAPI.SCOPES,
                'token_type': 'Bearer',
            },
            status=200,
            match=[
                responses.matchers.urlencoded_params_matcher(
                    {
                        'grant_type': 'client_credentials',
                        'client_id': VENCY.client_id,
                        'client_secret': VENCY.client_secret,
                        'scope': VencyRenewTokenAPI.SCOPES,
                    }
                ),
            ],
        )

        with open(os.path.join(os.path.dirname(__file__), 'test_data', 'vency_calculator_response_10.json'), 'r') as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': 10_000_000_0})],
        )

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('400'))
        get_provider_mock.return_value = self.vency_provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 10_686_000_0,
            'principal': 10_000_000_0,
            'period': 6,
            'uniqueIdentifier': unique_id,
            'redirectUrl': 'https://gateway.vencytest.ir/main/select/12345',
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'ok',
        }
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data=expected_result['status'],
        )

        user_service = UserService.objects.get(service=self.loan_service, account_number=unique_id)
        assert user_service.user == self.user
        assert user_service.internal_user.uid == self.user.uid
        assert user_service.user_service_permission == self.loan_permission
        assert user_service.closed_at is None
        assert user_service.current_debt == Decimal(10_686_000_0)
        assert user_service.initial_debt == Decimal(10_686_000_0)
        assert UserService.get_total_active_debt(self.user) == Decimal(10_686_000_0)
        assert user_service.installment_amount == Decimal(1_781_000_0)
        assert user_service.account_number == unique_id
        assert user_service.extra_info == {
            'collaboratorLoanPlanId': '488e8dc5-d143-4bec-8229-7fe6cfc4d0c7',
            'loanPrincipalSupplyPlanId': 'd9235dba-8405-4d07-bc24-b8e2244db17e',
            'redirect_url': 'https://gateway.vencytest.ir/main/select/12345',
        }

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=0,
            provider=self.vency_provider.id,
            response_code=status.HTTP_200_OK,
            user=self.user,
            service=self.loan_service.tp,
            user_service=user_service,
        )

        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            api_call_log=OutgoingAPICallLog(
                status=0,
                api_url=VencyCalculatorAPI.url,
                response_code=200,
                provider=VENCY,
            )
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_loan_failure_insufficient_balance(self, get_provider_mock, *_):
        responses.post(
            url=VencyRenewTokenAPI.url,
            json={
                'access_token': 'ACCESS_TOKEN',
                'expires_in': 599,
                'scope': VencyRenewTokenAPI.SCOPES,
                'token_type': 'Bearer',
            },
            status=200,
            match=[
                responses.matchers.urlencoded_params_matcher(
                    {
                        'grant_type': 'client_credentials',
                        'client_id': VENCY.client_id,
                        'client_secret': VENCY.client_secret,
                        'scope': VencyRenewTokenAPI.SCOPES,
                    }
                ),
            ],
        )

        with open(os.path.join(os.path.dirname(__file__), 'test_data', 'vency_calculator_response_10.json'), 'r') as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': 10_000_000_0})],
        )

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('20'))
        get_provider_mock.return_value = self.vency_provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 10_686_000_0,
            'principal': 10_000_000_0,
            'period': 6,
            'uniqueIdentifier': str(uuid.uuid4()),
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'failed',
        }
        check_response(
            response=response,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            status_data=expected_result['status'],
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_loan_failure_calculation_error(self, get_provider_mock, *_):
        responses.post(
            url=VencyRenewTokenAPI.url,
            json={
                'access_token': 'ACCESS_TOKEN',
                'expires_in': 599,
                'scope': VencyRenewTokenAPI.SCOPES,
                'token_type': 'Bearer',
            },
            status=200,
            match=[
                responses.matchers.urlencoded_params_matcher(
                    {
                        'grant_type': 'client_credentials',
                        'client_id': VENCY.client_id,
                        'client_secret': VENCY.client_secret,
                        'scope': VencyRenewTokenAPI.SCOPES,
                    }
                ),
            ],
        )

        with open(os.path.join(os.path.dirname(__file__), 'test_data', 'vency_calculator_response_45.json'), 'r') as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': 5_000_000_0})],
        )

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('200'))
        get_provider_mock.return_value = self.vency_provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 5_500_000_0,
            'principal': 5_000_000_0,
            'period': 6,
            'uniqueIdentifier': str(uuid.uuid4()),
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {'status': 'failed', 'code': 'LoanCalculationError', 'message': 'LoanCalculationError'}
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_loan_success_prevent_duplicate(self, get_provider_mock, *_):
        order_id = str(uuid.uuid4())
        unique_id = str(uuid.uuid4())

        responses.post(
            url=VencyRenewTokenAPI.url,
            json={
                'access_token': 'ACCESS_TOKEN',
                'expires_in': 599,
                'scope': VencyRenewTokenAPI.SCOPES,
                'token_type': 'Bearer',
            },
            status=200,
            match=[
                responses.matchers.urlencoded_params_matcher(
                    {
                        'grant_type': 'client_credentials',
                        'client_id': VENCY.client_id,
                        'client_secret': VENCY.client_secret,
                        'scope': VencyRenewTokenAPI.SCOPES,
                    }
                ),
            ],
        )

        responses.get(
            url=VencyGetOrderAPI.get_url(account_number=unique_id),
            json={
                'orderId': str(order_id),
                'type': 'LENDING',
                'status': 'IN_PROGRESS',
                'uniqueIdentifier': unique_id,
                'createdAt': '2024-08-08T06:01:08.220457Z',
            },
            status=200,
        )

        with open(os.path.join(os.path.dirname(__file__), 'test_data', 'vency_calculator_response_10.json'), 'r') as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': 10_000_000_0})],
        )

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('300'))
        get_provider_mock.return_value = self.vency_provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 10_686_000_0,
            'principal': 10_000_000_0,
            'period': 6,
            'uniqueIdentifier': unique_id,
        }

        response = self.lock(json.dumps(request_data))
        assert response.status_code == status.HTTP_200_OK

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 10_686_000_0,
            'principal': 10_000_000_0,
            'period': 6,
            'uniqueIdentifier': unique_id,
        }

        response = self.lock(json.dumps(request_data))
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        check_response(
            response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ServiceAlreadyActivated',
            message='Service is already activated.',
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_loan_success_from_created_to_initiated_check_debt_once(self, get_provider_mock, *_):
        responses.post(
            url=VencyRenewTokenAPI.url,
            json={
                'access_token': 'ACCESS_TOKEN',
                'expires_in': 599,
                'scope': VencyRenewTokenAPI.SCOPES,
                'token_type': 'Bearer',
            },
            status=200,
            match=[
                responses.matchers.urlencoded_params_matcher(
                    {
                        'grant_type': 'client_credentials',
                        'client_id': VENCY.client_id,
                        'client_secret': VENCY.client_secret,
                        'scope': VencyRenewTokenAPI.SCOPES,
                    }
                ),
            ],
        )

        with open(os.path.join(os.path.dirname(__file__), 'test_data', 'vency_calculator_response_10.json'), 'r') as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': 10_000_000_0})],
        )

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('300'))

        internal_user = self.create_internal_user(self.user)
        unique_id = 'b928e9ce-0782-4583-98aa-2abc045f51cf'
        with patch(
            'exchange.asset_backed_credit.externals.providers.vency.VencyCreateAccountAPI.request',
            lambda *_: {'orderId': '12345', 'redirectUrl': 'test.ccc', 'uniqueIdentifier': unique_id},
        ):
            with patch(
                'exchange.asset_backed_credit.services.loan.create.uuid.uuid4', return_value=uuid.UUID(unique_id)
            ):
                user_service = LoanCreateService(
                    user=self.user,
                    internal_user=internal_user,
                    service=self.loan_service,
                    permission=self.loan_permission,
                    principal=10_000_000_0,
                    period=6,
                ).execute()

        assert user_service.status == UserService.STATUS.created
        assert user_service.account_number == 'b928e9ce-0782-4583-98aa-2abc045f51cf'

        get_provider_mock.return_value = self.vency_provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 10_686_000_0,
            'principal': 10_000_000_0,
            'period': 6,
            'uniqueIdentifier': unique_id,
            'redirectUrl': 'https://gateway.vencytest.ir/main/select/12345',
        }

        response = self.lock(json.dumps(request_data))
        assert response.status_code == status.HTTP_200_OK

        user_service.refresh_from_db()
        assert user_service.status == UserService.STATUS.initiated
        assert user_service.account_number == unique_id
        assert user_service.extra_info['redirect_url'] == 'https://gateway.vencytest.ir/main/select/12345'

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_loan_success_from_created_to_initiated_keep_redirect_url(self, get_provider_mock, *_):
        responses.post(
            url=VencyRenewTokenAPI.url,
            json={
                'access_token': 'ACCESS_TOKEN',
                'expires_in': 599,
                'scope': VencyRenewTokenAPI.SCOPES,
                'token_type': 'Bearer',
            },
            status=200,
            match=[
                responses.matchers.urlencoded_params_matcher(
                    {
                        'grant_type': 'client_credentials',
                        'client_id': VENCY.client_id,
                        'client_secret': VENCY.client_secret,
                        'scope': VencyRenewTokenAPI.SCOPES,
                    }
                ),
            ],
        )

        with open(os.path.join(os.path.dirname(__file__), 'test_data', 'vency_calculator_response_10.json'), 'r') as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': 10_000_000_0})],
        )

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('300'))
        get_provider_mock.return_value = self.vency_provider

        internal_user = self.create_internal_user(self.user)
        unique_id = str(uuid.uuid4())
        with patch('exchange.asset_backed_credit.services.loan.create.uuid.uuid4', return_value=uuid.UUID(unique_id)):
            with patch(
                'exchange.asset_backed_credit.externals.providers.vency.VencyCreateAccountAPI.request',
                lambda _: {
                    'orderId': 'test-order-id',
                    'uniqueIdentifier': unique_id,
                    'redirectUrl': 'test-redirect-url',
                },
            ):
                user_service = LoanCreateService(
                    user=self.user,
                    internal_user=internal_user,
                    service=self.loan_service,
                    permission=self.loan_permission,
                    principal=10_000_000_0,
                    period=6,
                ).execute()

        assert user_service.status == UserService.STATUS.created
        assert user_service.account_number == unique_id
        assert user_service.extra_info['redirect_url'] == 'test-redirect-url'

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 10_686_000_0,
            'principal': 10_000_000_0,
            'period': 6,
            'uniqueIdentifier': unique_id,
            'redirectUrl': 'test-redirect-url-2',
        }

        response = self.lock(json.dumps(request_data))
        assert response.status_code == status.HTTP_200_OK

        user_service.refresh_from_db()
        assert user_service.status == UserService.STATUS.initiated
        assert user_service.account_number == unique_id
        assert user_service.extra_info['redirect_url'] == 'test-redirect-url-2'
        assert user_service.extra_info['loanPrincipalSupplyPlanId'] == 'd9235dba-8405-4d07-bc24-b8e2244db17e'
        assert user_service.extra_info['collaboratorLoanPlanId'] == '488e8dc5-d143-4bec-8229-7fe6cfc4d0c7'

    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_loan_failure_no_value_for_period(self, get_provider_mock, *_):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('300'))
        get_provider_mock.return_value = self.vency_provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 5_000_000_0,
            'principal': 5_000_000_0,
        }

        response = self.lock(json.dumps(request_data))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            code='ParseError',
        )

    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_loan_failure_no_value_for_principal(self, get_provider_mock, *_):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('300'))
        get_provider_mock.return_value = self.vency_provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 5_000_000_0,
            'period': 6,
        }

        response = self.lock(json.dumps(request_data))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            code='ParseError',
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_loan_failure_insufficient_balance_with_unique_id(self, get_provider_mock, *_):
        responses.post(
            url=VencyRenewTokenAPI.url,
            json={
                'access_token': 'ACCESS_TOKEN',
                'expires_in': 599,
                'scope': VencyRenewTokenAPI.SCOPES,
                'token_type': 'Bearer',
            },
            status=200,
            match=[
                responses.matchers.urlencoded_params_matcher(
                    {
                        'grant_type': 'client_credentials',
                        'client_id': VENCY.client_id,
                        'client_secret': VENCY.client_secret,
                        'scope': VencyRenewTokenAPI.SCOPES,
                    }
                ),
            ],
        )

        with open(os.path.join(os.path.dirname(__file__), 'test_data', 'vency_calculator_response_10.json'), 'r') as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': 10_000_000_0})],
        )

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('10'))
        get_provider_mock.return_value = self.vency_provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 10_686_000_0,
            'principal': 10_000_000_0,
            'period': 6,
            'uniqueIdentifier': str(uuid.uuid4()),
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'failed',
        }
        check_response(
            response=response,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            status_data=expected_result['status'],
        )

    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_loan_failure_no_value_for_principal(self, get_provider_mock, *_):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('300'))
        get_provider_mock.return_value = self.vency_provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 5_000_000_0,
            'period': 6,
            'uniqueIdentifier': str(uuid.uuid4()),
        }

        response = self.lock(json.dumps(request_data))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            code='ParseError',
        )

    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_loan_failure_no_value_for_unique_identifier(self, get_provider_mock, *_):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('300'))
        get_provider_mock.return_value = self.vency_provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 5_000_000_0,
            'principal': 3_000_000_0,
            'period': 6,
        }

        response = self.lock(json.dumps(request_data))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            code='ParseError',
        )

    @override_settings(IS_TESTNET=True)
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_loan_dummy_calculator_success(self, get_provider_mock, *_):
        unique_id = str(uuid.uuid4())

        service = self.create_service(
            provider=Service.PROVIDERS.baloan,
            tp=Service.TYPES.loan,
            contract_id='223456789',
        )
        permission = self.create_user_service_permission(self.user, service)
        UserFinancialServiceLimit.set_service_limit(service, max_limit=10_000_000_0)

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('200'))
        get_provider_mock.return_value = self.baloan_provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 6_000_000_0,
            'principal': 5_000_000_0,
            'period': 6,
            'uniqueIdentifier': unique_id,
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            'status': 'ok',
        }
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data=expected_result['status'],
        )

        user_service = UserService.objects.get(service=service, account_number=unique_id)
        assert user_service.user == self.user
        assert user_service.internal_user.uid == self.user.uid
        assert user_service.user_service_permission == permission
        assert user_service.closed_at is None
        assert user_service.current_debt == Decimal(6_000_000_0)
        assert user_service.initial_debt == Decimal(6_000_000_0)
        assert UserService.get_total_active_debt(self.user) == Decimal(6_000_000_0)
        assert user_service.installment_amount == Decimal(1_000_000_0)

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=0,
            provider=self.baloan_provider.id,
            response_code=status.HTTP_200_OK,
            user=self.user,
            service=service.tp,
            user_service=user_service,
        )

    @override_settings(IS_PROD=True)
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_loan_dummy_calculator_failure(self, get_provider_mock, *_):
        unique_id = str(uuid.uuid4())

        service = self.create_service(
            provider=Service.PROVIDERS.baloan,
            tp=Service.TYPES.loan,
            contract_id='223456789',
        )
        self.create_user_service_permission(self.user, service)
        UserFinancialServiceLimit.set_service_limit(service, max_limit=10_000_000_0)

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('200'))
        get_provider_mock.return_value = self.baloan_provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'loan',
            'trackId': str(uuid.uuid4()),
            'amount': 6_000_000_0,
            'principal': 5_000_000_0,
            'period': 6,
            'uniqueIdentifier': unique_id,
        }

        response = self.lock(json.dumps(request_data))
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_with_user_not_having_service_permission(self, get_provider_mock, _):
        self.permission.revoked_at = ir_now()
        self.permission.save()

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            "status": "failed",
            "code": "UserNotActivated",
            "message": "User has not activated",
        }
        check_response(response=response, status_code=status.HTTP_404_NOT_FOUND, code='UserNotActivated')

        user_service = UserService.objects.filter(user=self.user).first()
        assert user_service is None

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_404_NOT_FOUND,
            user=self.user,
            service=self.service.tp,
            user_service=None,
        )

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_lock_with_inactive_service(self, get_provider_mock, _):
        self.service.is_active = False
        self.service.save()

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0101010109',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }

        response = self.lock(json.dumps(request_data))
        expected_result = {
            "status": "failed",
            "code": "ServiceUnavailable",
            "message": "The service is not currently active",
        }
        check_response(response=response, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, code='ServiceUnavailable')

        user_service = UserService.objects.filter(user=self.user).first()
        assert user_service is None

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            user=None,
            service=None,
            user_service=None,
        )
