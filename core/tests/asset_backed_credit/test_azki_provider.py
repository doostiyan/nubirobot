import json
import os
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import responses
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import ThirdPartyError
from exchange.asset_backed_credit.externals.providers import AZKI
from exchange.asset_backed_credit.externals.providers.azki import (
    AzkiCalculatorAPI,
    AzkiCreateAccountAPI,
    AzkiRenewTokenAPI,
    CreateResponseSchema,
)
from exchange.asset_backed_credit.externals.providers.azki import ResultSchema as AzkiResultSchema
from exchange.asset_backed_credit.models import OutgoingAPICallLog, Service
from exchange.asset_backed_credit.services.logging import process_abc_outgoing_api_logs
from exchange.asset_backed_credit.services.providers.dispatcher import AzkiLoanAPIs, api_dispatcher, api_dispatcher_v2
from exchange.asset_backed_credit.types import LoanServiceOptions, UserInfo, UserServiceCreateResponse
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import ABCMixins, MockCacheValue, sign_mock


class AzkiProviderRenewTokenTest(TestCase):
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
        AZKI.set_token(value, timeout=2)
        token = AZKI.get_token()
        assert token == value

    @responses.activate
    @patch.object(AZKI, 'username', 'test-username')
    @patch.object(AZKI, 'password', 'test-password')
    def test_renew_token_successful(self):
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

        cache.clear()
        token = AzkiRenewTokenAPI().request()
        assert token == 'test-access-token'

        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 1

        api_log = OutgoingAPICallLog.objects.all().first()
        assert api_log.request_body == {
            'username': '*****',
            'password': '*****',
        }


class AzkiProviderCreateAccountTest(TestCase, ABCMixins):
    def setUp(self) -> None:
        self.user, _ = User.objects.get_or_create(username='test-azki-user')
        self.user.first_name = 'john'
        self.user.last_name = 'doe'
        self.user.national_code = '9579321906'
        self.user.mobile = '09112003000'
        self.user.birthday = date(year=1993, month=11, day=15)
        self.user.save()

        self.service = self.create_service(provider=Service.PROVIDERS.azki, tp=Service.TYPES.loan)
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch.object(AZKI, 'username', 'test-username')
    @patch.object(AZKI, 'password', 'test-password')
    @patch.object(AZKI, 'contract_id', 123456)
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful(self, *_):
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

        responses.post(
            url='https://service.azkiloan.com/crypto-exchange/request-credit',
            json={
                'rsCode': 0,
                'result': {'request_id': 10002000, 'credit_account_id': 40005000, 'coupon_book_id': 60007000},
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'user': {
                            'first_name': 'john',
                            'last_name': 'doe',
                            'mobile_number': '09112003000',
                            'national_code': '9579321906',
                        },
                        'amount': 100_000_000,
                        'financier_id': 123456,
                        'period': 12,
                    }
                )
            ],
        )

        url = AzkiCreateAccountAPI.url
        user_service = self.create_loan_user_service(
            user=self.user,
            service=self.service,
            principal=100_000_000,
            installment_period=12,
        )

        result = AzkiCreateAccountAPI(
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
                period=int(user_service.installment_period),
            ),
        ).request()
        assert AZKI.get_token() == 'test-access-token'
        assert result == CreateResponseSchema(
            rs_code=0, result=AzkiResultSchema(request_id=10002000, credit_account_id=40005000, coupon_book_id=60007000)
        )

        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            OutgoingAPICallLog(api_url=url, response_code=200, user_service=user_service, service=self.service.tp),
        )


