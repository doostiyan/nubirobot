from typing import Any, Dict, List, Optional

from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Service, UserServicePermission
from exchange.base.parsers import parse_iso_date
from exchange.base.serializers import serialize_choices
from tests.asset_backed_credit.helper import ABCMixins, APIHelper


class UserServicePermissionListAPITest(APIHelper, ABCMixins):
    URL = '/asset-backed-credit/user-service-permissions/list'

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self._set_client_credentials(self.user.auth_token.key)
        self.services = [
            self.create_service(tp=tp)
            for tp in [
                Service.TYPES.credit,
                Service.TYPES.loan,
                Service.TYPES.debit,
            ]
        ]
        self.user2 = User.objects.get(pk=202)
        self.create_user_service_permission(self.user2, service=self.services[2])

    def _check_api_result(self, response: Dict[str, Any], permissions: Optional[List[UserServicePermission]]):
        assert 'permissions' in response
        assert len(response['permissions']) == len(permissions)
        for index, p in enumerate(response['permissions']):
            assert p['serviceId'] == permissions[index].service.pk
            assert parse_iso_date(p['createdAt']) == permissions[index].created_at
            assert p['type'] == serialize_choices(Service.TYPES, permissions[index].service.tp)
            assert p['provider'] == serialize_choices(Service.PROVIDERS, permissions[index].service.provider)

    def test_empty_list(self):
        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, [])

    def test_active_permissions_list(self):
        permissions = [
            self.create_user_service_permission(self.user, self.services[0]),
            self.create_user_service_permission(self.user, self.services[1]),
        ]
        permissions.reverse()
        self.create_user_service_permission(self.user, self.services[2], is_active=False)
        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, permissions)
