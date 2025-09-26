from django.test import TestCase
from rest_framework import status

from exchange.accounts.models import ReferralProgram, User, UserReferral


class TestReferralAPI(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

        self.referee_kyc_level_1 = User.objects.get(pk=202)
        self.referee_kyc_level_1.user_type = User.USER_TYPES.level1
        self.referee_kyc_level_1.save(update_fields=('user_type',))

        self.referee_kyc_level_0 = User.objects.get(pk=203)
        self.referee_kyc_level_0.user_type = User.USER_TYPES.level0
        self.referee_kyc_level_0.save(update_fields=('user_type',))

        self.referee_kyc_level_2 = User.objects.get(pk=204)
        self.referee_kyc_level_2.user_type = User.USER_TYPES.level2
        self.referee_kyc_level_2.save(update_fields=('user_type',))

    def tearDown(self):
        ReferralProgram.objects.all().delete()
        UserReferral.objects.all().delete()

    def create_referral_program(self, friend_share, agenda):
        return ReferralProgram.create(self.user, friend_share, agenda=agenda)

    def test_add_referral_program_invalid_request_error(self):
        # given ->
        request = {'friendShare': 60, 'agenda': 'campaign'}

        # when->
        response = self.client.post('/users/referral/links-add', data=request)

        # then->
        assert response.json()['status'] == 'failed'

    def test_add_referral_program_with_agenda_success(self):
        expected_result = {
            'status': 'ok',
            'result': {'agenda': 'campaign', 'description': None, 'friendShare': 15, 'userShare': 15},
        }

        # given ->
        request = {'friendShare': 15, 'agenda': 'campaign'}

        # when->
        response = self.client.post('/users/referral/links-add', data=request)

        # then->
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        self._assert_created_referral_program(result, expected_result, ReferralProgram.AGENDA.campaign)

    def test_add_referral_program_without_agenda_success(self):
        expected_result = {
            'status': 'ok',
            'result': {'agenda': 'default', 'description': None, 'friendShare': 20, 'userShare': 10},
        }

        # given ->
        request = {'friendShare': 20}

        # when->
        response = self.client.post('/users/referral/links-add', data=request)

        # then->
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        self._assert_created_referral_program(result, expected_result, ReferralProgram.AGENDA.default)

    def _assert_created_referral_program(self, result, expected_result, expected_agenda):
        id = result['result'].pop('id')
        created_at = result['result'].pop('createdAt')
        referral_code = result['result'].pop('referralCode')

        assert expected_result == result
        assert id
        assert created_at
        assert referral_code

        program = ReferralProgram.objects.get(pk=id)
        assert program
        assert program.created_at
        assert referral_code == program.referral_code
        assert expected_agenda == program.agenda

    def test_get_all_referral_programs_without_referee_success(self):
        # given ->
        ReferralProgram.create(self.user, 10)
        ReferralProgram.create(self.user, 15, ReferralProgram.AGENDA.campaign)
        ReferralProgram.create(self.user, 20, ReferralProgram.AGENDA.default)

        # when->
        response = self.client.get('/users/referral/links-list')

        # then->
        assert response.status_code == status.HTTP_200_OK
        links = response.json()['links']
        self._assert_referrer_program_list(links)
        assert len(links) == 3

    def test_get_all_referral_programs_with_referer_success(self):
        # given ->
        rp, _ = ReferralProgram.create(self.user, 20, agenda=ReferralProgram.AGENDA.campaign)
        UserReferral.set_user_referrer(self.referee_kyc_level_0, rp.referral_code)
        UserReferral.set_user_referrer(self.referee_kyc_level_1, rp.referral_code)
        UserReferral.set_user_referrer(self.referee_kyc_level_2, rp.referral_code)

        # when->
        response = self.client.get('/users/referral/links-list')

        # then->
        assert response.status_code == status.HTTP_200_OK
        links = response.json()['links']
        self._assert_referrer_program_list(links)
        assert len(links) == 1
        assert 2 == links[0]['statsRegisters']

    def _assert_referrer_program_list(self, links):
        for rp in links:
            assert rp['id']
            assert rp['agenda']
            assert rp['friendShare'] >= 0
            assert rp['referralCode']
            assert rp['createdAt']
            assert rp['statsProfit'] >= 0
            assert rp['statsRegisters'] >= 0
            assert rp['statsTrades'] >= 0
            assert rp['userShare'] > 0

    def test_user_has_referrer_success(self):
        # given ->
        rp, _ = ReferralProgram.create(self.referee_kyc_level_1, 30, ReferralProgram.AGENDA.default)
        UserReferral.set_user_referrer(self.user, rp.referral_code)

        # when->
        response = self.client.get('/users/referral/referral-status')

        # then->
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['hasReferrer'] == True

    def test_set_referrer_for_joined_user_date_time_gt_yesterday_failed(self):
        # given ->
        rp, _ = ReferralProgram.create(self.referee_kyc_level_1, 30, ReferralProgram.AGENDA.default)
        request = {'referralCode': rp.referral_code}

        # when->
        response = self.client.post('/users/referral/set-referrer', data=request)

        # then->
        assert response.json()['status'] == 'failed'
