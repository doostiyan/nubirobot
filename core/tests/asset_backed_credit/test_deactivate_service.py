import uuid
from unittest import mock
from unittest.mock import patch

import responses
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.providers import VENCY
from exchange.asset_backed_credit.externals.providers.vency import VencyGetOrderAPI, VencyRenewTokenAPI
from exchange.asset_backed_credit.externals.restriction import UserRestrictionType
from exchange.asset_backed_credit.models import Service, UserService
from exchange.base.calendar import ir_now
from tests.asset_backed_credit.helper import ABCMixins, APIHelper, MockCacheValue
from tests.base.utils import check_response


class DeactivateServiceTest(ABCMixins, APIHelper):
    fixtures = ('test_data',)

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.get(pk=201)
        cls.url = '/asset-backed-credit/services/{}/deactivate'

    def setUp(self) -> None:
        self.service = self.create_service()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

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

    def _deactivate_service(self, service):
        url = self.url.format(service.id)
        return self.client.post(url)

    @mock.patch(
        'exchange.asset_backed_credit.services.providers.dispatcher.TaraCreditAPIs.get_available_balance',
        lambda self: 5_000_000_0,
    )
    @mock.patch(
        'exchange.asset_backed_credit.services.providers.dispatcher.TaraCreditAPIs.discharge_account',
        lambda self, amount: None,
    )
    @mock.patch(
        'exchange.asset_backed_credit.services.user_service_permission.send_permission_deactivation_notification',
        lambda permission: None,
    )
    @mock.patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_deactivate_service_has_user_service_ok(self, mock_restriction_task):
        user_service = self.create_user_service(user=self.user, service=self.service, initial_debt=5_000_000_0)
        response = self._deactivate_service(service=self.service)
        check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        mock_restriction_task.assert_called_once_with(
            user_service_id=user_service.id, restriction=UserRestrictionType.CHANGE_MOBILE.value
        )

    @mock.patch(
        'exchange.asset_backed_credit.services.providers.dispatcher.TaraCreditAPIs.get_available_balance',
        lambda self: 3_000_000_0,
    )
    @mock.patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_deactivate_service_has_user_service_nok(self, mock_restriction_task):
        self.create_user_service(user=self.user, service=self.service, initial_debt=5_000_000_0)
        response = self._deactivate_service(service=self.service)
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data='failed',
            code='ExternalProviderError',
            message='لغو اعتبار به دلیل بدهی در سرویس‌دهنده امکان‌پذیر نیست.',
        )
        mock_restriction_task.assert_not_called()

    @mock.patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_deactivate_service_already_deactivated(self, mock_restriction_task):
        self.create_user_service_permission(user=self.user, service=self.service, is_active=False)

        response = self._deactivate_service(service=self.service)
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data='failed',
            code='ServiceAlreadyDeactivatedError',
            message='Service is already deactivated.',
        )
        mock_restriction_task.assert_not_called()

    @mock.patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_deactivate_service_no_user_service_ok(self, mock_restriction_task):
        permission = self.create_user_service_permission(user=self.user, service=self.service, is_active=True)
        self.create_user_service(
            user=self.user,
            service=self.service,
            closed_at=ir_now(),
            permission=permission,
        )
        response = self._deactivate_service(service=self.service)
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data='ok',
        )
        mock_restriction_task.assert_not_called()

    @responses.activate
    @mock.patch('exchange.asset_backed_credit.externals.providers.vency.VencyCancelOrderAPI.request', lambda _: True)
    @mock.patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_deactivate_service_with_status_created_ok(self, mock_restriction_task):
        service = self.create_service(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan, is_active=True)
        permission = self.create_user_service_permission(user=self.user, service=service, is_active=True)
        user_service = self.create_loan_user_service(
            user=self.user,
            service=service,
            permission=permission,
            status=UserService.STATUS.created,
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
                'orderId': '12345',
                'type': 'LENDING',
                'status': 'IN_PROGRESS',
                'uniqueIdentifier': user_service.account_number,
                'createdAt': '2024-08-08T06:01:08.220457Z',
            },
            status=200,
        )

        response = self._deactivate_service(service=service)
        check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data='ok',
        )

        user_service.refresh_from_db()
        assert user_service.status == UserService.STATUS.closed
        mock_restriction_task.assert_not_called()

        permission.refresh_from_db()
        assert permission.revoked_at

    @responses.activate
    @mock.patch('exchange.asset_backed_credit.externals.providers.vency.VencyCancelOrderAPI.request', lambda _: True)
    @mock.patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_deactivate_service_with_status_created_nok(self, mock_restriction_task):
        service = self.create_service(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan, is_active=True)
        permission = self.create_user_service_permission(user=self.user, service=service, is_active=True)
        user_service = self.create_loan_user_service(
            user=self.user,
            service=service,
            permission=permission,
            status=UserService.STATUS.created,
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
            url=VencyGetOrderAPI.get_url(account_number=user_service.account_number),
            json={
                'orderId': '3122e56e-6140-4498-83b4-8ba2ccbc3341',
                'type': 'LENDING',
                'status': 'VERIFIED',
                'uniqueIdentifier': user_service.account_number,
                'createdAt': '2024-08-08T06:01:08.220457Z',
            },
            status=200,
        )

        response = self._deactivate_service(service=service)
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data='failed',
            code='ExternalProviderError',
            message='لغو اعتبار به دلیل بدهی در سرویس‌دهنده امکان‌پذیر نیست.',
        )

        user_service.refresh_from_db()
        assert user_service.status == UserService.STATUS.created
        mock_restriction_task.assert_not_called()

        permission.refresh_from_db()
        assert not permission.revoked_at

    @responses.activate
    @mock.patch('exchange.asset_backed_credit.externals.providers.vency.VencyCancelOrderAPI.request', lambda _: True)
    @mock.patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_deactivate_service_with_status_close_requested_nok(self, mock_restriction_task):
        service = self.create_service(provider=Service.PROVIDERS.digipay, tp=Service.TYPES.credit, is_active=True)
        permission = self.create_user_service_permission(user=self.user, service=service, is_active=True)
        user_service = self.create_loan_user_service(
            user=self.user,
            service=service,
            permission=permission,
            status=UserService.STATUS.close_requested,
            account_number='ACCOUNT-NUMBER',
        )

        response = self._deactivate_service(service=service)
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data='failed',
        )

        user_service.refresh_from_db()
        assert user_service.status == UserService.STATUS.close_requested
        mock_restriction_task.assert_not_called()

        permission.refresh_from_db()
        assert not permission.revoked_at

    def test_deactivate_service_with_user_service_is_not_internally_closeable(self):
        service = self.create_service(provider=Service.PROVIDERS.azki, tp=Service.TYPES.loan, is_active=True)
        permission = self.create_user_service_permission(user=self.user, service=service, is_active=True)
        self.create_loan_user_service(
            user=self.user,
            service=service,
            permission=permission,
            status=UserService.STATUS.created,
            account_number='ACCOUNT-NUMBER',
        )

        response = self._deactivate_service(service=service)
        check_response(
            response=response,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_data='failed',
            code='ServiceDeactivationError',
        )
