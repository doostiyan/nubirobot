import re
from datetime import datetime

from rest_framework.test import APITestCase

from exchange.accounts.models import ReferralProgram, User, UserReferral
from exchange.base.calendar import parse_shamsi_date
from exchange.base.models import Settings
from tests.base.utils import check_response


class TestReferralCampaignAPITests(APITestCase):

    def setUp(self) -> None:
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        self.user3 = User.objects.get(pk=203)
        self.user1.user_type = User.USER_TYPES.level1
        self.user2.user_type = User.USER_TYPES.level1
        self.user3.user_type = User.USER_TYPES.level1
        self.user1.save()
        self.user2.save()
        self.user3.save()
        self.url = '/marketing/campaign/referral'
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        Settings.set_cached_json(
            'referral_campaign_special_dates',
            {
                '1402-08-01': 2,
                '1402-08-03': 3,
                '1402-08-05': 4,
                '1402-08-07': 2,
            },
        )
        Settings.set('referral_campaign_start_date', '1402-08-01')
        Settings.set('referral_campaign_end_date', '1402-08-20')
        ref_code, _ = ReferralProgram.create(self.user1, 0)
        self.referral_code = ref_code.referral_code

    def _get_referral_info(self):
        return self.client.get(self.url)

    def _set_referral(self, new_user: User, date: datetime):
        assert UserReferral.set_user_referrer(new_user, self.referral_code)
        user_referral = UserReferral.objects.get(child=new_user, parent=self.user1)
        user_referral.created_at = date
        user_referral.save()

    def test_not_started_campaign(self):
        Settings.set('referral_campaign_start_date', '')
        Settings.set('referral_campaign_end_date', '')
        result = self._get_referral_info()
        check_response(result, 422, 'failed', 'ValidationError', 'Date range of the campaign is not defined')

    def test_no_referral(self):
        result = self._get_referral_info()
        check_response(result, 200, 'ok', special_key='totalBonus', special_value=0)

    def test_referral_out_of_campaign_date(self):
        result = self._get_referral_info()
        check_response(result, 200, 'ok', special_key='totalBonus', special_value=0)

        self._set_referral(self.user2, parse_shamsi_date('1402-07-30'))
        assert UserReferral.objects.all().count() == 1

        result = self._get_referral_info()
        check_response(result, 200, 'ok', special_key='totalBonus', special_value=0)

    def test_referral_normal_date(self):
        result = self._get_referral_info()
        check_response(result, 200, 'ok', special_key='totalBonus', special_value=0)

        self._set_referral(self.user2, parse_shamsi_date('1402-08-02'))
        assert UserReferral.objects.all().count() == 1

        result = self._get_referral_info()
        check_response(result, 200, 'ok', special_key='totalBonus', special_value=1)

    def test_referral_bad_ratio(self):
        result = self._get_referral_info()
        check_response(result, 200, 'ok', special_key='totalBonus', special_value=0)

        self._set_referral(self.user2, parse_shamsi_date('1402-08-05'))
        assert UserReferral.objects.all().count() == 1

        result = self._get_referral_info()
        check_response(result, 200, 'ok', special_key='totalBonus', special_value=1)

    def test_referral_special_date(self):
        result = self._get_referral_info()
        check_response(result, 200, 'ok', special_key='totalBonus', special_value=0)

        self._set_referral(self.user2, parse_shamsi_date('1402-08-01'))
        assert UserReferral.objects.all().count() == 1

        result = self._get_referral_info()
        check_response(result, 200, 'ok', special_key='totalBonus', special_value=2)

        self._set_referral(self.user3, parse_shamsi_date('1402-08-03'))
        assert UserReferral.objects.all().count() == 2

        result = self._get_referral_info()
        check_response(result, 200, 'ok', special_key='totalBonus', special_value=5)

    def test_referral_complex_type(self):
        result = self._get_referral_info()
        check_response(result, 200, 'ok', special_key='totalBonus', special_value=0)

        # special date
        self._set_referral(self.user2, parse_shamsi_date('1402-08-01'))
        assert UserReferral.objects.all().count() == 1

        result = self._get_referral_info()
        check_response(result, 200, 'ok', special_key='totalBonus', special_value=2)

        # normal date
        self._set_referral(self.user3, parse_shamsi_date('1402-08-02'))
        assert UserReferral.objects.all().count() == 2

        result = self._get_referral_info()
        check_response(result, 200, 'ok', special_key='totalBonus', special_value=3)

    def test_generate_referral_code_in_alphanumeric_success(self):
        referral_code = ReferralProgram._generate_referral_code()
        assert bool(re.fullmatch(r'[A-Z0-9]+', referral_code))
