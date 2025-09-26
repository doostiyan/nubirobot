import base64
import hashlib
import random
import string

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.oauth.constants import Scopes
from exchange.oauth.models import Grant
from tests.oauth.helpers import create_application


class AuthorizationAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.get(id=202)
        self.application_user = User.objects.get(id=203)
        self.scope = ' '.join(Scopes.get_all().keys())
        self.application = create_application(
            self.application_user, redirect_uris='https://www.nobitex.com localhost:8020/', scope=self.scope
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.url = '/oauth/authorization'
        self.state = 'lkajdslkfalikafylkfjldsakf'
        self.code_verifier = ''.join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(random.randint(43, 128))
        )
        self.code_challenge = hashlib.sha256(self.code_verifier.encode('utf-8')).digest()
        self.code_challenge = base64.urlsafe_b64encode(self.code_challenge).decode('utf-8').replace('=', '')
        self.code_challenge_method = 'S256'

    def test_call_get_api_successfully(self):
        data = {
            'clientId': self.application.client_id,
            'redirectUri': 'https://www.nobitex.com',  # or localhost:8020/
            'scope': self.scope,
            'state': self.state,
            'responseType': 'code',
            'codeChallenge': self.code_challenge,
            'codeChallengeMethod': self.code_challenge_method,
        }
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_200_OK
        output_data = response.json()
        assert output_data['status'] == 'ok'
        grant = Grant.objects.get(user=self.user, application=self.application)
        assert grant.scope == self.scope
        assert grant.code_challenge == self.code_challenge
        assert grant.code_challenge_method == self.code_challenge_method
        assert grant.redirect_uri == data['redirectUri']
        assert (
            output_data['data']['redirectUri']
            == self.application.redirect_uris.split()[0] + f'?code={grant.code}&state={self.state}'
        )
        assert output_data['data']['state'] == self.state

    def test_call_without_authenticated_user_fail(self):
        self.client.credentials(HTTP_AUTHORIZATION='')
        response = self.client.post(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_call_with_invalid_PKCE_method_fail(self):
        data = {
            'clientId': self.application.client_id,
            'redirectUri': 'localhost:8020/',
            'scope': self.scope,
            'state': self.state,
            'responseType': 'code',
            'codeChallenge': 'test',
            'codeChallengeMethod': 'test',
        }
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.check_failed_response(response, 'InvalidCodeChallengeMethod', 'Transform algorithm not supported.')

    def test_call_with_invalid_scope_fail(self):
        data = {
            'clientId': self.application.client_id,
            'redirectUri': 'localhost:8020/',
            'scope': 'ali kafy',
            'state': self.state,
            'responseType': 'code',
            'codeChallenge': self.code_challenge,
            'codeChallengeMethod': self.code_challenge_method,
        }
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.check_failed_response(response, 'InvalidScope', 'Scope is invalid.')

    def test_call_with_invalid_redirect_uri_fail(self):
        data = {
            'clientId': self.application.client_id,
            'redirectUri': 'alikafy',
            'scope': self.scope,
            'state': self.state,
            'responseType': 'code',
            'codeChallenge': self.code_challenge,
            'codeChallengeMethod': self.code_challenge_method,
        }
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.check_failed_response(response, 'InvalidRedirectURI', 'Redirect_uri is invalid.')

    def test_call_with_invalid_response_type_fail(self):
        data = {
            'clientId': self.application.client_id,
            'redirectUri': 'localhost:8020/',
            'scope': self.scope,
            'state': self.state,
            'responseType': 'kafy',
            'codeChallenge': self.code_challenge,
            'codeChallengeMethod': self.code_challenge_method,
        }
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.check_failed_response(response, 'UnsupportedResponseType', 'Unsupported response_type.')

    def test_call_with_invalid_client_id(self):
        data = {
            'clientId': self.application.client_id + 'ali',
            'redirectUri': 'localhost:8020/',
            'scope': self.scope,
            'state': self.state,
            'responseType': 'code',
            'codeChallenge': self.code_challenge,
            'codeChallengeMethod': self.code_challenge_method,
        }
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        self.check_failed_response(response, 'NotFound', 'Client not found')

    def test_call_with_out_of_application_scopes_fail(self):
        self.application.scope = 'user-info'
        self.application.save()
        data = {
            'clientId': self.application.client_id,
            'redirectUri': 'localhost:8020/',
            'scope': self.scope,
            'state': self.state,
            'responseType': 'code',
            'codeChallenge': self.code_challenge,
            'codeChallengeMethod': self.code_challenge_method,
        }
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.check_failed_response(response, 'InvalidScope', 'Scope is invalid.')

    def test_call_with_mismatching_uri(self):
        data = {
            'clientId': self.application.client_id,
            'redirectUri': 'https://www.google.com/',
            'scope': self.scope,
            'state': self.state,
            'responseType': 'code',
            'codeChallenge': self.code_challenge,
            'codeChallengeMethod': self.code_challenge_method,
        }
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.check_failed_response(response, 'MismatchingRedirectURIError', 'Mismatching redirect URI.')

    def test_call_with_inactive_user(self):
        data = {
            'clientId': self.application.client_id,
            'redirectUri': 'https://www.nobitex.com',  # or localhost:8020/
            'scope': self.scope,
            'state': self.state,
            'responseType': 'code',
            'codeChallenge': self.code_challenge,
            'codeChallengeMethod': self.code_challenge_method,
        }
        self.user.is_active = False
        self.user.save()
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {'detail': 'کاربر غیرفعال است یا حذف شده.'}

    def check_failed_response(self, response, code, message):
        output = response.json()
        assert output['status'] == 'failed'
        assert output['code'] == code
        assert output['message'] == message
        assert output['state'] == self.state
