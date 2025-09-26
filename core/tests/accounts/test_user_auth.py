from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User


class AuthTest(APITestCase):
    def setUp(self):
        self.user = User.objects.get(id=202)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def test_auth_user_with_patch_method_fail(self):
        url = '/auth/user/'
        data = {'username': 'ali'}
        response = self.client.patch(url, data)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_auth_user_with_put_method_fail(self):
        url = '/auth/user/'
        data = {'username': 'ali'}
        response = self.client.put(url, data)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_auth_user_with_get_method_successfully(self):
        url = '/auth/user/'
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        excepted_output = {
            'pk': 202,
            'email': 'user2@example.com',
            'first_name': 'User',
            'last_name': 'Two',
            'username': 'user2@example.com',
        }
        self.assertDictEqual(excepted_output, output)
