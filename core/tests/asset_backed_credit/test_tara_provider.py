from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
import responses
from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import ThirdPartyError
from exchange.asset_backed_credit.externals.providers import TARA
from exchange.asset_backed_credit.externals.providers.tara import (
    TaraChargeToAccount,
    TaraCheckUserBalance,
    TaraCreateAccount,
    TaraDischargeAccount,
    TaraGetTraceNumber,
    TaraRenewToken,
    TaraTotalInstallments,
)
from exchange.asset_backed_credit.externals.restriction import UserRestrictionType
from exchange.asset_backed_credit.models import OutgoingAPICallLog
from exchange.asset_backed_credit.services.logging import process_abc_outgoing_api_logs
from exchange.asset_backed_credit.services.providers.dispatcher import TaraCreditAPIs, api_dispatcher
from exchange.asset_backed_credit.types import UserInfo, UserServiceCreateResponse
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import SIGN, ABCMixins, APIHelper, MockCacheValue, sign_mock
from tests.base.utils import mock_on_commit


class TaraProviderRenewTokenTest(TestCase):
    def setUp(self):
        cache.clear()
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()
        Settings.set_cached_json('scrubber_sensitive_fields', [])

    def tearDown(self):
        cache.clear()

    def test_set_and_get_token(self):
        value = 'XXX'
        TARA.set_token(value, timeout=2)
        tara_token = TARA.get_token()
        assert tara_token
        assert tara_token == value

    @responses.activate
    def test_renew_token_error_not_respond(self):
        with pytest.raises(ThirdPartyError):
            TaraRenewToken().request()
        assert not TARA.get_token()
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.count() == 1
        api_log = OutgoingAPICallLog.objects.last()
        assert api_log.retry == 3

    @responses.activate
    def test_renew_token_error_wrong_auth_data(self):
        # wrong user or pass
        responses.post(
            url=TaraRenewToken.url,
            json={
                'data': {'code': 840002, 'message': 'نام کاربری یا رمز عبور اشتباه است. یا کابر غیر فعال است.'},
                'success': False,
                'timestamp': '2023-12-02T13:18:33.380918861Z',
                'cause': 'exception',
            },
            status=417,
            match=[
                responses.matchers.json_params_matcher(
                    {'principal': TARA.username, 'password': TARA.password},
                ),
            ],
        )
        with pytest.raises(ThirdPartyError):
            TaraRenewToken().request()
        assert not TARA.get_token()
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 1
        api_log = OutgoingAPICallLog.objects.all().first()
        assert api_log.request_body == {'principal': '*****', 'password': '*****'}

    @responses.activate
    def test_renew_token_wrong_format_response(self):
        tara_token = TARA.get_token()
        assert not tara_token
        # has not accessCode
        responses.post(
            url=TaraRenewToken.url,
            json={
                'success': True,
                'doTime': None,
                'message': 'login success test',
                'code': 0,
                'expiryDuration': 1800000,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {'principal': TARA.username, 'password': TARA.password},
                ),
            ],
        )
        with pytest.raises(ThirdPartyError):
            TaraRenewToken().request()
        tara_token = TARA.get_token()
        assert not tara_token
        # wrong format expiryDuration
        responses.post(
            url=TaraRenewToken.url,
            json={
                'success': True,
                'doTime': None,
                'message': 'login success test',
                'code': 0,
                'accessCode': 'X',
                'expiryDuration': '1800000',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {'principal': TARA.username, 'password': TARA.password},
                ),
            ],
        )
        with pytest.raises(ThirdPartyError):
            TaraRenewToken().request()
        tara_token = TARA.get_token()
        assert not tara_token
        # wrong format expiryDuration
        responses.post(
            url=TaraRenewToken.url,
            json={
                'success': True,
                'doTime': None,
                'message': 'login success test',
                'code': 0,
                'accessCode': None,
                'expiryDuration': 1800000,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {'principal': TARA.username, 'password': TARA.password},
                ),
            ],
        )
        with pytest.raises(ThirdPartyError):
            TaraRenewToken().request()
        tara_token = TARA.get_token()
        assert not tara_token
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 3

    @responses.activate
    def test_renew_token_successful(self):
        # set expired token
        value = 'XXX'
        TARA.set_token(value, timeout=1)
        assert TARA.get_token() == value
        cache.clear()
        # get new token
        value = 'YYY'
        responses.post(
            url=TaraRenewToken.url,
            json={
                'success': True,
                'doTime': None,
                'message': 'login success',
                'code': 0,
                'accessCode': value,
                'expiryDuration': 1800000,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {'principal': TARA.username, 'password': TARA.password},
                ),
            ],
        )
        tara_token = TaraRenewToken().request()
        assert tara_token
        assert tara_token == value
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 1
        api_log = OutgoingAPICallLog.objects.all().first()
        assert api_log.request_body == {'principal': '*****', 'password': '*****'}


