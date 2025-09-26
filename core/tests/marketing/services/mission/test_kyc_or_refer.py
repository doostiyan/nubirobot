from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from exchange.accounts.models import ReferralProgram, User, UserReferral
from exchange.marketing.services.mission.kyc_or_refer import KycOrReferMission, MissionProgressStatus, MissionTarget
from exchange.marketing.types import UserInfo


class TestKycOrReferCampaignMission(TestCase):

    def setUp(self):
        self.mission = KycOrReferMission()
        self.user = User.objects.get(pk=201)

        self.referee_kyc_level_1 = User.objects.get(pk=202)
        self.referee_kyc_level_1.user_type = User.USER_TYPES.level1
        self.referee_kyc_level_1.save(update_fields=('user_type',))

    def tearDown(self):
        ReferralProgram.objects.all().delete()
        UserReferral.objects.all().delete()

    def test_initiate_when_user_is_not_registered_then_mission_is_register_and_kyc_and_success(self):
        # given ->
        campaign_id = 'sample_campaign_id'
        user_info = UserInfo(mobile_number='09123456987')

        # when->
        details = self.mission.initiate(user_info, campaign_id)

        # then->
        cache_key = self.mission._get_cache_key(campaign_id, user_info.mobile_number)
        assert details['status'] == MissionProgressStatus.NEEDS_KYC.value
        state_data = cache.get(cache_key)
        assert state_data
        assert state_data['target'] == MissionTarget.KYC.value
        assert state_data['user_level'] == -1
        assert state_data['timestamp']
        cache.delete(cache_key)

    def test_initiate__when_user_is_level_0_then_mission_is_kyc_and_success(self):
        # given ->
        campaign_id = "sample_campaign_id"
        user_info = UserInfo(mobile_number='09123456987', user_id=self.user.id, level=User.USER_TYPES.level0)

        # when->
        details = self.mission.initiate(user_info, campaign_id)

        # then->
        cache_key = self.mission._get_cache_key(campaign_id, user_info.mobile_number)
        assert details['status'] == MissionProgressStatus.NEEDS_KYC.value
        state_data = cache.get(cache_key)
        assert state_data
        assert state_data['target'] == MissionTarget.KYC.value
        assert state_data['user_level'] == User.USER_TYPES.level0
        assert state_data['timestamp']
        cache.delete(cache_key)

    def test_initiate_when_user_is_level1_without_referral_code_then_a_referral_code_is_generated_and_success(self):
        # given ->
        campaign_id = "sample_campaign_id"
        user_info = UserInfo(mobile_number='09123456988', user_id=self.user.id, level=User.USER_TYPES.level1)

        # when->
        details = self.mission.initiate(user_info, campaign_id)

        # then->
        cache_key = self.mission._get_cache_key(campaign_id, user_info.mobile_number)
        assert details['status'] == MissionProgressStatus.NEEDS_REFER_A_USER.value
        assert details['referral_code']

        state_data = cache.get(cache_key)
        assert state_data
        assert state_data['target'] == MissionTarget.USER_REFER.value
        assert state_data['timestamp']
        cache.delete(cache_key)

        program = ReferralProgram.objects.filter(referral_code=details['referral_code']).first()
        assert program
        assert program.created_at
        assert program.agenda == program.AGENDA.default
        assert program.user_share == 30
        assert program.friend_share == 0
        assert program.description == self.mission._get_campaign_tag(campaign_id)

    def test_initiate_when_record_has_already_been_created_then_return_the_record_and_success(self):
        # given ->
        campaign_id = "sample_campaign_id"
        timestamp = timezone.now()
        user_info = UserInfo(mobile_number='09123456988', user_id=self.user.id, level=self.user.user_type)
        history = {'target': MissionTarget.KYC.value, 'user_level': self.user.user_type, 'timestamp': timestamp}
        cache.set(
            self.mission._get_cache_key(campaign_id, user_info.mobile_number),
            history,
            timeout=self.mission.validity_duration,
        )

        # when->
        details = self.mission.initiate(user_info, campaign_id)

        # then->
        cache_key = self.mission._get_cache_key(campaign_id, user_info.mobile_number)
        assert details['status'] == MissionProgressStatus.NEEDS_KYC.value

        state_data = cache.get(cache_key)
        assert state_data
        assert state_data['target'] == MissionTarget.KYC.value
        assert state_data['user_level'] == self.user.user_type
        assert state_data['timestamp'] == timestamp
        cache.delete(cache_key)

    def test_get_progress_details_when_mission_is_kyc_and_user_does_it_returns_done_status_and_success(self):
        # given ->
        campaign_id = "sample_campaign_id"
        history = {'target': MissionTarget.KYC.value, 'user_level': User.USER_TYPES.level0, 'timestamp': timezone.now()}
        cache.set(
            self.mission._get_cache_key(campaign_id, '09123456988'), history, timeout=self.mission.validity_duration
        )

        # when->
        user_info = UserInfo(mobile_number='09123456988', user_id=self.user.id, level=User.USER_TYPES.level1)
        details = self.mission.get_progress_details(user_info, campaign_id)

        # then->
        assert details['status'] == MissionProgressStatus.DONE.value
        cache.delete(self.mission._get_cache_key(campaign_id, user_info.mobile_number))

    def test_get_progress_details_when_mission_is_refer_a_user_and_user_does_it_returns_done_status_and_success(self):
        # given ->
        campaign_id = "sample_campaign_id"
        user_info = UserInfo(mobile_number='09123456983', user_id=self.user.id, level=User.USER_TYPES.level1)
        history = {
            'target': MissionTarget.USER_REFER.value,
            'user_level': self.user.user_type,
            'timestamp': timezone.now(),
        }
        cache.set(
            self.mission._get_cache_key(campaign_id, user_info.mobile_number),
            history,
            timeout=self.mission.validity_duration,
        )
        user_rp, _ = ReferralProgram.create(self.user, 10, agenda=ReferralProgram.AGENDA.default)
        campaign_rp, _ = ReferralProgram.create(
            self.user,
            0,
            agenda=ReferralProgram.AGENDA.default,
            description=self.mission._get_campaign_tag(campaign_id),
        )

        # when->
        UserReferral.set_user_referrer(self.referee_kyc_level_1, user_rp.referral_code)
        details = self.mission.get_progress_details(user_info, campaign_id)

        # then->
        assert details['status'] == MissionProgressStatus.DONE.value
        assert details['referral_code'] == campaign_rp.referral_code
        cache.delete(self.mission._get_cache_key(campaign_id, user_info.mobile_number))
