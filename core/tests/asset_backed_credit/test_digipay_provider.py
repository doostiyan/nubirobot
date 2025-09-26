import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
import responses
from django.core.cache import cache
from django.test import TestCase, override_settings

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.providers import DIGIPAY
from exchange.asset_backed_credit.externals.providers.digipay import DigipayGetAccountAPI, DigipayRenewTokenApi
from exchange.asset_backed_credit.externals.providers.digipay.schema import ResponseSchema, ResultSchema
from exchange.asset_backed_credit.models import OutgoingAPICallLog, Service, UserService
from exchange.asset_backed_credit.services.logging import process_abc_outgoing_api_logs
from exchange.asset_backed_credit.services.providers.dispatcher import api_dispatcher
from exchange.asset_backed_credit.types import (
    UserInfo,
    UserServiceCloseResponse,
    UserServiceCreateRequest,
    UserServiceCreateResponse,
    UserServiceProviderMessage,
)
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import ABCMixins, MockCacheValue, sign_mock
from tests.base.utils import mock_on_commit


class DigipayProviderRenewTokenTestCase(TestCase):
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

    def test_provider_set_token(self):
        value = 'TOKEN'
        DIGIPAY.set_token(value, timeout=2)
        token = DIGIPAY.get_token()
        assert token == value

    @responses.activate
    @override_settings(SCRUBBER_SENSITIVE_FIELDS=[])
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_renew_token_successful(self):
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

        cache.clear()

        access_token = DigipayRenewTokenApi().request()
        assert access_token == 'ACCESS_TOKEN'

        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 1

        api_log = OutgoingAPICallLog.objects.all().first()
        assert api_log.request_body == {
            'username': 'digipay-username',
            'password': 'digipay-password',
            'grant_type': 'password',
        }