class TaraProviderCreateAccountTest(TestCase, ABCMixins):
    def setUp(self) -> None:
        self.user = User.objects.get(pk=202)
        self.user.national_code = '9579321906'
        self.user.birthday = date(year=1993, month=11, day=15)
        self.user.mobile = '99800000012'
        self.user.save()
        self.service = self.create_service()
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful(self, *_):
        TARA.set_token(None)
        token = 'XXX'
        responses.post(
            url=TaraRenewToken.url,
            json={
                'success': True,
                'doTime': None,
                'message': 'login success',
                'code': 0,
                'accessCode': token,
                'expiryDuration': 1800000,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {'principal': TARA.username, 'password': TARA.password},
                ),
            ],
        )
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
                        'mobile': '99800000012',
                        'nationalCode': '9579321906',
                        'name': 'User',
                        'family': 'Two',
                        'sign': SIGN,
                    },
                ),
            ],
        )
        user_service = self.create_user_service(user=self.user, service=self.service)
        account_number = TaraCreateAccount(
            user_service,
            self.get_user_service_create_request(
                user_info=UserInfo(
                    national_code=user_service.user.national_code,
                    mobile=user_service.user.mobile,
                    first_name=user_service.user.first_name,
                    last_name=user_service.user.last_name,
                    birthday_shamsi=user_service.user.birthday_shamsi,
                ),
                amount=int(user_service.initial_debt),
                unique_id=str(user_service.external_id),
            ),
        ).request()
        assert TARA.get_token() == token
        assert account_number
        assert account_number == account_number_data
        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=200, user_service=user_service, service=self.service.tp),
        )


class TaraProviderGetTraceNumberTest(TestCase, ABCMixins):
    def setUp(self) -> None:
        TARA.set_token('XXX')
        self.user = User.objects.get(pk=202)
        self.service = self.create_service()
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    def test_successful(self):
        user_service = self.create_user_service(user=self.user, service=self.service)
        trace_number_data = '1234'
        url = TaraGetTraceNumber('charge', user_service).url
        amount = '100000'
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': trace_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': None,
                        'nationalCode': None,
                        'amount': str(amount),
                    },
                ),
            ],
        )
        trace_number = TaraGetTraceNumber(tp='charge', user_service=user_service).request(amount=amount)
        process_abc_outgoing_api_logs()
        assert trace_number
        assert trace_number == trace_number_data
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=200, user_service=user_service, service=self.service.tp),
        )


class TaraProviderChargeToAccountTest(TestCase, ABCMixins):
    def setUp(self) -> None:
        TARA.set_token('XXX')
        self.user = User.objects.get(pk=202)
        self.service = self.create_service()
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful(self, sign_method_mock):
        trace_number_data = '1234'
        reference_number_data = '123456'
        amount = Decimal(100000)
        user_service = self.create_user_service(user=self.user, service=self.service, initial_debt=amount)
        url = TaraGetTraceNumber('charge', user_service).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': trace_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': None,
                        'nationalCode': None,
                        'amount': str(amount),
                    },
                ),
            ],
        )
        url = TaraChargeToAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'referenceNumber': reference_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': None,
                        'nationalCode': None,
                        'amount': str(amount),
                        'sign': SIGN,
                        'traceNumber': trace_number_data,
                    },
                ),
            ],
        )
        reference_number = TaraChargeToAccount(user_service=user_service, amount=amount).request()
        process_abc_outgoing_api_logs()
        assert reference_number
        assert reference_number == reference_number_data
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=200, user_service=user_service, service=self.service.tp),
        )
        user_service.refresh_from_db()
        sign_method_mock.assert_called_once_with(
            f'{TARA.contract_id},{self.user.mobile},{self.user.national_code},{str(int(user_service.initial_debt))}'
        )