class AzkiLoanAPIsTestCase(TestCase, ABCMixins):
    def setUp(self) -> None:
        self.user, _ = User.objects.get_or_create(username='test-azki-user')
        self.user.first_name = 'hossein'
        self.user.last_name = 'nasser'
        self.user.national_code = '0100200300'
        self.user.mobile = '09109209300'
        self.user.birthday = date(year=1993, month=11, day=15)
        self.user.save()
        self.service = self.create_service(provider=Service.PROVIDERS.azki, tp=Service.TYPES.loan)
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch.object(AZKI, 'username', 'test-username')
    @patch.object(AZKI, 'password', 'test-password')
    @patch.object(AZKI, 'contract_id', 123456)
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful(self, *_):
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

        user_service = self.create_loan_user_service(
            user=self.user,
            service=self.service,
            principal=100_000_000,
            installment_period=12,
        )

        responses.post(
            url='https://service.azkiloan.com/crypto-exchange/request-credit',
            json={'rsCode': 0, 'result': {'request_id': 1000, 'credit_account_id': 2000, 'coupon_book_id': 3000}},
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'user': {
                            'first_name': 'hossein',
                            'last_name': 'nasser',
                            'mobile_number': '09109209300',
                            'national_code': '0100200300',
                        },
                        'amount': 100_000_000,
                        'financier_id': 123456,
                        'period': 12,
                    }
                )
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
                amount=int(user_service.principal),
                unique_id=str(user_service.external_id),
                period=int(user_service.installment_period),
            )
        )
        assert result.status == UserServiceCreateResponse.Status.SUCCEEDED
        assert result.provider_tracking_id == '1000'
        assert result.options == {'request_id': 1000, 'credit_account_id': 2000, 'coupon_book_id': 3000}

    @responses.activate
    @patch.object(AZKI, 'username', 'test-username')
    @patch.object(AZKI, 'password', 'test-password')
    @patch.object(AZKI, 'contract_id', 123456)
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_get_options_successful(self, _):
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
            url='https://service.azkiloan.com/crypto-exchange/summary',
            status=200,
            json={
                'rsCode': 0,
                'result': {
                    'minimumFinance': 100000000.000,
                    'maximumFinance': 750000000.000,
                    'periods': [12, 18],
                },
            },
        )

        result = api_dispatcher_v2(
            provider=Service.PROVIDERS.azki, service_type=Service.TYPES.loan
        ).get_service_options()

        assert result == LoanServiceOptions(
            min_principal_limit=100_000_000, max_principal_limit=750_000_000, periods=[12, 18]
        )

        process_abc_outgoing_api_logs()
        self.check_outgoing_log(
            OutgoingAPICallLog(
                api_url='https://service.azkiloan.com/crypto-exchange/summary',
                response_code=200,
                response_body={
                    'rsCode': 0,
                    'result': {
                        'minimumFinance': 100000000.000,
                        'maximumFinance': 750000000.000,
                        'periods': [12, 18],
                    },
                },
            ),
        )


class AzkiLoanCalculatorAPITestCase(TestCase, ABCMixins):
    def setUp(self) -> None:
        self.service = self.create_service()
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch.object(AZKI, 'username', 'test-username')
    @patch.object(AZKI, 'password', 'test-password')
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful(self, *_):
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
                responses.matchers.query_param_matcher({'amount': 100_000_000, 'period': 12}),
                responses.matchers.header_matcher({'Authorization': 'Bearer test-access-token'}),
            ],
        )

        data = AzkiLoanAPIs().calculate(principal=100_000_000, period=12)

        assert asdict(data) == {
            'principal': 100_000_000,
            'period': 12,
            'interest_rate': Decimal('23'),
            'provider_fee_percent': Decimal('13.5'),
            'provider_fee_amount': 13_500_000,
            'provider_fee_type': 'PRE_PAID',
            'installment_amount': 9_407_633,
            'total_installments_amount': 12 * 9_407_633,
            'extra_info': {
                'name': 'ازکی فاند',
                'repaymentModel': 'دفترچه اقساط',
            },
        }

    @responses.activate
    @patch.object(AZKI, 'username', 'test-username')
    @patch.object(AZKI, 'password', 'test-password')
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_invalid_azki_response_format_missing_field(self, *_):
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
                responses.matchers.query_param_matcher({'amount': 100_000_000, 'period': 12}),
                responses.matchers.header_matcher({'Authorization': 'Bearer test-access-token'}),
            ],
        )

        with self.assertRaises(ThirdPartyError) as cm:
            AzkiLoanAPIs().calculate(principal=100_000_000, period=12)

        assert str(cm.exception) == 'AzkiCalculator: invalid response schema, no valid plan.'
