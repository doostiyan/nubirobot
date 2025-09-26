from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User, AntiPhishing, UserOTP, VerificationProfile
from exchange.base.models import Settings
from exchange.security.models import LoginAttempt


class AntiPhishingTest(APITestCase):
    fixtures = ['otp']

    def setUp(self):
        self.user = User.objects.get(pk=305)
        self.user_otp = UserOTP.objects.get(pk=54)
        self.user_otp2 = UserOTP.objects.get(pk=55)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=True)

    def tearDown(self):
        UserOTP.objects.all().delete()
        AntiPhishing.objects.all().delete()

    # test success to set anti phishing code
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_set_anti_phishing(self, send_email):
        sample_anti_phishing_code = 'dge45345435'
        r = self.client.post(f'/security/anti-phishing',
                             data={
                                 'code': sample_anti_phishing_code,
                                 'otpCode': self.user_otp.code,
                             })
        assert r.status_code == status.HTTP_200_OK
        current_anti_phishing_code = AntiPhishing.get_anti_phishing_code_by_user(self.user)
        assert sample_anti_phishing_code == current_anti_phishing_code

        # check get anti phishing code is working
        r = self.client.get('/security/anti-phishing')
        assert r.status_code == 200
        assert r.json()['antiPhishingCode'] == AntiPhishing.hide_code(sample_anti_phishing_code)
        # check anti phishing code exists
        assert AntiPhishing.objects.filter(user=self.user, is_active=True).count() == 1

        # test success to update anti phishing code
        sample_2_anti_phishing_code = 'vb5gn34tgf3d'
        r = self.client.post(f'/security/anti-phishing',
                             data={
                                 'code': sample_2_anti_phishing_code,
                                 'otpCode': self.user_otp2.code,
                             })
        assert r.status_code == status.HTTP_200_OK
        current_anti_phishing_code = AntiPhishing.get_anti_phishing_code_by_user(self.user)
        assert sample_2_anti_phishing_code == current_anti_phishing_code
        assert send_email.call_count == 2

    # test failed response without any code
    def test_without_anti_phishing_code(self):
        r = self.client.post(f'/security/anti-phishing', data={})
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert r.json()['code'] == 'ParseError'

    def test_without_verified_email(self):
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=False)
        sample_anti_phishing_code = 'dge45345435'
        r = self.client.post(f'/security/anti-phishing',
                             data={
                                 'code': sample_anti_phishing_code,
                                 'otpCode': self.user_otp.code,
                             })
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert r.json()['code'] == 'UnverifiedEmail'
        assert not bool(AntiPhishing.get_anti_phishing_code_by_user(self.user))

    def test_validation_anti_phishing_code(self):
        # test failed response by short length code
        short_length_anti_phishing_code = 'teg'
        r = self.client.post('/security/anti-phishing',
                             data={'code': short_length_anti_phishing_code, 'otpCode': self.user_otp2.code})
        assert r.json()['code'] == 'InvalidCodeLength'
        assert r.json()['status'] == 'failed'

        # test failed response by large length code
        large_length_anti_phishing_code = '143f5y4wfeq3t5efe'
        r = self.client.post('/security/anti-phishing',
                             data={'code': large_length_anti_phishing_code, 'otpCode': self.user_otp2.code})
        assert r.json()['code'] == 'InvalidCodeLength'
        assert r.json()['status'] == 'failed'

    @pytest.mark.slow
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_anti_phishing_code_email(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')
        AntiPhishing.objects.create(user=self.user, code='123$@456#&', is_active=True)
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)  # send sample email
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')
