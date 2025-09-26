from django.test import TestCase

from exchange.accounts.models import User, EmailActivation


class EmailActivationTest(TestCase):
    def test_email_activation(self):
        user = User.objects.create_user(username='test')
        assert not user.is_email_verified
        # Invalid token format
        r = self.client.get('/users/email-activation-redirect?token=wrong')
        assert r.status_code == 200
        assert r.context['message'] == 'قالب آدرسی که روی آن کلیک کردید، نامعتبر است.'
        # Create activation link
        activation = EmailActivation.objects.create(user=user)
        # Invalid token format
        r = self.client.get('/users/email-activation-redirect?token=742b5582-f931-4b26-a4e5-88beb7d40d41')
        assert r.status_code == 200
        assert r.context['message'] == 'آدرسی که روی آن کلیک کردید، نامعتبر است.'
        user.refresh_from_db()
        assert not user.is_email_verified
        # Use link
        r = self.client.get(f'/users/email-activation-redirect?token={activation.token}')
        assert r.status_code == 302
        user.refresh_from_db()
        activation.refresh_from_db()
        assert activation.status == EmailActivation.STATUS.used
        assert user.is_email_verified
        # Check reuse
        r = self.client.get(f'/users/email-activation-redirect?token={activation.token}')
        assert r.context['message'] == 'ایمیل شما قبلاً فعال شده است، می‌توانید هم‌اکنون از حساب خود استفاده نمایید.'
        assert r.status_code == 200
