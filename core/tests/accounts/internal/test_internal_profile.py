from uuid import uuid4

from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.internal.services import Services
from tests.helpers import InternalAPITestMixin, create_internal_token, mock_internal_service_settings


class TestInternalUserProfile(InternalAPITestMixin, APITestCase):
    URL = '/internal/users/%s/profile'

    def setUp(self):
        self.user = User.objects.create_user(
            uid=uuid4(), username='test-user', mobile='09123334455', email='test@test.com', national_code='123456890'
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ABC.value)}')
        vp = self.user.get_verification_profile()
        vp.email_confirmed = True
        vp.mobile_confirmed = True
        vp.identity_confirmed = True
        vp.mobile_identity_confirmed = True
        vp.save()

    def _request(self, user_uid=None):
        return self.client.get(self.URL % (user_uid or uuid4()))

    @mock_internal_service_settings
    def test_get_internal_user_profile(self):
        response = self.client.get(self.URL % self.user.uid)
        assert response.status_code == 200, response.json()
        profile = response.json()
        assert profile['uid'] == str(self.user.uid)
        assert profile['email'] == self.user.email
        assert profile['mobile'] == self.user.mobile
        assert profile['username'] == self.user.username
        assert profile['nationalCode'] == self.user.national_code
        assert profile['verificationStatus'] == self.user.verification_status
        assert profile['userType'] == self.user.user_type
        assert profile['gender'] == self.user.gender
        assert profile['fatherName'] == self.user.father_name
        assert profile['birthdateShamsi'] == self.user.birthday_shamsi
        assert profile['requires2fa'] == self.user.requires_2fa
        vp = self.user.get_verification_profile()
        assert profile['verificationProfile']['emailConfirmed'] == vp.email_confirmed
        assert profile['verificationProfile']['mobileConfirmed'] == vp.mobile_confirmed
        assert profile['verificationProfile']['identityConfirmed'] == vp.identity_confirmed
        assert profile['verificationProfile']['mobileIdentityConfirmed'] == vp.mobile_identity_confirmed

    @mock_internal_service_settings
    def test_get_internal_user_profile_user_not_found(self):
        response = self.client.get(self.URL % str(uuid4()))
        assert response.status_code == 404
        assert response.json() == {'message': 'User not found', 'error': 'NotFound'}

    @mock_internal_service_settings
    def test_get_internal_user_profile_invalid_uuid(self):
        response = self.client.get(self.URL % 'invalid-uuid')
        assert response.status_code == 404

    @mock_internal_service_settings
    def test_get_internal_user_profile_token_without_permission(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token("notification")}')

        response = self.client.get(self.URL % self.user.uid)
        assert response.status_code == 404
        assert response.json() == {'detail': 'یافت نشد.'}
