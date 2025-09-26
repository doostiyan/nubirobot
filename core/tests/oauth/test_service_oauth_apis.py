import hashlib

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_today
from exchange.base.serializers import serialize
from tests.oauth.helpers import create_access_token, create_application, create_grant


class BaseNobitexOauthAPIsTest(APITestCase):
    def setUp(self):
        self.application_user = User.objects.get(id=203)
        self.user = User.objects.get(id=202)
        self.application = create_application(self.application_user, acceptable_ip='127.0.0.1')
        self.grant = create_grant(self.application, self.user)
        self.access = create_access_token(user=self.user, application=self.application, scope='profile-info')
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.access.token}'}
        self.verification_profile = self.user.get_verification_profile()
        self.user.mobile = '09133556358'
        self.user.save()
        self.verification_profile.email_confirmed = True
        self.verification_profile.mobile_confirmed = True
        self.verification_profile.save()


class TestProfileInfo(BaseNobitexOauthAPIsTest):
    URL = '/oauth-services/profile-info'

    def test_call_api_successfully(self):
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output['status'] == 'ok'
        assert output['data']['userId'] == hashlib.sha256(f'{self.application.id}-{self.user.id}'.encode()).hexdigest()
        assert output['data']['email'] == self.user.email
        assert output['data']['phoneNumber'] == self.user.mobile

    def test_call_api_without_access_token_fail(self):
        response = self.client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_call_api_with_invalid_access_token_fail(self):
        extra = {'HTTP_AUTHORIZATION': f'Bearer {self.access.token}alikafy'}
        response = self.client.get(self.URL, **extra)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_call_api_with_out_of_range_scope_fail(self):
        self.access.scope = 'user-info'
        self.access.save()
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_call_api_with_invalid_ip_fail(self):
        self.application.acceptable_ip = '192.168.10.199'
        self.application.save()
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_call_api_with_not_verified_mobile_number(self):
        self.verification_profile.mobile_confirmed = False
        self.verification_profile.save()
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output['status'] == 'ok'
        assert output['data']['userId'] == hashlib.sha256(f'{self.application.id}-{self.user.id}'.encode()).hexdigest()
        assert output['data']['email'] == self.user.email
        assert output['data']['phoneNumber'] is None

    def test_call_api_with_not_verified_email(self):
        self.verification_profile.email_confirmed = False
        self.verification_profile.save()
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output['status'] == 'ok'
        assert output['data']['userId'] == hashlib.sha256(f'{self.application.id}-{self.user.id}'.encode()).hexdigest()
        assert output['data']['email'] is None
        assert output['data']['phoneNumber'] == self.user.mobile

    def test_call_api_with_inactive_user(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {'detail': 'کاربر غیرفعال است یا حذف شده.'}


class TestUserInfo(BaseNobitexOauthAPIsTest):
    URL = '/oauth-services/user-info'

    def setUp(self):
        super().setUp()
        self.access.scope = 'user-info'
        self.access.save()
        self.user.birthday = ir_today()
        self.user.save()

    def test_call_api_successfully(self):
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output['status'] == 'ok'
        assert output['data']['firstName'] == self.user.first_name
        assert output['data']['lastName'] == self.user.last_name
        assert output['data']['birthdate'] == serialize(self.user.birthday)
        assert output['data']['level'] == self.user.get_user_type_display()

    def test_call_api_without_access_token_fail(self):
        response = self.client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_call_api_with_invalid_access_token_fail(self):
        extra = {'HTTP_AUTHORIZATION': f'Bearer {self.access.token}alikafy'}
        response = self.client.get(self.URL, **extra)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_call_api_with_out_of_range_scope_fail(self):
        self.access.scope = 'profile-info'
        self.access.save()
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_call_api_with_other_ip_fail(self):
        self.application.acceptable_ip = '192.168.10.199'
        self.application.save()
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_call_api_with_inactive_user_fail(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {'detail': 'کاربر غیرفعال است یا حذف شده.'}


class TestIdentityInfo(BaseNobitexOauthAPIsTest):
    URL = '/oauth-services/identity-info'

    def setUp(self):
        super().setUp()
        self.access.scope = 'identity-info'
        self.access.save()
        self.user.birthday = ir_today()
        self.user.save()

    def test_call_api_successfully(self):
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output['status'] == 'ok'
        assert output['data']['nationalCode'] == self.user.national_code

    def test_call_api_without_access_token_fail(self):
        response = self.client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_call_api_with_invalid_access_token_fail(self):
        extra = {'HTTP_AUTHORIZATION': f'Bearer {self.access.token}alikafy'}
        response = self.client.get(self.URL, **extra)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_call_api_with_out_of_range_scope_fail(self):
        self.access.scope = 'profile-info'
        self.access.save()
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_call_api_with_other_ip_fail(self):
        self.application.acceptable_ip = '192.168.10.199'
        self.application.save()
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_call_api_with_inactive_user_fail(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.get(self.URL, **self.header)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {'detail': 'کاربر غیرفعال است یا حذف شده.'}
