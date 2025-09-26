from datetime import datetime, timedelta
from typing import List

from django.http import JsonResponse
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.oauth.constants import Scopes
from exchange.oauth.models import AccessToken, Application
from tests.oauth.helpers import create_access_token, create_application


class GetGrantedAccessesAPITest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.client_user_one = User.objects.get(pk=202)
        cls.client_user_two = User.objects.get(pk=203)
        cls.profile_scope = 'profile-info'
        cls.user_scope = 'user-info'
        cls.url = '/oauth/granted-accesses'

    def setUp(self) -> None:
        self.application_one = create_application(
            user=self.client_user_one, scope=f'{self.profile_scope} {self.user_scope}'
        )
        self.application_two = create_application(
            user=self.client_user_two, scope=f'{self.profile_scope} {self.user_scope}'
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def test_get_granted_accesses_successfully_with_no_token(self):
        response = self.client.get(self.url)
        self._assert_successful_response(response, tokens=[])

    def test_get_granted_accesses_successfully(self):
        user_token = create_access_token(user=self.user, application=self.application_one, scope=self.user_scope)
        response = self.client.get(self.url)
        self._assert_successful_response(response, tokens=[user_token])

        user_token2 = create_access_token(user=self.user, application=self.application_two, scope=self.user_scope)
        response = self.client.get(self.url)
        self._assert_successful_response(response, tokens=[user_token, user_token2])

        profile_token = create_access_token(user=self.user, application=self.application_one, scope=self.profile_scope)
        profile_token2 = create_access_token(user=self.user, application=self.application_two, scope=self.profile_scope)
        response = self.client.get(self.url)
        self._assert_successful_response(response, tokens=[user_token, user_token2, profile_token, profile_token2])

    def test_get_granted_accesses_successfully_with_old_and_new_tokens(self):
        user_token = create_access_token(user=self.user, application=self.application_one, scope=self.user_scope)
        user_token2 = create_access_token(user=self.user, application=self.application_two, scope=self.user_scope)
        profile_token = create_access_token(user=self.user, application=self.application_one, scope=self.profile_scope)
        profile_token2 = create_access_token(user=self.user, application=self.application_two, scope=self.profile_scope)
        old_token = create_access_token(user=self.user, application=self.application_one, scope=self.user_scope)
        old_token.created = ir_now() - timedelta(hours=2)
        old_token.save()
        old_token = create_access_token(user=self.user, application=self.application_two, scope=self.user_scope)
        old_token.created = ir_now() - timedelta(minutes=5)
        old_token.save()
        old_token = create_access_token(user=self.user, application=self.application_one, scope=self.profile_scope)
        old_token.created = ir_now() - timedelta(minutes=2)
        old_token.save()
        old_token = create_access_token(user=self.user, application=self.application_two, scope=self.profile_scope)
        old_token.created = ir_now() - timedelta(hours=5)
        old_token.save()
        response = self.client.get(self.url)
        self._assert_successful_response(response, tokens=[user_token, user_token2, profile_token, profile_token2])

    def test_get_granted_accesses_successfully_with_expired_tokens(self):
        create_access_token(user=self.user, application=self.application_one, scope=self.user_scope)
        create_access_token(user=self.user, application=self.application_two, scope=self.user_scope)
        create_access_token(user=self.user, application=self.application_one, scope=self.profile_scope)
        create_access_token(user=self.user, application=self.application_two, scope=self.profile_scope)
        user_token = create_access_token(
            user=self.user,
            application=self.application_one,
            scope=self.user_scope,
            expires=ir_now() - timedelta(days=5),
        )
        user_token2 = create_access_token(
            user=self.user,
            application=self.application_two,
            scope=self.user_scope,
            expires=ir_now() - timedelta(minutes=5),
        )
        profile_token = create_access_token(
            user=self.user,
            application=self.application_one,
            scope=self.profile_scope,
            expires=ir_now() - timedelta(hours=2),
        )
        profile_token2 = create_access_token(
            user=self.user,
            application=self.application_two,
            scope=self.profile_scope,
            expires=ir_now() - timedelta(seconds=15),
        )
        response = self.client.get(self.url)
        self._assert_successful_response(response, tokens=[user_token, user_token2, profile_token, profile_token2])

    def test_get_granted_accesses_successfully_with_no_application(self):
        create_access_token(user=self.user, application=self.application_one, scope=self.user_scope)
        create_access_token(user=self.user, application=self.application_two, scope=self.user_scope)
        Application.objects.all().delete()
        response = self.client.get(self.url)
        self._assert_successful_response(response, tokens=[])

    def test_unauthorized_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token wrong_token')
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {'detail': 'توکن غیر مجاز'}

    def _assert_successful_response(self, response: JsonResponse, tokens: List[AccessToken]):
        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert 'status' in json_response
        assert json_response['status'] == 'ok'
        assert 'grantedAccesses' in json_response
        assert len(json_response['grantedAccesses']) == len(tokens)
        response_tokens = sorted(json_response['grantedAccesses'], key=lambda g: g['id'])
        tokens.sort(key=lambda g: g.id)
        for response_token, token in zip(response_tokens, tokens):
            assert 'id' in response_token
            assert response_token['id'] == token.id
            assert 'scope' in response_token
            assert response_token['scope'] == {token.scope: Scopes.get_all()[token.scope]}
            assert 'client' in response_token
            assert response_token['client']['clientName'] == token.application.name
            assert response_token['client']['authorizationGrantType'] == token.application.authorization_grant_type
            assert 'scopes' not in response_token['client']
            assert 'createdAt' in response_token
            assert datetime.fromisoformat(response_token['createdAt']) == token.created
            assert 'lastUpdate' in response_token
            assert datetime.fromisoformat(response_token['lastUpdate']) == token.updated
            assert 'expiration' in response_token
            assert datetime.fromisoformat(response_token['expiration']) == token.expires
