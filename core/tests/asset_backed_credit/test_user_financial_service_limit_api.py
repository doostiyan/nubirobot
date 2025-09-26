import json
from decimal import Decimal

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit
from exchange.base.internal.services import Services
from tests.helpers import create_internal_token, mock_internal_service_settings


class UserFinancialServiceLimitApiTestCase(APITestCase):
    LIST_URL = '/internal/asset-backed-credit/user-financial-limits'

    @classmethod
    def setUpTestData(cls) -> None:
        user = User.objects.get(pk=201)
        user.user_type = User.USER_TYPES.level1
        user.save(update_fields=('user_type',))
        cls.user = user

        cls.service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.tara, tp=Service.TYPES.credit, is_active=True
        )

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ADMIN.value)}')

    @staticmethod
    def get_detail_url(pk):
        return f'/internal/asset-backed-credit/user-financial-limits/{pk}'

    @override_settings(RATELIMIT_ENABLE=True)
    @mock_internal_service_settings
    def test_create_user_limit(self):
        data = {'limitType': 10, 'maxLimit': 0, 'userId': str(self.user.uid), 'serviceId': self.service.id}  # 'user'
        resp = self.client.post(
            path=self.LIST_URL,
            data=json.dumps(data),
            content_type='application/json',
        )

        assert resp.status_code == status.HTTP_201_CREATED

        limit = UserFinancialServiceLimit.objects.order_by('pk').last()
        assert limit.tp == UserFinancialServiceLimit.TYPES.user
        assert limit.limit == 0
        assert limit.user == self.user
        assert limit.service is None

    @override_settings(RATELIMIT_ENABLE=True)
    @mock_internal_service_settings
    def test_create_user_service_limit(self):
        data = {
            'limitType': 20,  # 'user_service'
            'maxLimit': 1000,
            'userId': str(self.user.uid),
            'serviceId': self.service.id,
        }

        resp = self.client.post(
            path=self.LIST_URL,
            data=json.dumps(data),
            content_type='application/json',
        )
        assert resp.status_code == status.HTTP_201_CREATED

        limit = UserFinancialServiceLimit.objects.order_by('pk').last()
        assert limit.tp == UserFinancialServiceLimit.TYPES.user_service
        assert limit.limit == 1000
        assert limit.user == self.user
        assert limit.service == self.service
        assert limit.user_type is None

    @override_settings(RATELIMIT_ENABLE=True)
    @mock_internal_service_settings
    def test_create_user_service_limit_error(self):
        data = {
            'limitType': 20,  # 'user_service'
            'userId': str(self.user.uid),
            'serviceId': self.service.id,
        }

        resp = self.client.post(
            path=self.LIST_URL,
            data=json.dumps(data),
            content_type='application/json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(RATELIMIT_ENABLE=True)
    @mock_internal_service_settings
    def test_create_service_limit(self):
        data = {
            'limitType': 90,  # 'service'
            'maxLimit': 10_000_000,
            'userId': str(self.user.uid),
            'serviceId': self.service.id,
        }

        resp = self.client.post(
            path=self.LIST_URL,
            data=json.dumps(data),
            content_type='application/json',
        )


        print(resp.json())


        assert resp.status_code == status.HTTP_201_CREATED

        limit = UserFinancialServiceLimit.objects.order_by('pk').last()
        assert limit.tp == UserFinancialServiceLimit.TYPES.service
        assert limit.limit == 10_000_000
        assert limit.user is None
        assert limit.service == self.service
        assert limit.user_type is None

    @override_settings(RATELIMIT_ENABLE=True)
    @mock_internal_service_settings
    def test_create_service_user_type_limit(self):
        data = {
            'limitType': 60,  # 'user_type_service'
            'maxLimit': 5000,
            'serviceId': self.service.id,
            'userType': User.USER_TYPES.level2,
        }

        resp = self.client.post(
            path=self.LIST_URL,
            data=json.dumps(data),
            content_type='application/json',
        )

        print(resp.json())
        assert resp.status_code == status.HTTP_201_CREATED

        limit = UserFinancialServiceLimit.objects.order_by('pk').last()
        assert limit.tp == UserFinancialServiceLimit.TYPES.user_type_service
        assert limit.limit == 5000
        assert limit.user is None
        assert limit.service == self.service
        assert limit.user_type == User.USER_TYPES.level2

    @override_settings(RATELIMIT_ENABLE=True)
    @mock_internal_service_settings
    def test_delete_limit(self):
        limit = UserFinancialServiceLimit.set_user_service_limit(user=self.user, service=self.service, max_limit=0)

        resp = self.client.delete(path=self.get_detail_url(limit.pk))
        assert resp.status_code == status.HTTP_200_OK

    @override_settings(RATELIMIT_ENABLE=True)
    @mock_internal_service_settings
    def test_delete_not_found(self):
        limit = UserFinancialServiceLimit.set_user_service_limit(user=self.user, service=self.service, max_limit=0)
        limit.delete()

        resp = self.client.delete(path=self.get_detail_url(limit.pk))
        assert resp.status_code == status.HTTP_404_NOT_FOUND
