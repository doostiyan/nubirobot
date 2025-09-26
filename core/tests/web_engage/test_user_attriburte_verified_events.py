from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from exchange.accounts.models import ChangeMobileRequest, User, UserPlan, VerificationProfile, VerificationRequest
from exchange.base.models import Settings
from exchange.web_engage.events import Level2VerifiedWebEngageEvent
from tests.base.utils import TransactionTestFastFlushMixin, set_feature_status


class VerifyMobileEventTest(APITestCase):

    def setUp(self) -> None:
        self.user = get_user_model().objects.get(id=201)
        self.user.mobile = 93021225236
        self.user.save()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

    @patch('exchange.accounts.models.ChangeMobileRequest.do_verify')
    @patch('exchange.web_engage.events.user_attribute_verified_events.MobileVerifiedWebEngageEvent.send')
    def test_verify_registered_mobile_event_in_users_verify_mobile_api(self, event_mock,
                                                                       verify_mock):
        ChangeMobileRequest.objects.create(user=self.user, status=0, old_mobile=123, new_mobile=1234)
        event_mock.return_value = True
        verify_mock.return_value = ("ok", "ok")
        url = reverse("verify-mobile")
        response = self.client.get(path=url)
        assert response.status_code == 200
        assert event_mock.called

    @patch('exchange.accounts.models.User.do_verify_mobile')
    @patch('exchange.accounts.models.User.verify_otp')
    @patch('exchange.accounts.models.ChangeMobileRequest.do_verify')
    @patch('exchange.web_engage.events.user_attribute_verified_events.MobileVerifiedWebEngageEvent.send')
    def test_verify_modified_mobile_event_in_users_verify_mobile_api(self, event_mock,
                                                                     verify_mock, otp_mock, mobile_verify_mock):
        ChangeMobileRequest.objects.create(user=self.user, status=3, old_mobile=123, new_mobile=1234)
        event_mock.return_value = True
        otp_mock.return_value = True
        mobile_verify_mock.return_value = True
        verify_mock.return_value = ("ok", "ok")
        url = reverse("verify-mobile")
        response = self.client.get(path=url)
        assert response.status_code == 200
        assert event_mock.called


