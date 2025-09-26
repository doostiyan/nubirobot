import time
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.security.models import LoginAttempt


class LoginAttemptsTest(APITestCase):

    def setUp(self) -> None:
        self.list_url = '/users/login-attempts'
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        attempts = []
        for i in range(0, 50):
            attempts.append(
                LoginAttempt(user=cls.user, username=cls.user.email)
            )
        LoginAttempt.objects.bulk_create(attempts)

    def test_list(self):
        # first page
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['attempts']), 15)

        # last page
        response = self.client.get(f'{self.list_url}?page=4')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['attempts']), 5)

        # out of index page
        response = self.client.get(f'{self.list_url}?page=5')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['attempts']), 0)

        # page size
        response = self.client.get(f'{self.list_url}?page=2&pageSize=30')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['attempts']), 20)