class TaraProviderDischargeAccountTest(TestCase, ABCMixins):
    def setUp(self) -> None:
        TARA.set_token('XXX')
        self.user = User.objects.get(pk=202)
        self.service = self.create_service()
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful(self, sign_method_mock):
        trace_number_data = '1234'
        reference_number_data = '123456'
        amount = Decimal(2000)
        user_service = self.create_user_service(
            user=self.user, service=self.service, initial_debt=amount, current_debt=amount
        )
        url = TaraGetTraceNumber('decharge', user_service).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': trace_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': None,
                        'nationalCode': None,
                        'amount': str(amount),
                    },
                ),
            ],
        )
        url = TaraDischargeAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'referenceNumber': reference_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': None,
                        'nationalCode': None,
                        'amount': str(amount),
                        'sign': SIGN,
                        'traceNumber': trace_number_data,
                    },
                ),
            ],
        )
        reference_number = TaraDischargeAccount(user_service=user_service, amount=amount).request()
        process_abc_outgoing_api_logs()
        assert reference_number
        assert reference_number == reference_number_data
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=200, user_service=user_service, service=self.service.tp),
        )
        user_service.refresh_from_db()
        sign_method_mock.assert_called_once_with(
            f'{TARA.contract_id},{self.user.mobile},{self.user.national_code},{str(int(user_service.initial_debt))}'
        )


class TaraProviderCheckUserBalanceTest(TestCase, ABCMixins):
    def setUp(self) -> None:
        TARA.set_token('XXX')
        self.user = User.objects.get(pk=202)
        self.service = self.create_service()
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful(self, *_):
        account_number = '1234'
        balance_data = '123456'
        user_service = self.create_user_service(user=self.user, service=self.service, account_number=account_number)
        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': account_number,
                'balance': balance_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': None,
                        'nationalCode': None,
                        'accountNumber': account_number,
                        'sign': SIGN,
                    },
                ),
            ],
        )

        balance = TaraCheckUserBalance(user_service=user_service).request()
        assert balance
        assert balance == Decimal(balance_data)
        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=200, service=self.service.tp, user_service=user_service),
        )


class TaraProviderTotalInstallmentsTest(ABCMixins, APIHelper):
    def setUp(self) -> None:
        TARA.set_token('XXX')
        self.user = User.objects.get(pk=202)
        self._change_parameters_in_object(self.user, {'national_code': '0010000000', 'mobile': '09120000000'})
        self.service = self.create_service()
        self.user_service = self.create_user_service(user=self.user, service=self.service)
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful(self, *_):
        not_settled = 25970000
        url = TaraTotalInstallments(self.user_service).url
        responses.post(
            url=url,
            json={
                'value': {
                    'pages': 1,
                    'elements': 2,
                    'items': [
                        {
                            'amount': not_settled,
                            'status': 'NOT_SETTLED',
                            'nationalCode': self.user.national_code,
                            'mobile': self.user.mobile,
                        },
                    ],
                },
                'status': {
                    'timestamp': '2024-02-26T14:38:31.878+00:00',
                    'code': '1',
                    'message': [
                        'با موفقیت انجام شد.',
                    ],
                },
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'status': 'NOT_SETTLED',
                        'sign': SIGN,
                    },
                ),
            ],
        )

        amount = TaraTotalInstallments(user_service=self.user_service).request()
        assert amount == not_settled
        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=200, service=self.service.tp, user_service=self.user_service),
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful_amount_zero(self, *_):
        not_settled = 0
        url = TaraTotalInstallments(self.user_service).url
        responses.post(
            url=url,
            json={
                'value': {
                    'pages': 1,
                    'elements': 2,
                    'items': [
                        {
                            'amount': not_settled,
                            'status': 'NOT_SETTLED',
                            'nationalCode': self.user.national_code,
                            'mobile': self.user.mobile,
                        },
                    ],
                },
                'status': {
                    'timestamp': '2024-02-26T14:38:31.878+00:00',
                    'code': '1',
                    'message': [
                        'با موفقیت انجام شد.',
                    ],
                },
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'status': 'NOT_SETTLED',
                        'sign': SIGN,
                    },
                ),
            ],
        )

        amount = TaraTotalInstallments(user_service=self.user_service).request()
        assert amount == not_settled
        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=200, service=self.service.tp, user_service=self.user_service),
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_empty_not_settled(self, *_):
        url = TaraTotalInstallments(self.user_service).url
        responses.post(
            url=url,
            json={
                'value': {
                    'pages': 1,
                    'elements': 2,
                    'items': [
                        {
                            'amount': None,
                            'status': 'NOT_SETTLED',
                            'nationalCode': self.user.national_code,
                            'mobile': self.user.mobile,
                        },
                    ],
                },
                'status': {
                    'timestamp': '2024-02-26T14:38:31.878+00:00',
                    'code': '1',
                    'message': [
                        'با موفقیت انجام شد.',
                    ],
                },
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'status': 'NOT_SETTLED',
                        'sign': SIGN,
                    },
                ),
            ],
        )
        with pytest.raises(ThirdPartyError):
            TaraTotalInstallments(user_service=self.user_service).request()
        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=200, service=self.service.tp, user_service=self.user_service),
        )


