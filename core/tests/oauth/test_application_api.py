from datetime import timedelta
from unittest.mock import patch

from django.http import JsonResponse
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.oauth.constants import Scopes
from tests.oauth.helpers import create_access_token, create_application


class ApplicationAPITest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client_user = User.objects.get(pk=201)
        cls.scope = 'profile-info'
        cls.url = '/oauth/client/{client_id}'
        cls.user = User.objects.get(pk=202)

    def setUp(self) -> None:
        self.application = create_application(user=self.client_user, client_id='my_app', scope=self.scope)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def test_unauthorized_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token wrong_token')
        response = self.client.get(self.url.format(client_id='wrong_app'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {'detail': 'توکن غیر مجاز'}

    def test_application_not_found(self):
        response = self.client.get(self.url.format(client_id='wrong_app'))
        self._assert_failed_response(
            response=response, code='NotFound', message='Client not found', status_code=status.HTTP_404_NOT_FOUND
        )

    def test_get_application_info_successfully(self):
        response = self.client.get(self.url.format(client_id='my_app'))
        self._assert_successful_response(response=response, scopes=[])

        self.application.scope = 'profile-info user-info'
        self.application.save()
        response = self.client.get(self.url.format(client_id='my_app'))
        self._assert_successful_response(response=response, scopes=[])

    def test_get_application_successfully_with_correct_scopes(self):
        data = {'scopes': 'profile-info'}
        response = self.client.get(self.url.format(client_id='my_app'), data=data)
        self._assert_successful_response(response=response)

    def test_get_application_successfully_with_wrong_scopes(self):
        data = {'scopes': ''}
        response = self.client.get(self.url.format(client_id='my_app'), data=data)
        self._assert_successful_response(response=response, scopes=[])

        data = {'scopes': 'no-scope'}
        response = self.client.get(self.url.format(client_id='my_app'), data=data)
        self._assert_successful_response(response=response, scopes=[])

        data = {'scopes': 'no-scope profile-info'}
        response = self.client.get(self.url.format(client_id='my_app'), data=data)
        self._assert_successful_response(response=response)

    @patch('exchange.oauth.constants.Scopes.get_all', return_value={**Scopes.get_all(), 'new-scope': 'Some new scope'})
    def test_get_application_successfully_with_scopes_out_of_applications_scopes(self, _):
        data = {'scopes': 'new-scope'}
        response = self.client.get(self.url.format(client_id='my_app'), data=data)
        self._assert_successful_response(response=response, scopes=[])

        data = {'scopes': 'new-scope profile-info'}
        response = self.client.get(self.url.format(client_id='my_app'), data=data)
        self._assert_successful_response(response=response)

    def test_get_application_successfully_with_authorized_scopes(self):
        access_token = create_access_token(user=self.user, application=self.application, scope='read')
        data = {'scopes': 'read profile-info'}
        response = self.client.get(self.url.format(client_id='my_app'), data=data)
        self._assert_successful_response(response=response)

        access_token.scope = 'read profile-info'
        access_token.save()
        response = self.client.get(self.url.format(client_id='my_app'), data=data)
        self._assert_successful_response(response=response, scopes=[])

        access_token.expires = ir_now() - timedelta(days=2)
        access_token.save()
        response = self.client.get(self.url.format(client_id='my_app'), data=data)
        self._assert_successful_response(response=response)

    def test_get_application_successfully_with_duplicated_scopes(self):
        data = {'scopes': 'user-info user-info profile-info profile-info'}
        response = self.client.get(self.url.format(client_id='my_app'), data=data)
        self._assert_successful_response(response=response)

        self.application.scope = 'profile-info user-info'
        self.application.save()
        response = self.client.get(self.url.format(client_id='my_app'), data=data)
        self._assert_successful_response(
            response=response, scopes=[Scopes.PROFILE_INFO.description, Scopes.USER_INFO.description]
        )

        create_access_token(user=self.user, application=self.application, scope='profile-info')
        response = self.client.get(self.url.format(client_id='my_app'), data=data)
        self._assert_successful_response(response=response, scopes=[Scopes.USER_INFO.description])

    def _assert_failed_response(self, response: JsonResponse, code: str, message: str, status_code: int):
        assert response.status_code == status_code
        json_response = response.json()
        assert 'status' in json_response
        assert json_response['status'] == 'failed'
        assert 'code' in json_response
        assert json_response['code'] == code
        assert 'message' in json_response
        assert json_response['message'] == message

    def _assert_successful_response(self, response: JsonResponse, scopes: [str] = None):
        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert 'status' in json_response
        assert json_response['status'] == 'ok'
        assert 'data' in json_response
        data = json_response['data']
        assert 'clientName' in data
        assert data['clientName'] == self.application.name
        assert 'scopes' in data
        if scopes is not None:
            assert sorted(data['scopes']) == sorted(scopes)
        else:
            assert data['scopes'] == [Scopes.get_all()[self.scope]]
        assert 'authorizationGrantType' in data
        assert data['authorizationGrantType'] == self.application.authorization_grant_type
