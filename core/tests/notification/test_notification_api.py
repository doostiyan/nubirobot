from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import Notification, User
from exchange.notification.models import InAppNotification


class NotificationAPITest(APITestCase):
    LIST_URL = '/notifications/list'
    READ_URL = '/notifications/read'

    def setUp(self):
        self.user = User.objects.get(id=202)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

        self.old_notification = Notification.objects.create(user=self.user, message='old notification')
        self.new_notification = InAppNotification.objects.create(user=self.user, message='new notification')

        cache.set('settings_kafka_broker_enabled', 'false')
        cache.set('settings_is_notification_broker_enabled', 'false')

    def test_list_notifications_from_old_model(self):
        response = self.client.get(self.LIST_URL)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output['notifications'][0]['message'] == 'old notification'

    def test_list_notifications_from_new_model(self):
        cache.set('settings_kafka_broker_enabled', 'true')
        cache.set('settings_is_notification_broker_enabled', 'true')
        response = self.client.get(self.LIST_URL)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output['notifications'][0]['message'] == 'new notification'

    def test_read_notifications_from_old_model(self):
        other_old_notification = Notification.objects.create(user=self.user, message='notification')
        response = self.client.get(
            self.READ_URL, data={'id': str(self.old_notification.id) + ',' + str(other_old_notification.id)}
        )
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output == {'processed': 2, 'status': 'ok'}

    def test_read_notifications_from_new_model(self):
        cache.set('settings_kafka_broker_enabled', 'true')
        cache.set('settings_is_notification_broker_enabled', 'true')
        assert not self.new_notification.is_read
        response = self.client.get(self.READ_URL, data={'id': self.new_notification.id})
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output == {'processed': 1, 'status': 'ok'}


class NewNotificationAPITest(APITestCase):
    LIST_URL = '/v2/notifications/list'
    READ_URL = '/v2/notifications/read'

    def setUp(self):
        self.user = User.objects.get(id=202)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.user_2 = User.objects.get(id=201)
        self.notification_1 = InAppNotification.objects.create(user=self.user, message='new notification 1')
        self.notification_2 = InAppNotification.objects.create(user=self.user, message='new notification 2')

    def test_list_notifications(self):
        response = self.client.get(self.LIST_URL)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert len(output['notifications']) == 2
        assert output['notifications'][0]['message'] == 'new notification 2'
        assert output['notifications'][1]['message'] == 'new notification 1'

    def test_read_notifications(self):
        assert not self.notification_2.is_read
        assert not self.notification_1.is_read
        response = self.client.post(
            self.READ_URL, data={'id': str(self.notification_1.id) + ',' + str(self.notification_2.id)}
        )
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output == {'processed': 2, 'status': 'ok'}

    def test_call_read_notifications_for_other_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_2.auth_token.key}')
        response = self.client.post(
            self.READ_URL, data={'id': str(self.notification_1.id) + ',' + str(self.notification_2.id)}
        )
        assert response.status_code == status.HTTP_200_OK
        assert not self.notification_1.is_read
        assert response.json() == {'processed': 0, 'status': 'ok'}

    def test_call_list_notifications_for_other_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_2.auth_token.key}')
        response = self.client.get(self.LIST_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {'hasNext': False, 'notifications': [], 'status': 'ok'}
