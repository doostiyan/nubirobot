import uuid
from unittest.mock import patch

import pytest
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import InvalidSignatureError
from exchange.asset_backed_credit.models import Service, SettlementTransaction, UserFinancialServiceLimit, UserService
from exchange.asset_backed_credit.services.price import get_ratios
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider
from exchange.base.calendar import ir_now
from tests.asset_backed_credit.helper import ABCMixins, APIHelper
from tests.base.utils import check_response

SAMPLE_TARA = SignSupportProvider('tara', ['127.0.0.1'], 1, 1, 'public_key')


@patch('exchange.asset_backed_credit.externals.price.PriceProvider.get_mark_price', lambda *_: 50_000_0)
class TestSettlementExternalAPI(APIHelper, ABCMixins):
    fixtures = ['test_data']

    @classmethod
    def setUpTestData(cls) -> None:
        cls.url = '/asset-backed-credit/v1/settlement'
        cls.user = User.objects.get(pk=201)
        cls.user.national_code = '0921234562'
        cls.user.save()
        cls.collateral_ratio = get_ratios().get('collateral')

    def setUp(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.service = self.create_service(contract_id='123456', tp=Service.TYPES.credit)
        self.permission = self.create_user_service_permission(self.user, self.service)
        self.service_limit = UserFinancialServiceLimit.set_service_limit(self.service, max_limit=10_000_000_0)

    def settlement(self, data=None):
        return self.client.post(
            path=self.url,
            data=data,
            content_type='application/json',
        )

    @patch('exchange.asset_backed_credit.api.views.api_utils.is_ratelimited', return_value=True)
    def test_rate_limit_error(self, _):
        response = self.settlement()
        check_response(
            response=response,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            status_data='failed',
            code='TooManyRequests',
            message='Too many requests',
        )

    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    def test_empty_body(self, _):
        response = self.settlement()
        check_response(
            response=response,
            status_code=status.HTTP_400_BAD_REQUEST,
            status_data='failed',
            code='ValidationError',
            message='Invalid or empty JSON in the request body',
        )

    def test_not_verified_ip(self):
        response = self.settlement(
            {
                'nationalCode': '0921234562',
                'serviceType': 'credit',
                'trackId': str(uuid.uuid4()),
                'amount': '19230768',
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider',
        return_value=SAMPLE_TARA,
    )
    def test_missing_signature(self, _):
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.settlement(request_data)
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
            provider=SAMPLE_TARA.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    def test_invalid_signature(self, _, verify_signature_mock):
        verify_signature_mock.side_effect = InvalidSignatureError('The signature is not valid!')
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.settlement(request_data)
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
            provider=SAMPLE_TARA.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    def test_invalid_json_body(self, *_):
        request_data = {'invalid_json'}
        response = self.settlement({'invalid_json'})

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
            provider=SAMPLE_TARA.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    def test_invalid_national_code(self, *_):
        request_data = {
            'nationalCode': '092',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.settlement(request_data)

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
            provider=SAMPLE_TARA.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    def test_invalid_service_type(self, *_):
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'crediit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.settlement(request_data)

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
            provider=SAMPLE_TARA.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    def test_service_unavailable(self, *_):
        self.service.delete()

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.settlement(request_data)

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
            provider=SAMPLE_TARA.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            service=self.service.id,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    def test_user_not_found(self, *_):
        self.user.national_code = ''
        self.user.save()

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '19230768',
        }
        response = self.settlement(request_data)

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
            provider=SAMPLE_TARA.id,
            response_code=status.HTTP_404_NOT_FOUND,
            service=self.service.tp,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    def test_zero_amount(self, *_):
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '0',
        }

        response = self.settlement(request_data)

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
            provider=SAMPLE_TARA.id,
            response_code=status.HTTP_400_BAD_REQUEST,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    def test_amount_over_1b(self, *_):
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '10000000000',  # 1B toman
        }

        response = self.settlement(request_data)

        expected_result = {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Amount too large, amount should be lower than 1B Toman/10B Rial.',
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
            user=self.user,
            service=self.service.tp,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=SAMPLE_TARA.id,
            response_code=status.HTTP_400_BAD_REQUEST,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    def test_missing_amount(self, *_):
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
        }

        response = self.settlement(request_data)

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
            provider=SAMPLE_TARA.id,
            response_code=status.HTTP_400_BAD_REQUEST,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    def test_without_user_service(self, *_):
        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '1000',
        }

        response = self.settlement(request_data)
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

        with pytest.raises(SettlementTransaction.DoesNotExist):
            SettlementTransaction.objects.get(user_service__user=self.user)

        self.check_incoming_log(
            api_url=self.url,
            user=self.user,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=SAMPLE_TARA.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            service=self.service.tp,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    def test_active_settlement_exist(self, *_):
        user_service = self.create_user_service(
            user=self.user,
            service=self.service,
            permission=self.permission,
            initial_debt=1000,
        )
        self.create_settlement(user_service=user_service, amount=100)

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '1000',
        }

        response = self.settlement(request_data)
        expected_result = {
            'status': 'failed',
            'code': 'SettlementError',
            'message': 'Another settlement process is running!',
        }

        check_response(
            response=response,
            status_code=status.HTTP_423_LOCKED,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        self.check_incoming_log(
            api_url=self.url,
            user=self.user,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=SAMPLE_TARA.id,
            response_code=status.HTTP_423_LOCKED,
            service=self.service.tp,
            user_service=user_service,
        )

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    def test_amount_greater_than_debt(self, *_):
        user_service = self.create_user_service(
            user=self.user, service=self.service, permission=self.permission, initial_debt=1000
        )

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '10000',
        }

        response = self.settlement(request_data)
        expected_result = {
            'status': 'failed',
            'code': 'InappropriateAmount',
            'message': 'Requested settlement amount exceeds user active debt.',
        }

        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data=expected_result['status'],
            code=expected_result['code'],
            message=expected_result['message'],
        )

        with pytest.raises(SettlementTransaction.DoesNotExist):
            SettlementTransaction.objects.get(user_service__user=self.user)

        self.check_incoming_log(
            api_url=self.url,
            user=self.user,
            request_body=request_data,
            response_body=expected_result,
            log_status=1,
            provider=SAMPLE_TARA.id,
            response_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            service=self.service.tp,
            user_service=user_service,
        )

    @patch('django.db.transaction.on_commit', lambda t: t())
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.verify_signature')
    @patch(
        'exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip',
        return_value=SAMPLE_TARA,
    )
    @patch('exchange.asset_backed_credit.tasks.task_settlement_settle_user.delay')
    def test_success(self, mock_settlement, *_):
        user_service = self.create_user_service(
            user=self.user,
            service=self.service,
            permission=self.permission,
            initial_debt=1000,
        )

        SettlementTransaction.objects.create(
            user_service=user_service,
            amount=1000,
            status=SettlementTransaction.STATUS.unknown_rejected,
        )
        SettlementTransaction.objects.create(
            user_service=user_service,
            amount=1000,
            status=SettlementTransaction.STATUS.confirmed,
            transaction_datetime=ir_now(),
        )

        request_data = {
            'nationalCode': '0921234562',
            'serviceType': 'credit',
            'trackId': str(uuid.uuid4()),
            'amount': '100',
        }

        response = self.settlement(request_data)
        expected_result = {
            'status': 'ok',
        }
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data=expected_result['status'],
        )
        user_service.refresh_from_db()
        assert user_service.closed_at is None
        assert user_service.current_debt == 1000
        assert user_service.initial_debt == 1000
        settlement = (
            SettlementTransaction.objects.filter(user_service=user_service, transaction_datetime__isnull=True)
            .order_by('pk')
            .last()
        )
        assert settlement.amount == 100
        assert not settlement.transaction_datetime
        assert not settlement.provider_deposit_transaction
        assert not settlement.insurance_withdraw_transaction
        assert not settlement.user_withdraw_transaction
        mock_settlement.assert_called()

        self.check_incoming_log(
            api_url=self.url,
            request_body=request_data,
            response_body=expected_result,
            log_status=0,
            provider=SAMPLE_TARA.id,
            response_code=status.HTTP_200_OK,
            user=self.user,
            service=self.service.tp,
            user_service=user_service,
        )
