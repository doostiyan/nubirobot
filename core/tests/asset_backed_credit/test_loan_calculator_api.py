import json
import os.path
from unittest.mock import patch

import responses
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.asset_backed_credit.exceptions import ThirdPartyError
from exchange.asset_backed_credit.externals.providers import VENCY
from exchange.asset_backed_credit.externals.providers.vency import VencyCalculatorAPI, VencyRenewTokenAPI
from exchange.asset_backed_credit.models import Service
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import MockCacheValue, sign_mock


class TestLoanCalculatorAPI(APITestCase):
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

    @staticmethod
    def get_or_create_service(provider, service_type):
        service, _ = Service.objects.get_or_create(provider=provider, tp=service_type, is_active=True)
        return service

    def test_invalid_service(self):
        service = self.get_or_create_service(provider=Service.PROVIDERS.tara, service_type=Service.TYPES.credit)
        principal = 20_000_000
        period = 3
        url = f'/asset-backed-credit/v1/services/{service.id}/calculator?principal={principal}&period={period}'
        resp = self.client.get(url)

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.json() == {
            'code': 'ServiceNotFound',
            'message': 'No Service matches the given query.',
            'status': 'failed',
        }

    def test_invalid_service_strategy_not_implemented(self):
        service = self.get_or_create_service(provider=Service.PROVIDERS.tara, service_type=Service.TYPES.loan)
        principal = 20_000_000
        period = 3
        url = f'/asset-backed-credit/v1/services/{service.id}/calculator?principal={principal}&period={period}'
        resp = self.client.get(url)

        assert resp.status_code == status.HTTP_501_NOT_IMPLEMENTED
        assert resp.json() == {
            'code': 'NotImplementedError',
            'message': 'service is not implemented yet.',
            'status': 'failed',
        }

    def test_invalid_query_params(self):
        service = self.get_or_create_service(provider=Service.PROVIDERS.vency, service_type=Service.TYPES.loan)
        principal = 20_000_000
        period = 'three'
        url = f'/asset-backed-credit/v1/services/{service.id}/calculator?principal={principal}&period={period}'
        resp = self.client.get(url)

        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_success(self, *_):
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

        self._assert_success_with_params(
            principal=10_000_000_0,
            period=6,
            file_name='vency_calculator_response_10.json',
            expected_response={
                'collateral_fee_amount': 0,
                'collateral_fee_percent': '0.0',
                'collateral_amount': 138918000,
                'extra_info': {
                    'collaboratorLoanPlanId': '488e8dc5-d143-4bec-8229-7fe6cfc4d0c7',
                    'loanPrincipalSupplyPlanId': 'd9235dba-8405-4d07-bc24-b8e2244db17e',
                },
                'installment_amount': 17810000,
                'interest_rate': 23,
                'period': 6,
                'principal': 100000000,
                'provider_fee_amount': 10000000,
                'provider_fee_percent': '10.0',
                'provider_fee_type': 'PRE_PAID',
                'total_repayment_amount': 116860000,
                'initial_debt_amount': 106860000,
            },
        )

        self._assert_success_with_params(
            principal=18_000_000_0,
            period=9,
            file_name='vency_calculator_response_18.json',
            expected_response={
                'collateral_amount': 257049000,
                'collateral_fee_amount': 0,
                'collateral_fee_percent': '0.0',
                'extra_info': {
                    'collaboratorLoanPlanId': '824a3255-ef60-4da7-993b-9ee5fa3f6f8b',
                    'loanPrincipalSupplyPlanId': 'b0ca2c09-3af5-461b-a6e2-ab63dc2650c9',
                },
                'initial_debt_amount': 197730000,
                'installment_amount': 21970000,
                'interest_rate': 23,
                'period': 9,
                'principal': 180000000,
                'provider_fee_amount': 21600000,
                'provider_fee_percent': '12.0',
                'provider_fee_type': 'PRE_PAID',
                'total_repayment_amount': 219330000,
            },
        )

        self._assert_success_with_params(
            principal=25_000_000_0,
            period=6,
            file_name='vency_calculator_response_25.json',
            expected_response={
                'collateral_amount': 347178000,
                'collateral_fee_amount': 0,
                'collateral_fee_percent': '0.0',
                'extra_info': {
                    'collaboratorLoanPlanId': '488e8dc5-d143-4bec-8229-7fe6cfc4d0c7',
                    'loanPrincipalSupplyPlanId': 'd9235dba-8405-4d07-bc24-b8e2244db17e',
                },
                'initial_debt_amount': 267060000,
                'installment_amount': 44510000,
                'interest_rate': 23,
                'period': 6,
                'principal': 250000000,
                'provider_fee_amount': 25000000,
                'provider_fee_percent': '10.0',
                'provider_fee_type': 'PRE_PAID',
                'total_repayment_amount': 292060000,
            },
        )

        self._assert_success_with_params(
            principal=45_000_000_0,
            period=3,
            file_name='vency_calculator_response_45.json',
            expected_response={
                'collateral_amount': 607581000,
                'collateral_fee_amount': 0,
                'collateral_fee_percent': '0.0',
                'extra_info': {
                    'collaboratorLoanPlanId': 'a7212f8a-3a72-44c6-b5ba-e1581807ec8a',
                    'loanPrincipalSupplyPlanId': 'f2b056b8-1213-464c-a72f-bad59997a209',
                },
                'initial_debt_amount': 467370000,
                'installment_amount': 155790000,
                'interest_rate': 23,
                'period': 3,
                'principal': 450000000,
                'provider_fee_amount': 27000000,
                'provider_fee_percent': '6.0',
                'provider_fee_type': 'PRE_PAID',
                'total_repayment_amount': 494370000,
            },
        )

        self._assert_success_with_params(
            principal=60_000_000_0,
            period=1,
            file_name='vency_calculator_response_45.json',
            expected_response={
                'collateral_amount': 596219000,
                'collateral_fee_amount': 0,
                'collateral_fee_percent': '0.0',
                'extra_info': {
                    'collaboratorLoanPlanId': 'f3b2d1bc-0763-4193-9427-f4ba4e49734c',
                    'loanPrincipalSupplyPlanId': '41e24c5a-7c32-4ce8-b923-129bbbc06b28',
                },
                'initial_debt_amount': 458630000,
                'installment_amount': 458630000,
                'interest_rate': 23,
                'period': 1,
                'principal': 600000000,
                'provider_fee_amount': 13500000,
                'provider_fee_percent': '3.0',
                'provider_fee_type': 'PRE_PAID',
                'total_repayment_amount': 472130000,
            },
        )

        self._assert_cache_is_set(principal=10_000_000_0, file_name='vency_calculator_response_10.json')
        self._assert_cache_is_set(principal=45_000_000_0, file_name='vency_calculator_response_45.json')

    @responses.activate
    @patch(
        'exchange.asset_backed_credit.services.providers.dispatcher.VencyLoanAPIs.calculate',
        side_effect=ThirdPartyError(f'invalid response schema'),
    )
    def test_third_party_error(self, _):
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

        service = self.get_or_create_service(provider=Service.PROVIDERS.vency, service_type=Service.TYPES.loan)
        principal = 20_000_000_0
        period = 6
        url = f'/asset-backed-credit/v1/services/{service.id}/calculator?principal={principal}&period={period}'
        resp = self.client.get(url)

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert resp.json() == {
            'code': 'LoanCalculationError',
            'message': 'third party error',
            'status': 'failed',
        }

    def _assert_success_with_params(self, principal, period, file_name, expected_response):
        with open(os.path.join(os.path.dirname(__file__), 'test_data', file_name), 'r') as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': principal})],
        )

        service = self.get_or_create_service(provider=Service.PROVIDERS.vency, service_type=Service.TYPES.loan)
        url = f'/asset-backed-credit/v1/services/{service.id}/calculator?principal={principal}&period={period}'
        resp = self.client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == expected_response

    @staticmethod
    def _assert_cache_is_set(principal, file_name):
        with open(os.path.join(os.path.dirname(__file__), 'test_data', file_name), 'r') as f:
            mocked_json = json.load(f)

        assert cache.get(f'abc:provider:vency:calculator:{principal}') == mocked_json
