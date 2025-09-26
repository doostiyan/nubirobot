from decimal import Decimal
from typing import Any, Dict, Optional
from unittest.mock import patch

import responses
from django.core.cache import cache
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import InsufficientCollateralError, UserLimitExceededError
from exchange.asset_backed_credit.externals.providers import TARA
from exchange.asset_backed_credit.externals.providers.tara import (
    TaraChargeToAccount,
    TaraCheckUserBalance,
    TaraDischargeAccount,
    TaraGetTraceNumber,
)
from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit, UserService
from exchange.base.constants import ZERO
from exchange.base.models import Currencies
from exchange.base.serializers import serialize_choices, serialize_decimal
from tests.asset_backed_credit.helper import SIGN, ABCMixins, APIHelper, MockCacheValue, sign_mock


class UserServiceDebtEditAPITest(APIHelper, ABCMixins):
    URL = '/asset-backed-credit/user-services/{}/debt/edit'

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.get(pk=201)
        cls.user.user_type = User.USER_TYPES.level1
        cls.user.mobile = '09120000000'
        cls.user.national_code = '0010000000'
        cls.user.first_name = 'Ali'
        cls.user.last_name = 'Ali'
        cls.user.save(update_fields=('user_type', 'mobile', 'national_code', 'first_name', 'last_name'))

        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.credit, min_limit=10_000_000)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.loan, min_limit=10_000_000)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.debit, min_limit=10_000)

    def setUp(self):
        self._set_client_credentials(self.user.auth_token.key)
        self.service = self.create_service(tp=Service.TYPES.credit)
        self.amount = Decimal('120_000_000')
        UserFinancialServiceLimit.set_service_limit(service=self.service, max_limit=self.amount)
        self.charge_exchange_wallet(self.user, Currencies.rls, amount=130_000_000)
        TARA.set_token('XXX')
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    def tearDown(self):
        cache.clear()

    def _check_api_result(self, response: Dict[str, Any], expected_user_service: Optional[UserService]):
        assert 'userService' in response
        actual_user_service = response['userService']
        assert actual_user_service['id'] == expected_user_service.id
        assert actual_user_service['status'] == expected_user_service.status
        assert 'service' in actual_user_service
        assert actual_user_service['service']['provider'] == serialize_choices(
            Service.PROVIDERS, expected_user_service.service.provider
        )
        assert actual_user_service['service']['type'] == serialize_choices(
            Service.TYPES, expected_user_service.service.tp
        )
        assert actual_user_service['currentDebt'] == serialize_decimal(expected_user_service.current_debt)
        assert actual_user_service['initialDebt'] == serialize_decimal(expected_user_service.initial_debt)
        assert actual_user_service['service']['fee'] == serialize_decimal(expected_user_service.service.fee)
        assert actual_user_service['service']['interest'] == serialize_decimal(expected_user_service.service.interest)

    def test_user_service_not_found(self, *_):
        initial_debt = 10000

        response = self.client.post(
            path=self.URL.format(0),
            data={'newInitialDebt': initial_debt - 1_000},
        )

        self._check_response(response=response, status_code=status.HTTP_404_NOT_FOUND)

    def test_service_not_implemented_error(self, *_):
        initial_debt = 11_000_000
        service = self.create_service(tp=Service.TYPES.loan)
        UserFinancialServiceLimit.set_service_limit(service=service, max_limit=self.amount)
        user_service = self.create_user_service(self.user, service=service, initial_debt=initial_debt)

        response = self.client.post(
            path=self.URL.format(user_service.pk),
            data={'newInitialDebt': initial_debt - 1_000},
        )

        self._check_response(response=response, status_code=status.HTTP_501_NOT_IMPLEMENTED)

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_discharge_initial_debt_successful(self, *_):
        initial_debt = 11_000_000
        user_service = self.create_user_service(
            self.user, service=self.service, initial_debt=initial_debt, account_number='1234'
        )

        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': '1234',
                'balance': '11000000',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'accountNumber': '1234',
                        'sign': SIGN,
                    },
                ),
            ],
        )
        url = TaraGetTraceNumber('decharge', UserService(user=self.user, service=self.service)).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '1000',
                    },
                ),
            ],
        )
        url = TaraDischargeAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': 'test error',
                'timestamp': '1701964345',
                'referenceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '1000',
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )

        response = self.client.post(
            path=self.URL.format(user_service.pk),
            data={'newInitialDebt': initial_debt - 1_000},
        )

        user_service.initial_debt = initial_debt - 1_000
        user_service.current_debt = initial_debt - 1_000
        user_service.status = 'initiated'

        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, user_service)

        user_service.refresh_from_db()
        assert user_service.status == UserService.STATUS.initiated

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_discharge_initial_debt_user_has_zero_debt_user_service_closed_successful(self, mock_restriction_task, *_):
        initial_debt = 11_000_000
        user_service = self.create_user_service(
            self.user,
            service=self.service,
            initial_debt=initial_debt,
            current_debt=initial_debt - 10_000_000,
            account_number='1234',
        )

        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': '1234',
                'balance': '1000000',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'accountNumber': '1234',
                        'sign': SIGN,
                    },
                ),
            ],
        )
        url = TaraGetTraceNumber('decharge', UserService(user=self.user, service=self.service)).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '1000000',
                    },
                ),
            ],
        )
        url = TaraDischargeAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': 'test error',
                'timestamp': '1701964345',
                'referenceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '1000000',
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )

        response = self.client.post(
            path=self.URL.format(user_service.pk),
            data={'newInitialDebt': initial_debt - 1_000_000},
        )

        user_service.initial_debt = initial_debt - 1_000_000
        user_service.current_debt = ZERO
        user_service.status = 'closed'

        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, user_service)

        user_service.refresh_from_db()
        assert user_service.status == UserService.STATUS.closed
        mock_restriction_task.assert_called_once()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_discharge_initial_debt_user_has_debt_and_settled_debt_successful(self, *_):
        initial_debt = 100_000_000
        user_service = self.create_user_service(
            self.user,
            service=self.service,
            initial_debt=initial_debt,
            current_debt=initial_debt - 20_000_000,
            account_number='1234',
        )

        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': '1234',
                'balance': '60000000',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'accountNumber': '1234',
                        'sign': SIGN,
                    },
                ),
            ],
        )
        url = TaraGetTraceNumber('decharge', UserService(user=self.user, service=self.service)).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '60000000',
                    },
                ),
            ],
        )
        url = TaraDischargeAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': 'test error',
                'timestamp': '1701964345',
                'referenceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '60000000',
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )

        response = self.client.post(
            path=self.URL.format(user_service.pk),
            data={'newInitialDebt': initial_debt - 60_000_000},
        )

        user_service.initial_debt = initial_debt - 60_000_000
        user_service.current_debt = 20_000_000
        user_service.status = 'initiated'

        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, user_service)

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_discharge_initial_debt_min_initial_debt_error(self, *_):
        initial_debt = 10_000_000
        user_service = self.create_user_service(
            self.user, service=self.service, initial_debt=initial_debt, account_number='1234'
        )

        response = self.client.post(
            path=self.URL.format(user_service.pk),
            data={'newInitialDebt': initial_debt - 1_000},
        )

        self._check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data='failed',
            code='MinimumInitialDebtError',
        )
        user_service.refresh_from_db()
        assert user_service.initial_debt == initial_debt
        assert user_service.current_debt == initial_debt

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_discharge_initial_debt_discharge_more_than_available_balance_error(self, *_):
        initial_debt = 11_000_000
        user_service = self.create_user_service(
            self.user, service=self.service, initial_debt=initial_debt, account_number='1234'
        )

        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': '1234',
                'balance': '500',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'accountNumber': '1234',
                        'sign': SIGN,
                    },
                ),
            ],
        )
        url = TaraGetTraceNumber('decharge', UserService(user=self.user, service=self.service)).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '1000',
                    },
                ),
            ],
        )
        url = TaraDischargeAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': 'test error',
                'timestamp': '1701964345',
                'referenceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '1000',
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )

        response = self.client.post(
            path=self.URL.format(user_service.pk),
            data={'newInitialDebt': initial_debt - 1_000},
        )

        self._check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data='failed',
            code='UserServiceHasActiveDebt',
        )
        user_service.refresh_from_db()
        assert user_service.initial_debt == initial_debt
        assert user_service.current_debt == initial_debt

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_discharge_initial_debt_tara_discharge_failed_error(self, *_):
        initial_debt = 11_000_000
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=initial_debt)

        url = TaraGetTraceNumber('decharge', UserService(user=self.user, service=self.service)).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '10999000',
                    },
                ),
            ],
        )
        url = TaraDischargeAccount.url
        responses.post(
            url=url,
            json={
                'success': False,
                'data': 'test error',
                'timestamp': '1701964345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '10999000',
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )

        response = self.client.post(
            path=self.URL.format(user_service.pk),
            data={'newInitialDebt': initial_debt - 1_000},
        )

        self._check_response(response=response, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, status_data='failed')
        user_service.refresh_from_db()
        assert user_service.initial_debt == initial_debt
        assert user_service.current_debt == initial_debt

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_charge_initial_debt_successful(self, *_):
        initial_debt = 10_000_000
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=initial_debt)

        url = TaraGetTraceNumber('charge', UserService(user=self.user, service=self.service)).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '10001000',
                    },
                ),
            ],
        )
        url = TaraChargeToAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': 'test error',
                'timestamp': '1701964345',
                'referenceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '10001000',
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )

        response = self.client.post(
            path=self.URL.format(user_service.pk),
            data={'newInitialDebt': initial_debt + 1_000},
        )

        user_service.initial_debt = initial_debt + 1_000
        user_service.current_debt = initial_debt + 1_000
        user_service.status = 'initiated'

        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, user_service)

        user_service.refresh_from_db()
        assert user_service.status == UserService.STATUS.initiated

    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_charge_initial_debt_collateral_ratio_error(self, *_):
        initial_debt = 100_000_000
        self.charge_exchange_wallet(self.user, Currencies.rls, amount=-30_000_000)
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=initial_debt)

        response = self.client.post(
            path=self.URL.format(user_service.pk),
            data={'newInitialDebt': initial_debt + 1_000},
        )

        user_service.initial_debt = initial_debt + 1_000
        user_service.current_debt = initial_debt + 1_000
        user_service.status = 'initiated'

        self._check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data='failed',
            code=InsufficientCollateralError.__name__,
        )
        user_service.refresh_from_db()
        assert user_service.initial_debt == initial_debt
        assert user_service.current_debt == initial_debt

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_charge_initial_debt_service_limit_exceeded_error(self, *_):
        initial_debt = 100_000_000
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=initial_debt)

        url = TaraGetTraceNumber('charge', UserService(user=self.user, service=self.service)).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '10001000',
                    },
                ),
            ],
        )
        url = TaraChargeToAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': 'test error',
                'timestamp': '1701964345',
                'referenceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '10001000',
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )

        response = self.client.post(
            path=self.URL.format(user_service.pk),
            data={'newInitialDebt': initial_debt + 50_000_000},
        )

        user_service.initial_debt = initial_debt + 50_000_000
        user_service.current_debt = initial_debt + 50_000_000
        user_service.status = 'initiated'

        self._check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data='failed',
            code=UserLimitExceededError.__name__,
        )
        user_service.refresh_from_db()
        assert user_service.initial_debt == initial_debt
        assert user_service.current_debt == initial_debt

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_charge_initial_debt_user_has_debt_and_settled_debt_successful(self, *_):
        initial_debt = 100_000_000
        user_service = self.create_user_service(
            self.user, service=self.service, initial_debt=initial_debt, current_debt=initial_debt - 20_000_000
        )

        url = TaraGetTraceNumber('charge', UserService(user=self.user, service=self.service)).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '100000000',
                    },
                ),
            ],
        )
        url = TaraChargeToAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': 'test error',
                'timestamp': '1701964345',
                'referenceNumber': '12345',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '100000000',
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )

        response = self.client.post(
            path=self.URL.format(user_service.pk),
            data={'newInitialDebt': initial_debt + 20_000_000},
        )

        user_service.initial_debt = initial_debt + 20_000_000
        user_service.current_debt = initial_debt
        user_service.status = 'initiated'

        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, user_service)

        user_service.refresh_from_db()
        assert user_service.status == UserService.STATUS.initiated
