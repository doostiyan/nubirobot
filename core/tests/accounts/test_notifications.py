from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import Notification, User


class NotificationTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        Notification.objects.all().delete()

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def send_notification(self, message, is_read=False):
        return Notification.objects.create(user=self.user, message=message, is_read=is_read)

    def test_notifications_list(self):
        self.send_notification('First Massage')
        self.send_notification('Second Massage', is_read=True)
        self.send_notification('Third Massage')
        response = self.client.get('/notifications/list')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['notifications']) == 3
        assert data['notifications'][0]['message'] == 'Third Massage'
        assert not data['notifications'][0]['read']
        assert data['notifications'][1]['message'] == 'Second Massage'
        assert data['notifications'][1]['read']
        assert data['notifications'][2]['message'] == 'First Massage'
        assert not data['notifications'][2]['read']

    def test_notifications_read(self):
        notifications = [self.send_notification(f'Massage {i}') for i in range(3)]
        response = self.client.post('/notifications/read', data={'id': f'{notifications[0].id},{notifications[2].id}'})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert data['processed'] == 2
        for notification in notifications:
            notification.refresh_from_db()
        assert notifications[0].is_read
        assert not notifications[1].is_read
        assert notifications[2].is_read

    def test_notifications_read_effect_on_list(self):
        notifications = [self.send_notification(f'Massage {i}') for i in range(2)]

        response = self.client.get('/notifications/list')
        data = response.json()
        assert data['status'] == 'ok'
        assert not any(n['read'] for n in data['notifications'])

        response = self.client.post('/notifications/read', data={'id': f'{notifications[0].id}'})
        data = response.json()
        assert data['status'] == 'ok'
        assert data['processed'] == 1

        response = self.client.get('/notifications/list')
        data = response.json()
        assert data['status'] == 'ok'
        assert not data['notifications'][0]['read']
        assert data['notifications'][1]['read']

    def test_notifications_read_an_already_read(self):
        notification = self.send_notification('Massage', is_read=True)
        response = self.client.post('/notifications/read', data={'id': f'{notification.id}'})
        data = response.json()
        assert data['status'] == 'ok'
        assert data['processed'] == 0
