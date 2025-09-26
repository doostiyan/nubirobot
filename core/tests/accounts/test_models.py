from typing import List
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase, override_settings

from exchange.accounts.kyc_param_notifier import KYCParam
from exchange.accounts.kyc_param_notifier.enums import KYCParamNotifyType
from exchange.accounts.kyc_param_notifier.policy import NotifierInterface
from exchange.accounts.models import BankAccount, BankCard, Notification, User, VerificationRequest
from exchange.base.models import Settings
from exchange.wallet.models import Wallet
from tests.base.utils import mock_on_commit, set_feature_status


class MockEmail:
    all_mock_emails: List['MockEmail'] = []

    def __new__(cls, *args, **kwargs):
        mock_email = super().__new__(cls)
        cls.all_mock_emails.append(mock_email)
        return mock_email

    def __init__(self, email, template, data=None, backend=None, scheduled_time=None, priority=None):
        self.email = email
        self.template = template
        self.data = data
        self.backend = backend
        self.scheduled_time = scheduled_time
        self.priority = priority

    @classmethod
    def get_mock_send_email(cls):
        def mock_send_email(*args, **kwargs):
            return cls(*args, **kwargs)

        return mock_send_email

    @classmethod
    def flush(cls):
        cls.all_mock_emails.clear()


class ModelsTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=202)
        self.first_name, self.last_name = self.user.first_name, self.user.last_name

    def set_or_reset_name(self, reset: bool):
        first, last = (self.first_name, self.last_name) if not reset else ('', '')
        User.objects.filter(id=self.user.id).update(first_name=first, last_name=last)
        self.user.refresh_from_db()

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_verification_profile(self, send_email, _):
        MockEmail.flush()
        send_email.side_effect = MockEmail.get_mock_send_email()

        vp = self.user.get_verification_profile()

        assert not vp.is_verified_level0
        self.user.do_verify_email()
        assert vp.is_verified_level0
        assert len(MockEmail.all_mock_emails) == 0

        assert not vp.is_verified_level1
        Wallet.create_user_wallets(self.user)
        self.card = BankCard.objects.create(
            user=self.user,
            card_number='1234123412341234',
            owner_name=self.user.get_full_name(),
            bank_id=10,
            confirmed=True,
            status=BankCard.STATUS.confirmed,
        )

        bank = BankAccount.BANK_ID.melli
        self.bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='78' * 6,
            shaba_number=f'IR000{bank:2<19}',
            owner_name=self.user.get_full_name(),
            bank_name=BankAccount.BANK_ID[bank],
            bank_id=bank,
            confirmed=True,
            status=BankAccount.STATUS.confirmed,
        )

        self.user.mobile = '09151234567'
        self.user.do_verify_mobile()
        assert KYCParam.MOBILE.value in ''.join(
            email.data['message']
            for email in MockEmail.all_mock_emails
        )

        vp.identity_confirmed = True
        vp.save()
        assert vp.is_verified_level1
        assert KYCParam.IDENTITY.value in Notification.objects.filter(user=self.user).last().message
        assert KYCParam.IDENTITY.value in MockEmail.all_mock_emails[-1].data['message']

        assert not vp.is_verified_level2
        set_feature_status('kyc2', False)
        self.user.city = 'مشهد'
        self.user.address = 'خیابان اول میلان سوم'
        self.user.national_code = '0921234567'
        self.user.save()
        self.user.update_mobile_identity_status()

        # phone confirm
        self.user.do_verify_address()

        assert KYCParam.ADDRESS.value in Notification.objects.filter(user=self.user).last().message
        assert KYCParam.ADDRESS.value in MockEmail.all_mock_emails[-1].data['message']

        # selfie confirm
        vr = VerificationRequest.objects.create(
            tp=VerificationRequest.TYPES.selfie,
            user=self.user,
            status=VerificationRequest.STATUS.confirmed
        )
        vr.update_user_verification()
        assert KYCParam.SELFIE.value in Notification.objects.filter(user=self.user).last().message
        assert KYCParam.SELFIE.value in MockEmail.all_mock_emails[-1].data['message']
        assert not vp.is_verified_level2

        set_feature_status('kyc2', True)
        assert vp.is_verified_level2

        set_feature_status('kyc2', False)
        self.user.phone = '38123456'
        self.user.save()

        assert vp.is_verified_level2

        vp.selfie_confirmed = False
        assert not vp.is_verified_level2

        # liveness confirm
        vr = VerificationRequest.objects.create(
            tp=VerificationRequest.TYPES.auto_kyc,
            user=self.user,
            status=VerificationRequest.STATUS.confirmed
        )
        self.user.do_verify_liveness_alpha()
        assert KYCParam.AUTO_KYC.value in Notification.objects.filter(user=self.user).last().message
        assert KYCParam.AUTO_KYC.value in MockEmail.all_mock_emails[-1].data['message']
        assert vp.is_verified_level2

        assert not vp.is_verified_level3

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_verification_request_fails(self, send_email, _):
        MockEmail.flush()
        send_email.side_effect = MockEmail.get_mock_send_email()

        vp = self.user.get_verification_profile()
        self.user.do_verify_email()
        Wallet.create_user_wallets(self.user)
        self.card = BankCard.objects.create(
            user=self.user,
            card_number='1234123412341234',
            owner_name=self.user.get_full_name(),
            bank_id=10,
            confirmed=True,
            status=BankCard.STATUS.confirmed,
        )
        bank = BankAccount.BANK_ID.melli
        self.bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='78' * 6,
            shaba_number=f'IR000{bank:2<19}',
            owner_name=self.user.get_full_name(),
            bank_name=BankAccount.BANK_ID[bank],
            bank_id=bank,
            confirmed=True,
            status=BankAccount.STATUS.confirmed,
        )
        vr = VerificationRequest.objects.create(
            tp=VerificationRequest.TYPES.selfie,
            user=self.user,
            status=VerificationRequest.STATUS.new
        )
        self.set_or_reset_name(reset=True)
        vr.status = VerificationRequest.STATUS.rejected
        vr.save()
        assert KYCParam.SELFIE.value in Notification.objects.filter(user=self.user).last().message
        assert 'کاربر گرامی' in Notification.objects.filter(user=self.user).last().message
        assert KYCParam.SELFIE.value in MockEmail.all_mock_emails[-1].data['message']
        assert 'کاربر گرامی' in MockEmail.all_mock_emails[-1].data['message']

        vr = VerificationRequest.objects.create(
            tp=VerificationRequest.TYPES.auto_kyc,
            user=self.user,
            status=VerificationRequest.STATUS.new
        )
        self.set_or_reset_name(reset=False)
        vr.status = VerificationRequest.STATUS.rejected
        vr.save()
        assert KYCParam.AUTO_KYC.value in Notification.objects.filter(user=self.user).last().message
        assert '{} عزیز'.format(self.user.get_full_name()) in Notification.objects.filter(user=self.user).last().message
        assert KYCParam.AUTO_KYC.value in MockEmail.all_mock_emails[-1].data['message']
        assert '{} عزیز'.format(self.user.get_full_name()) in MockEmail.all_mock_emails[-1].data['message']

    @pytest.mark.slow
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_send_email_on_something_accepted(self, _):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')

        NotifierInterface.configure_notifier(
            KYCParamNotifyType.EMAIL, KYCParam.IDENTITY, None, self.user, True
        ).notify_user()
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    @pytest.mark.slow
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_send_email_on_something_rejected(self, _):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')

        NotifierInterface.configure_notifier(
            KYCParamNotifyType.EMAIL, KYCParam.MOBILE_IDENTITY, None, self.user, False
        ).notify_user()

        with patch('django.db.connection.close'):
            call_command('send_queued_mail')