class TaraIntegrationAPIsTest(TestCase, ABCMixins):
    def setUp(self) -> None:
        TARA.set_token('XXX')
        self.user = self.create_user()
        self.service = self.create_service()
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful(self, *_):
        previous_log_count = OutgoingAPICallLog.objects.count()
        account_number = '1234'
        trace_number = '1234'
        reference_number = '123456'
        amount = 10000
        user_service = self.create_user_service(
            user=self.user,
            service=self.service,
            current_debt=amount,
            initial_debt=amount,
        )
        responses.post(
            url=TaraCreateAccount.url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': account_number,
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
        responses.post(
            url=TaraGetTraceNumber('charge', user_service).url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': trace_number,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': str(amount),
                    },
                ),
            ],
        )
        responses.post(
            url=TaraChargeToAccount.url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'referenceNumber': reference_number,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': str(amount),
                        'sign': SIGN,
                        'traceNumber': trace_number,
                    },
                ),
            ],
        )
        result = api_dispatcher(user_service).create_user_service(
            request_data=self.get_user_service_create_request(
                user_info=UserInfo(
                    national_code=user_service.user.national_code,
                    mobile=user_service.user.mobile,
                    first_name=user_service.user.first_name,
                    last_name=user_service.user.last_name,
                    birthday_shamsi=user_service.user.birthday_shamsi,
                ),
                amount=int(user_service.initial_debt),
                unique_id=str(user_service.external_id),
            )
        )
        assert result.status == UserServiceCreateResponse.Status.SUCCEEDED
        assert result.provider_tracking_id == '1234'
        assert result.amount == Decimal(amount)

        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.count() == 3 + previous_log_count

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.tasks.add_user_restriction_task.delay')
    def test_content_type_json(self, mock_add_restriction, *_):
        user_service = self.create_user_service(user=self.user, service=self.service)
        url = TaraTotalInstallments(user_service).url
        responses.post(
            url=url,
            body='text-content',
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'status': 'NOT_SETTLED',
                        'sign': SIGN,
                    },
                ),
            ],
        )

        with pytest.raises(ThirdPartyError):
            TaraTotalInstallments(user_service=user_service).request()

        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            OutgoingAPICallLog(
                api_url=url,
                response_code=200,
                response_body={'body': 'text-content'},
                service=self.service.tp,
                user_service=user_service,
            )
        )
        assert mock_add_restriction.call_count == 0

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.tasks.add_user_restriction_task.delay')
    def test_http_error_response(self, mock_add_restriction, *_):
        user_service = self.create_user_service(user=self.user, service=self.service)
        url = TaraTotalInstallments(user_service).url

        for status_code in [400, 500]:
            responses.post(
                url=url,
                json={'success': False, 'error': str(status_code)},
                status=status_code,
                match=[
                    responses.matchers.json_params_matcher(
                        {
                            'mobile': self.user.mobile,
                            'nationalCode': self.user.national_code,
                            'status': 'NOT_SETTLED',
                            'sign': SIGN,
                        },
                    ),
                ],
            )

            with pytest.raises(ThirdPartyError):
                TaraTotalInstallments(user_service=user_service).request()

            process_abc_outgoing_api_logs()
            self.check_outgoing_log(
                OutgoingAPICallLog(
                    api_url=url,
                    response_code=status_code,
                    response_body={'success': False, 'error': str(status_code)},
                    service=self.service.tp,
                    user_service=user_service,
                )
            )

            assert mock_add_restriction.call_count == 0
