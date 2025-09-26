from urllib.parse import urlencode

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.charts.models import StudyTemplate


class StudyTemplateAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.endpoint = '/charts/storage/1.1/study_templates'
        cls.user: User = User.objects.get(pk=201)
        cls.user2: User = User.objects.get(pk=202)
        cls.client_name = 'nobitex'

    def setUp(self):
        self.study_template = StudyTemplate.objects.create(
            ownerId=str(self.user.id),
            ownerSource=self.client_name,
            name='template1',
            content='{"key": "value"}',
            user=self.user,
        )


    def test_list_of_templates_using_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

        response = self.client.get(self.endpoint, {'client': self.client_name})

        assert response.status_code == status.HTTP_200_OK

        response = response.json()

        assert response.get('status') == 'ok'
        assert len(response.get('data', [])) == 1


    def test_delete_template_using_token(self):
        data = {'client': self.client_name, 'template': 'template1'}

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        response = self.client.delete(f'{self.endpoint}?{urlencode(data)}')

        assert response.status_code == status.HTTP_200_OK

        response = response.json()

        assert response.get('status') == 'ok'
        assert StudyTemplate.objects.filter(user=self.user).count() == 0

    def test_delete_template_other_user_fail(self):
        data = {'client': self.client_name, 'template': 'template1'}

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user2.auth_token.key}')
        response = self.client.delete(f'{self.endpoint}?{urlencode(data)}')

        assert response.status_code == status.HTTP_200_OK

        response = response.json()

        assert response.get('status') == 'error'
        assert StudyTemplate.objects.filter(user=self.user).count() == 1



    def test_update_template_using_token(self):
        data = {'client': self.client_name}
        payload = {'name': 'template1', 'content': '{"key2": "value2"}'}

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        response = self.client.post(f'{self.endpoint}?{urlencode(data)}', payload)

        assert response.status_code == status.HTTP_200_OK
        response = response.json()

        assert response.get('status') == 'ok'

        template = StudyTemplate.objects.filter(user=self.user, name='template1').first()

        assert template is not None
        assert template.content == '{"key2": "value2"}'
        assert StudyTemplate.objects.filter(user=self.user).count() == 1

