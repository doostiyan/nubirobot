from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from exchange.accounts.models import User
from exchange.base.models import Settings


class APIKeyEmailTest(APITestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)

        self.user.requires_2fa = True

        self.client = APIClient(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user201token',
            HTTP_X_TOTP='111111',
        )

        vp = self.user.get_verification_profile()
        vp.email_confirmed = True
        vp.save()

        self.user.save()

    @pytest.mark.slow
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    @patch('exchange.accounts.functions.check_user_otp', lambda *_args, **_kwargs: True)
    def test_api_email(self):
        Settings.set_dict('email_whitelist', [self.user.email])

        call_command('update_email_templates')

        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing an email',
                'permissions': 'READ,TRADE,WITHDRAW',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response

        key = response['key']['key']

        response = self.client.post(
            f'/apikeys/update/{key}',
            data={
                'ipAddressesWhitelist': ['188.121.146.46', '188.121.146.45'],
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response

        response = self.client.post(
            f'/apikeys/delete/{key}',
            format='json',
        ).json()

        assert response['status'] == 'ok', response

        with patch('django.db.connection.close'):
            call_command('send_queued_mail')
