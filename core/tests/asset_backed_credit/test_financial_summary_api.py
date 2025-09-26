import json
import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from unittest.mock import patch

import responses
from django.core.cache import cache
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.providers import VENCY
from exchange.asset_backed_credit.externals.providers.vency import VencyCalculatorAPI, VencyRenewTokenAPI
from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.services.loan.debt_to_grant_ratio import cache_min_loan_debt_to_grant_ratio
from exchange.base.models import Currencies, Settings
from tests.asset_backed_credit.helper import ABCMixins, APIHelper, MockCacheValue


@dataclass
class ResponseAPI:
    wallets_value: Optional[Decimal] = None
    total_debt: Optional[Decimal] = None
    asset_to_debt_ratio: Optional[Decimal] = None
    max_credit: Optional[Decimal] = None
    max_loan: Optional[Decimal] = None


def decimal_parser(value):
    return Decimal(value) if value else None


@patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
@patch('exchange.wallet.estimator.PriceEstimator.get_price_range', lambda *_: (54_300_0, 55_500_0))
class FinancialSummaryAPITest(APIHelper, ABCMixins):
    URL = '/asset-backed-credit/financial-summary'

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self._set_client_credentials(self.user.auth_token.key)
        self.mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=self.mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=self.mock_cache).start()

    def tearDown(self) -> None:
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=self.mock_cache
        ).stop()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=self.mock_cache).stop()
        cache.clear()

    def _check_financial_summery_exist(self, response, expected_response: ResponseAPI):
        assert all(
            x in response
            for x in ['assetToDebtRatio', 'walletsRialValue', 'maxAvailableCredit', 'maxAvailableLoan', 'totalDebt']
        )
        assert decimal_parser(response['assetToDebtRatio']) == expected_response.asset_to_debt_ratio
        assert decimal_parser(response['walletsRialValue']) == expected_response.wallets_value
        assert decimal_parser(response['maxAvailableCredit']) == expected_response.max_credit
        assert decimal_parser(response['maxAvailableLoan']) == expected_response.max_loan
        assert decimal_parser(response['totalDebt']) == expected_response.total_debt

    def test_total_wallet_zero(self):
        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_financial_summery_exist(
            res,
            ResponseAPI(
                wallets_value=Decimal('0'),
                total_debt=Decimal('0'),
                asset_to_debt_ratio=Decimal('infinity'),
                max_credit=Decimal('0'),
                max_loan=Decimal('0'),
            ),
        )

    def test_total_debt_zero(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_financial_summery_exist(
            res,
            ResponseAPI(
                wallets_value=Decimal('5_430_000_0'),
                total_debt=Decimal('0'),
                asset_to_debt_ratio=Decimal('infinity'),
                max_credit=Decimal('4_176_923_0'),
                max_loan=Decimal('4_176_923_0'),
            ),
        )

    def test_total_wallet_and_debt_non_zero(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        services = [self.create_service(), self.create_service(tp=Service.TYPES.loan)]
        self.create_user_service(
            self.user,
            initial_debt=Decimal('3_000_000_0'),
            current_debt=Decimal('2_000_000_0'),
            service=services[0],
        )
        self.create_user_service(
            self.user,
            initial_debt=Decimal('1_600_000_0'),
            current_debt=Decimal('1_600_000_0'),
            service=services[1],
        )
        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_financial_summery_exist(
            res,
            ResponseAPI(
                wallets_value=Decimal('5_430_000_0'),
                total_debt=Decimal('3_600_000_0'),
                asset_to_debt_ratio=Decimal('1.38'),
                max_credit=Decimal('576_923_0'),
                max_loan=Decimal('576_923_0'),
            ),
        )

    def test_total_wallet_and_debt_non_zero_cached_wallets(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        services = [self.create_service(), self.create_service(tp=Service.TYPES.loan)]
        self.create_user_service(
            self.user,
            initial_debt=Decimal('3_000_000_0'),
            current_debt=Decimal('2_000_000_0'),
            service=services[0],
        )
        self.create_user_service(
            self.user,
            initial_debt=Decimal('1_600_000_0'),
            current_debt=Decimal('1_600_000_0'),
            service=services[1],
        )
        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_financial_summery_exist(
            res,
            ResponseAPI(
                wallets_value=Decimal('5_430_000_0'),
                total_debt=Decimal('3_600_000_0'),
                asset_to_debt_ratio=Decimal('1.38'),
                max_credit=Decimal('576_923_0'),
                max_loan=Decimal('576_923_0'),
            ),
        )

        with patch(
            'exchange.asset_backed_credit.externals.wallet.ExchangeWallet.objects.filter'
        ) as mock_exchange_filter:
            response = self._get_request()
            res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
            self._check_financial_summery_exist(
                res,
                ResponseAPI(
                    wallets_value=Decimal('5_430_000_0'),
                    total_debt=Decimal('3_600_000_0'),
                    asset_to_debt_ratio=Decimal('1.38'),
                    max_credit=Decimal('576_923_0'),
                    max_loan=Decimal('576_923_0'),
                ),
            )

            mock_exchange_filter.assert_not_called()

    @responses.activate
    def test_max_available_loan_success(self):
        with open(os.path.join(os.path.dirname(__file__), 'test_data', 'vency_calculator_response_10.json'), 'r') as f:
            mocked_json = json.load(f)

        responses.get(
            url=VencyCalculatorAPI.url,
            json=mocked_json,
            status=status.HTTP_200_OK,
            match=[responses.matchers.query_param_matcher({'amountRials': 100_000_000})],
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

        service = Service.objects.create(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan, is_active=True)
        cache_min_loan_debt_to_grant_ratio()

        service.refresh_from_db()
        assert service.options.get('debt_to_grant_ratio') == '1.05'

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        services = [self.create_service(), self.create_service(tp=Service.TYPES.loan)]
        self.create_user_service(
            self.user,
            initial_debt=Decimal('3_000_000_0'),
            current_debt=Decimal('2_000_000_0'),
            service=services[0],
        )
        self.create_user_service(
            self.user,
            initial_debt=Decimal('1_600_000_0'),
            current_debt=Decimal('1_600_000_0'),
            service=services[1],
        )
        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_financial_summery_exist(
            res,
            ResponseAPI(
                wallets_value=Decimal('5_430_000_0'),
                total_debt=Decimal('3_600_000_0'),
                asset_to_debt_ratio=Decimal('1.38'),
                max_credit=Decimal('576_923_0'),
                max_loan=Decimal('549_450_4'),
            ),
        )
