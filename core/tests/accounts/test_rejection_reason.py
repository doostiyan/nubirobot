from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from exchange.accounts.models import (
    AdminConsideration,
    ChangeMobileRequest,
    UpgradeLevel3Request,
    User,
    VerificationRequest,
)
from exchange.accounts.user_levels_rejection_results import ReasonTypes, get_rejection_reasons
from exchange.base.calendar import ir_now
from tests.base.utils import check_nobitex_response, make_user_upgradable_to_level3, set_feature_status


def make_reject_reason(
    user: User,
    tp: int = VerificationRequest.TYPES.identity,
    consideration: str = 'test admin consideration',
):
    vr = VerificationRequest.objects.create(user=user, tp=tp, status=3, explanations='test')
    _content_type = ContentType.objects.get(model='verificationrequest')
    AdminConsideration.objects.create(
        content_type=_content_type,
        object_id=vr.id,
        is_important=False,
        user_id=user.id,
        admin_user_id=user.id,
        consideration='test',
        user_consideration=consideration,
    )


def make_user_level2(user):
    user.user_type = User.USER_TYPES.level2
    user.city = 'mashhad'
    user.address = 'pelak1'
    user.save()
    vp = user.get_verification_profile()
    vp.phone_confirmed = False
    vp.save()

    with patch('exchange.accounts.models.User.update_verification_status'):
        vp = user.get_verification_profile()
        vp.mobile_confirmed = vp.identity_confirmed = True
        vp.save()

    VerificationRequest.objects.create(
        user=user,
        tp=VerificationRequest.TYPES.selfie,
        status=VerificationRequest.STATUS.confirmed,
    )
    return user


class RejectionReasonTest(TestCase):
    fixtures = ['test_data']

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        set_feature_status('kyc2', True)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.url = '/users/upgrade/level3'

    def _send_upgrade_request(self):
        return self.client.post(self.url).json()

    def test_rejection_result_level2(self):
        self.user.user_type = User.USER_TYPES.level1
        self.user.city = 'mashhad'
        self.user.address = 'pelak1'
        self.user.save()
        vp = self.user.get_verification_profile()
        vp.phone_confirmed = False
        vp.save()

        # doesn't have verification request with type address
        reasons = get_rejection_reasons(self.user)
        assert reasons == []

        make_reject_reason(user=self.user, tp=VerificationRequest.TYPES.selfie)

        expected_reason1 = ReasonTypes.SELFIE_REJECTED.value
        expected_reason1.description = 'test admin consideration'
        reasons = get_rejection_reasons(self.user)
        assert reasons == [expected_reason1]

        self.user.address = ''
        self.user.save()
        expected_reason1 = ReasonTypes.SELFIE_REJECTED.value
        expected_reason1.description = 'test admin consideration'
        reasons = get_rejection_reasons(self.user)
        assert reasons == [expected_reason1]

        make_reject_reason(
            user=self.user,
            tp=VerificationRequest.TYPES.address,
            consideration='test admin consideration - address',
        )

        expected_reason2 = ReasonTypes.USER_ADDRESS_NOT_VALID.value
        expected_reason2.description = 'test admin consideration - address'
        reasons = get_rejection_reasons(self.user)
        assert reasons == [expected_reason1, expected_reason2]

    def test_rejection_result_level1(self):
        self.user.user_type = User.USER_TYPES.level0
        self.user.mobile = '09151234567'
        self.user.save()

        with patch('exchange.accounts.models.User.update_verification_status'):
            vp = self.user.get_verification_profile()
            vp.mobile_confirmed = vp.identity_confirmed = True
            vp.save()

        expected_reasons = []
        reasons = get_rejection_reasons(self.user)
        assert reasons == expected_reasons

        vp.identity_confirmed = False
        vp.save()
        make_reject_reason(user=self.user)

        expected_reason = ReasonTypes.IDENTITY_REJECTED.value
        expected_reason.description = 'test admin consideration'
        reasons = get_rejection_reasons(self.user)
        assert reasons == [expected_reason]

        self.user.mobile = ''
        self.user.save()
        ChangeMobileRequest.objects.create(user=self.user, old_mobile='09151234567', new_mobile='09151234567', status=4)
        expected_reason1 = ReasonTypes.IDENTITY_REJECTED.value
        expected_reason1.description = 'test'
        expected_reason2 = ReasonTypes.USER_NO_MOBILE.value
        reasons = get_rejection_reasons(self.user)
        assert reasons == [expected_reason2, expected_reason1]

    def test_rejection_result_level3_not_verified_level2(self):
        self.user = make_user_level2(self.user)

        make_user_upgradable_to_level3(user=self.user)

        r = self._send_upgrade_request()
        assert r['status'] == 'ok'

        expected_reasons = ['PendingToApproveRequest']
        reasons = get_rejection_reasons(self.user)
        assert reasons == expected_reasons

        _vr = VerificationRequest.objects.filter(
            user=self.user,
            tp=VerificationRequest.TYPES.selfie,
            status=VerificationRequest.STATUS.confirmed,
        ).first()
        _vr.status = VerificationRequest.STATUS.rejected
        _vr.save()

        _vp = self.user.get_verification_profile()
        _vp.selfie_confirmed = False
        _vp.save()
        UpgradeLevel3Request.objects.all().delete()

        r = self._send_upgrade_request()
        assert r['status'] == 'failed'

        expected_reasons = ['NotVerifiedLevel2']
        reasons = get_rejection_reasons(self.user)
        assert reasons == expected_reasons

    def test_rejection_result_level3_not_mobile_identity(self):
        self.user = make_user_level2(self.user)

        make_user_upgradable_to_level3(user=self.user)

        r = self._send_upgrade_request()
        assert r['status'] == 'ok'

        expected_reasons = ['PendingToApproveRequest']
        reasons = get_rejection_reasons(self.user)
        assert reasons == expected_reasons

        _vp = self.user.get_verification_profile()
        _vp.mobile_identity_confirmed = False
        _vp.save()
        UpgradeLevel3Request.objects.all().delete()

        r = self._send_upgrade_request()
        assert r['status'] == 'failed'

        expected_reasons = ['NotMobileIdentityConfirmed']
        reasons = get_rejection_reasons(self.user)
        assert reasons == expected_reasons

    def test_rejection_result_level3_min_days_not_passed(self):
        self.user = make_user_level2(self.user)

        make_user_upgradable_to_level3(user=self.user)

        r = self._send_upgrade_request()
        assert r['status'] == 'ok'

        expected_reasons = ['PendingToApproveRequest']
        reasons = get_rejection_reasons(self.user)
        assert reasons == expected_reasons

        _vr = VerificationRequest.objects.filter(
            user=self.user,
            tp=VerificationRequest.TYPES.auto_kyc,
            status=VerificationRequest.STATUS.confirmed,
        ).first()
        _vr.created_at = ir_now()
        _vr.save()
        UpgradeLevel3Request.objects.all().delete()

        r = self._send_upgrade_request()
        assert r['status'] == 'failed'

        expected_reasons = ['DaysLimitationViolated']
        reasons = get_rejection_reasons(self.user)
        assert reasons == expected_reasons


