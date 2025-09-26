from unittest.mock import patch

import responses
from django.core.cache import cache
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.providers import TARA
from exchange.asset_backed_credit.externals.providers.tara import TaraTotalInstallments
from exchange.asset_backed_credit.models import OutgoingAPICallLog, Service
from exchange.asset_backed_credit.services.logging import process_abc_outgoing_api_logs
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import SIGN, ABCMixins, APIHelper, MockCacheValue, sign_mock


class TotalInstallmentsInquiryAPI(APIHelper, ABCMixins):
    URL = '/asset-backed-credit/user-services/{}/total-installments'

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.get(pk=201)
        cls.user.user_type = User.USER_TYPES.level1
        cls.user.mobile = '09120000000'
        cls.user.national_code = '0010000000'
        cls.user.first_name = 'Ali'
        cls.user.last_name = 'Ali'
        cls.user.save(update_fields=('user_type', 'mobile', 'national_code', 'first_name', 'last_name'))
        Settings.set_cached_json('abc_minimum_debt', {'credit': '1000'})
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
        response = self._get_request(self.URL.format('0'))
        self._check_response(response=response, status_code=status.HTTP_404_NOT_FOUND)

        # wrong serviceId
        user_service = self.create_user_service(service=self.service, user=self.user2)
        response = self._get_request(self.URL.format(user_service.pk))
        self._check_response(response=response, status_code=status.HTTP_404_NOT_FOUND)

        # inactive service
        user_service = self.create_user_service(service=self.service, user=self.user, closed_at=ir_now())
        response = self._get_request(self.URL.format(user_service.pk))
        self._check_response(response=response, status_code=status.HTTP_404_NOT_FOUND)

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_unsuccessful_tara_error_check_balance(self, *_):
        not_settled = 25970000
        user_service = self.create_user_service(service=self.service, user=self.user, account_number='1234')
        url = TaraTotalInstallments(user_service).url
        responses.post(
            url=url,
            json={
                'value': {
                    'pages': 1,
                    'elements': 2,
                    'items': [
                        {
                            'amount': not_settled,
                            'status': 'SETTLED',
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
        response = self._get_request(self.URL.format(user_service.pk))
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='ThirdPartyError',
            message='TaraTotalInstallments: Fail to get total installments',
        )
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.count() == 1

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_successful(self, *_):
        not_settled = 25970000
        user_service = self.create_user_service(service=self.service, user=self.user, account_number='1234')
        url = TaraTotalInstallments(user_service).url
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
        response = self._get_request(self.URL.format(user_service.pk))
        data = self._check_response(
            response=response,
            status_data='ok',
            status_code=status.HTTP_200_OK,
        )
        assert 'notSettled' in data
        assert not_settled == data['notSettled']
        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.count() == 1

    def test_not_implemented_error(self):
        service = self.create_service(tp=Service.TYPES.loan)
        user_service = self.create_user_service(user=self.user, service=service)
        response = self._get_request(self.URL.format(user_service.pk))
        self._check_response(
            response=response,
            status_data='failed',
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code='NotImplementedError',
            message='This service not implemented yet.',
        )
