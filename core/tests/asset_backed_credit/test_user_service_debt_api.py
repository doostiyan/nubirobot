from decimal import Decimal
from unittest.mock import patch

import responses
from django.core.cache import cache
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.providers import TARA
from exchange.asset_backed_credit.externals.providers.tara import TaraCheckUserBalance
from exchange.asset_backed_credit.models import Service
from exchange.base.models import Currencies
from tests.asset_backed_credit.helper import SIGN, ABCMixins, APIHelper, MockCacheValue, sign_mock


class UserServiceDebtAPITest(APIHelper, ABCMixins):
    URL = '/asset-backed-credit/user-services/{}/debt'

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.get(pk=201)
        cls.user.user_type = User.USER_TYPES.level1
        cls.user.mobile = '09120000000'
        cls.user.national_code = '0010000000'
        cls.user.first_name = 'Siavash'
        cls.user.last_name = 'Kavousi'
        cls.user.save(update_fields=('user_type', 'mobile', 'national_code', 'first_name', 'last_name'))

    def setUp(self):
        self._set_client_credentials(self.user.auth_token.key)
        self.service = self.create_service(tp=Service.TYPES.credit)
        self.amount = Decimal('120_000_000')
        self.charge_exchange_wallet(self.user, Currencies.rls, amount=130_000_000)
        TARA.set_token('XXX')
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    def tearDown(self):
        cache.clear()

    def test_user_service_not_found(self, *_):
        response = self.client.get(path=self.URL.format(0))

        self._check_response(response=response, status_code=status.HTTP_404_NOT_FOUND)

    def test_service_not_implemented_error(self, *_):
        initial_debt = 11_000_000
        service = self.create_service(tp=Service.TYPES.loan)
        user_service = self.create_user_service(self.user, service=service, initial_debt=initial_debt)

        response = self.client.get(path=self.URL.format(user_service.pk))

        self._check_response(response=response, status_code=status.HTTP_501_NOT_IMPLEMENTED)

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful(self, *_):
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

        response = self.client.get(path=self.URL.format(user_service.pk))

        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        assert Decimal(res['usedBalance']) == 0

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_user_has_debt_and_settled_debt_successful(self, *_):
        initial_debt = 10_000_000_0
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

        response = self.client.get(path=self.URL.format(user_service.pk))

        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        assert Decimal(res['usedBalance']) == 4_000_000_0

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_third_party_error(self, *_):
        initial_debt = 10_000_000_0
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
                'success': False,
                'data': '',
                'timestamp': '1701964345',
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

        response = self.client.get(path=self.URL.format(user_service.pk))

        self._check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data='failed',
            code='ThirdPartyError',
        )