class DigipayProviderCreateAccountTestCase(TestCase, ABCMixins):
    def setUp(self) -> None:
        self.user, _ = User.objects.get_or_create(username='test-user')
        self.user.national_code = '1234567890'
        self.user.mobile = '09123004000'
        self.user.birthday = datetime.date(year=1990, month=10, day=10)
        self.user.save()
        self.service = self.create_service(provider=Service.PROVIDERS.digipay, tp=Service.TYPES.credit)
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_successful(self, *_):
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
                'allocatedAmount': 50_000_000,
                'result': {'title': 'SUCCESS', 'status': 0, 'message': 'عملیات با موفقیت انجام شد', 'level': 'INFO'},
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'nationalCode': '1234567890',
                        'cellNumber': '09123004000',
                        'birthDate': '1369-07-18',
                        'amount': 50_000_000,
                    },
                ),
            ],
        )

        user_service = UserService.objects.create(
            user=self.user,
            internal_user=self.create_internal_user(self.user),
            service=self.service,
            user_service_permission=self.create_user_service_permission(user=self.user, service=self.service),
            initial_debt=Decimal(50_000_000),
            current_debt=Decimal(50_000_000),
        )
        result = api_dispatcher(user_service=user_service).create_user_service(
            request_data=self.get_user_service_create_request(user_service)
        )
        assert result.status == UserServiceCreateResponse.Status.SUCCEEDED
        assert result.amount == Decimal(50_000_000)
        assert result.provider_tracking_id == '8ff2700e-af49-43f4-8621-e969027e587f'

        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=200, user_service=user_service, service=self.service.tp),
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_successful_different_allocated_amount(self, *_):
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
                'allocatedAmount': 30_000_000,
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
                        'nationalCode': '1234567890',
                        'cellNumber': '09123004000',
                        'birthDate': '1369-07-18',
                        'amount': 50_000_000,
                    },
                ),
            ],
        )

        user_service = UserService.objects.create(
            user=self.user,
            internal_user=self.create_internal_user(self.user),
            service=self.service,
            user_service_permission=self.create_user_service_permission(user=self.user, service=self.service),
            initial_debt=Decimal(50_000_000),
            current_debt=Decimal(50_000_000),
        )
        result = api_dispatcher(user_service=user_service).create_user_service(
            request_data=self.get_user_service_create_request(user_service)
        )
        assert result.status == UserServiceCreateResponse.Status.SUCCEEDED
        assert result.amount == Decimal(30_000_000)
        assert result.provider_tracking_id == '8ff2700e-af49-43f4-8621-e969027e587f'

        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=200, user_service=user_service, service=self.service.tp),
        )

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_successful_status_in_progress_then_call_get_details_return_activated(self, *_):
        tracking_code = '8ff2700e-af49-43f4-8621-e969027e587f'

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

        create_url = 'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/activation'
        responses.post(
            url=create_url,
            json={
                'trackingCode': tracking_code,
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
                responses.matchers.header_matcher({'Authorization': 'Bearer ACCESS_TOKEN'}),
                responses.matchers.json_params_matcher(
                    {
                        'nationalCode': '1234567890',
                        'cellNumber': '09123004000',
                        'birthDate': '1369-07-18',
                        'amount': 50_000_000,
                    },
                ),
            ],
        )

        get_url = f'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/inquiry/{tracking_code}'
        responses.get(
            url=get_url,
            json={
                'trackingCode': tracking_code,
                'status': 'ACTIVATED',
                'allocatedAmount': 40_000_000,
                'result': {'title': 'SUCCESS', 'status': 0, 'message': 'عملیات با موفقیت انجام شد', 'level': 'INFO'},
            },
            status=200,
            match=[
                responses.matchers.header_matcher({'Authorization': 'Bearer ACCESS_TOKEN'}),
            ],
        )

        user_service = UserService.objects.create(
            user=self.user,
            internal_user=self.create_internal_user(self.user),
            service=self.service,
            user_service_permission=self.create_user_service_permission(user=self.user, service=self.service),
            initial_debt=Decimal(50_000_000),
            current_debt=Decimal(50_000_000),
        )
        result = api_dispatcher(user_service=user_service).create_user_service(
            request_data=self.get_user_service_create_request(user_service)
        )
        assert result.status == UserServiceCreateResponse.Status.REQUESTED
        assert result.amount == Decimal(50_000_000)
        assert result.provider_tracking_id == '8ff2700e-af49-43f4-8621-e969027e587f'

        process_abc_outgoing_api_logs()
        self.check_outgoing_logs(
            [
                OutgoingAPICallLog(
                    api_url=create_url, response_code=200, user_service=user_service, service=self.service.tp
                ),
            ]
        )

        with pytest.raises(ValueError, match='account number is required for Digipay inquiry'):
            result = api_dispatcher(user_service=user_service).get_details()

        # Assign the account_number for testing purposes!
        user_service.account_number = result.provider_tracking_id

        result = api_dispatcher(user_service=user_service).get_details()
        assert result.id == '8ff2700e-af49-43f4-8621-e969027e587f'
        assert result.status == UserService.Status.initiated
        assert result.amount == Decimal(40_000_000)

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_status_failed_in_response(self, *_):
        tracking_code = '8ff2700e-af49-43f4-8621-e969027e587f'

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
                'trackingCode': tracking_code,
                'status': 'FAILED',
                'allocatedAmount': 50_000_000,
                'result': {
                    'title': 'SUCCESS',
                    'status': 19701,
                    'message': 'عملیات با موفقیت انجام نشد',
                    'level': 'INFO',
                },
            },
            status=200,
            match=[
                responses.matchers.header_matcher({'Authorization': 'Bearer ACCESS_TOKEN'}),
                responses.matchers.json_params_matcher(
                    {
                        'nationalCode': '1234567890',
                        'cellNumber': '09123004000',
                        'birthDate': '1369-07-18',
                        'amount': 50_000_000,
                    },
                ),
            ],
        )

        user_service = UserService.objects.create(
            user=self.user,
            internal_user=self.create_internal_user(self.user),
            service=self.service,
            user_service_permission=self.create_user_service_permission(user=self.user, service=self.service),
            initial_debt=Decimal(50_000_000),
            current_debt=Decimal(50_000_000),
        )
        result = api_dispatcher(user_service=user_service).create_user_service(
            request_data=self.get_user_service_create_request(user_service)
        )
        assert result.status == UserServiceCreateResponse.Status.FAILED

        process_abc_outgoing_api_logs()
        self.check_outgoing_logs(
            [
                OutgoingAPICallLog(api_url=url, response_code=200, user_service=user_service, service=self.service.tp),
            ]
        )

    def get_user_service_create_request(self, user_service: UserService) -> UserServiceCreateRequest:
        return UserServiceCreateRequest(
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


class DigiPayProviderCloseAccountTestCase(TestCase, ABCMixins):
    def setUp(self):
        self.user, _ = User.objects.get_or_create(username='test-user')
        self.user.national_code = '1234567890'
        self.user.mobile = '09123004000'
        self.user.birthday = datetime.date(year=1990, month=10, day=10)
        self.user.save()
        self.service = self.create_service(provider=Service.PROVIDERS.digipay, tp=Service.TYPES.credit)
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_success(self):
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

        url = 'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/close/ACCOUNT-NUMBER'
        responses.post(
            url=url,
            json={'result': {'title': 'success', 'status': 0, 'message': 'عملیات با موفقیت انجام شد', 'level': 'INFO'}},
            match=[responses.matchers.header_matcher({'Authorization': 'Bearer ACCESS_TOKEN'})],
            status=200,
        )

        user_service = UserService.objects.create(
            user=self.user,
            internal_user=self.create_internal_user(self.user),
            service=self.service,
            user_service_permission=self.create_user_service_permission(user=self.user, service=self.service),
            initial_debt=Decimal(50_000_000),
            current_debt=Decimal(50_000_000),
            account_number='ACCOUNT-NUMBER',
        )
        result = api_dispatcher(user_service=user_service).close_user_service()
        assert result == UserServiceCloseResponse(status=UserServiceCloseResponse.Status.REQUESTED)

        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=200, user_service=user_service, service=self.service.tp),
        )

    @responses.activate
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_failure(self):
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

        url = 'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/close/ACCOUNT-NUMBER'
        responses.post(
            url=url,
            json={
                'result': {
                    'title': 'failure',
                    'status': 17805,
                    'message': 'کاربر دارای بدهی معوق می‌باشد',
                    'level': 'INFO',
                }
            },
            match=[responses.matchers.header_matcher({'Authorization': 'Bearer ACCESS_TOKEN'})],
            status=422,
        )

        user_service = UserService.objects.create(
            user=self.user,
            internal_user=self.create_internal_user(self.user),
            service=self.service,
            user_service_permission=self.create_user_service_permission(user=self.user, service=self.service),
            initial_debt=Decimal(50_000_000),
            current_debt=Decimal(50_000_000),
            account_number='ACCOUNT-NUMBER',
        )
        result = api_dispatcher(user_service=user_service).close_user_service()
        assert result == UserServiceCloseResponse(
            status=UserServiceCloseResponse.Status.FAILED, message=UserServiceProviderMessage.USER_HAS_DEBT_CLOSE_ERROR
        )

        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=422, user_service=user_service, service=self.service.tp),
        )