class Level1VerifiedWebEngageEventTest(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create(
            username='Level1VerifiedWebEngageEventTest@nobitex.ir',
            email='Level1VerifiedWebEngageEventTest@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )
        self.vp: VerificationProfile = self.user.get_verification_profile()
        self.vp.mobile_confirmed = True
        self.vp.save()
        self.user.user_type = User.USER_TYPES.level0
        self.user.save()

    @patch('exchange.web_engage.events.user_attribute_verified_events.Level1VerifiedWebEngageEvent.send')
    def test_called_level1_verified_event(self, verify_mock):
        if Settings.is_feature_active("kyc2"):
            assert self.user.user_type == User.USER_TYPES.level0
            vp: VerificationProfile = self.user.get_verification_profile()
            vp.identity_confirmed = True
            vp.save()
            verify_mock.return_value = True
            self.user.update_verification_status()
            assert verify_mock.called
        else:
            vp = self.user.get_verification_profile()
            vp.email_confirmed = True
            vp.mobile_confirmed = True
            vp.identity_confirmed = True
            vp.bank_account_confirmed = True

            verify_mock.return_value = True
            self.user.update_verification_status()
            assert verify_mock.called


class Level2VerifiedWebEngageEventTest(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        set_feature_status('kyc2', True)
        self.user = User.objects.create(
            username='Level2VerifiedWebEngageEventTest@nobitex.ir',
            email='Level2VerifiedWebEngageEventTest@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )
        self.vp = self.user.get_verification_profile()
        self.vp.mobile_confirmed = True
        self.vp.mobile_identity_confirmed = True
        self.vp.identity_confirmed = True
        self.vp.email_confirmed = True
        self.vp.phone_confirmed = True
        self.vp.address_confirmed = True
        self.vp.bank_account_confirmed = True
        self.vp.save()
        self.user.user_type = User.USER_TYPES.level1
        self.user.city = 'test'
        self.user.address = 'test'
        self.user.save()

    @patch('exchange.web_engage.events.user_attribute_verified_events.Level2VerifiedWebEngageEvent.send')
    def test_called_level2_verified_event(self, verify_mock):
        assert self.user.user_type == User.USER_TYPES.level1
        vr = VerificationRequest.objects.create(user=self.user, tp=3, explanations="test")  # confirmed
        vr.status = 2
        vr.save(update_fields=['status'])
        verify_mock.return_value = True
        self.user.update_verification_status()
        self.user.refresh_from_db()
        assert self.user.user_type == User.USER_TYPES.level2
        assert verify_mock.called

    @patch.object(Level2VerifiedWebEngageEvent, 'send')
    def test_not_called_level2_verified_event_for_trader(self, verify_mock):
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()
        assert self.user.user_type == User.USER_TYPES.level2
        assert verify_mock.call_count == 1

        plan = UserPlan(user=self.user, type=UserPlan.TYPE.trader)
        plan.activate()
        assert self.user.user_type == User.USER_TYPES.trader
        assert verify_mock.call_count == 1

        plan.deactivate()
        assert self.user.user_type == User.USER_TYPES.level2
        assert verify_mock.call_count == 1


class Level3VerifiedWebEngageEventTest(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        set_feature_status('kyc2', True)
        self.user = User.objects.create(
            username='Level3VerifiedWebEngageEventTest@nobitex.ir',
            email='Level3VerifiedWebEngageEventTest@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )
        self.vp: VerificationProfile = self.user.get_verification_profile()
        self.vp.mobile_confirmed = True
        self.vp.mobile_identity_confirmed = True
        self.vp.identity_confirmed = True
        self.vp.email_confirmed = True
        self.vp.phone_confirmed = True
        self.vp.bank_account_confirmed = True
        self.vp.selfie_confirmed = True
        self.vp.save()
        self.user.user_type = User.USER_TYPES.level2
        self.user.city = 'test'
        self.user.address = 'test'
        self.user.save()

    @patch('exchange.web_engage.events.user_attribute_verified_events.Level3VerifiedWebEngageEvent.send')
    def test_called_level3_verified_event(self, verify_mock):
        assert self.user.user_type == User.USER_TYPES.level2
        verify_mock.return_value = True
        self.user.user_type = User.USER_TYPES.verified
        self.user.save()
        assert self.user.user_type == User.USER_TYPES.verified
        assert verify_mock.called


class MobileEnteredWebEngageEventTest(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        set_feature_status('kyc2', True)
        self.user = User.objects.create(
            username='MobileEnteredWebEngageEventTest@nobitex.ir',
            email='MobileEnteredWebEngageEventTest@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )

    @patch('exchange.web_engage.events.user_attribute_verified_events.MobileEnteredWebEngageEvent.send')
    def test_called_mobile_entered_event(self, verify_mock):
        ChangeMobileRequest.create(self.user, '09151234567', ChangeMobileRequest.STATUS.new_mobile_otp_sent)
        verify_mock.return_value = True
        assert verify_mock.called


class IdentityConfirmedWebEngageEventTest(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        set_feature_status('kyc2', True)
        self.user = User.objects.create(
            username='IdentityConfirmedWebEngageEventTest@nobitex.ir',
            email='IdentityConfirmedWebEngageEventTest@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )

    @patch('exchange.web_engage.events.user_attribute_verified_events.IdentityConfirmedWebEngageEvent.send')
    def test_called_mobile_entered_event(self, verify_mock):
        vr = VerificationRequest.objects.create(user=self.user, tp=1, explanations="test")
        vr.status = 2
        vr.save(update_fields=['status'])
        verify_mock.return_value = True
        assert verify_mock.called


class SelfieConfirmedWebEngageEventTest(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        set_feature_status('kyc2', True)
        self.user = User.objects.create(
            username='SelfieConfirmedWebEngageEventTest@nobitex.ir',
            email='SelfieConfirmedWebEngageEventTest@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )

    @patch('exchange.web_engage.events.user_attribute_verified_events.SelfieConfirmedWebEngageEvent.send')
    def test_called_mobile_entered_event(self, verify_mock):
        vr = VerificationRequest.objects.create(user=self.user, tp=3, explanations="test")
        vr.status = 2
        vr.save(update_fields=['status'])
        verify_mock.return_value = True
        assert verify_mock.called


class AutoKycConfirmedWebEngageEventTest(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        set_feature_status('kyc2', True)
        self.user = User.objects.create(
            username='AutoKycConfirmedWebEngageEventTest@nobitex.ir',
            email='AutoKycConfirmedWebEngageEventTest@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )

    @patch('exchange.web_engage.events.user_attribute_verified_events.AutoKycConfirmedWebEngageEvent.send')
    def test_called_mobile_entered_event(self, verify_mock):
        vr = VerificationRequest.objects.create(user=self.user, tp=4, explanations="test")
        vr.status = 2
        vr.save(update_fields=['status'])
        verify_mock.return_value = True
        assert verify_mock.called


class SelfieStartedWebEngageEventTest(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        set_feature_status('kyc2', True)
        self.user = User.objects.create(
            username='SelfieStartedWebEngageEventTest@nobitex.ir',
            email='SelfieStartedWebEngageEventTest@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )

    @patch('exchange.web_engage.events.user_attribute_verified_events.SelfieStartedWebEngageEvent.send')
    def test_called_mobile_entered_event(self, verify_mock):
        vr = VerificationRequest(user=self.user, tp=3, explanations="test", device='mobile')
        vr.save()
        verify_mock.return_value = True
        assert verify_mock.called


class AutoKycStartedWebEngageEventTest(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        set_feature_status('kyc2', True)
        self.user = User.objects.create(
            username='AutoKycStartedWebEngageEventTest@nobitex.ir',
            email='AutoKycStartedWebEngageEventTest@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )

    @patch('exchange.web_engage.events.user_attribute_verified_events.AutoKycStartedWebEngageEvent.send')
    def test_called_mobile_entered_event(self, verify_mock):
        vr = VerificationRequest.objects.create(user=self.user, tp=4, explanations="test", device='mobile')
        vr.save()
        verify_mock.return_value = True
        assert verify_mock.called


class SelfieRejectedWebEngageEventTest(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        set_feature_status('kyc2', True)
        self.user = User.objects.create(
            username='SelfieRejectedWebEngageEventTest@nobitex.ir',
            email='SelfieRejectedWebEngageEventTest@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )

    @patch('exchange.web_engage.events.user_attribute_verified_events.SelfieRejectedWebEngageEvent.send')
    def test_called_mobile_entered_event(self, verify_mock):
        vr = VerificationRequest.objects.create(user=self.user, tp=3, explanations="test")
        vr.status = 3
        vr.save(update_fields=['status'])
        verify_mock.return_value = True
        assert verify_mock.called


class AutoKycRejectedWebEngageEventTest(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        set_feature_status('kyc2', True)
        self.user = User.objects.create(
            username='AutoKycRejectedWebEngageEventTest@nobitex.ir',
            email='AutoKycRejectedWebEngageEventTest@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )

    @patch('exchange.web_engage.events.user_attribute_verified_events.AutoKycRejectedWebEngageEvent.send')
    def test_called_mobile_entered_event(self, verify_mock):
        vr = VerificationRequest.objects.create(user=self.user, tp=4, explanations="test")
        vr.status = 3
        vr.save(update_fields=['status'])
        verify_mock.return_value = True
        assert verify_mock.called
