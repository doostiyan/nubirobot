import json
import os
import uuid
from dataclasses import asdict
from datetime import date
from unittest.mock import patch

import responses
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import ThirdPartyError
from exchange.asset_backed_credit.externals.providers import VENCY
from exchange.asset_backed_credit.externals.providers.vency import (
    VencyCalculatorAPI,
    VencyCreateAccountAPI,
    VencyRenewTokenAPI,
)
from exchange.asset_backed_credit.models import OutgoingAPICallLog, Service
from exchange.asset_backed_credit.services.logging import process_abc_outgoing_api_logs
from exchange.asset_backed_credit.services.providers.dispatcher import VencyLoanAPIs, api_dispatcher
from exchange.asset_backed_credit.types import UserInfo, UserServiceCloseResponse, UserServiceCreateResponse
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import ABCMixins, MockCacheValue, sign_mock


class VencyProviderRenewTokenTest(TestCase):
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
        VENCY.set_token(value, timeout=2)
        token = VENCY.get_token()
        assert token == value

    @responses.activate
    def test_renew_token_successful(self):
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

        cache.clear()
        token = VencyRenewTokenAPI().request()
        assert token == 'ACCESS_TOKEN'

        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 1

        api_log = OutgoingAPICallLog.objects.all().first()
        assert api_log.request_body == {
            'grant_type': 'client_credentials',
            'client_id': VENCY.client_id,
            'client_secret': VENCY.client_secret,
            'scope': VencyRenewTokenAPI.SCOPES.replace(':', '%3A').replace(' ', '+'),
        }


class VencyProviderCreateAccountTest(TestCase, ABCMixins):
    def setUp(self) -> None:
        self.user = User.objects.get(pk=202)
        self.user.national_code = '9579321906'
        self.user.birthday = date(year=1993, month=11, day=15)
        self.user.mobile = '99800000012'
        self.user.save()
        self.service = self.create_service(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful(self, *_):
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

        url = VencyCreateAccountAPI.url
        user_service = self.create_loan_user_service(
            user=self.user,
            service=self.service,
            principal=7_800_000_0,
            installment_period=12,
            account_number=str(uuid.uuid4()),
            extra_info={
                'loanPrincipalSupplyPlanId': 'c392a321-ff5a-4d60-a590-69c3c99b6bbd',
                'collaboratorLoanPlanId': '0a806541-705c-4942-85b5-16944caeced2',
            },
        )
        responses.post(
            url=url,
            json={
                'orderId': '2b56e1a7-68cc-47a5-bd80-21424183f7d1',
                'uniqueIdentifier': str(user_service.external_id),
                'redirectUrl': 'https://api.vencytest.ir/main/select/2b56e1a7-68cc-47a5-bd80-21424183f7d1',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'uniqueIdentifier': str(user_service.external_id),
                        'amountRials': user_service.principal,
                        'loanPrincipalSupplyPlanId': 'c392a321-ff5a-4d60-a590-69c3c99b6bbd',
                        'collaboratorLoanPlanId': '0a806541-705c-4942-85b5-16944caeced2',
                        'customerNationalCode': self.user.national_code,
                    },
                ),
            ],
        )

        data = VencyCreateAccountAPI(
            user_service,
            self.get_user_service_create_request(
                user_info=UserInfo(
                    national_code=user_service.user.national_code,
                    mobile=user_service.user.mobile,
                    first_name=user_service.user.first_name,
                    last_name=user_service.user.last_name,
                    birthday_shamsi=user_service.user.birthday_shamsi,
                ),
                amount=int(user_service.principal),
                unique_id=str(user_service.external_id),
                extra_info=user_service.extra_info,
            ),
        ).request()

        assert VENCY.get_token() == 'ACCESS_TOKEN'

        assert 'orderId' in data and 'uniqueIdentifier' in data and 'redirectUrl' in data
        assert data['orderId'] == '2b56e1a7-68cc-47a5-bd80-21424183f7d1'
        assert data['redirectUrl'] == 'https://api.vencytest.ir/main/select/2b56e1a7-68cc-47a5-bd80-21424183f7d1'

        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=200, user_service=user_service, service=self.service.tp),
        )


