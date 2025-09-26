import datetime
import enum
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.constants import RESTRICTION_REMOVAL_INTERVAL_MINUTES
from exchange.accounts.models import (
    AdminConsideration,
    ChangeMobileRequest,
    PasswordRecovery,
    User,
    UserOTP,
    UserRestriction,
    UserRestrictionRemoval,
)
from exchange.accounts.user_restrictions import UserRestrictionsDescription
from exchange.base.serializers import serialize


class UserRestrictionTest(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.user.mobile = '09151234567'
        self.user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def test_add_restriction(self):
        user = User.objects.get(pk=201)
        r1 = UserRestriction.add_restriction(user, 'WithdrawRequest', considerations='تست یک')
        assert r1.pk
        assert r1.restriction == UserRestriction.RESTRICTION.WithdrawRequest
        assert r1.considerations == 'تست یک'
        assert UserRestriction.objects.filter(user=user).count() == 1
        # Check admin consideration
        admin_consideration = AdminConsideration.objects.filter(user=user).order_by('-id').first()
        assert admin_consideration
        assert admin_consideration.consideration == 'محدودیت: ایجاد محدودیت Withdraw --- ملاحظات: تست یک'
        # Add another consideration
        r2 = UserRestriction.add_restriction(user, 'WithdrawRequest', considerations='تست دو')
        assert r2.pk == r1.pk
        assert UserRestriction.objects.filter(user=user).count() == 1
        # Add restriction of another type
        r3 = UserRestriction.add_restriction(user, 'WithdrawRequestCoin', considerations='تست سه')
        assert r3.pk
        assert r3.restriction == UserRestriction.RESTRICTION.WithdrawRequestCoin
        assert r3.considerations == 'تست سه'
        assert UserRestriction.objects.filter(user=user).count() == 2
        # Check temporary restriction - existing
        dt = datetime.timedelta(hours=1)
        r4 = UserRestriction.add_restriction(user, 'WithdrawRequest', considerations='تست سه', duration=dt)
        assert r4.pk == r1.pk
        assert r4.restriction == UserRestriction.RESTRICTION.WithdrawRequest
        assert r4.considerations == 'تست یک --- + --- تست دو --- + --- تست سه'
        assert UserRestrictionRemoval.objects.filter(restriction=r4).count() == 0
        # Temporary restriction - new
        r5 = UserRestriction.add_restriction(user, 'Trading', considerations='تست پنج', duration=dt)
        assert r5.pk
        assert r5.restriction == UserRestriction.RESTRICTION.Trading
        assert r5.considerations == 'تست پنج'
        assert UserRestriction.objects.filter(user=user).count() == 3
        rm5 = UserRestrictionRemoval.objects.get(restriction=r5)
        assert rm5.is_active
        assert rm5.admin_user_id == 1000
        expiry = (rm5.ends_at - now()).total_seconds()
        assert 3599 <= expiry <= 3600
        # Temporary restriction - new + extend end time
        r6 = UserRestriction.add_restriction(user, 'Trading', considerations='تست شش', duration=2 * dt)
        assert r6.pk == r5.pk
        assert UserRestriction.objects.filter(user=user).count() == 3
        rm6 = UserRestrictionRemoval.objects.get(restriction=r6)
        assert rm6.pk == rm5.pk
        expiry = (rm6.ends_at - now()).total_seconds()
        assert 7199 <= expiry <= 7200

    def _change_mobile(self, mobile):
        verify_mobile_url = '/users/verify-mobile'
        change_mobile = ChangeMobileRequest.objects.create(
            user=self.user,
            status=ChangeMobileRequest.STATUS.old_mobile_otp_sent,
            old_mobile=self.user.mobile,
            new_mobile=mobile
        )
        change_mobile.send_otp()
        otp = UserOTP.active_otps(
            user=self.user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.change_phone_number,
        ).first().code
        self.client.post(verify_mobile_url, {"otp": otp})

    def _change_password(self, new_password=None, new_password_confirm=None):
        change_password_url = '/auth/user/change-password'
        new_password = new_password or '123@Nobitex'
        new_password_confirm = new_password_confirm or new_password
        self.user.set_password('123')
        self.user.save()
        return self.client.post(change_password_url, {
            "currentPassword": '123',
            "newPassword": new_password,
            "newPasswordConfirm": new_password_confirm
        })

    def _remove_tfa(self):
        verify_mobile_url = '/users/tfa/disable'
        self.client.post(verify_mobile_url, {"otp": 123})

    def _forget_password(self):
        self.user.set_password('123')
        self.user.username = self.user.email = 'test@gmail.com'
        self.user.save()
        forget_password_url = '/auth/forget-password/'
        forget_password_confirm_url = '/auth/forget-password-commit/'
        self.client.post(forget_password_url, {"email": self.user.username}).json()
        token = PasswordRecovery.objects.get(user=self.user).token
        self.client.post(forget_password_confirm_url, {
            "token": token,
            "email": self.user.username,
            "password1": "123@Nobitex",
            "password2": "123@Nobitex",
        })

    def test_restriction_on_change_mobile(self):
        self._change_mobile('09371234567')
        self.assertTrue(self.user.is_restricted('WithdrawRequestCoin'))
        user_restriction = UserRestriction.objects.get(user=self.user,
                                                       restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin)
        user_restriction_removal = UserRestrictionRemoval.objects.get(restriction=user_restriction, is_active=True)
        remove_date = now() + datetime.timedelta(days=2) - datetime.timedelta(minutes=1)
        assert user_restriction_removal.ends_at >= remove_date
        assert (
            user_restriction.description
            == 'به\u200cدلیل تغییر شماره موبایل، تا 48 ساعت نمی\u200cتوانید رمزارز برداشت کنید. این محدودیت خودکار رفع می\u200cشود و نیازی نیست با پشتیبانی نوبیتکس تماس بگیرید.'
        )

    def test_restriction_on_change_mobile_when_user_has_permanent_restriction(self):

        UserRestriction.add_restriction(
            self.user, 'WithdrawRequestCoin', 'تست', description=DescriptionEnumForTest.test
        )
        self._change_mobile('09371234567')
        assert self.user.is_restricted('WithdrawRequestCoin')
        user_restriction = UserRestriction.objects.get(
            user=self.user, restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin
        )
        assert (
            user_restriction.considerations
            == 'تست --- + --- ایجاد محدودیت 48 ساعته برداشت رمز ارز بعلت تغییر شماره موبایل'
        )
        assert user_restriction.description == 'تست توضیحات'
        with pytest.raises(UserRestrictionRemoval.DoesNotExist):
            UserRestrictionRemoval.objects.get(restriction=user_restriction, is_active=True)

    def test_restriction_on_change_mobile_when_user_has_temporary_restriction(self):
        UserRestriction.add_restriction(
            self.user, 'WithdrawRequestCoin', 'تست', datetime.timedelta(days=3), description=DescriptionEnumForTest.test
        )
        self._change_mobile('09371234567')
        assert self.user.is_restricted('WithdrawRequestCoin')
        user_restriction = UserRestriction.objects.get(
            user=self.user, restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin
        )
        assert (
            user_restriction.considerations
            == 'تست --- + --- ایجاد محدودیت 48 ساعته برداشت رمز ارز بعلت تغییر شماره موبایل'
        )
        assert user_restriction.description == 'تست توضیحات'
        user_restriction_removal = UserRestrictionRemoval.objects.get(restriction=user_restriction, is_active=True)
        remove_date = now() + datetime.timedelta(days=3) - datetime.timedelta(minutes=1)
        assert user_restriction_removal.ends_at >= remove_date

    def test_restriction_on_change_mobile_when_user_has_different_type_restriction(self):
        UserRestriction.add_restriction(self.user, 'WithdrawRequestRial', 'تست')
        self._change_mobile('09371234567')

        assert self.user.is_restricted('WithdrawRequestCoin')
        user_restriction_coin = UserRestriction.objects.get(
            user=self.user, restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin
        )
        assert user_restriction_coin.considerations == 'ایجاد محدودیت 48 ساعته برداشت رمز ارز بعلت تغییر شماره موبایل'
        assert (
            user_restriction_coin.description
            == 'به\u200cدلیل تغییر شماره موبایل، تا 48 ساعت نمی\u200cتوانید رمزارز برداشت کنید. این محدودیت خودکار رفع می\u200cشود و نیازی نیست با پشتیبانی نوبیتکس تماس بگیرید.'
        )
        user_restriction_removal = UserRestrictionRemoval.objects.get(restriction=user_restriction_coin, is_active=True)
        remove_date = now() + datetime.timedelta(days=2) - datetime.timedelta(minutes=1)
        assert user_restriction_removal.ends_at >= remove_date

        assert self.user.is_restricted('WithdrawRequestRial')
        user_restriction_rial = UserRestriction.objects.get(user=self.user,
                                                            restriction=UserRestriction.RESTRICTION.WithdrawRequestRial)
        assert user_restriction_rial.considerations == 'تست'
        assert user_restriction_rial.description is None
        with pytest.raises(UserRestrictionRemoval.DoesNotExist):
            UserRestrictionRemoval.objects.get(restriction=user_restriction_rial, is_active=True)

    @patch('exchange.accounts.models.User.tfa_verify')
    def test_restriction_on_remove_tfa(self, mock):
        mock.return_value = True
        self._remove_tfa()
        assert self.user.is_restricted('WithdrawRequestCoin')
        user_restriction = UserRestriction.objects.get(user=self.user,
                                                       restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin)
        user_restriction.considerations = 'ایجاد محدودیت برداشت به علت غیر فعال سازی شناسایی دو عاملی'
        user_restriction_removal = UserRestrictionRemoval.objects.get(restriction=user_restriction, is_active=True)
        remove_date = now() + datetime.timedelta(days=1) - datetime.timedelta(minutes=1)
        assert user_restriction_removal.ends_at >= remove_date
        assert (
            user_restriction.description
            == 'به‌دلیل غیرفعالسازی کد دو عاملی، تا ۲۴ ساعت نمی‌توانید رمزارز برداشت کنید. این محدودیت خودکار رفع می‌شود و نیازی نیست با پشتیبانی تماس بگیرید.'
        )

    def test_restriction_on_change_password(self):
        self._change_password()
        assert self.user.is_restricted('WithdrawRequestCoin')
        user_restriction = UserRestriction.objects.get(user=self.user,
                                                       restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin)
        user_restriction.considerations = 'ایجاد محدودیت 24 ساعته برداشت رمز ارز بعلت تغییر رمز عبور'
        user_restriction_removal = UserRestrictionRemoval.objects.get(restriction=user_restriction, is_active=True)
        remove_date = now() + datetime.timedelta(days=1) - datetime.timedelta(minutes=1)
        assert user_restriction_removal.ends_at >= remove_date
        assert (
            user_restriction.description
            == 'به\u200cدلیل تغییر رمز عبور، تا 24 ساعت نمی\u200cتوانید رمزارز برداشت کنید. این محدودیت خودکار رفع می\u200cشود و نیازی نیست با پشتیبانی نوبیتکس تماس بگیرید.'
        )

    def test_no_restriction_on_change_password_failed(self):
        resp_json = self._change_password(new_password='abc').json()
        assert resp_json['status'] == 'failed'
        assert resp_json['code'] == 'UnacceptablePassword'
        assert not self.user.is_restricted('WithdrawRequestCoin')
        assert self.user.auth_token is not None
        assert self.user.check_password('123')  # current password

        resp_json = self._change_password(new_password='abc', new_password_confirm='cba').json()
        assert resp_json['status'] == 'failed'
        assert resp_json['code'] == 'InvalidPasswordConfirm'
        assert not self.user.is_restricted('WithdrawRequestCoin')
        assert self.user.auth_token is not None
        assert self.user.check_password('123')  # current password

    @patch('exchange.accounts.views.auth.validate_request_captcha')
    def test_restriction_on_forget_password(self, mock_captcha):
        mock_captcha.return_value = True
        self._forget_password()
        assert self.user.is_restricted('WithdrawRequestCoin')
        user_restriction = UserRestriction.objects.get(user=self.user,
                                                       restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin)
        user_restriction.considerations = 'ایجاد محدودیت 24 ساعته برداشت رمز ارز بعلت بازیابی رمز عبور'
        user_restriction_removal = UserRestrictionRemoval.objects.get(restriction=user_restriction, is_active=True)
        remove_date = now() + datetime.timedelta(days=1) - datetime.timedelta(minutes=1)
        assert user_restriction_removal.ends_at >= remove_date
        assert (
            user_restriction.description
            == 'به\u200cدلیل بازیابی رمز عبور، تا 24 ساعت نمی\u200cتوانید رمزارز برداشت کنید. این محدودیت خودکار رفع می\u200cشود و نیازی نیست با پشتیبانی نوبیتکس تماس بگیرید.'
        )

    def test_add_permanent_restriction_when_user_has_temporary_restriction(self):
        temporary_restriction = UserRestriction.add_restriction(
            self.user, 'WithdrawRequestCoin', 'تست', datetime.timedelta(days=3)
        )
        user_restriction_removal = UserRestrictionRemoval.objects.filter(
            restriction=temporary_restriction, is_active=True
        ).first()
        assert user_restriction_removal is not None
        permanent_restriction = UserRestriction.add_restriction(self.user, 'WithdrawRequestCoin', 'تست 2')
        restriction = UserRestriction.objects.filter(
            user=self.user, restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin
        )
        assert restriction.exists()
        assert not restriction.first().restriction_removals.filter(is_active=True).exists()

    def test_add_restriction_when_has_bigger_restriction(self):
        test_restriction_1 = UserRestriction.add_restriction(self.user,
                                                             'WithdrawRequestCoin',
                                                             'تست',
                                                             datetime.timedelta(hours=72))
        user_restriction_removal = UserRestrictionRemoval.objects.get(restriction=test_restriction_1, is_active=True)
        smaller_point_72 = now() + datetime.timedelta(hours=72) - datetime.timedelta(minutes=1)
        bigger_point_72 = now() + datetime.timedelta(hours=72) + datetime.timedelta(minutes=1)
        assert user_restriction_removal.ends_at >= smaller_point_72
        assert user_restriction_removal.ends_at <= bigger_point_72

        test_restriction_2 = UserRestriction.add_restriction(
            self.user, 'WithdrawRequestCoin', 'تست', datetime.timedelta(hours=40), DescriptionEnumForTest.test
        )
        user_restriction_removal = UserRestrictionRemoval.objects.get(restriction=test_restriction_2, is_active=True)
        # these assert prove that previous removal time remain
        assert user_restriction_removal.ends_at >= smaller_point_72
        assert user_restriction_removal.ends_at <= bigger_point_72
        assert test_restriction_2.description is None
        test_restriction_3 = UserRestriction.add_restriction(
            self.user, 'WithdrawRequestCoin', 'تست', datetime.timedelta(hours=80), DescriptionEnumForTest.test
        )
        user_restriction_removal = UserRestrictionRemoval.objects.get(restriction=test_restriction_3, is_active=True)
        smaller_point = now() + datetime.timedelta(hours=80) - datetime.timedelta(minutes=1)
        bigger_point = now() + datetime.timedelta(hours=80) + datetime.timedelta(minutes=1)
        # but these assert prove removal time is updated, because it's bigger
        assert user_restriction_removal.ends_at >= smaller_point
        assert user_restriction_removal.ends_at <= bigger_point
        assert test_restriction_3.description == 'تست توضیحات'

    def test_multiple_restrictions(self):
        UserRestriction.add_restriction(self.user, 'WithdrawRequestRial')
        UserRestriction.add_restriction(self.user, 'WithdrawRequestCoin', duration=datetime.timedelta(hours=72))
        assert UserRestriction.is_restricted(self.user, 'WithdrawRequest', 'WithdrawRequestCoin', 'WithdrawRequestRial')
        assert UserRestriction.is_restricted(self.user, 'Trading', 'WithdrawRequestRial')
        assert UserRestriction.is_restricted(self.user, 'WithdrawRequestCoin', UserRestriction.RESTRICTION.Trading)
        assert not UserRestriction.is_restricted(self.user, 'WithdrawRequest', 'Trading')

    @patch('exchange.accounts.views.auth.is_client_iranian')
    def test_iran_access_login_restriction(self, mock_is_client_iranian):
        self.user.set_password('123')
        self.user.save()
        UserRestriction.add_restriction(self.user, 'IranAccessLogin')

        mock_is_client_iranian.return_value = False
        response = self.client.post('/auth/login/', {
            'username': self.user.username,
            'password': '123'
        })
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == 'ActionIsRestricted'
        assert 'key' not in data
        assert response.status_code == 400

        mock_is_client_iranian.return_value = True
        response = self.client.post('/auth/login/', {
            'username': self.user.username,
            'password': '123'
        })
        data = response.json()
        assert data['status'] == 'success'
        assert 'key' in data
        assert response.status_code == 200

    @patch('exchange.accounts.views.auth.id_token.verify_oauth2_token', lambda *args: {
        'aud': settings.GOOGLE_CLIENT_IDS[0],
        'iss': 'accounts.google.com',
        'email_verified': True,
        'email': 'somefake@nobitex.fake',
        'given_name': 'fake name',
        'family_name': 'surname',
    })
    @patch('exchange.accounts.views.auth.is_client_iranian')
    def test_iran_access_social_login_restriction(self, mock_is_client_iranian: Mock):
        self.user.email = 'somefake@nobitex.fake'
        self.user.save()
        UserRestriction.add_restriction(self.user, 'IranAccessLogin')

        mock_is_client_iranian.return_value = True
        response = self.client.post('/auth/google/', {
            'token': 'token',
        })
        data = response.json()
        assert data['status'] == 'ok'
        assert 'key' in data
        assert response.status_code == 200

        mock_is_client_iranian.return_value = False
        response = self.client.post('/auth/google/', {
            'token': 'token',
        })
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == 'ActionIsRestricted'
        assert 'key' not in data
        assert response.status_code == 400


class FreezeUserTest(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)

    def test_add_restrictions(self):
        assert not UserRestriction.objects.filter(user=self.user).exists()
        UserRestriction.freeze_user(self.user.id)
        assert set(UserRestriction.objects.filter(
            user=self.user
        ).values_list('restriction', flat=True)) == UserRestriction.RESTRICTION._db_values

    def test_disable_existing_restriction_auto_remove(self):
        UserRestriction.add_restriction(self.user, 'WithdrawRequestCoin', duration=datetime.timedelta(hours=72))
        restriction__removal = UserRestrictionRemoval.objects.filter(
            restriction__restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin,
            is_active=True,
        )
        assert restriction__removal.exists()
        UserRestriction.freeze_user(self.user.id)
        assert not restriction__removal.exists()


class RestrictionsTestCase(APITestCase):
    URL = '/users/restrictions'

    def setUp(self):
        self.user = User.objects.get(pk=202)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

        self.restriction_1 = UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.WithdrawRequest,
            'ملاحظات',
            datetime.timedelta(hours=2),
            UserRestrictionsDescription.CHANGE_PASSWORD,
        )
        self.restriction_2 = UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.WithdrawRequest,
            'ملاحظات2',
            datetime.timedelta(hours=3),
            UserRestrictionsDescription.RECOVERY_PASSWORD,
        )
        self.extra_time = datetime.timedelta(minutes=RESTRICTION_REMOVAL_INTERVAL_MINUTES)

    def test_get_user_restrictions_successfully(self):
        response = self.client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output == {
            'restrictions': [
                {
                    'action': 'Withdraw',
                    'endsAt': serialize(self.restriction_2.restriction_removals.first().ends_at + self.extra_time),
                    'reason': self.restriction_2.description,
                }
            ],
            'status': 'ok',
        }

    def test_get_user_restrictions_without_description_successfully(self):
        restriction_2 = UserRestriction.add_restriction(
            self.user, UserRestriction.RESTRICTION.WithdrawRequestCoin, 'ملاحظات3', datetime.timedelta(hours=3)
        )
        UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.ShetabDeposit,
            'ملاحظات1',
            description='',
        )

        response = self.client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert len(output['restrictions']) == 3
        assert output == {
            'status': 'ok',
            'restrictions': [
                {'action': 'Shetab Deposit', 'reason': None, 'endsAt': None},
                {
                    'action': 'Withdraw Coin',
                    'reason': 'برداشت رمزارز شما محدود شده است. برای اطلاع بیشتر، لطفا با کارشناس پشتیبانی چت کنید.',
                    'endsAt': None,
                },
                {
                    'action': 'Withdraw',
                    'reason': self.restriction_2.description,
                    'endsAt': serialize(self.restriction_2.restriction_removals.first().ends_at + self.extra_time),
                },
            ],
        }

    def test_get_user_restrictions_with_several_restriction(self):
        UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.WithdrawRequestCoin,
            'ملاحظات بدون توضیحات',
        )
        restriction_3 = UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.ShetabDeposit,
            'ملاحظات باتوضیحات',
            datetime.timedelta(hours=4),
            description=UserRestrictionsDescription.ADD_ADDRESS_BOOK,
        )

        response = self.client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert len(output['restrictions']) == 3
        assert output == {
            'restrictions': [
                {
                    'action': 'Shetab Deposit',
                    'endsAt': serialize(restriction_3.restriction_removals.first().ends_at + self.extra_time),
                    'reason': 'به‌دلیل افزودن آدرس به دفتر آدرس‌ها، تا 4 ساعت نمی‌توانید رمزارز برداشت کنید. این محدودیت خودکار رفع می‌شود و نیازی نیست با پشتیبانی نوبیتکس تماس بگیرید.',
                },
                {
                    'action': 'Withdraw Coin',
                    'endsAt': None,
                    'reason': 'برداشت رمزارز شما محدود شده است. برای اطلاع بیشتر، لطفا با کارشناس پشتیبانی چت کنید.',
                },
                {
                    'action': 'Withdraw',
                    'endsAt': serialize(self.restriction_2.restriction_removals.first().ends_at + self.extra_time),
                    'reason': 'به‌دلیل بازیابی رمز عبور، تا 3 ساعت نمی‌توانید رمزارز برداشت کنید. این محدودیت خودکار رفع می‌شود و نیازی نیست با پشتیبانی نوبیتکس تماس بگیرید.',
                },
            ],
            'status': 'ok',
        }

    def test_get_user_restrictions_with_unauthenticated_user_fail(self):
        self.client.credentials(HTTP_AUTHORIZATION='')
        response = self.client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_user_restrictions_that_has_restriction_out_of_allowed_restriction_successfully(self):
        UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.Gateway,
            'ملاحظات',
            datetime.timedelta(hours=5),
            UserRestrictionsDescription.CHANGE_PASSWORD,
        )
        UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.Trading,
            'ملاحظات',
            datetime.timedelta(hours=5),
            UserRestrictionsDescription.CHANGE_PASSWORD,
        )
        UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.Position,
            'ملاحظات ',
            datetime.timedelta(hours=5),
            UserRestrictionsDescription.CHANGE_PASSWORD,
        )
        UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.Leverage,
            'ملاحظات ',
            datetime.timedelta(hours=5),
            UserRestrictionsDescription.CHANGE_PASSWORD,
        )
        UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.StakingParticipation,
            'ملاحظات ',
            datetime.timedelta(hours=5),
            UserRestrictionsDescription.CHANGE_PASSWORD,
        )
        UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.StakingRenewal,
            'ملاحظات ',
            datetime.timedelta(hours=5),
            UserRestrictionsDescription.CHANGE_PASSWORD,
        )
        UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.StakingCancellation,
            'ملاحظات ',
            datetime.timedelta(hours=5),
            UserRestrictionsDescription.CHANGE_PASSWORD,
        )

        response = self.client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output == {
            'restrictions': [
                {
                    'action': 'Withdraw',
                    'endsAt': serialize(self.restriction_2.restriction_removals.first().ends_at + self.extra_time),
                    'reason': self.restriction_2.description,
                }
            ],
            'status': 'ok',
        }

    def test_get_user_restrictions_by_other_user(self):
        user = User.objects.get(pk=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {user.auth_token.key}')

        response = self.client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()['restrictions']) == 0

    def test_get_user_restriction_with_inactive_removal(self):
        removal = self.restriction_2.restriction_removals.first()
        removal.is_active = False
        removal.save()
        response = self.client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output['restrictions'][0] == {
            'action': 'Withdraw',
            'endsAt': None,
            'reason': 'به\u200cدلیل بازیابی رمز عبور، تا 3 ساعت نمی\u200cتوانید رمزارز برداشت کنید. این محدودیت خودکار رفع می\u200cشود و نیازی نیست با پشتیبانی نوبیتکس تماس بگیرید.',
        }

    def test_get_user_withdraw_restrictions(self):
        UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.WithdrawRequestCoin,
            'ملاحظات ',
            datetime.timedelta(hours=4),
        )
        UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.WithdrawRequestRial,
            'ملاحظات ',
            datetime.timedelta(hours=5),
        )
        UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.WithdrawRequest,
            'ملاحظات ',
            datetime.timedelta(hours=6),
        )
        response = self.client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output == {
            'restrictions': [
                {
                    'action': 'Withdraw Rial',
                    'endsAt': None,
                    'reason': 'برداشت تومان شما محدود شده است. برای اطلاع بیشتر، لطفا با کارشناس پشتیبانی چت کنید.',
                },
                {
                    'action': 'Withdraw Coin',
                    'endsAt': None,
                    'reason': 'برداشت رمزارز شما محدود شده است. برای اطلاع بیشتر، لطفا با کارشناس پشتیبانی چت کنید.',
                },
                {
                    'action': 'Withdraw',
                    'endsAt': None,
                    'reason': 'برداشت تومان و رمزارز شما محدود شده است. برای اطلاع بیشتر، لطفا با کارشناس پشتیبانی چت کنید.',
                },
            ],
            'status': 'ok',
        }


class DescriptionEnumForTest(enum.Enum):
    test = 'تست توضیحات'
