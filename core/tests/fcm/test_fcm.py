from django.test import TestCase
from django.test import Client
from rest_framework.test import DjangoClient
from exchange.accounts.models import User
from exchange.fcm.models import FCMDevice


class MarketTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.get(pk=201)

    def test_set_user_token(self):
        tp_android, tp_web = FCMDevice.DEVICE_TYPES.android, FCMDevice.DEVICE_TYPES.web
        token1 = 'test:token1'
        token2 = 'test:token1'
        # Test registering a new token
        d1 = FCMDevice.set_user_token(self.user1, tp_android, token1)
        assert d1.user == self.user1
        assert d1.token == token1
        assert d1.device_type == tp_android
        assert d1.is_active
        assert d1.created_at
        # Test updating existing token
        d2 = FCMDevice.set_user_token(self.user1, tp_android, token2)
        assert d2.token == token2
        assert d2.id == d1.id
        assert d2.device_type == tp_android
        assert d2.is_active
        # Test adding a token of another type
        d3 = FCMDevice.set_user_token(self.user1, tp_web, 't3')
        assert d3.id != d2.id
        assert d3.token == 't3'
        assert d3.device_type == tp_web
        assert d3.is_active
        # Test registering an existing token again
        d4 = FCMDevice.set_user_token(self.user1, tp_android, token2)
        assert d4.token == token2
        assert d4.id == d2.id
        assert d4.device_type == tp_android
        assert d4.is_active


class UserFCMDevicesTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client = Client(HTTP_USER_AGENT='Android/9.0', HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.anonymous_client = DjangoClient('')
        self.user_password = 'password'
        self.user.set_password(self.user_password)
        self.user.save()

    def test_deactive_device_after_logout_android(self):

        request_body = {
            'username': self.user.username,
            'password': self.user_password,
        }
        response = self.anonymous_client.post('/auth/login/', request_body)
        assert response.status_code == 200


        token_value = 'FCM_registration_token'
        request_body = {
            'value': token_value,
            'preference': 'fcm-deviceid'
        }
        device_type = FCMDevice.DEVICE_TYPES.android
        devices = FCMDevice.objects.filter(user=self.user, device_type=device_type, is_active=True)
        assert devices.count() == 0

        response = self.client.post('/users/set-preference', request_body)
        assert response.status_code == 200
        devices = FCMDevice.objects.filter(user=self.user, device_type=device_type, token=token_value)
        assert devices.count() == 1
        device = devices.first()
        assert device.is_active is True
        assert device.device_type == device_type

        response = self.client.post('/auth/logout/')
        assert response.status_code == 200
        devices = FCMDevice.objects.filter(user=self.user, device_type=device_type, token=token_value)
        assert devices.count() == 1
        device = devices.first()
        assert device.is_active is False