class DigipayProviderTestCase(TestCase, ABCMixins):
    def setUp(self):
        self.user, _ = User.objects.update_or_create(
            username='digipay-test-user',
            defaults={
                'national_code': '1234567890',
                'mobile': '09123994999',
                'birthday': datetime.date(year=2000, month=10, day=10),
            },
        )

        self.service = self.create_service(provider=Service.PROVIDERS.digipay, tp=Service.TYPES.credit)

        self.mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=self.mock_cache
        ).start()

        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=self.mock_cache).start()

    def tearDown(self):
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=self.mock_cache
        ).stop()

        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=self.mock_cache).stop()

    @responses.activate
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_success_when_service_status_is_blocked(self):
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

        account_number = '573884271743241455632'
        responses.get(
            url=f'https://uat.mydigipay.info/digipay/api/business/smc/credit-demands/bnpl/inquiry/{account_number}',
            status=200,
            json={
                'result': {'title': 'SUCCESS', 'status': 0, 'message': 'عملیات با موفقیت انجام شد', 'level': 'INFO'},
                'trackingCode': '573884271743241455632',
                'status': 'BLOCKED',
                'allocatedAmount': 1_000_000,
            },
            match=[
                responses.matchers.header_matcher({'Authorization': 'Bearer ACCESS_TOKEN'}),
            ],
        )

        user_service = self.create_user_service(
            user=self.user, service=self.service, initial_debt=1_000_000, account_number=account_number
        )
        digipay_response = DigipayGetAccountAPI(
            account_number=user_service.account_number, user_service=user_service
        ).request()

        assert digipay_response == ResponseSchema(
            tracking_code=account_number,
            status='BLOCKED',
            allocated_amount=1_000_000,
            result=ResultSchema(
                title='SUCCESS',
                status=0,
                message='عملیات با موفقیت انجام شد',
                level='INFO',
            ),
        )
