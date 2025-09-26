import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
import responses
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from rest_framework import status

from exchange.accounts.models import Notification, User
from exchange.asset_backed_credit.externals.providers import DIGIPAY, TARA, VENCY
from exchange.asset_backed_credit.externals.providers.tara import (
    TaraCheckUserBalance,
    TaraDischargeAccount,
    TaraGetTraceNumber,
)
from exchange.asset_backed_credit.externals.providers.vency import (
    VencyCancelOrderAPI,
    VencyGetOrderAPI,
    VencyRenewTokenAPI,
)
from exchange.asset_backed_credit.models import OutgoingAPICallLog, Service, SettlementTransaction, UserService
from exchange.asset_backed_credit.services.logging import process_abc_outgoing_api_logs
from exchange.asset_backed_credit.services.providers.dispatcher import api_dispatcher
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import SIGN, ABCMixins, APIHelper, MockCacheValue, sign_mock


@patch('exchange.asset_backed_credit.externals.price.PriceProvider.get_mark_price', lambda *_: 10000)
class TestCloseUserServiceAPI(APIHelper, ABCMixins):
    URL = '/asset-backed-credit/user-services/{}/close'

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.get(pk=201)
        cls.user.user_type = User.USER_TYPES.level1
        cls.user.mobile = '09120000000'
        cls.user.national_code = '0010000000'
        cls.user.first_name = 'Ali'
        cls.user.last_name = 'Ali'
        cls.user.save(update_fields=('user_type', 'mobile', 'national_code', 'first_name', 'last_name'))
        cls.user2 = User.objects.get(pk=202)

    def tearDown(self):
        cache.clear()

    def setUp(self) -> None:
        self._set_client_credentials(self.user.auth_token.key)
        self.service = self.create_service(contract_id='1234')
        TARA.set_token('XXX')
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    def test_error_service_id(self):
        # not sent user-service-id
        response = self._post_request(self.URL.format('0'))
        self._check_response(response=response, status_code=status.HTTP_404_NOT_FOUND)

        # wrong serviceId
        user_service = self.create_user_service(service=self.service, user=self.user2)
        response = self._post_request(self.URL.format(user_service.pk))
        self._check_response(response=response, status_code=status.HTTP_404_NOT_FOUND)

        # inactive service
        user_service = self.create_user_service(service=self.service, user=self.user, closed_at=ir_now())
        response = self._post_request(self.URL.format(user_service.pk))
        self._check_response(response=response, status_code=status.HTTP_404_NOT_FOUND)

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_unsuccessful_tara_error_check_balance(self, *_):
        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': False,
                'data': 'test error',
                'timestamp': '1701964345',
                'accountNumber': '1234',
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
        user_service = self.create_user_service(service=self.service, user=self.user, account_number='1234')
        response = self._post_request(self.URL.format(user_service.pk))
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ThirdPartyError',
            message='TaraCheckUserBalance: Fail to get balance',
        )
        user_service.refresh_from_db()
        assert user_service.current_debt > 0
        assert not user_service.closed_at
        assert user_service.status == UserService.STATUS.initiated
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.count() == 1

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_unsuccessful_tara_error_get_trace_number(self, *_):
        account_number_data = '1234'
        user_service = self.create_user_service(
            service=self.service,
            user=self.user,
            account_number=account_number_data,
        )
        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': 'test error',
                'timestamp': '1701964345',
                'accountNumber': '1234',
                'balance': '10000',
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
                        'amount': str(user_service.current_debt),
                    },
                ),
            ],
        )
        response = self._post_request(self.URL.format(user_service.pk))
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ThirdPartyError',
            message='TaraGetTraceNumber: Fail to get a trace number',
        )
        user_service.refresh_from_db()
        assert user_service.current_debt > 0
        assert not user_service.closed_at
        assert user_service.status == UserService.STATUS.initiated
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.count() == 2


    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_unsuccessful_tara_error_discharge_account(self, *_):
        account_number_data = '1234'
        user_service = self.create_user_service(
            service=self.service,
            user=self.user,
            account_number=account_number_data,
        )
        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': 'test error',
                'timestamp': '1701964345',
                'accountNumber': '1234',
                'balance': '10000',
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
                        'amount': str(user_service.current_debt),
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
                        'amount': str(user_service.current_debt),
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )
        response = self._post_request(self.URL.format(user_service.pk))
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ThirdPartyError',
            message='TaraDischargeAccount: Fail to discharge account',
        )
        user_service.refresh_from_db()
        assert user_service.current_debt > 0
        assert not user_service.closed_at
        assert user_service.status == UserService.STATUS.initiated
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.count() == 3

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_successful(self, mock_restriction_task, *_):
        account_number_data = '1234'
        user_service = self.create_user_service(
            service=self.service,
            user=self.user,
            account_number=account_number_data,
        )
        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': 'test error',
                'timestamp': '1701964345',
                'accountNumber': '1234',
                'balance': '10000',
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
                        'amount': str(user_service.current_debt),
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
                        'amount': str(user_service.current_debt),
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )
        response = self._post_request(self.URL.format(user_service.pk))
        data = self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )
        user_service.refresh_from_db()
        assert user_service.current_debt == 0
        assert user_service.closed_at
        assert user_service.status == UserService.STATUS.closed
        assert 'userService' in data

        notif = Notification.objects.filter(user=self.user).order_by('-created_at').first()
        assert notif
        assert notif.message == f'سرویس {user_service.service.readable_name} لغو شد.'
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.count() == 3
        mock_restriction_task.assert_called_once()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_permission_already_deactivated_successful(self, mock_restriction_task, *_):
        account_number_data = '1234'
        permission = self.create_user_service_permission(self.user, self.service)
        permission.deactivate()

        user_service = self.create_user_service(
            service=self.service,
            user=self.user,
            account_number=account_number_data,
            permission=permission,
        )
        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': 'test error',
                'timestamp': '1701964345',
                'accountNumber': '1234',
                'balance': '10000',
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
                        'amount': str(user_service.current_debt),
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
                        'amount': str(user_service.current_debt),
                        'sign': SIGN,
                        'traceNumber': '12345',
                    },
                ),
            ],
        )
        response = self._post_request(self.URL.format(user_service.pk))
        data = self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )
        user_service.refresh_from_db()
        assert user_service.current_debt == 0
        assert user_service.closed_at
        assert user_service.status == UserService.STATUS.closed
        assert 'userService' in data

        notif = Notification.objects.filter(user=self.user).order_by('-created_at').first()
        assert notif
        assert notif.message == f'سرویس {user_service.service.readable_name} لغو شد.'
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.count() == 3
        mock_restriction_task.assert_called_once()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_unsuccessful_user_service_has_active_debt(self, *_):
        account_number_data = '1234'
        user_service = self.create_user_service(
            service=self.service,
            user=self.user,
            account_number=account_number_data,
        )
        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': 'test error',
                'timestamp': '1701964345',
                'accountNumber': '1234',
                'balance': '9000',
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
        response = self._post_request(self.URL.format(user_service.pk))
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ExternalProviderError',
            message='لغو اعتبار به دلیل بدهی در سرویس‌دهنده امکان‌پذیر نیست.',
        )
        user_service.refresh_from_db()
        assert user_service.current_debt == 10000
        assert user_service.closed_at is None
        assert user_service.status == UserService.STATUS.initiated

        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.count() == 1


    @pytest.mark.slow()
    @patch('exchange.asset_backed_credit.services.providers.dispatcher.TaraCreditAPIs.discharge_account')
    @patch('exchange.asset_backed_credit.services.providers.dispatcher.TaraCreditAPIs.get_available_balance')
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_email_notification(self, mock_available_balance, *_):
        balance = 1000
        mock_available_balance.return_value = balance
        vp = self.user.get_verification_profile()
        vp.email_confirmed = True
        vp.save()

        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')
        account_number_data = '1234'
        user_service = self.create_user_service(
            service=self.service,
            user=self.user,
            account_number=account_number_data,
            initial_debt=balance,
        )
        api_dispatcher(user_service).close_user_service()
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    def test_not_implemented_error(self):
        service = self.create_service(tp=Service.TYPES.loan)
        user_service = self.create_user_service(user=self.user, service=service)
        response = self._post_request(self.URL.format(user_service.pk))
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code='NotImplementedError',
            message='This service not implemented yet.',
        )

    def test_pending_settlement(self):
        service = self.create_service(tp=Service.TYPES.credit)
        user_service = self.create_user_service(user=self.user, service=service)
        self.create_settlement(
            amount=Decimal('1000'), user_service=user_service, status=SettlementTransaction.STATUS.confirmed
        )
        response = self._post_request(self.URL.format(user_service.pk))
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='PendingSettlementExists',
            message='A pending settlement exists, try again later.',
        )
        user_service.refresh_from_db()
        assert user_service.current_debt == 10000
        assert user_service.closed_at is None
        assert user_service.status == UserService.STATUS.initiated

    @responses.activate
    def test_loan_success(self):
        service = self.create_service(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
        user_service = self.create_loan_user_service(
            user=self.user,
            service=service,
            current_debt=6_000_000_0,
            initial_debt=6_000_000_0,
            principal=5_000_000_0,
            total_repayment=6_000_000_0,
            installment_amount=500_000_0,
            installment_period=12,
            account_number=str(uuid.uuid4()),
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

        responses.get(
            url=VencyGetOrderAPI.get_url(user_service.account_number),
            json={
                'orderId': user_service.account_number,
                'type': 'LENDING',
                'status': 'IN_PROGRESS',
                'uniqueIdentifier': user_service.account_number,
                'createdAt': '2024-08-08T06:01:08.220457Z',
            },
            status=200,
        )

        responses.put(
            url=VencyCancelOrderAPI.get_url(user_service.account_number),
            status=200,
        )

        response = self._post_request(self.URL.format(user_service.pk))
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data['status'] == 'ok'
        assert data['userService']['currentDebt'] == '0'
        assert data['userService']['status'] == 'closed'
        assert data['userService']['closedAt'] is not None

        user_service.refresh_from_db()
        assert user_service.current_debt == 0
        assert user_service.status == UserService.STATUS.closed
        assert user_service.closed_at is not None

    @responses.activate
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_credit_digipay_success(self):
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

        url = 'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/close/test-account-number'
        responses.post(
            url=url,
            json={'result': {'title': 'success', 'status': 0, 'message': 'عملیات با موفقیت انجام شد', 'level': 'INFO'}},
            match=[responses.matchers.header_matcher({'Authorization': 'Bearer ACCESS_TOKEN'})],
            status=200,
        )

        service = self.create_service(provider=Service.PROVIDERS.digipay, tp=Service.TYPES.credit)
        user_service = self.create_user_service(
            user=self.user,
            service=service,
            current_debt=6_000_000_0,
            initial_debt=6_000_000_0,
            account_number='test-account-number',
        )

        response = self._post_request(self.URL.format(user_service.pk))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert data['userService']['status'] == 'close_requested'

        user_service.refresh_from_db()
        assert user_service.status == UserService.STATUS.close_requested

    @responses.activate
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_credit_digipay_failure(self):
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

        url = 'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/close/test-account-number'
        responses.post(
            url=url,
            json={
                'result': {
                    'title': 'success',
                    'status': 17805,
                    'message': 'کاربر دارای بدهی معوق می‌باشد',
                    'level': 'INFO',
                }
            },
            match=[responses.matchers.header_matcher({'Authorization': 'Bearer ACCESS_TOKEN'})],
            status=200,
        )

        service = self.create_service(provider=Service.PROVIDERS.digipay, tp=Service.TYPES.credit)
        user_service = self.create_user_service(
            user=self.user,
            service=service,
            current_debt=6_000_000_0,
            initial_debt=6_000_000_0,
            account_number='test-account-number',
        )

        response = self._post_request(self.URL.format(user_service.pk))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == 'ExternalProviderError'
        assert data['message'] == 'لغو اعتبار به دلیل بدهی در سرویس‌دهنده امکان‌پذیر نیست.'

        user_service.refresh_from_db()
        assert user_service.status == UserService.STATUS.initiated

    @responses.activate
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_credit_digipay_failure_already_closed_android_client(self):
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

        url = 'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/close/test-account-number'
        responses.post(
            url=url,
            json={
                'result': {
                    'title': 'success',
                    'status': 19705,
                    'message': 'اعتبار از قبل بسته است',
                    'level': 'INFO',
                }
            },
            match=[responses.matchers.header_matcher({'Authorization': 'Bearer ACCESS_TOKEN'})],
            status=200,
        )

        service = self.create_service(provider=Service.PROVIDERS.digipay, tp=Service.TYPES.credit)
        user_service = self.create_user_service(
            user=self.user,
            service=service,
            current_debt=6_000_000_0,
            initial_debt=6_000_000_0,
            account_number='test-account-number',
        )

        response = self._post_request(
            self.URL.format(user_service.pk),
            headers={'User-Agent': 'Android/6.8.0-dev'},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == 'این اعتبار قبلا لغو شده‌است.'
        assert data['message'] == 'ExternalProviderError'

        user_service.refresh_from_db()
        assert user_service.status == UserService.STATUS.initiated

    def test_failure_close_user_service_already_requested_error(self):
        service = self.create_service(provider=Service.PROVIDERS.digipay, tp=Service.TYPES.credit)
        user_service = self.create_user_service(
            user=self.user,
            service=service,
            current_debt=6_000_000_0,
            initial_debt=6_000_000_0,
            account_number='test-account-number',
            status=UserService.Status.close_requested,
        )

        response = self._post_request(self.URL.format(user_service.pk))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == 'CloseUserServiceAlreadyRequestedError'
        assert data['message'] == 'قبلا درخواست لغو را ثبت کرده‌اید. در صورتی که بدهی نداشته باشید، لغو انجام می‌شود.'

        user_service.refresh_from_db()
        assert user_service.status == UserService.Status.close_requested

    def test_loan_azki_failure_user_service_is_not_internally_closeable(self):
        service = self.create_service(provider=Service.PROVIDERS.azki, tp=Service.TYPES.loan)
        user_service = self.create_loan_user_service(
            user=self.user,
            service=service,
            principal=5_000_000_0,
            installment_period=10,
            current_debt=6_000_000_0,
            initial_debt=6_000_000_0,
            account_number='test-account-number',
        )

        response = self._post_request(self.URL.format(user_service.pk))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'status': 'failed',
            'code': 'UserServiceIsNotInternallyCloseable',
            'message': 'برای لغو وام لازم است از طریق سرویس‌دهنده اقدام کنید.',
        }

    @responses.activate
    def test_loan_vency_close_user_service_success_when_status_is_cancelled_in_provider(self):
        service = self.create_service(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
        user_service = self.create_loan_user_service(
            user=self.user,
            service=service,
            principal=5_000_000_0,
            installment_period=10,
            current_debt=6_000_000_0,
            initial_debt=6_000_000_0,
            account_number='test-account-number',
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

        responses.get(
            url=VencyGetOrderAPI.get_url(user_service.account_number),
            json={
                'orderId': str(uuid.uuid4()),
                'type': 'LENDING',
                'status': 'CANCELED_BY_USER',
                'uniqueIdentifier': user_service.account_number,
                'createdAt': '2024-08-08T06:01:08.220457Z',
            },
            status=200,
        )

        response = self._post_request(self.URL.format(user_service.pk))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert data['userService']['currentDebt'] == '0'
        assert data['userService']['status'] == 'closed'
        assert data['userService']['closedAt'] is not None

        user_service.refresh_from_db()
        assert user_service.current_debt == 0
        assert user_service.status == UserService.STATUS.closed
        assert user_service.closed_at is not None

    @responses.activate
    def test_loan_vency_close_user_service_failure_ongoing_loan_in_provider(self):
        service = self.create_service(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
        user_service = self.create_loan_user_service(
            user=self.user,
            service=service,
            principal=5_000_000_0,
            installment_period=10,
            current_debt=6_000_000_0,
            initial_debt=6_000_000_0,
            account_number='test-account-number',
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

        responses.get(
            url=VencyGetOrderAPI.get_url(user_service.account_number),
            json={
                'orderId': str(uuid.uuid4()),
                'type': 'LENDING',
                'status': 'LOAN_INSTALLMENTS_PAYMENT_IN_PROGRESS',
                'uniqueIdentifier': user_service.account_number,
                'createdAt': '2024-08-08T06:01:08.220457Z',
            },
            status=200,
        )

        response = self._post_request(self.URL.format(user_service.pk))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert data == {
            'status': 'failed',
            'code': 'ExternalProviderError',
            'message': 'لغو اعتبار به دلیل بدهی در سرویس‌دهنده امکان‌پذیر نیست.',
        }

        user_service.refresh_from_db()
        assert user_service.current_debt == 6_000_000_0
        assert user_service.status == UserService.STATUS.initiated
        assert user_service.closed_at is None
