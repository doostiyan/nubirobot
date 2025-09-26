import hashlib
import random
import string
import time
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.core.cache import cache
from django.test.testcases import TestCase

from exchange.accounts.models import User, UserOTP, UserSms
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.marketing.exceptions import (
    InvalidUserIDException,
    NoDiscountCodeIsAvailable,
    RewardHasBeenAlreadyAssigned,
)
from exchange.marketing.models import ExternalDiscount
from exchange.marketing.services.campaign.base import (
    CAMPAIGNS_SETTINGS_KEY,
    UserIdentifier,
    UserIdentifierType,
    UTMParameters,
)
from exchange.marketing.services.campaign.external_discount import ExternalDiscountCampaign
from exchange.marketing.services.mission.kyc_or_refer import KycOrReferMission, MissionTarget
from exchange.web_engage.models import WebEngageSMSLog


class TestExternalDiscountCampaign(TestCase):

    def setUp(self):
        mission = Mock()
        current_time = ir_now()

        self.campaign_id = 'sample_campaign_id'
        self.campaign = ExternalDiscountCampaign(self.campaign_id, mission)
        self.user = User.objects.get(pk=201)

        self.campaign_settings = {
            'start_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': (current_time + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'),
            'reward_sms_template': '{name} عزیز\nماموریت شما با موفقیت انجام شد.'
            '\nکد تخفیف ۴۰ هزار تومانی اسنپ : {discount_code}'
            '\nمهلت استفاده: ۲۰ بهمن'
            '\nنوبیتکس مورد اعتماد ۱۰ میلیون ایرانی',
        }
        Settings.set_dict(f'{CAMPAIGNS_SETTINGS_KEY}', {self.campaign_id: self.campaign_settings})

    def tearDown(self):
        ExternalDiscount.objects.all().delete()
        UserOTP.objects.all().delete()
        UserSms.objects.all().delete()
        Settings.set_dict(f'{CAMPAIGNS_SETTINGS_KEY}', {})

    def test_join_user_invalid_id_error(self):
        # given->
        user_identifier = UserIdentifier(type=UserIdentifierType.EMAIL, id='example@test.com')
        params = UTMParameters(utm_campaign='test_utm_campaign', utm_medium='web', utm_source='snapp')

        # when->
        with pytest.raises(InvalidUserIDException) as context:
            self.campaign.send_otp(user_identifier, utm_params=params)

        # then->
        assert str(context.value) == 'identifier with type=email is not supported for this campaign'

    def test_join_user_success(self):
        # given->
        user_identifier = UserIdentifier(type=UserIdentifierType.MOBILE, id='09123456789')
        params = UTMParameters(utm_campaign='test_utm_campaign', utm_medium='web', utm_source='snapp')

        # when->
        self.campaign.send_otp(user_identifier, utm_params=params)

        # then->
        otp = UserOTP.objects.filter(phone_number=user_identifier.id).first()
        assert otp

    def test_verify_new_user_success(self):
        # given->
        user_identifier = UserIdentifier(type=UserIdentifierType.MOBILE, id='09123456789')
        params = UTMParameters(utm_campaign='test_utm_campaign', utm_medium='web', utm_source='snapp')
        self.campaign.send_otp(user_identifier, utm_params=params)
        otp = UserOTP.objects.filter(phone_number=user_identifier.id).first()
        self.campaign.mission.initiate.return_value = {'status': 'mocked_status'}

        # when->
        result = self.campaign.verify_otp(user_identifier, otp.code, params)

        # then ->
        assert result.user_details.mobile_number == user_identifier.id
        assert result.campaign_details['status'] == 'mocked_status'

    def test_verify_known_user_success(self):
        # given->
        self.user.mobile = '09123456789'
        self.user.save(update_fields=['mobile'])
        user_identifier = UserIdentifier(type=UserIdentifierType.MOBILE, id=self.user.mobile)
        params = UTMParameters(utm_campaign='test_utm_campaign', utm_medium='web', utm_source='snapp')
        self.campaign.send_otp(user_identifier, utm_params=params)
        otp = UserOTP.objects.filter(phone_number=user_identifier.id).first()
        self.campaign.mission.initiate.return_value = {'status': 'mocked_status'}

        # when->
        result = self.campaign.verify_otp(user_identifier, otp.code, params)

        # then ->
        assert result.user_details.mobile_number == self.user.mobile
        assert result.user_details.user_id == self.user.id
        assert result.user_details.webengage_id == str(self.user.webengage_cuid)
        assert result.user_details.level == self.user.user_type
        assert result.campaign_details['status'] == 'mocked_status'

    def test_verify_user_is_won_success(self):
        # given->
        target_discount = self._create_external_discount()
        self.user.mobile = '09123456789'
        self.user.save(update_fields=['mobile'])
        user_identifier = UserIdentifier(type=UserIdentifierType.MOBILE, id=self.user.mobile)
        params = UTMParameters(utm_campaign='test_utm_campaign', utm_medium='web', utm_source='snapp')
        self.campaign.send_otp(user_identifier, utm_params=params)
        otp = UserOTP.objects.filter(phone_number=user_identifier.id).first()
        self.campaign.mission.initiate.return_value = {'status': 'mocked_status'}
        self.campaign.assign_discount(self.user)

        # when->
        result = self.campaign.verify_otp(user_identifier, otp.code, params)

        # then ->
        assert result.user_details.mobile_number == self.user.mobile
        assert result.user_details.user_id == self.user.id
        assert result.user_details.webengage_id == str(self.user.webengage_cuid)
        assert result.user_details.level == self.user.user_type
        assert result.campaign_details['status'] == 'REWARDED'
        assert result.campaign_details['reward_content'] == target_discount.code

    def _create_external_discount(self):
        return ExternalDiscount.objects.create(
            campaign_id=self.campaign_id,
            business_name='snapp',
            code=self._generate_discount_code(),
            enabled_at=ir_now(),
            description='sample description',
        )

    @staticmethod
    def _generate_discount_code():
        random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=3))
        raw_code = str(time.time()) + random_part
        hashed_code = hashlib.sha256(raw_code.encode()).hexdigest()
        referral_code = ''.join([char for char in hashed_code if char.isalnum()])[:7]
        return referral_code.upper()

    def test_send_reward_success(self):
        # given->
        target_discount = self._create_external_discount()
        user_identifier = UserIdentifier(type=UserIdentifierType.WEBENGAGE_USER_ID, id=self.user.webengage_cuid)

        # when->
        self.campaign.send_reward(user_identifier)

        # then->
        assigned_discount = ExternalDiscount.objects.filter(user=self.user).first()
        assert assigned_discount.pk == target_discount.pk
        assert assigned_discount.created_at
        assert assigned_discount.assigned_at

    def test_send_reward_when_no_reward_available_error(self):
        # given->
        user_identifier = UserIdentifier(type=UserIdentifierType.WEBENGAGE_USER_ID, id=self.user.webengage_cuid)

        # when->
        with pytest.raises(NoDiscountCodeIsAvailable) as context:
            self.campaign.send_reward(user_identifier)

        # then->
        assert context.value

    def test_send_reward_when_no_reward_is_enabled_error(self):
        # given->
        discount = self._create_external_discount()
        discount.enabled_at = ir_now() + timedelta(minutes=10)
        discount.save(update_fields=['enabled_at'])

        user_identifier = UserIdentifier(type=UserIdentifierType.WEBENGAGE_USER_ID, id=self.user.webengage_cuid)

        # when->
        with pytest.raises(NoDiscountCodeIsAvailable) as context:
            self.campaign.send_reward(user_identifier)

        # then->
        assert context.value

    def test_send_reward_when_user_has_already_rewarded_success_and_return_that_reward(self):
        # given->
        available_discount = self._create_external_discount()

        target_discount = self._create_external_discount()
        target_discount.user = self.user
        target_discount.assigned_at = ir_now()
        target_discount.save()
        user_identifier = UserIdentifier(type=UserIdentifierType.WEBENGAGE_USER_ID, id=self.user.webengage_cuid)

        # when->
        with pytest.raises(RewardHasBeenAlreadyAssigned) as context:
            self.campaign.send_reward(user_identifier)

        # then ->
        assert available_discount.user is None
        assert context.value

    def test_check_mission_is_completed_and_send_reward_success(self):
        # given->
        self.user.mobile = '09123456988'
        self.user.first_name = 'محمد'
        self.user.user_type = User.USER_TYPE_LEVEL1
        self.user.save(update_fields=['mobile', 'user_type'])

        self.campaign.mission = KycOrReferMission()
        campaign_id = 'sample_campaign_id'
        history = {
            'target': MissionTarget.KYC.value,
            'user_level': User.USER_TYPES.level0,
            'timestamp': ir_now(),
        }
        cache.set(
            self.campaign.mission._get_cache_key(campaign_id, '09123456988'),
            history,
            timeout=self.campaign.mission.validity_duration,
        )
        target_discount = self._create_external_discount()
        user_identifier = UserIdentifier(type=UserIdentifierType.WEBENGAGE_USER_ID, id=self.user.webengage_cuid)

        # when->
        self.campaign.send_reward(user_identifier)

        # then->
        assigned_discount = ExternalDiscount.objects.filter(user_id=self.user.id).first()
        assert assigned_discount.pk == target_discount.pk
        assert assigned_discount.created_at
        assert assigned_discount.assigned_at

        sms = WebEngageSMSLog.objects.filter(user=self.user).first()
        assert sms.phone_number == self.user.mobile

    def test_reward_capacity_success(self):
        # given->

        # first discount
        first_discount = self._create_external_discount()
        first_discount.user = self.user
        first_discount.assigned_at = ir_now()
        first_discount.save(update_fields=['user', 'assigned_at'])

        # second discount
        self._create_external_discount()

        # third discount
        self._create_external_discount()

        # forth discount
        forth_discount = self._create_external_discount()
        forth_discount.enabled_at = ir_now() + timedelta(minutes=5)
        forth_discount.save(update_fields=['enabled_at'])

        # when->
        result = self.campaign.get_capacity_details()

        # then->
        assert result['total'] == 4
        assert result['available'] == 2
        assert result['assigned'] == 1