class RejectionReasonApiTest(APITestCase):
    fixtures = ['test_data']

    def _send_upgrade_request(self):
        return self.client.post(self.upgrade_url).json()

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        set_feature_status('kyc2', True)
        self.rejection_url = reverse('rejection_reason_url')
        self.upgrade_url = '/users/upgrade/level3'
        vp = self.user.get_verification_profile()
        vp.phone_confirmed = False
        vp.save()

    def test_rejection_result_fail(self):
        self.user.user_type = User.USER_TYPES.verified
        self.user.save()
        response = self.client.get(self.rejection_url)
        check_nobitex_response(response.json(), 'failed', 'InvalidUserType',
                               'User is not eligible to get rejection reason')

    def test_rejection_result_level2(self):
        self.user.user_type = User.USER_TYPES.level1
        self.user.city = 'mashhad'
        self.user.address = 'pelak1'
        self.user.save()

        # doesn't have verification request with type address
        expected_reasons = {
            'status': 'ok',
            'reasons': [],
        }
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

        make_reject_reason(user=self.user, tp=VerificationRequest.TYPES.selfie)

        expected_reasons = {
            'status': 'ok',
            'reasons': [
                {
                    'reason': 'SelfieRequestRejected',
                    'reasonFa': 'درخواست احراز هویت شما رد شده است.',
                    'description': 'test admin consideration',
                },
            ],
        }
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

        make_reject_reason(
            user=self.user,
            tp=VerificationRequest.TYPES.address,
            consideration='test admin consideration - address',
        )

        expected_reasons = {
            'status': 'ok',
            'reasons': [
                {
                    'reason': 'SelfieRequestRejected',
                    'reasonFa': 'درخواست احراز هویت شما رد شده است.',
                    'description': 'test admin consideration',
                },
                {
                    'reason': 'UserAddressIsNotValid',
                    'reasonFa': 'اطلاعات سکونتی کاربر تکمیل نیست.',
                    'description': 'test admin consideration - address',
                },
            ],
        }
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

    def test_rejection_result_level1(self):
        self.user.user_type = User.USER_TYPES.level0
        self.user.mobile = '09151234567'
        self.user.save()
        make_reject_reason(user=self.user)

        with patch('exchange.accounts.models.User.update_verification_status'):
            vp = self.user.get_verification_profile()
            vp.mobile_confirmed = vp.identity_confirmed = True
            vp.save()

        expected_reasons = {
            'status': 'ok',
            'reasons': [],
        }
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

        vp.identity_confirmed = False
        vp.save()
        expected_reasons = {
            'status': 'ok',
            'reasons': [
                {
                    'reason': 'IdentityRequestRejected',
                    'reasonFa': 'اطلاعات هویتی رد شده است.',
                    'description': 'test admin consideration',
                },
            ],
        }
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

        self.user.mobile = ''
        self.user.save()
        ChangeMobileRequest.objects.create(user=self.user, old_mobile='09151234567', new_mobile='09151234567', status=4)
        expected_reasons = {
            'status': 'ok',
            'reasons': [
                {
                    'reason': 'UserDoesNotHaveMobile',
                    'reasonFa': 'کاربر موبایل ندارد.',
                    'description': '',
                },
                {
                    'reason': 'IdentityRequestRejected',
                    'reasonFa': 'اطلاعات هویتی رد شده است.',
                    'description': 'test admin consideration',
                },
            ],
        }
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

    def test_rejection_result_level1_no_admin_consideration(self):
        self.user.user_type = User.USER_TYPES.level0
        self.user.mobile = '09151234567'
        self.user.save()
        make_reject_reason(user=self.user, consideration='')

        with patch('exchange.accounts.models.User.update_verification_status'):
            vp = self.user.get_verification_profile()
            vp.mobile_confirmed = vp.identity_confirmed = True
            vp.save()

        expected_reasons = {'status': 'ok', 'reasons': []}
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

        vp.identity_confirmed = False
        vp.save()
        expected_reasons = {
            'status': 'ok',
            'reasons': [
                {
                    'reason': 'IdentityRequestRejected',
                    'reasonFa': 'اطلاعات هویتی رد شده است.',
                    'description': '',
                },
            ],
        }
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

    def test_rejection_result_level3_not_verified_level2(self):
        self.user = make_user_level2(self.user)

        expected_reasons = {
            'status': 'ok',
            'reasons': ['Level3RequestNotFound'],
        }
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

        _vr = VerificationRequest.objects.filter(
            user=self.user,
            tp=VerificationRequest.TYPES.selfie,
            status=VerificationRequest.STATUS.confirmed,
        ).first()
        _vr.status = VerificationRequest.STATUS.rejected
        _vr.save()

        _vp = self.user.get_verification_profile()
        _vp.selfie_confirmed = False
        _vp.save()

        r = self._send_upgrade_request()
        assert r['status'] == 'failed'

        expected_reasons = {
            'status': 'ok',
            'reasons': ['NotVerifiedLevel2'],
        }
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

    def test_rejection_result_level3_not_mobile_identity(self):
        self.user = make_user_level2(self.user)
        make_user_upgradable_to_level3(user=self.user)

        expected_reasons = {
            'status': 'ok',
            'reasons': ['Level3RequestNotFound'],
        }
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

        _vp = self.user.get_verification_profile()
        _vp.mobile_identity_confirmed = False
        _vp.save()

        r = self._send_upgrade_request()
        assert r['status'] == 'failed'

        expected_reasons = {
            'status': 'ok',
            'reasons': ['NotMobileIdentityConfirmed'],
        }
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

    def test_rejection_result_level3_min_days_not_passed(self):
        self.user = make_user_level2(self.user)
        make_user_upgradable_to_level3(user=self.user)

        expected_reasons = {
            'status': 'ok',
            'reasons': ['Level3RequestNotFound'],
        }
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

        _vr = VerificationRequest.objects.filter(
            user=self.user,
            tp=VerificationRequest.TYPES.auto_kyc,
            status=VerificationRequest.STATUS.confirmed,
        ).first()
        _vr.created_at = ir_now()
        _vr.save()

        r = self._send_upgrade_request()
        assert r['status'] == 'failed'

        expected_reasons = {
            'status': 'ok',
            'reasons': ['DaysLimitationViolated'],
        }
        reasons = self.client.get(self.rejection_url)
        assert reasons.json() == expected_reasons

