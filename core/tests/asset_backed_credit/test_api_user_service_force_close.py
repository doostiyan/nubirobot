from unittest.mock import patch

import responses
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.providers.tara import (
    TaraCheckUserBalance,
    TaraDischargeAccount,
    TaraGetTraceNumber,
    TaraTotalInstallments,
)
from exchange.asset_backed_credit.models import Service, UserService
from exchange.base.calendar import ir_now
from exchange.base.internal.services import Services
from tests.asset_backed_credit.helper import SIGN, ABCMixins, MockCacheValue, sign_mock
from tests.helpers import create_internal_token, mock_internal_service_settings


class TestUserServiceForceCloseApi(APITestCase, ABCMixins):
    URL_FORMAT = '/internal/asset-backed-credit/user-services/{user_service_id}/close'

    @classmethod
    def setUpTestData(cls) -> None:
        user = User.objects.get(pk=201)
        user.mobile = '09120000000'
        user.national_code = '0010000000'
        user.first_name = 'Ali'
        user.last_name = 'Ali'
        user.save(update_fields=('user_type', 'mobile', 'national_code', 'first_name', 'last_name'))
        cls.user = user

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ADMIN.value)}')
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @override_settings(RATELIMIT_ENABLE=True)
    @responses.activate
    @mock_internal_service_settings
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.externals.providers.tara.TaraRenewToken.request', lambda _: 'XXXX')
    def test_success(self, _):
        service = self.create_service(provider=Service.PROVIDERS.tara, tp=Service.TYPES.credit)
        user_service = self.create_user_service(user=self.user, service=service, account_number='1111')

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
                        'accountNumber': user_service.account_number,
                        'sign': SIGN,
                    },
                ),
            ],
        )

        url = TaraGetTraceNumber('decharge', UserService(user=self.user, service=service)).url
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

        url = TaraTotalInstallments(user_service).url
        responses.post(
            url=url,
            json={
                'value': {
                    'items': [
                        {
                            'amount': 0,
                            'mobile': self.user.mobile,
                            'status': 'NOT_SETTLED',
                            'contractId': None,
                            'nationalCode': self.user.national_code,
                        }
                    ],
                    'pages': 1,
                    'elements': 1,
                },
                'status': {
                    'code': '1',
                    'message': ['با موفقیت انجام شد.'],
                    'timestamp': '2024-09-09T14:46:36.116+03:30',
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
                    }
                )
            ],
        )

        resp = self.client.post(
            path=self.URL_FORMAT.format(user_service_id=user_service.id),
            content_type='application/json',
        )
        assert resp.status_code == status.HTTP_200_OK

    @override_settings(RATELIMIT_ENABLE=True)
    @responses.activate
    @mock_internal_service_settings
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.externals.providers.tara.TaraRenewToken.request', lambda _: 'XXXX')
    def test_failure_already_closed(self, _):
        service = self.create_service(provider=Service.PROVIDERS.tara, tp=Service.TYPES.credit)
        user_service = self.create_user_service(user=self.user, service=service, account_number='1111')
        user_service.closed_at = ir_now()
        user_service.status = UserService.STATUS.closed
        user_service.save()

        resp = self.client.post(
            path=self.URL_FORMAT.format(user_service_id=user_service.id),
            content_type='application/json',
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert resp.json().get('message') == 'UpdateClosedUserService'

    @override_settings(RATELIMIT_ENABLE=True)
    @responses.activate
    @mock_internal_service_settings
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.externals.providers.tara.TaraRenewToken.request', lambda _: 'XXXX')
    def test_failure_user_service_not_found(self, _):
        last = UserService.objects.all().order_by('id').last()
        us_id = last.pk + 1 if last else 1
        resp = self.client.post(
            path=self.URL_FORMAT.format(user_service_id=us_id),
            content_type='application/json',
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.json().get('message') == 'UserServiceDoesNotExist'
