import base64
import datetime

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.oauth.models import AccessToken, Application, Grant, RefreshToken
from tests.oauth.helpers import create_access_token, create_application, create_grant, create_refresh_token


class BaseTokenAPITest(APITestCase):
    app: Application

    @classmethod
    def setUpTestData(cls):
        cls.app = create_application(user=User.objects.get(pk=201))

    def get_request_defaults(self):
        raise NotImplementedError

    def get_token_response(self, *, refresh=False, **kwargs):
        client_id = kwargs.pop('client_id', self.app.client_id) or ''
        client_secret = kwargs.pop('client_secret', getattr(self.app, 'actual_client_secret', ''))
        data = self.get_request_defaults()
        data.update(kwargs)
        data = {k: v for k, v in data.items() if v is not None}
        auth_string = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
        return self.client.post('/oauth/token', data, HTTP_AUTHORIZATION=f'Basic {auth_string}')


class AuthCodeTokenAPITest(BaseTokenAPITest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.grant = create_grant(application=cls.app, user=User.objects.get(pk=202))

    def get_request_defaults(self):
        return {
            'grantType': 'authorization_code',
            'codeVerifier': getattr(self.grant, 'code_verifier', ''),
            'redirectUri': self.grant.redirect_uri,
        }

    def test_generate_token_with_correct_code(self):
        assert not AccessToken.objects.exists()
        assert not RefreshToken.objects.exists()

        response = self.get_token_response(code=self.grant.code)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'

        assert AccessToken.objects.count() == 1
        assert RefreshToken.objects.count() == 1
        access_token = AccessToken.objects.first()

        assert access_token.token == data['accessToken']
        assert access_token.user_id == 202
        assert access_token.application_id == self.app.id
        assert access_token.scope == data['scope'] == self.grant.scope == 'read'
        assert access_token.source_refresh_token is None
        assert access_token.refresh_token.token == data['refreshToken']
        assert not access_token.refresh_token.revoked
        assert data['tokenType'] == 'Bearer'
        assert data['expiresIn'] == 3600
        assert not Grant.objects.exists()

    @staticmethod
    def _assert_token_generation_failed(response, code, message):
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code
        assert data['message'] == message
        assert not AccessToken.objects.exists()
        assert not RefreshToken.objects.exists()
        assert Grant.objects.exists()

    def test_generate_token_with_wrong_code(self):
        response = self.get_token_response(code='1234')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self._assert_token_generation_failed(response, code='InvalidGrant', message='Invalid grant')

    def test_generate_token_with_wrong_verifier(self):
        response = self.get_token_response(code=self.grant.code, codeVerifier='1234')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self._assert_token_generation_failed(response, code='InvalidGrant', message='Invalid grant')

    def test_generate_token_with_wrong_redirect_uri(self):
        response = self.get_token_response(code=self.grant.code, redirectUri='http://wronghost/callback')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self._assert_token_generation_failed(response, code='InvalidRequest', message='Mismatching redirect URI.')

    def test_generate_token_with_wrong_or_missing_grant_type(self):
        for grant_type in ('random', None):
            response = self.get_token_response(code=self.grant.code, grantType=grant_type)
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            self._assert_token_generation_failed(
                response,
                code='UnsupportedGrantType',
                message='Unsupported grant type',
            )

    def test_generate_token_with_wrong_client_secret(self):
        for client_secret in (
            '1a2b3c',  # Wrong secret
            self.app.client_secret,  # Leaked encoded secret (client_secret is encoded on save to protect from leaking)
        ):
            response = self.get_token_response(code=self.grant.code, client_secret=client_secret)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            self._assert_token_generation_failed(response, code='InvalidClient', message='Invalid client')

    def test_generate_token_with_restricted_ip_on_correct_ip(self):
        assert not AccessToken.objects.exists()
        assert not RefreshToken.objects.exists()

        self.app.acceptable_ip = '127.0.0.1'
        self.app.save(update_fields=('acceptable_ip',))

        response = self.get_token_response(code=self.grant.code)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'

        assert AccessToken.objects.count() == 1
        assert RefreshToken.objects.count() == 1
        assert not Grant.objects.exists()

    def test_generate_token_with_restricted_ip_on_wrong_ip(self):
        assert not AccessToken.objects.exists()
        assert not RefreshToken.objects.exists()

        self.app.acceptable_ip = '127.0.0.2'
        self.app.save(update_fields=('acceptable_ip',))

        response = self.get_token_response(code=self.grant.code)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        self._assert_token_generation_failed(
            response,
            code='InvalidIp',
            message='Invalid ip',
        )

    def test_generate_token_with_inactive_user(self):
        assert not AccessToken.objects.exists()
        assert not RefreshToken.objects.exists()

        user = User.objects.get(pk=202)
        user.is_active = False
        user.save()

        response = self.get_token_response(code=self.grant.code)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        self._assert_token_generation_failed(
            response,
            code='UnavailableUser',
            message='Cannot be authorized for this user.',
        )
        user.is_active = True
        user.save()


class RefreshTokenAPITest(BaseTokenAPITest):
    access_token: AccessToken
    refresh_token: RefreshToken

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.access_token = create_access_token(application=cls.app, user=User.objects.get(pk=202))
        cls.refresh_token = create_refresh_token(cls.access_token)

    def get_request_defaults(self):
        return {
            'grantType': 'refresh_token',
        }

    def test_refresh_token_with_correct_token(self):
        response = self.get_token_response(refreshToken=self.refresh_token.token, refresh=True)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'

        self.refresh_token.refresh_from_db()
        new_access_token = self.refresh_token.refreshed_access_token
        assert new_access_token != self.access_token
        assert new_access_token.application_id == self.app.id
        assert new_access_token.user_id == 202
        assert new_access_token.token == data['accessToken'] != self.access_token.token
        assert new_access_token.scope == data['scope'] == self.access_token.scope == 'read'
        assert new_access_token.source_refresh_token == self.refresh_token
        assert new_access_token.refresh_token != self.refresh_token
        assert new_access_token.refresh_token.token == data['refreshToken'] != self.refresh_token.token
        assert data['tokenType'] == 'Bearer'
        assert data['expiresIn'] == 3600

        assert not AccessToken.objects.filter(id=self.access_token.id).exists()
        assert self.refresh_token.revoked
        assert not new_access_token.refresh_token.revoked

    @classmethod
    def _assert_token_refresh_failed(cls, response, code, message, *, used_revoked_token=False):
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code
        assert data['message'] == message
        cls.access_token.refresh_from_db()
        if not used_revoked_token:
            cls.refresh_token.refresh_from_db()
            assert not cls.refresh_token.revoked

    def test_refresh_token_with_wrong_token(self):
        response = self.get_token_response(refreshToken='fAkEtOkEn', refresh=True)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self._assert_token_refresh_failed(
            response,
            code='InvalidGrant',
            message='Invalid grant',
        )

    def test_refresh_token_with_revoked_token(self):
        self.refresh_token.revoked = ir_now() - datetime.timedelta(minutes=30)
        self.refresh_token.save()

        response = self.get_token_response(refreshToken=self.refresh_token.token, refresh=True)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self._assert_token_refresh_failed(
            response,
            code='InvalidGrant',
            message='Invalid grant',
            used_revoked_token=True,
        )

    def test_refresh_token_of_other_app(self):
        other_app = create_application(user=User.objects.get(pk=203))
        access_token = create_access_token(other_app, user=User.objects.get(pk=204))
        refresh_token = create_refresh_token(access_token)

        response = self.get_token_response(refreshToken=refresh_token.token, refresh=True)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self._assert_token_refresh_failed(
            response,
            code='InvalidGrant',
            message='Invalid grant',
        )
        access_token.refresh_from_db()
        refresh_token.refresh_from_db()
        assert not refresh_token.revoked

    def test_refresh_token_with_no_token(self):
        response = self.get_token_response(refreshToken=None, refresh=True)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self._assert_token_refresh_failed(
            response,
            code='InvalidRequest',
            message='Missing refresh token parameter.',
        )

    def test_refresh_token_with_wrong_client_secret(self):
        response = self.get_token_response(refreshToken=self.refresh_token.token, client_secret='*' * 10, refresh=True)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        self._assert_token_refresh_failed(response, code='InvalidClient', message='Invalid client')

    def test_refresh_token_twice_in_a_row(self):
        response = self.get_token_response(refreshToken=self.refresh_token.token, refresh=True)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'

        next_response = self.get_token_response(refreshToken=self.refresh_token.token, refresh=True)
        assert next_response.status_code == status.HTTP_200_OK
        next_data = next_response.json()
        assert next_data['status'] == 'ok'

        assert data['accessToken'] == next_data['accessToken']
        assert data['refreshToken'] == next_data['refreshToken']
        assert AccessToken.objects.count() == 1

    def test_refresh_token_with_restricted_ip_on_correct_ip(self):
        self.app.acceptable_ip = '127.0.0.1'
        self.app.save(update_fields=('acceptable_ip',))

        response = self.get_token_response(refreshToken=self.refresh_token.token, refresh=True)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'

        assert AccessToken.objects.count() == 1
        assert RefreshToken.objects.count() == 2

    def test_refresh_token_with_restricted_ip_on_wrong_ip(self):
        self.app.acceptable_ip = '127.0.0.2'
        self.app.save(update_fields=('acceptable_ip',))

        response = self.get_token_response(refreshToken=self.refresh_token.token, refresh=True)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        self._assert_token_refresh_failed(
            response,
            code='InvalidIp',
            message='Invalid ip',
        )

    def test_refresh_token_with_inactive_user(self):
        assert AccessToken.objects.count() == 1
        assert RefreshToken.objects.count() == 1

        user = User.objects.get(pk=202)
        user.is_active = False
        user.save()

        response = self.get_token_response(refreshToken=self.refresh_token.token, refresh=True)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        self._assert_token_refresh_failed(
            response,
            code='UnavailableUser',
            message='Cannot be authorized for this user.',
        )
        user.is_active = True
        user.save()
