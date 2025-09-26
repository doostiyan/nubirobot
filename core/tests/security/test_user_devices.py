import datetime
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase, DjangoClient

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.security.models import KnownDevice, LoginAttempt


class UserDevicesTest(APITestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.anonymous_client = DjangoClient()
        self.user_password = 'password'
        self.user.set_password(self.user_password)
        self.user.save()

    def _login(self, device=None):
        request_body = {
            'username': self.user.username,
            'password': self.user_password,
        }
        if device is not None:
            request_body['device'] = device
        response = self.anonymous_client.post('/auth/login/', request_body).json()
        assert response['status'] == 'success'
        return response['device']

    def _create_devices(self):
        devices = []
        number_of_logins = [4, 3, 6]
        for n in number_of_logins:
            device = self._login()
            devices.append(device)
            for _ in range(n-1):
                self._login(device)
        return devices, number_of_logins

    def test_devices_list(self):
        devices, number_of_logins = self._create_devices()

        response = self.client.get('/security/devices').json()
        assert response['status'] == 'ok'
        assert len(response['devices']) == len(devices)
        fetched_devices = dict(map(
            lambda device_info: (device_info['device'], device_info),
            response['devices'],
        ))
        for device, login_count in zip(devices, number_of_logins):
            device_info = fetched_devices.get(device)
            assert device_info is not None
            assert len(device_info['login_attempts']) == login_count
            login_datetimes = []
            for login_attempt in device_info['login_attempts']:
                login_datetimes.append(datetime.datetime.fromisoformat(login_attempt['created_at']))
            assert max(login_datetimes) == login_datetimes[0]


    def test_remove_device(self):
        devices, _ = self._create_devices()
        deleted_device = devices[0]
        deleted_device_login_attempts_ids = list(KnownDevice.objects.get(
            device_id=deleted_device
        ).loginattempt_set.all().values_list('id', flat=True))
        response = self.client.post('/security/devices/delete', data={
            'device': deleted_device
        }).json()
        assert response['status'] == 'ok'
        assert len(deleted_device_login_attempts_ids) == LoginAttempt.objects.filter(
            id__in=deleted_device_login_attempts_ids,
            device_id__isnull=True,
        ).count()
        response = self.client.get('/security/devices').json()
        assert response['status'] == 'ok'
        assert len(response['devices']) == len(devices) - 1
        assert deleted_device not in [
            device_info['device']
            for device_info in response['devices']
        ]
        response = self.client.post('/security/devices/delete', data={
            'device': deleted_device
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_remove_all_devices(self):
        _, _ = self._create_devices()
        user_devices_login_attempts_ids = LoginAttempt.objects.filter(
            device_id__in=list(KnownDevice.objects.filter(
                user=self.user
            ).values_list('id', flat=True)),
        )
        response = self.client.post('/security/devices/delete-all', data={}).json()
        assert response['status'] == 'ok'
        assert len(user_devices_login_attempts_ids) == LoginAttempt.objects.filter(
            id__in=user_devices_login_attempts_ids,
            device_id__isnull=True,
        ).count()
        response = self.client.get('/security/devices').json()
        assert response['status'] == 'ok'
        assert len(response['devices']) == 0

    def test_new_unknown_login(self):
        assert not self.user.has_new_unknown_login(duration=datetime.timedelta(hours=1))
        self._create_devices()
        assert self.user.has_new_unknown_login(duration=datetime.timedelta(hours=1))
        assert self.user.has_new_unknown_login(duration=datetime.timedelta(minutes=10))
        LoginAttempt.objects.update(created_at=ir_now() - datetime.timedelta(minutes=20))
        assert not self.user.has_new_unknown_login(duration=datetime.timedelta(minutes=10))


class KnownDeviceTest(TestCase):

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)

    @pytest.mark.slow
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    @patch('exchange.security.signals.Settings.get_flag', return_value=True)
    def test_login_from_new_device_call_email(self, mock_settings_get_flag):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')

        KnownDevice.objects.create(name='test_device', user=self.user, device_id='123456', user_agent='Firefox 123',
                                   last_activity=ir_now())

        with patch('django.db.connection.close'):
            call_command('send_queued_mail')