class VencyLoanAPIsTestCase(TestCase, ABCMixins):
    def setUp(self) -> None:
        self.user = User.objects.get(pk=202)
        self.user.national_code = '9579321906'
        self.user.birthday = date(year=1993, month=11, day=15)
        self.user.mobile = '99800000012'
        self.user.save()
        self.service = self.create_service(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful(self, *_):
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

        url = VencyCreateAccountAPI.url
        user_service = self.create_loan_user_service(
            user=self.user,
            service=self.service,
            principal=7_800_000_0,
            installment_period=6,
            account_number=str(uuid.uuid4()),
            extra_info={
                'loanPrincipalSupplyPlanId': 'b43b5c3a-b93b-4e2f-920b-df6afc61a3f0',
                'collaboratorLoanPlanId': '8bea4c5b-9172-430a-877e-ccb1c4c52575',
            },
        )
        responses.post(
            url=url,
            json={
                'orderId': '2b56e1a7-68cc-47a5-bd80-21424183f7d1',
                'uniqueIdentifier': str(user_service.external_id),
                'redirectUrl': 'https://api.vencytest.ir/main/select/2b56e1a7-68cc-47a5-bd80-21424183f7d1',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'uniqueIdentifier': str(user_service.external_id),
                        'amountRials': user_service.principal,
                        'loanPrincipalSupplyPlanId': 'b43b5c3a-b93b-4e2f-920b-df6afc61a3f0',
                        'collaboratorLoanPlanId': '8bea4c5b-9172-430a-877e-ccb1c4c52575',
                        'customerNationalCode': self.user.national_code,
                    },
                ),
            ],
        )
        result = api_dispatcher(user_service).create_user_service(
            self.get_user_service_create_request(
                user_info=UserInfo(
                    national_code=user_service.user.national_code,
                    mobile=user_service.user.mobile,
                    first_name=user_service.user.first_name,
                    last_name=user_service.user.last_name,
                    birthday_shamsi=user_service.user.birthday_shamsi,
                ),
                amount=int(user_service.principal),
                unique_id=str(user_service.external_id),
                extra_info=user_service.extra_info,
            )
        )
        assert result.status == UserServiceCreateResponse.Status.REQUESTED
        assert result.provider_tracking_id == str(user_service.external_id)
        assert result.options == {
            'redirect_url': 'https://api.vencytest.ir/main/select/2b56e1a7-68cc-47a5-bd80-21424183f7d1'
        }

    def test_cancel_api_success(self):
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

        unique_id = uuid.uuid4()
        user_service = self.create_loan_user_service(
            user=self.user,
            service=self.service,
            principal=7_800_000_0,
            installment_period=6,
            account_number=str(unique_id),
            external_id=unique_id,
        )

        url = f'https://api.vencytest.ir/v3/collaborators/orders/{user_service.account_number}/cancel'
        responses.put(
            url=url,
            json={'body': ''},
            status=200,
            match=[responses.matchers.json_params_matcher(None)],
        )

        result = api_dispatcher(user_service).close_user_service()
        assert result.status == UserServiceCloseResponse.Status.SUCCEEDED

        process_abc_outgoing_api_logs()

        log = OutgoingAPICallLog.objects.order_by('id').last()
        assert log.api_url == url
        assert log.user == self.user
        assert log.provider == self.service.provider


class VencyLoanCalculatorAPITestCase(TestCase, ABCMixins):
    def setUp(self) -> None:
        self.user = User.objects.get(pk=202)
        self.user.national_code = 9579321906
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

        with open(os.path.join(os.path.dirname(__file__), 'test_data/vency_calculator_response_45.json'), 'r') as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': 45_000_000_0})],
        )

        data = VencyLoanAPIs().calculate(principal=45_000_000_0, period=3)

        assert asdict(data) == {
            'principal': 45_000_000_0,
            'period': 3,
            'interest_rate': 23.0,
            'provider_fee_percent': 6.0,
            'provider_fee_amount': 2_700_000_0,
            'provider_fee_type': 'PRE_PAID',
            'installment_amount': 15_579_000_0,
            'total_installments_amount': 46_737_000_0,
            'extra_info': {
                'collaboratorLoanPlanId': 'a7212f8a-3a72-44c6-b5ba-e1581807ec8a',
                'loanPrincipalSupplyPlanId': 'f2b056b8-1213-464c-a72f-bad59997a209',
            },
        }

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_invalid_vency_response_format_missing_field(self, *_):
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

        with open(
            os.path.join(os.path.dirname(__file__), 'test_data/vency_calculator_invalid_response.json'), 'r'
        ) as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': 7_000_000_0})],
        )

        with self.assertRaises(ThirdPartyError) as cm:
            VencyLoanAPIs().calculate(principal=7_000_000_0, period=3)

        assert str(cm.exception) == 'VencyCalculator: invalid response schema'
