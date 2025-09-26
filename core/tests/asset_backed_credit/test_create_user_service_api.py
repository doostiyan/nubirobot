import datetime
import json
import os
import uuid
from decimal import Decimal
from unittest.mock import patch

import responses
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.providers import AZKI, DIGIPAY, TARA, VENCY
from exchange.asset_backed_credit.externals.providers.tara import (
    TaraAccountTransactionInquiry,
    TaraChargeToAccount,
    TaraCreateAccount,
    TaraGetTraceNumber,
)
from exchange.asset_backed_credit.externals.providers.vency import (
    VencyCalculatorAPI,
    VencyCreateAccountAPI,
    VencyRenewTokenAPI,
)
from exchange.asset_backed_credit.externals.restriction import UserRestrictionType
from exchange.asset_backed_credit.models import OutgoingAPICallLog, Service, UserFinancialServiceLimit, UserService
from exchange.asset_backed_credit.services.loan.create import LoanCreateService
from exchange.asset_backed_credit.services.logging import process_abc_outgoing_api_logs
from exchange.asset_backed_credit.services.price import get_ratios
from exchange.asset_backed_credit.services.providers.dispatcher import TaraCreditAPIs
from exchange.asset_backed_credit.services.user_service import update_credit_user_services_status
from exchange.asset_backed_credit.types import LoanServiceOptions
from exchange.base.models import Currencies, Settings
from exchange.wallet.models import Wallet as ExchangeWallet
from tests.asset_backed_credit.helper import SIGN, ABCMixins, APIHelper, MockCacheValue, sign_mock
from tests.base.utils import mock_on_commit


@patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 10_000_0)
class TestCreateUserServiceAPI(APIHelper, ABCMixins):
    URL = '/asset-backed-credit/user-services/create'

    user: User

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.get(pk=201)
        cls.user.user_type = User.USER_TYPES.level1
        cls.user.mobile = '09120000000'
        cls.user.national_code = '0010000000'
        cls.user.first_name = 'Ali'
        cls.user.last_name = 'Ali'
        cls.user.birthday = datetime.date(year=1990, month=10, day=10)
        cls.user.save(update_fields=('user_type', 'mobile', 'national_code', 'first_name', 'last_name', 'birthday'))
        cls.collateral_ratio = get_ratios().get('collateral')
        cls.amount = Decimal('10000')

        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.credit, min_limit=1000)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.loan, min_limit=10000)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.debit, min_limit=1000)

    def tearDown(self):
        cache.clear()

    def setUp(self) -> None:
        self._set_client_credentials(self.user.auth_token.key)
        self.service = self.create_service(contract_id='1234')
        self.digipay_credit_service = self.create_service(provider=Service.PROVIDERS.digipay, tp=Service.TYPES.credit)
        self.unavailable_service = self.create_service(tp=Service.TYPES.loan, contract_id='1111', is_available=False)
        TARA.set_token('XXX')
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

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

    def _precondition_user_service(self, service=None, service_limit_amount=None, charge_account_amount=Decimal(0)):
        service = service or self.service
        self._add_user_eligibility()
        self.create_user_service_permission(user=self.user, service=service)
        if service_limit_amount is not None:
            UserFinancialServiceLimit.set_service_limit(service=service, max_limit=service_limit_amount)
        if charge_account_amount > 0:
            self.charge_exchange_wallet(self.user, Currencies.usdt, amount=charge_account_amount)

    def _check_user_service(self, user_service: UserService):
        us = UserService.objects.order_by('id').last()
        assert us.user == user_service.user
        assert us.account_number == user_service.account_number
        assert us.service == user_service.service
        assert us.initial_debt == user_service.initial_debt
        assert us.current_debt == user_service.current_debt
        assert us.principal == user_service.principal
        assert us.total_repayment == user_service.total_repayment
        assert us.installment_amount == user_service.installment_amount
        assert us.installment_period == user_service.installment_period
        assert us.provider_fee_percent == user_service.provider_fee_percent
        assert us.provider_fee_amount == user_service.provider_fee_amount
        assert us.status == user_service.status
        assert us.extra_info.get('redirect_url') == user_service.extra_info.get('redirect_url')

    def test_error_service_id(self):
        self._add_user_eligibility()
        # not sent serviceId
        response = self._post_request()
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_400_BAD_REQUEST,
            code='ParseError',
            message='Missing integer value',
        )
        # wrong serviceId
        response = self._post_request(data={'serviceId': -1})
        self._check_response(response=response, status_code=status.HTTP_404_NOT_FOUND)
        # inactive service
        self._change_parameters_in_object(self.service, {'is_active': False})
        response = self._post_request(data={'serviceId': self.service.pk})
        self._check_response(response=response, status_code=status.HTTP_404_NOT_FOUND)

    def test_unsuccessful_service_unavailable(self):
        self._add_user_eligibility()
        response = self._post_request(data={'serviceId': self.unavailable_service.pk, 'amount': '10000'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ServiceUnavailableError',
            message='در حال حاضر، سرویس‌دهنده ظرفیتی برای اعطای وام ندارد. لطفا روزهای آینده دوباره این صفحه را بررسی کنید.',
        )

    def test_unsuccessful_service_unavailable_android_client(self):
        self._add_user_eligibility()
        response = self._post_request(
            data={'serviceId': self.unavailable_service.pk, 'amount': '10000'},
            headers={'User-Agent': 'Android/6.8.0-dev'},
        )
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='در حال حاضر، سرویس‌دهنده ظرفیتی برای اعطای وام ندارد. لطفا روزهای آینده دوباره این صفحه را بررسی کنید.',
            message='ServiceUnavailableError',
        )

    def test_wrong_amount(self):
        self._add_user_eligibility()
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': 'abc'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_400_BAD_REQUEST,
            code='ParseError',
        )

    def test_unsuccessful_not_have_permission(self):
        self._add_user_eligibility()
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='GrantedPermissionDoseNotFound',
            message='You need to grant permission to activate this service.',
        )

    def test_unsuccessful_eligibility(self):
        self.create_user_service_permission(user=self.user, service=self.service)
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_400_BAD_REQUEST,
            code='UserLevelRestriction',
            message='User is not verified as level 1.',
        )

    def test_unsuccessful_eligibility_user_level(self):
        self._add_user_mobile_confirmed()
        self.create_user_service_permission(user=self.user, service=self.service)
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_400_BAD_REQUEST,
            code='UserLevelRestriction',
            message='User is not verified as level 1.',
        )

    def test_unsuccessful_eligibility_user_mobile(self):
        self._add_user_level1_confirmed()
        self.create_user_service_permission(user=self.user, service=self.service)
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_400_BAD_REQUEST,
            code='UserLevelRestriction',
            message='User has no confirmed mobile number.',
        )

    def test_unsuccessful_user_service_exist(self):
        self._precondition_user_service(service_limit_amount=self.amount, charge_account_amount=Decimal('10000'))
        self.create_user_service(user=self.user, service=self.service)
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ServiceAlreadyActivated',
            message='service is already activated.',
        )

    def test_unsuccessful_service_limit_not_set(self):
        self._precondition_user_service()
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ServiceLimitNotSet',
            message='Service limit is not set.',
        )

    def test_unsuccessful_user_limit_zero(self):
        self._precondition_user_service(service_limit_amount=self.amount)
        UserFinancialServiceLimit.set_user_limit(self.user, max_limit=0)
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='UserLimitExceededError',
            message='The user limit exceeded',
        )

    def test_unsuccessful_zero_collateral(self):
        self._precondition_user_service(service_limit_amount=self.amount)
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            code='InsufficientCollateralError',
            message='Amount cannot exceed active balance',
        )

    def test_lock_wrong_minimum_init_debt(self):
        self._precondition_user_service(service_limit_amount=self.amount, charge_account_amount=Decimal('100'))
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '100'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='MinimumInitialDebtError',
            message=f'Amount is less than {1000} rls',
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.tasks.add_user_restriction_task.delay')
    def test_unsuccessful_tara_error_create_account(self, mock_add_restriction, *_):
        url = TaraCreateAccount.url
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
                        'name': self.user.first_name,
                        'family': self.user.last_name,
                        'sign': SIGN,
                    },
                ),
            ],
        )
        self._precondition_user_service(service_limit_amount=self.amount, charge_account_amount=Decimal('2'))
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ThirdPartyError',
            message='TaraCreateAccount: Fail to create account',
        )
        assert not UserService.objects.filter(user=self.user).exists()
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 1
        assert mock_add_restriction.call_count == 0

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_unsuccessful_tara_error_get_trace_number(self, *_):
        account_number_data = '1234'
        url = TaraCreateAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': account_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'name': self.user.first_name,
                        'family': self.user.last_name,
                        'sign': SIGN,
                    },
                ),
            ],
        )
        url = TaraGetTraceNumber('charge', UserService(user=self.user, service=self.service)).url
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
                        'amount': '10000',
                    },
                ),
            ],
        )
        self._precondition_user_service(service_limit_amount=self.amount, charge_account_amount=Decimal('2'))
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ThirdPartyError',
            message='TaraGetTraceNumber: Fail to get a trace number',
        )
        assert not UserService.objects.filter(user=self.user).exists()
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 2

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_unsuccessful_tara_error_charge_account(self, *_):
        account_number_data = '1234'
        url = TaraCreateAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': account_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'name': self.user.first_name,
                        'family': self.user.last_name,
                        'sign': SIGN,
                    },
                ),
            ],
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
                        'amount': '10000',
                    },
                ),
            ],
        )
        url = TaraChargeToAccount.url
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
                        'amount': '10000',
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )
        url = TaraAccountTransactionInquiry('12345', user_service=UserService(user=self.user, service=self.service)).url
        responses.post(
            url=url,
            json={'id': '12345', 'status': False, 'doTime': '1701964345'},
            status=200,
        )
        self._precondition_user_service(service_limit_amount=self.amount, charge_account_amount=Decimal('2'))
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ThirdPartyError',
            message='TaraChargeAccount: Fail to charge account',
        )
        assert not UserService.objects.filter(user=self.user).exists()
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 4

    @responses.activate
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.tasks.add_user_restriction_task.delay')
    def test_unsuccessful_tara_error_charge_account_inquiry_status_true_successful_charge_account(
        self, mock_add_restriction, *_
    ):
        account_number_data = '1234'
        url = TaraCreateAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': account_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'name': self.user.first_name,
                        'family': self.user.last_name,
                        'sign': SIGN,
                    },
                ),
            ],
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
                        'amount': '10000',
                    },
                ),
            ],
        )
        url = TaraChargeToAccount.url
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
                        'amount': '10000',
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )
        url = TaraAccountTransactionInquiry('12345', user_service=UserService(user=self.user, service=self.service)).url
        responses.post(
            url=url,
            json={'id': '12345', 'status': True, 'doTime': '1701964345', 'amount': 10000},
            status=200,
        )
        self._precondition_user_service(service_limit_amount=self.amount, charge_account_amount=Decimal('2'))
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        data = self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )
        assert 'userService' in data
        self._check_user_service(
            UserService(
                user=self.user,
                service=self.service,
                account_number=account_number_data,
                initial_debt=self.amount,
                current_debt=self.amount,
            ),
        )
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 4
        user_service = UserService.objects.order_by('id').last()
        mock_add_restriction.assert_called_once_with(
            user_service_id=user_service.id,
            restriction=UserRestrictionType.CHANGE_MOBILE.value,
            description_key='ACTIVE_TARA_CREDIT',
            considerations=TaraCreditAPIs.USER_RESTRICTION_CONSIDERATIONS,
        )

    @responses.activate
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.tasks.add_user_restriction_task.delay')
    def test_successful(self, mock_add_restriction, *_):
        account_number_data = '1234'
        url = TaraCreateAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': account_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'name': self.user.first_name,
                        'family': self.user.last_name,
                        'sign': SIGN,
                    },
                ),
            ],
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
                        'amount': '10000',
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
                        'amount': '10000',
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )
        self._precondition_user_service(service_limit_amount=self.amount, charge_account_amount=Decimal('2'))
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        data = self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )
        assert 'userService' in data
        self._check_user_service(
            UserService(
                user=self.user,
                service=self.service,
                account_number=account_number_data,
                initial_debt=self.amount,
                current_debt=self.amount,
            ),
        )
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 3
        user_service = UserService.objects.order_by('id').last()
        mock_add_restriction.assert_called_once_with(
            user_service_id=user_service.id,
            restriction=UserRestrictionType.CHANGE_MOBILE.value,
            description_key='ACTIVE_TARA_CREDIT',
            considerations=TaraCreditAPIs.USER_RESTRICTION_CONSIDERATIONS,
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful_vency(self, _):
        service = self.create_service(
            provider=Service.PROVIDERS.vency,
            tp=Service.TYPES.loan,
            options=dict(
                LoanServiceOptions(
                    min_principal_limit=10_000_000,
                    max_principal_limit=200_000_000,
                    periods=[1, 3, 6, 9],
                    provider_fee=Decimal(10),
                )
            ),
        )

        unique_id = '4d3ebb0a-317f-4f57-812b-a4b85066a1be'
        amount = 18_000_000_0
        period = 6
        redirect_url = f'https://api.vencytest.ir/main/select/6712a9ba-70db-419d-9669-b5c68bcf5beb'

        with open(os.path.join(os.path.dirname(__file__), 'test_data', 'vency_calculator_response_18.json'), 'r') as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': amount})],
        )

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

        responses.post(
            url=VencyCreateAccountAPI.url,
            json={
                'orderId': '6712a9ba-70db-419d-9669-b5c68bcf5beb',
                'uniqueIdentifier': unique_id,
                'redirectUrl': redirect_url,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'uniqueIdentifier': unique_id,
                        'amountRials': amount,
                        'loanPrincipalSupplyPlanId': 'd9235dba-8405-4d07-bc24-b8e2244db17e',
                        'collaboratorLoanPlanId': '488e8dc5-d143-4bec-8229-7fe6cfc4d0c7',
                        'customerNationalCode': self.user.national_code,
                    },
                ),
            ],
        )

        self._precondition_user_service(
            service=service, service_limit_amount=25_000_000_0, charge_account_amount=Decimal('3000')
        )

        original_create_user_service = LoanCreateService._create_user_service

        def mocked_create_user_service(self, calculated_info):
            user_service = original_create_user_service(self, calculated_info)
            user_service.external_id = uuid.UUID(unique_id)
            return user_service

        with patch.object(LoanCreateService, '_create_user_service', new=mocked_create_user_service):
            response = self._post_request(data={'serviceId': service.pk, 'amount': amount, 'period': period})

        data = self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )

        assert 'userService' in data
        assert 'collateralFeePercent' in data['userService']
        assert data['userService']['collateralFeePercent'] == '0'
        assert 'collateralFeeAmount' in data['userService']
        assert data['userService']['collateralFeeAmount'] == 0

        self._check_user_service(
            UserService(
                user=self.user,
                service=service,
                account_number=unique_id,
                principal=amount,
                total_repayment=Decimal('210300000'),
                initial_debt=Decimal('192300000'),
                current_debt=Decimal('192300000'),
                installment_amount=Decimal('32050000'),
                installment_period=period,
                provider_fee_percent=Decimal('10.0'),
                provider_fee_amount=Decimal('18000000'),
                extra_info={'redirect_url': redirect_url},
                status=UserService.STATUS.created,
            ),
        )
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 3

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_create_duplicate_loan_user_service(self, _):
        service = self.create_service(
            provider=Service.PROVIDERS.vency,
            tp=Service.TYPES.loan,
            options=dict(
                LoanServiceOptions(
                    min_principal_limit=10_000_000_0,
                    max_principal_limit=100_000_000_0,
                    periods=[1, 3, 6, 9],
                    provider_fee=Decimal(10),
                )
            ),
        )
        account_number = '4d3ebb0a-317f-4f57-812b-a4b85066a1be'
        amount = 25_000_000_0
        period = 6
        redirect_url = f'https://api.vencytest.ir/main/select/6712a9ba-70db-419d-9669-b5c68bcf5beb'

        with open(os.path.join(os.path.dirname(__file__), 'test_data', 'vency_calculator_response_25.json'), 'r') as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': amount})],
        )

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

        responses.post(
            url=VencyCreateAccountAPI.url,
            json={
                'orderId': '6712a9ba-70db-419d-9669-b5c68bcf5beb',
                'uniqueIdentifier': account_number,
                'redirectUrl': redirect_url,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'uniqueIdentifier': account_number,
                        'amountRials': amount,
                        'loanPrincipalSupplyPlanId': 'd9235dba-8405-4d07-bc24-b8e2244db17e',
                        'collaboratorLoanPlanId': '488e8dc5-d143-4bec-8229-7fe6cfc4d0c7',
                        'customerNationalCode': self.user.national_code,
                    },
                ),
            ],
        )

        self._precondition_user_service(
            service=service, service_limit_amount=50_000_000_0, charge_account_amount=Decimal('5000')
        )

        original_create_user_service = LoanCreateService._create_user_service

        def mocked_create_user_service(self, calculated_info):
            user_service = original_create_user_service(self, calculated_info)
            user_service.external_id = uuid.UUID(account_number)
            return user_service

        with patch.object(LoanCreateService, '_create_user_service', new=mocked_create_user_service):
            response = self._post_request(data={'serviceId': service.pk, 'amount': amount, 'period': period})

        self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )

        response = self._post_request(data={'serviceId': service.pk, 'amount': amount, 'period': period})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful_vency_another_terms(self, _):
        service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan, is_active=True, is_available=True
        )
        unique_id = 'af272513-8b9c-4271-8831-f718cf7ad4af'
        amount = 75_000_000_0
        period = 9
        redirect_url = f'https://api.vencytest.ir/main/select/6712a9ba-70db-419d-9669-b5c67bcf5beb'

        with open(os.path.join(os.path.dirname(__file__), 'test_data', 'vency_calculator_response_75.json'), 'r') as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': amount})],
        )

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

        responses.post(
            url=VencyCreateAccountAPI.url,
            json={
                'orderId': '6712a9ba-70db-419d-9669-b5c67bcf5beb',
                'uniqueIdentifier': unique_id,
                'redirectUrl': redirect_url,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'uniqueIdentifier': unique_id,
                        'amountRials': amount,
                        'loanPrincipalSupplyPlanId': 'b0ca2c09-3af5-461b-a6e2-ab63dc2650c9',
                        'collaboratorLoanPlanId': '824a3255-ef60-4da7-993b-9ee5fa3f6f8b',
                        'customerNationalCode': self.user.national_code,
                    },
                ),
            ],
        )

        self._precondition_user_service(
            service=service, service_limit_amount=100_000_000_0, charge_account_amount=Decimal('13000')
        )

        original_create_user_service = LoanCreateService._create_user_service

        def mocked_create_user_service(self, calculated_info):
            user_service = original_create_user_service(self, calculated_info)
            user_service.external_id = uuid.UUID(unique_id)
            return user_service

        with patch.object(LoanCreateService, '_create_user_service', new=mocked_create_user_service):
            # with patch.object(UserService.external_id.field, "default", new=uuid.UUID(unique_id)):
            response = self._post_request(data={'serviceId': service.pk, 'amount': amount, 'period': period})

        data = self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )

        assert 'userService' in data
        self._check_user_service(
            UserService(
                user=self.user,
                service=service,
                status=UserService.STATUS.created,
                account_number=unique_id,
                principal=amount,
                total_repayment=Decimal('913770000'),
                initial_debt=Decimal('823770000'),
                current_debt=Decimal('823770000'),
                installment_amount=Decimal('91530000'),
                installment_period=period,
                provider_fee_percent=Decimal('12.0'),
                provider_fee_amount=Decimal('90000000'),
                extra_info={'redirect_url': redirect_url},
            ),
        )
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 3

    def test_not_implemented_error(self):
        Settings.set('abc_debit_wallet_enabled', 'yes')
        self._add_user_eligibility()
        service = self.create_service(tp=Service.TYPES.debit)
        self.create_user_service_permission(user=self.user, service=service)
        UserFinancialServiceLimit.set_service_limit(service=service, max_limit=self.amount)
        self.charge_exchange_wallet(self.user, Currencies.usdt, amount='1000000', tp=ExchangeWallet.WALLET_TYPE.debit)
        response = self._post_request(data={'serviceId': service.pk, 'amount': '10000', 'period': 12})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code='NotImplementedError',
            message='This service not implemented yet.',
        )

    def test_prod_protection(self):
        Settings.set('abc_is_activated_apis', 'no')
        self._precondition_user_service(service_limit_amount=self.amount, charge_account_amount=Decimal('2'))
        response = self._post_request(data={'serviceId': self.service.pk, 'amount': '10000'})
        assert response.status_code == status.HTTP_404_NOT_FOUND

        response = self._get_request()
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_loan_min_max_principal_validation(self, _):
        service = self.create_service(
            provider=Service.PROVIDERS.vency,
            tp=Service.TYPES.loan,
            options=dict(
                LoanServiceOptions(
                    min_principal_limit=10_000_000,
                    max_principal_limit=50_000_000,
                    periods=[1, 3, 6, 9],
                    provider_fee=Decimal(10),
                )
            ),
        )

        self._precondition_user_service(
            service=service, service_limit_amount=10_000_000_0, charge_account_amount=Decimal('500')
        )

        response = self._post_request(data={'serviceId': service.pk, 'amount': 5_000_000, 'period': 3})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ValueError',
            message='Principal must be greater than or equal 10000000.',
        )

        response = self._post_request(data={'serviceId': service.pk, 'amount': 55_000_000, 'period': 3})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ValueError',
            message='Principal must be less than or equal 50000000.',
        )

    @responses.activate
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_create_digipay_user_service(self, *_):
        responses.post(
            url='https://uat.mydigipay.info/digipay/api/oauth/token',
            json={
                'access_token': 'ACCESS_TOKEN',
                'refresh_token': 'REFRESH_TOKEN',
                'token_type': 'Bearer',
                'expires_in': 599,
            },
            status=200,
            match=[
                responses.matchers.header_matcher(
                    {'Authorization': 'Basic ZGlnaXBheS1jbGllbnQtaWQ6ZGlnaXBheS1jbGllbnQtc2VjcmV0'}
                ),
                responses.matchers.urlencoded_params_matcher(
                    {
                        'username': 'digipay-username',
                        'password': 'digipay-password',
                        'grant_type': 'password',
                    }
                ),
            ],
        )

        url = 'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/activation'
        responses.post(
            url=url,
            json={
                'trackingCode': '8ff2700e-af49-43f4-8621-e969027e587f',
                'status': 'ACTIVATED',
                'allocatedAmount': 10_000_000,
                'result': {'title': 'SUCCESS', 'status': 0, 'message': 'عملیات با موفقیت انجام شد', 'level': 'INFO'},
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'nationalCode': '0010000000',
                        'cellNumber': '09120000000',
                        'birthDate': '1369-07-18',
                        'amount': 20_000_000,
                    },
                ),
            ],
        )

        self._precondition_user_service(
            service=self.digipay_credit_service,
            service_limit_amount=Decimal(50_000_000),
            charge_account_amount=Decimal(1000),
        )
        response = self._post_request(data={'serviceId': self.digipay_credit_service.pk, 'amount': 20_000_000})

        user_service = UserService.objects.order_by('id').last()
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['status'] == 'ok'
        assert response_data['userService']['id'] == user_service.id
        assert Decimal(response_data['userService']['currentDebt']) == Decimal(10_000_000)
        assert Decimal(response_data['userService']['initialDebt']) == Decimal(20_000_000)
        assert response_data['userService']['service']['id'] == self.digipay_credit_service.id
        assert response_data['userService']['status'] == 'initiated'

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_create_digipay_user_service_in_progress(self, *_):
        responses.post(
            url='https://uat.mydigipay.info/digipay/api/oauth/token',
            json={
                'access_token': 'ACCESS_TOKEN',
                'refresh_token': 'REFRESH_TOKEN',
                'token_type': 'Bearer',
                'expires_in': 599,
            },
            status=200,
            match=[
                responses.matchers.header_matcher(
                    {'Authorization': 'Basic ZGlnaXBheS1jbGllbnQtaWQ6ZGlnaXBheS1jbGllbnQtc2VjcmV0'}
                ),
                responses.matchers.urlencoded_params_matcher(
                    {
                        'username': 'digipay-username',
                        'password': 'digipay-password',
                        'grant_type': 'password',
                    }
                ),
            ],
        )

        url = 'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/activation'
        responses.post(
            url=url,
            json={
                'trackingCode': '8ff2700e-af49-43f4-8621-e969027e587f',
                'status': 'IN_PROGRESS',
                'result': {
                    'title': 'SUCCESS',
                    'status': 0,
                    'message': 'ok',
                    'level': 'INFO',
                },
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'nationalCode': '0010000000',
                        'cellNumber': '09120000000',
                        'birthDate': '1369-07-18',
                        'amount': 20_000_000,
                    },
                ),
            ],
        )

        url = 'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/inquiry/8ff2700e-af49-43f4-8621-e969027e587f'
        responses.get(
            url=url,
            json={
                'trackingCode': '8ff2700e-af49-43f4-8621-e969027e587f',
                'status': 'ACTIVATED',
                'allocatedAmount': '16_600_000',
                'result': {
                    'title': 'SUCCESS',
                    'status': 0,
                    'message': 'ok',
                    'level': 'INFO',
                },
            },
            status=200,
        )

        self._precondition_user_service(
            service=self.digipay_credit_service,
            service_limit_amount=Decimal(50_000_000),
            charge_account_amount=Decimal(1000),
        )
        response = self._post_request(data={'serviceId': self.digipay_credit_service.pk, 'amount': 20_000_000})

        assert response.status_code == status.HTTP_200_OK

        user_service = UserService.objects.filter(user=self.user).order_by('id').last()

        assert user_service.status == UserService.STATUS.created
        assert user_service.initial_debt == Decimal(20_000_000)
        assert user_service.current_debt == Decimal(20_000_000)

        update_credit_user_services_status()

        user_service.refresh_from_db()
        assert user_service.status == UserService.STATUS.initiated
        assert user_service.initial_debt == Decimal(20_000_000)
        assert user_service.current_debt == Decimal(16_600_000)

    @responses.activate
    @patch.object(AZKI, 'username', 'test-username')
    @patch.object(AZKI, 'password', 'test-password')
    @patch.object(AZKI, 'contract_id', 123456)
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful_azki(self, _):
        service = self.create_service(
            provider=Service.PROVIDERS.azki,
            tp=Service.TYPES.loan,
            options=dict(
                LoanServiceOptions(
                    min_principal_limit=100_000_000,
                    max_principal_limit=750_000_000,
                    periods=[12, 18],
                    provider_fee=Decimal(10),
                )
            ),
        )

        amount = 100_000_000
        period = 12
        request_id = 344820

        responses.post(
            url='https://service.azkiloan.com/auth/login',
            json={
                'rsCode': 0,
                'result': {'token': 'test-access-token'},
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'username': 'test-username',
                        'password': 'test-password',
                    }
                ),
            ],
        )

        responses.get(
            url='https://service.azkiloan.com/crypto-exchange/plans',
            json={
                'rsCode': 0,
                'result': [
                    {
                        'name': 'ازکی فاند',
                        'logoUrl': 'https://cdn.azkiloan.com/1403/0715/7e219c15-9088-4f12-9dbd-5448cc583d89.jpg',
                        'interestRate': 23.0000,
                        'monthlyAmount': 9407633,
                        'feeRate': 13.5000,
                        'feeAmount': 13500000,
                        'sumOfAmounts': 126391596,
                        'loanAmount': 100000000,
                        'repaymentModel': 'دفترچه اقساط',
                        'period': 12,
                    },
                    {
                        'name': 'ازکی فاند',
                        'logoUrl': 'https://cdn.azkiloan.com/1403/0715/7e219c15-9088-4f12-9dbd-5448cc583d89.jpg',
                        'interestRate': 23.0000,
                        'monthlyAmount': 9407633,
                        'feeRate': 13.5000,
                        'feeAmount': 13500000,
                        'sumOfAmounts': 126391596,
                        'loanAmount': 100000000,
                        'repaymentModel': 'دفترچه اقساط',
                        'period': 12,
                    },
                ],
            },
            match=[
                responses.matchers.query_param_matcher({'amount': amount, 'period': period}),
                responses.matchers.header_matcher({'Authorization': 'Bearer test-access-token'}),
            ],
        )

        responses.post(
            url='https://service.azkiloan.com/crypto-exchange/request-credit',
            json={
                'rsCode': 0,
                'result': {'request_id': request_id, 'credit_account_id': 4982134, 'coupon_book_id': 543678},
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'user': {
                            'first_name': 'Ali',
                            'last_name': 'Ali',
                            'mobile_number': '09120000000',
                            'national_code': '0010000000',
                        },
                        'amount': 100_000_000,
                        'financier_id': 123456,
                        'period': 12,
                    }
                )
            ],
        )

        self._precondition_user_service(
            service=service, service_limit_amount=200_000_000, charge_account_amount=Decimal('2000')
        )

        response = self._post_request(data={'serviceId': service.pk, 'amount': amount, 'period': period})
        data = self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )

        assert 'userService' in data

        assert 'collateralFeePercent' in data['userService']
        assert data['userService']['collateralFeePercent'] == '0'
        assert 'collateralFeeAmount' in data['userService']
        assert data['userService']['collateralFeeAmount'] == 0

        self._check_user_service(
            UserService(
                user=self.user,
                service=service,
                account_number=str(request_id),
                principal=amount,
                total_repayment=Decimal('126391596'),
                initial_debt=Decimal('112891596'),
                current_debt=Decimal('112891596'),
                installment_amount=Decimal('9407633'),
                installment_period=period,
                provider_fee_percent=Decimal('13.5'),
                provider_fee_amount=Decimal('13500000'),
                extra_info={'request_id': request_id, 'credit_account_id': 4982134, 'coupon_book_id': 543678},
                status=UserService.Status.initiated,
            ),
        )
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 3

    @responses.activate
    @patch.object(AZKI, 'username', 'test-username')
    @patch.object(AZKI, 'password', 'test-password')
    @patch.object(AZKI, 'contract_id', 123456)
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_failed_azki_no_plans(self, _):
        service = self.create_service(
            provider=Service.PROVIDERS.azki,
            tp=Service.TYPES.loan,
            options=dict(
                LoanServiceOptions(
                    min_principal_limit=100_000_000,
                    max_principal_limit=750_000_000,
                    periods=[12, 18],
                    provider_fee=Decimal(10),
                )
            ),
        )

        amount = 100_000_000
        period = 18

        responses.post(
            url='https://service.azkiloan.com/auth/login',
            json={
                'rsCode': 0,
                'result': {'token': 'test-access-token'},
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'username': 'test-username',
                        'password': 'test-password',
                    }
                ),
            ],
        )

        responses.get(
            url='https://service.azkiloan.com/crypto-exchange/plans',
            json={'rsCode': 0, 'result': []},
            match=[
                responses.matchers.query_param_matcher({'amount': amount, 'period': period}),
                responses.matchers.header_matcher({'Authorization': 'Bearer test-access-token'}),
            ],
        )

        self._precondition_user_service(
            service=service, service_limit_amount=200_000_000, charge_account_amount=Decimal('2000')
        )

        response = self._post_request(data={'serviceId': service.pk, 'amount': amount, 'period': period})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='LoanCalculationError',
        )

        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 2

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_create_digipay_user_service_failed_blacklist_user(self, *_):
        responses.post(
            url='https://uat.mydigipay.info/digipay/api/oauth/token',
            json={
                'access_token': 'ACCESS_TOKEN',
                'refresh_token': 'REFRESH_TOKEN',
                'token_type': 'Bearer',
                'expires_in': 599,
            },
            status=200,
            match=[
                responses.matchers.header_matcher(
                    {'Authorization': 'Basic ZGlnaXBheS1jbGllbnQtaWQ6ZGlnaXBheS1jbGllbnQtc2VjcmV0'}
                ),
                responses.matchers.urlencoded_params_matcher(
                    {
                        'username': 'digipay-username',
                        'password': 'digipay-password',
                        'grant_type': 'password',
                    }
                ),
            ],
        )

        url = 'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/activation'
        responses.post(
            url=url,
            json={
                'status': 'FAILED',
                'result': {
                    'title': 'failure',
                    'status': 19701,
                    'message': 'کاربر مورد نظر در بلک لیست قرار دارد',
                    'level': 'INFO',
                },
            },
            status=422,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'nationalCode': '0010000000',
                        'cellNumber': '09120000000',
                        'birthDate': '1369-07-18',
                        'amount': 20_000_000,
                    },
                ),
            ],
        )

        self._precondition_user_service(
            service=self.digipay_credit_service,
            service_limit_amount=Decimal(50_000_000),
            charge_account_amount=Decimal(1000),
        )
        response = self._post_request(data={'serviceId': self.digipay_credit_service.pk, 'amount': 20_000_000})

        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ExternalProviderError',
            message='فعالسازی اعتبار از طرف سرویس‌دهنده برای شما امکان‌پذیر نیست.',
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_create_digipay_user_service_failed_invalid_user_identity(self, *_):
        responses.post(
            url='https://uat.mydigipay.info/digipay/api/oauth/token',
            json={
                'access_token': 'ACCESS_TOKEN',
                'refresh_token': 'REFRESH_TOKEN',
                'token_type': 'Bearer',
                'expires_in': 599,
            },
            status=200,
            match=[
                responses.matchers.header_matcher(
                    {'Authorization': 'Basic ZGlnaXBheS1jbGllbnQtaWQ6ZGlnaXBheS1jbGllbnQtc2VjcmV0'}
                ),
                responses.matchers.urlencoded_params_matcher(
                    {
                        'username': 'digipay-username',
                        'password': 'digipay-password',
                        'grant_type': 'password',
                    }
                ),
            ],
        )

        url = 'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/activation'
        responses.post(
            url=url,
            json={
                'result': {
                    'level': 'WARN',
                    'title': 'SMC_SHAHKAR_FAILED',
                    'status': 19702,
                    'message': 'شناسه ملی و شماره همراه با هم تطابق ندارند',
                }
            },
            status=422,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'nationalCode': '0010000000',
                        'cellNumber': '09120000000',
                        'birthDate': '1369-07-18',
                        'amount': 20_000_000,
                    },
                ),
            ],
        )

        self._precondition_user_service(
            service=self.digipay_credit_service,
            service_limit_amount=Decimal(50_000_000),
            charge_account_amount=Decimal(1000),
        )
        response = self._post_request(data={'serviceId': self.digipay_credit_service.pk, 'amount': 20_000_000})

        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ExternalProviderError',
            message='فعالسازی اعتبار به دلیل مطابقت نداشتن کد ملی و شماره موبایل در سرویس‌دهنده امکان‌پذیر نیست.',
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_create_digipay_user_service_failed_unknown_provider_error(self, *_):
        responses.post(
            url='https://uat.mydigipay.info/digipay/api/oauth/token',
            json={
                'access_token': 'ACCESS_TOKEN',
                'refresh_token': 'REFRESH_TOKEN',
                'token_type': 'Bearer',
                'expires_in': 599,
            },
            status=200,
            match=[
                responses.matchers.header_matcher(
                    {'Authorization': 'Basic ZGlnaXBheS1jbGllbnQtaWQ6ZGlnaXBheS1jbGllbnQtc2VjcmV0'}
                ),
                responses.matchers.urlencoded_params_matcher(
                    {
                        'username': 'digipay-username',
                        'password': 'digipay-password',
                        'grant_type': 'password',
                    }
                ),
            ],
        )

        url = 'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/activation'
        responses.post(
            url=url,
            json={
                'result': {
                    'level': 'WARN',
                    'title': 'CREDIT_ONB_BUSINESS_ID_AND_CREDIT_ID_MISMATCH',
                    'status': 5382,
                    'message': 'شناسه اعتباری با شناسه بیزنس تطابق ندارد.',
                }
            },
            status=422,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'nationalCode': '0010000000',
                        'cellNumber': '09120000000',
                        'birthDate': '1369-07-18',
                        'amount': 20_000_000,
                    },
                ),
            ],
        )

        self._precondition_user_service(
            service=self.digipay_credit_service,
            service_limit_amount=Decimal(50_000_000),
            charge_account_amount=Decimal(1000),
        )
        response = self._post_request(data={'serviceId': self.digipay_credit_service.pk, 'amount': 20_000_000})

        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ExternalProviderError',
            message='سرویس‌دهنده در دسترس نیست. کمی بعد دوباره تلاش کنید.',
        )

    @responses.activate
    @patch.object(AZKI, 'username', 'test-username')
    @patch.object(AZKI, 'password', 'test-password')
    @patch.object(AZKI, 'contract_id', 123456)
    def test_create_azki_user_service_failed_user_has_active_loan(self):
        service = self.create_service(
            provider=Service.PROVIDERS.azki,
            tp=Service.TYPES.loan,
            options=dict(
                LoanServiceOptions(
                    min_principal_limit=100_000_000,
                    max_principal_limit=750_000_000,
                    periods=[12, 18],
                    provider_fee=Decimal(10),
                )
            ),
        )

        responses.post(
            url='https://service.azkiloan.com/auth/login',
            json={
                'rsCode': 0,
                'result': {'token': 'test-access-token'},
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'username': 'test-username',
                        'password': 'test-password',
                    }
                ),
            ],
        )

        amount = 100_000_000
        period = 12
        responses.get(
            url='https://service.azkiloan.com/crypto-exchange/plans',
            json={
                'rsCode': 0,
                'result': [
                    {
                        'name': 'ازکی فاند',
                        'logoUrl': 'https://cdn.azkiloan.com/1403/0715/7e219c15-9088-4f12-9dbd-5448cc583d89.jpg',
                        'interestRate': 23.0000,
                        'monthlyAmount': 9407633,
                        'feeRate': 13.5000,
                        'feeAmount': 13500000,
                        'sumOfAmounts': 126391596,
                        'loanAmount': 100000000,
                        'repaymentModel': 'دفترچه اقساط',
                        'period': 12,
                    },
                    {
                        'name': 'ازکی فاند',
                        'logoUrl': 'https://cdn.azkiloan.com/1403/0715/7e219c15-9088-4f12-9dbd-5448cc583d89.jpg',
                        'interestRate': 23.0000,
                        'monthlyAmount': 9407633,
                        'feeRate': 13.5000,
                        'feeAmount': 13500000,
                        'sumOfAmounts': 126391596,
                        'loanAmount': 100000000,
                        'repaymentModel': 'دفترچه اقساط',
                        'period': 12,
                    },
                ],
            },
            match=[
                responses.matchers.query_param_matcher({'amount': amount, 'period': period}),
                responses.matchers.header_matcher({'Authorization': 'Bearer test-access-token'}),
            ],
        )

        responses.post(
            url='https://service.azkiloan.com/crypto-exchange/request-credit',
            json={'result': 5496996, 'rsCode': 76, 'message': 'This user has active request(couponBook): 5496996'},
            status=409,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'user': {
                            'first_name': 'Ali',
                            'last_name': 'Ali',
                            'mobile_number': '09120000000',
                            'national_code': '0010000000',
                        },
                        'amount': 100_000_000,
                        'financier_id': 123456,
                        'period': 12,
                    }
                )
            ],
        )

        self._precondition_user_service(
            service=service, service_limit_amount=200_000_000, charge_account_amount=Decimal('2000')
        )

        response = self._post_request(data={'serviceId': service.pk, 'amount': amount, 'period': period})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ExternalProviderError',
            message='فعالسازی وام به‌دلیل فعال بودن یک وام دیگر در سرویس‌دهنده امکان‌پذیر نیست.',
        )

        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 3

    @responses.activate
    @patch.object(AZKI, 'username', 'test-username')
    @patch.object(AZKI, 'password', 'test-password')
    @patch.object(AZKI, 'contract_id', 123456)
    def test_create_azki_user_service_success_but_invalid_response(self):
        service = self.create_service(
            provider=Service.PROVIDERS.azki,
            tp=Service.TYPES.loan,
            options=dict(
                LoanServiceOptions(
                    min_principal_limit=100_000_000,
                    max_principal_limit=750_000_000,
                    periods=[12, 18],
                    provider_fee=Decimal(10),
                )
            ),
        )

        responses.post(
            url='https://service.azkiloan.com/auth/login',
            json={
                'rsCode': 0,
                'result': {'token': 'test-access-token'},
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'username': 'test-username',
                        'password': 'test-password',
                    }
                ),
            ],
        )

        amount = 100_000_000
        period = 12
        responses.get(
            url='https://service.azkiloan.com/crypto-exchange/plans',
            json={
                'rsCode': 0,
                'result': [
                    {
                        'name': 'ازکی فاند',
                        'logoUrl': 'https://cdn.azkiloan.com/1403/0715/7e219c15-9088-4f12-9dbd-5448cc583d89.jpg',
                        'interestRate': 23.0000,
                        'monthlyAmount': 9407633,
                        'feeRate': 13.5000,
                        'feeAmount': 13500000,
                        'sumOfAmounts': 126391596,
                        'loanAmount': 100000000,
                        'repaymentModel': 'دفترچه اقساط',
                        'period': 12,
                    },
                    {
                        'name': 'ازکی فاند',
                        'logoUrl': 'https://cdn.azkiloan.com/1403/0715/7e219c15-9088-4f12-9dbd-5448cc583d89.jpg',
                        'interestRate': 23.0000,
                        'monthlyAmount': 9407633,
                        'feeRate': 13.5000,
                        'feeAmount': 13500000,
                        'sumOfAmounts': 126391596,
                        'loanAmount': 100000000,
                        'repaymentModel': 'دفترچه اقساط',
                        'period': 12,
                    },
                ],
            },
            match=[
                responses.matchers.query_param_matcher({'amount': amount, 'period': period}),
                responses.matchers.header_matcher({'Authorization': 'Bearer test-access-token'}),
            ],
        )

        responses.post(
            url='https://service.azkiloan.com/crypto-exchange/request-credit',
            json={
                'result': 5496996,
                'rsCode': 0,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'user': {
                            'first_name': 'Ali',
                            'last_name': 'Ali',
                            'mobile_number': '09120000000',
                            'national_code': '0010000000',
                        },
                        'amount': 100_000_000,
                        'financier_id': 123456,
                        'period': 12,
                    }
                )
            ],
        )

        self._precondition_user_service(
            service=service, service_limit_amount=200_000_000, charge_account_amount=Decimal('2000')
        )

        response = self._post_request(data={'serviceId': service.pk, 'amount': amount, 'period': period})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ThirdPartyError',
            message='ThirdPartyError',
        )

        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 3

    @responses.activate
    @patch.object(AZKI, 'username', 'test-username')
    @patch.object(AZKI, 'password', 'test-password')
    @patch.object(AZKI, 'contract_id', 123456)
    def test_create_azki_user_service_failed_unknown_provider_error(self):
        service = self.create_service(
            provider=Service.PROVIDERS.azki,
            tp=Service.TYPES.loan,
            options=dict(
                LoanServiceOptions(
                    min_principal_limit=100_000_000,
                    max_principal_limit=750_000_000,
                    periods=[12, 18],
                    provider_fee=Decimal(10),
                )
            ),
        )

        responses.post(
            url='https://service.azkiloan.com/auth/login',
            json={
                'rsCode': 0,
                'result': {'token': 'test-access-token'},
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'username': 'test-username',
                        'password': 'test-password',
                    }
                ),
            ],
        )

        amount = 100_000_000
        period = 12
        responses.get(
            url='https://service.azkiloan.com/crypto-exchange/plans',
            json={
                'rsCode': 0,
                'result': [
                    {
                        'name': 'ازکی فاند',
                        'logoUrl': 'https://cdn.azkiloan.com/1403/0715/7e219c15-9088-4f12-9dbd-5448cc583d89.jpg',
                        'interestRate': 23.0000,
                        'monthlyAmount': 9407633,
                        'feeRate': 13.5000,
                        'feeAmount': 13500000,
                        'sumOfAmounts': 126391596,
                        'loanAmount': 100000000,
                        'repaymentModel': 'دفترچه اقساط',
                        'period': 12,
                    },
                    {
                        'name': 'ازکی فاند',
                        'logoUrl': 'https://cdn.azkiloan.com/1403/0715/7e219c15-9088-4f12-9dbd-5448cc583d89.jpg',
                        'interestRate': 23.0000,
                        'monthlyAmount': 9407633,
                        'feeRate': 13.5000,
                        'feeAmount': 13500000,
                        'sumOfAmounts': 126391596,
                        'loanAmount': 100000000,
                        'repaymentModel': 'دفترچه اقساط',
                        'period': 12,
                    },
                ],
            },
            match=[
                responses.matchers.query_param_matcher({'amount': amount, 'period': period}),
                responses.matchers.header_matcher({'Authorization': 'Bearer test-access-token'}),
            ],
        )

        responses.post(
            url='https://service.azkiloan.com/crypto-exchange/request-credit',
            json={'result': 1000, 'rsCode': 55, 'message': 'this is new error.'},
            status=422,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'user': {
                            'first_name': 'Ali',
                            'last_name': 'Ali',
                            'mobile_number': '09120000000',
                            'national_code': '0010000000',
                        },
                        'amount': 100_000_000,
                        'financier_id': 123456,
                        'period': 12,
                    }
                )
            ],
        )

        self._precondition_user_service(
            service=service, service_limit_amount=200_000_000, charge_account_amount=Decimal('2000')
        )

        response = self._post_request(data={'serviceId': service.pk, 'amount': amount, 'period': period})
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ExternalProviderError',
            message='سرویس‌دهنده در دسترس نیست. کمی بعد دوباره تلاش کنید.',
        )

        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 3

    @responses.activate
    @patch.object(AZKI, 'username', 'test-username')
    @patch.object(AZKI, 'password', 'test-password')
    @patch.object(AZKI, 'contract_id', 123456)
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful_azki_almost_exact_collateral(self, _):
        service = self.create_service(
            provider=Service.PROVIDERS.azki,
            tp=Service.TYPES.loan,
            options=dict(
                LoanServiceOptions(
                    min_principal_limit=100_000_000,
                    max_principal_limit=750_000_000,
                    periods=[12, 18],
                    provider_fee=Decimal(10),
                )
            ),
        )

        amount = 100_000_000
        period = 12
        request_id = 344820

        responses.post(
            url='https://service.azkiloan.com/auth/login',
            json={
                'rsCode': 0,
                'result': {'token': 'test-access-token'},
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'username': 'test-username',
                        'password': 'test-password',
                    }
                ),
            ],
        )

        responses.get(
            url='https://service.azkiloan.com/crypto-exchange/plans',
            json={
                'rsCode': 0,
                'result': [
                    {
                        'name': 'ازکی فاند',
                        'logoUrl': 'https://cdn.azkiloan.com/1403/0715/7e219c15-9088-4f12-9dbd-5448cc583d89.jpg',
                        'interestRate': 23.0000,
                        'monthlyAmount': 9407633,
                        'feeRate': 13.5000,
                        'feeAmount': 13500000,
                        'sumOfAmounts': 126391596,
                        'loanAmount': 100000000,
                        'repaymentModel': 'دفترچه اقساط',
                        'period': 12,
                    },
                    {
                        'name': 'ازکی فاند',
                        'logoUrl': 'https://cdn.azkiloan.com/1403/0715/7e219c15-9088-4f12-9dbd-5448cc583d89.jpg',
                        'interestRate': 23.0000,
                        'monthlyAmount': 9407633,
                        'feeRate': 13.5000,
                        'feeAmount': 13500000,
                        'sumOfAmounts': 126391596,
                        'loanAmount': 100000000,
                        'repaymentModel': 'دفترچه اقساط',
                        'period': 12,
                    },
                ],
            },
            match=[
                responses.matchers.query_param_matcher({'amount': amount, 'period': period}),
                responses.matchers.header_matcher({'Authorization': 'Bearer test-access-token'}),
            ],
        )

        responses.post(
            url='https://service.azkiloan.com/crypto-exchange/request-credit',
            json={
                'rsCode': 0,
                'result': {'request_id': request_id, 'credit_account_id': 4982134, 'coupon_book_id': 543678},
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'user': {
                            'first_name': 'Ali',
                            'last_name': 'Ali',
                            'mobile_number': '09120000000',
                            'national_code': '0010000000',
                        },
                        'amount': 100_000_000,
                        'financier_id': 123456,
                        'period': 12,
                    }
                )
            ],
        )

        self._precondition_user_service(
            service=service, service_limit_amount=200_000_000, charge_account_amount=Decimal('1500')
        )

        response = self._post_request(data={'serviceId': service.pk, 'amount': amount, 'period': period})
        data = self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )

        assert 'userService' in data

        assert 'collateralFeePercent' in data['userService']
        assert data['userService']['collateralFeePercent'] == '0'
        assert 'collateralFeeAmount' in data['userService']
        assert data['userService']['collateralFeeAmount'] == 0

        self._check_user_service(
            UserService(
                user=self.user,
                service=service,
                account_number=str(request_id),
                principal=amount,
                total_repayment=Decimal('126391596'),
                initial_debt=Decimal('112891596'),
                current_debt=Decimal('112891596'),
                installment_amount=Decimal('9407633'),
                installment_period=period,
                provider_fee_percent=Decimal('13.5'),
                provider_fee_amount=Decimal('13500000'),
                extra_info={'request_id': request_id, 'credit_account_id': 4982134, 'coupon_book_id': 543678},
                status=UserService.Status.initiated,
            ),
        )
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 3

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_create_digipay_user_service_failed_create_account_has_debt_error(self, *_):
        responses.post(
            url='https://uat.mydigipay.info/digipay/api/oauth/token',
            json={
                'access_token': 'ACCESS_TOKEN',
                'refresh_token': 'REFRESH_TOKEN',
                'token_type': 'Bearer',
                'expires_in': 599,
            },
            status=200,
            match=[
                responses.matchers.header_matcher(
                    {'Authorization': 'Basic ZGlnaXBheS1jbGllbnQtaWQ6ZGlnaXBheS1jbGllbnQtc2VjcmV0'}
                ),
                responses.matchers.urlencoded_params_matcher(
                    {
                        'username': 'digipay-username',
                        'password': 'digipay-password',
                        'grant_type': 'password',
                    }
                ),
            ],
        )

        url = 'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/activation'
        responses.post(
            url=url,
            json={
                'result': {
                    'level': 'WARN',
                    'title': 'CREDIT_ACCOUNT_HAS_DEBT',
                    'status': 17805,
                    'message': 'حساب اعتبار دارای بدهی می‌باشد.',
                }
            },
            status=422,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'nationalCode': '0010000000',
                        'cellNumber': '09120000000',
                        'birthDate': '1369-07-18',
                        'amount': 20_000_000,
                    },
                ),
            ],
        )

        self._precondition_user_service(
            service=self.digipay_credit_service,
            service_limit_amount=Decimal(50_000_000),
            charge_account_amount=Decimal(1000),
        )
        response = self._post_request(data={'serviceId': self.digipay_credit_service.pk, 'amount': 20_000_000})

        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ExternalProviderError',
            message='فعالسازی اعتبار به دلیل بدهی در سرویس‌دهنده امکان‌پذیر نیست.',
        )
