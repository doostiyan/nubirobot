from decimal import ROUND_DOWN, Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import override_settings

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import InvalidSignatureError
from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit
from exchange.asset_backed_credit.services.price import get_ratios
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider
from exchange.base.models import Currencies, Settings
from tests.asset_backed_credit.helper import ABCMixins, APIHelper
from tests.base.utils import check_response


@patch('exchange.wallet.estimator.PriceEstimator.get_price_range', lambda *_: (10_000, _))
class TestEstimateAPI(APIHelper, ABCMixins):
    fixtures = ['test_data']

    @classmethod
    def setUpTestData(cls) -> None:
        cls.url = reverse('abc_estimate_url')
        cls.user = User.objects.get(pk=201)
        cls.user.national_code = '0921234562'
        cls.user.save()
        cls.provider = SignSupportProvider('tara', ['127.0.0.1'], 1, 910, 'public_key')
        cls.collateral_ratio = get_ratios().get('collateral')

    def setUp(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.service = self.create_service(contract_id='123456')
        self.permission = self.create_user_service_permission(self.user, self.service)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.credit, min_limit=500_000)
        self.service_limit = UserFinancialServiceLimit.set_service_limit(self.service, max_limit=10_000_000)

    def estimate(self, data=None):
        return self.client.post(
            path=self.url,
            data=data,
            content_type='application/json',
        )

    @patch('exchange.asset_backed_credit.api.views.api_utils.is_ratelimited', return_value=True)
    def test_estimate_rate_limit_error(self, rate_limit_mock):
        response = self.estimate()
        check_response(
            response=response,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            status_data='failed',
            code='TooManyRequests',
            message='Too many requests',
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider')
    def test_estimate_empty_body(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        response = self.estimate()
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            status_data='failed',
            code='ValidationError',
            message='Invalid or empty JSON in the request body',
        )

    def test_estimate_not_verified_ip(self):
        response = self.estimate(
            {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
            }
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @override_settings(IS_TESTNET=True)
    def test_estimate_not_verified_ip_testnet(self):
        Settings.set_cached_json('abc_test_net_providers', {1: ['127.0.0.3'], 2: ['127.0.0.4']})
        response = self.estimate(
            {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        Settings.set_cached_json('abc_test_net_providers', {1: ['127.0.0.1']})
        response = self.estimate(
            {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
            },
        )
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

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider')
    def test_estimate_missing_signature(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
        }
        response = self.estimate(request_data)
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
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_invalid_signature(self, verify_signature, get_provider_mock):
        get_provider_mock.return_value = self.provider
        verify_signature.side_effect = InvalidSignatureError('The signature is not valid!')
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
        }
        response = self.estimate(request_data)
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
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            response_code=status.HTTP_401_UNAUTHORIZED,
            provider=self.provider.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_invalid_json_body(self, _, get_provider_mock):
        get_provider_mock.return_value = self.provider

        request_data = {'invalid_json'}
        response = self.estimate(request_data)

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
            request_body=str(request_data),
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_invalid_national_code(self, _, get_provider_mock):
        get_provider_mock.return_value = self.provider
        request_data = {
            'nationalCode': '092',
            'serviceType': 'credit',
        }
        response = self.estimate(request_data)

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
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_invalid_national_code_invalid_digits(self, _, get_provider_mock):
        get_provider_mock.return_value = self.provider
        request_data = {
            'nationalCode': '0101010101',
            'serviceType': 'credit',
        }
        response = self.estimate(request_data)

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
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_invalid_service_type(self, _, get_provider_mock):
        get_provider_mock.return_value = self.provider
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'crediit',
        }
        response = self.estimate(request_data)

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
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_has_another_active_service(self, _, get_provider_mock):
        self.create_user_service(
            self.user,
            self.service,
            self.permission,
            current_debt=Decimal('1_000_000_0'),
            initial_debt=Decimal('1_000_000_0'),
        )
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
        }
        response = self.estimate(request_data)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        expected_data = {'status': 'ok', 'amount': '0', 'total_debt': '10000000'}
        assert data == expected_data

        self.check_incoming_log(
            request_body=request_data,
            response_body=expected_data,
            log_status=0,
            provider=self.provider.id,
            response_code=status.HTTP_200_OK,
            user=self.user,
            service=self.service.tp,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_service_unavailable(self, _, get_provider_mock):
        self.service.delete()
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
        }
        response = self.estimate(request_data)

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
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            service=None,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_user_not_found(self, _, get_provider_mock):
        self.user.national_code = ''
        self.user.save()
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
        }
        response = self.estimate(request_data)

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
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_404_NOT_FOUND,
            service=self.service.tp,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_user_permission_not_found(self, _, get_provider_mock):
        self.permission.delete()
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
        }
        response = self.estimate(request_data)

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
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_404_NOT_FOUND,
            service=self.service.tp,
            user=self.user,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_service_limit_not_defined(self, _, get_provider_mock):
        self.service_limit.delete()
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
        }
        response = self.estimate(request_data)

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
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=self.provider.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            service=self.service.tp,
            user=self.user,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_not_collateral(self, _, get_provider_mock):
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
        }
        response = self.estimate(request_data)

        assert response.status_code == status.HTTP_200_OK
        expected_data = {'status': 'ok', 'amount': '0', 'total_debt': '0'}
        assert response.json() == expected_data

        self.check_incoming_log(
            request_body=request_data,
            response_body=expected_data,
            log_status=0,
            provider=self.provider.id,
            response_code=status.HTTP_200_OK,
            service=self.service.tp,
            user=self.user,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_more_collateral(self, _, get_provider_mock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('10_000_000_0'))
        self.set_usdt_mark_price(Decimal('10_000'))
        get_provider_mock.return_value = self.provider

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
        }
        response = self.estimate(request_data)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        expected_data = {'status': 'ok', 'amount': '10000000', 'total_debt': '0'}
        assert data == expected_data

        self.check_incoming_log(
            request_body=request_data,
            response_body=expected_data,
            log_status=0,
            provider=self.provider.id,
            response_code=status.HTTP_200_OK,
            service=self.service.tp,
            user=self.user,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_just_collateral(self, _, get_provider_mock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('90'))
        self.set_usdt_mark_price(Decimal('10_000'))
        get_provider_mock.return_value = self.provider
        response = self.estimate(
            {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
            }
        )

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        expected_data = {
            'status': 'ok',
            'amount': str(((90 * 10000) / self.collateral_ratio).quantize(Decimal('1'), ROUND_DOWN)),
            'total_debt': '0',
        }
        assert data == expected_data

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_zero_available_collateral_has_service(self, _, get_provider_mock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('90'))
        self.set_usdt_mark_price(Decimal('10_000'))
        self.create_user_service(
            user=self.user,
            service=self.service,
            permission=self.permission,
            current_debt=Decimal('1_000_000_0'),
            initial_debt=Decimal('1_000_000_0'),
        )
        get_provider_mock.return_value = self.provider
        response = self.estimate(
            {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
            }
        )
        expected_data = {'status': 'ok', 'amount': '0', 'total_debt': '10000000'}

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected_data

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_zero_available_collateral_has_other_service(self, _, get_provider_mock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('90'))
        self.set_usdt_mark_price(Decimal('10_000'))
        self.create_user_service(
            user=self.user,
            service=self.create_service(tp=Service.TYPES.debit, contract_id='123456'),
            permission=self.permission,
            current_debt=Decimal('1_000_000_0'),
            initial_debt=Decimal('1_000_000_0'),
        )
        get_provider_mock.return_value = self.provider
        response = self.estimate(
            {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
            }
        )
        expected_data = {'status': 'ok', 'amount': '0', 'total_debt': '0'}

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected_data

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_user_limit(self, _, get_provider_mock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100_000_000_0'))
        self.set_usdt_mark_price(Decimal('10_000'))
        UserFinancialServiceLimit.set_user_limit(self.user, max_limit=500_000_0)
        get_provider_mock.return_value = self.provider
        response = self.estimate(
            {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
            }
        )
        expected_data = {'status': 'ok', 'amount': '5000000', 'total_debt': '0'}

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected_data

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_user_service_limit(self, _, get_provider_mock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100_000_000_0'))
        self.set_usdt_mark_price(Decimal('10_000'))
        UserFinancialServiceLimit.set_user_limit(self.user, max_limit=500_000_0)
        UserFinancialServiceLimit.set_user_service_limit(self.user, self.service, max_limit=400_000_0)
        get_provider_mock.return_value = self.provider
        response = self.estimate(
            {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
            }
        )
        expected_data = {'status': 'ok', 'amount': '4000000', 'total_debt': '0'}

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected_data

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_user_type_service_limit(self, _, get_provider_mock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100_000_000_0'))
        self.set_usdt_mark_price(Decimal('10_000'))
        UserFinancialServiceLimit.set_user_limit(self.user, max_limit=500_000_0)
        UserFinancialServiceLimit.set_user_service_limit(self.user, self.service, max_limit=400_000_0)
        UserFinancialServiceLimit.set_user_type_service_limit(
            user_type=self.user.user_type,
            service=self.service,
            max_limit=300_000_0,
        )
        get_provider_mock.return_value = self.provider
        response = self.estimate(
            {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
            }
        )
        expected_data = {'status': 'ok', 'amount': '4000000', 'total_debt': '0'}

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected_data

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_available_collateral_and_debt_has_other_service(self, _, get_provider_mock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('2834'))
        self.set_usdt_mark_price(Decimal('10_000'))
        self.create_user_service(
            user=self.user,
            service=self.create_service(tp=Service.TYPES.debit, contract_id='123456'),
            permission=self.permission,
            current_debt=Decimal('1_300_000_0'),
            initial_debt=Decimal('1_300_000_0'),
        )
        get_provider_mock.return_value = self.provider
        response = self.estimate(
            {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
            }
        )
        expected_data = {'status': 'ok', 'amount': '8800000', 'total_debt': '0'}

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected_data

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    def test_estimate_available_collateral_and_debt_has_service(self, _, get_provider_mock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('2834'))
        self.set_usdt_mark_price(Decimal('10_000'))
        self.create_user_service(
            user=self.user,
            service=self.service,
            permission=self.permission,
            current_debt=Decimal('1_300_000_0'),
            initial_debt=Decimal('1_300_000_0'),
        )
        get_provider_mock.return_value = self.provider
        response = self.estimate(
            {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
            }
        )
        expected_data = {'status': 'ok', 'amount': '8800000', 'total_debt': '13000000'}

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected_data
