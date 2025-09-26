from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import override_settings

from exchange.accounts.models import BankCard, UpgradeLevel3Request, User, VerificationRequest
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.wallet.models import BankDeposit, Transaction, Wallet, WithdrawRequest
from tests.base.utils import check_nobitex_response, make_user_upgradable_to_level3, set_feature_status


class UpgradeLevel3Test(TestCase):

    def _create_test_data(self) -> None:
        self.user.date_joined = ir_now() - timezone.timedelta(days=60)
        self.user.user_type = User.USER_TYPES.level2
        Wallet.create_user_wallets(self.user)
        self.card = BankCard.objects.create(
            user=self.user,
            card_number='1234123412341234',
            owner_name=self.user.get_full_name(),
            bank_id=10,
            confirmed=True,
            status=BankCard.STATUS.confirmed,
        )

        self.user.city = 'test'
        self.user.address = 'test'
        self.user.phone = '0512345678'
        self.user.mobile = '09151234567'

        vp = self.user.get_verification_profile()
        vp.identity_confirmed = True
        vp.selfie_confirmed = True
        vp.phone_confirmed = True
        vp.address_confirmed = True
        vp.email_confirmed = True
        vp.mobile_confirmed = True
        vp.mobile_identity_confirmed = True
        vp.bank_account_confirmed = True

        self.user.save()
        vp.save()
        assert self.user.user_type == User.USER_TYPES.level2
        assert vp.is_verified_level2

    def _send_upgrade_request(self):
        return self.client.post(self.url).json()

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.get(pk=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.url = '/users/upgrade/level3'
        self._create_test_data()
        set_feature_status('kyc2', True)

    def tearDown(self) -> None:
        super().tearDown()
        BankDeposit.objects.all().delete()
        Transaction.objects.all().delete()
        WithdrawRequest.objects.all().delete()
        VerificationRequest.objects.all().delete()

    def test_user_already_verified(self):
        self.user.user_type = User.USER_TYPES.verified
        self.user.save()
        r = self._send_upgrade_request()
        check_nobitex_response(r, 'failed', 'UserAlreadyVerified', 'User already is upgraded to level3')

    def test_user_not_level2(self):
        self._create_test_data()
        self.user.user_type = User.USER_TYPES.level1
        self.user.save()
        r = self._send_upgrade_request()
        check_nobitex_response(r, 'failed', 'NotVerifiedLevel2', 'User is not eligible to upgrade level3')

        _request = UpgradeLevel3Request.objects.filter(
            user=self.user,
            status=UpgradeLevel3Request.STATUS.rejected,
        ).first()
        assert _request.status == UpgradeLevel3Request.STATUS.rejected
        assert _request.closed_at
        assert _request.reject_reason == 'NotVerifiedLevel2'

    def test_kyc_feature_disabled(self):
        set_feature_status('kyc2', False)
        self._create_test_data()
        make_user_upgradable_to_level3(user=self.user)
        r = self._send_upgrade_request()
        check_nobitex_response(r, 'failed', 'KYC2Disabled', 'User is not eligible to upgrade level3')

        _request = UpgradeLevel3Request.objects.filter(
            user=self.user,
            status=UpgradeLevel3Request.STATUS.rejected,
        ).first()
        assert _request.status == UpgradeLevel3Request.STATUS.rejected
        assert _request.closed_at
        assert _request.reject_reason == 'KYC2Disabled'

    def test_user_not_verified_level2(self):
        self._create_test_data()
        make_user_upgradable_to_level3(user=self.user)
        vp = self.user.get_verification_profile()
        vp.identity_confirmed = False
        vp.save()
        r = self._send_upgrade_request()
        check_nobitex_response(r, 'failed', 'NotVerifiedLevel2', 'User is not eligible to upgrade level3')

        _request = UpgradeLevel3Request.objects.filter(
            user=self.user,
            status=UpgradeLevel3Request.STATUS.rejected,
        ).first()
        assert _request.status == UpgradeLevel3Request.STATUS.rejected
        assert _request.closed_at
        assert _request.reject_reason == 'NotVerifiedLevel2'

    def test_user_mobile_identity_not_confirmed(self):
        self._create_test_data()
        make_user_upgradable_to_level3(user=self.user, mobile_identity=False)
        r = self._send_upgrade_request()
        check_nobitex_response(r, 'failed', 'NotMobileIdentityConfirmed', 'User is not eligible to upgrade level3')

        _request = UpgradeLevel3Request.objects.filter(
            user=self.user,
            status=UpgradeLevel3Request.STATUS.rejected,
        ).first()
        assert _request.status == UpgradeLevel3Request.STATUS.rejected
        assert _request.closed_at
        assert _request.reject_reason == 'NotMobileIdentityConfirmed'

    def test_user_days_limitation_violated(self):
        self._create_test_data()
        make_user_upgradable_to_level3(user=self.user, use_day_limitation=False)
        r = self._send_upgrade_request()
        check_nobitex_response(r, 'failed', 'DaysLimitationViolated', 'User is not eligible to upgrade level3')

        _request = UpgradeLevel3Request.objects.filter(
            user=self.user,
            status=UpgradeLevel3Request.STATUS.rejected,
        ).first()
        assert _request.status == UpgradeLevel3Request.STATUS.rejected
        assert _request.closed_at
        assert _request.reject_reason == 'DaysLimitationViolated'

    def test_user_trades_less_than_limitation(self):
        self._create_test_data()
        make_user_upgradable_to_level3(user=self.user, add_trades=False)
        r = self._send_upgrade_request()
        check_nobitex_response(r, 'failed', 'InsufficientTrades', 'User is not eligible to upgrade level3')

        _request = UpgradeLevel3Request.objects.filter(
            user=self.user,
            status=UpgradeLevel3Request.STATUS.rejected,
        ).first()
        assert _request.status == UpgradeLevel3Request.STATUS.rejected
        assert _request.closed_at
        assert _request.reject_reason == 'InsufficientTrades'

    def test_upgrade_level3_api(self):
        self._create_test_data()
        make_user_upgradable_to_level3(self.user)

        r = self._send_upgrade_request()
        assert r['status'] == 'ok'

        _request = UpgradeLevel3Request.get_active_request(self.user)
        assert _request
        assert not _request.closed_at

        _request.approve()
        assert _request.status == UpgradeLevel3Request.STATUS.approved
        assert _request.closed_at

        self.user.refresh_from_db()
        assert self.user.user_type == User.USER_TYPES.verified

    def test_upgrade_level3_api_duplicate_request_today_limit_reached(self):
        self._create_test_data()
        make_user_upgradable_to_level3(self.user)

        r = self._send_upgrade_request()
        assert r['status'] == 'ok'

        _request = UpgradeLevel3Request.get_active_request(self.user)
        assert _request
        assert not _request.closed_at

        r2 = self._send_upgrade_request()
        expected_result = {
            'status': 'failed',
            'code': 'UpgradeLimitExceededError',
            'message': 'Upgrade request limit exceeded',
        }
        assert r2 == expected_result

    def test_upgrade_level3_api_duplicate_request(self):
        self._create_test_data()
        make_user_upgradable_to_level3(self.user)

        r = self._send_upgrade_request()
        assert r['status'] == 'ok'

        _yesterday = ir_now() - timedelta(days=1)
        _request = UpgradeLevel3Request.get_active_request(self.user)
        assert _request
        _request.created_at = _yesterday
        _request.save()

        r2 = self._send_upgrade_request()
        expected_result = {
            'status': 'failed',
            'code': 'DuplicateRequestError',
            'message': 'Another active request already exist!',
        }
        assert r2 == expected_result

    def test_upgrade_level3_get_active_request(self):
        self._create_test_data()
        make_user_upgradable_to_level3(self.user)

        r = self._send_upgrade_request()
        assert r['status'] == 'ok'

        _request = UpgradeLevel3Request.get_active_request(self.user)
        assert _request
        assert not _request.closed_at

        _request.approve()
        assert _request.status == UpgradeLevel3Request.STATUS.approved
        assert _request.closed_at

        _request = UpgradeLevel3Request.get_active_request(self.user)
        assert not _request

    @pytest.mark.slow()
    @override_settings(IS_PROD=True)
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @override_settings(POST_OFFICE={'BACKENDS': {'critical': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_upgrade_level3_api_confirm_notif(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')

        self._create_test_data()

        assert self.user.user_type == User.USER_TYPES.level2

        _request = UpgradeLevel3Request.objects.create(
            user=self.user, status=UpgradeLevel3Request.STATUS.pre_conditions_approved
        )

        _request.approve()
        assert _request.status == UpgradeLevel3Request.STATUS.approved
        assert _request.closed_at

        self.user.refresh_from_db()
        assert self.user.user_type == User.USER_TYPES.verified

        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    @pytest.mark.slow()
    @override_settings(IS_PROD=True)
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @override_settings(POST_OFFICE={'BACKENDS': {'critical': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_upgrade_level3_api_reject_notif(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')

        self._create_test_data()

        _request = UpgradeLevel3Request.objects.create(
            user=self.user, status=UpgradeLevel3Request.STATUS.pre_conditions_approved
        )

        _request.reject('کافی نبودن واریز')
        assert _request.status == UpgradeLevel3Request.STATUS.rejected
        assert _request.closed_at

        self.user.refresh_from_db()
        assert self.user.user_type == User.USER_TYPES.level2

        with patch('django.db.connection.close'):
            call_command('send_queued_mail')
