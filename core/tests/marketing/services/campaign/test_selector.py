from unittest import TestCase
from unittest.mock import patch

from exchange.marketing.exceptions import InvalidCampaignException
from exchange.marketing.services.campaign.base import CampaignType
from exchange.marketing.services.campaign.discount import UserDiscountCampaign
from exchange.marketing.services.campaign.external_discount import ExternalDiscountCampaign
from exchange.marketing.services.campaign.selector import choose_campaign_by_name, choose_campaign_by_type
from exchange.marketing.services.mission.base import CampaignMission
from exchange.marketing.services.mission.kyc_or_refer import KycOrReferMission


class TestCampaignSelector(TestCase):

    def test_choose_campaign_by_type_valid_arguments_success(self):
        # given ->
        campaign_type = CampaignType.EXTERNAL_DISCOUNT
        campaign_mission = CampaignMission.KYC_OR_REFER
        campaign_id = '10M_nobitex_snapp'

        # when->
        campaign_service = choose_campaign_by_type(campaign_type, campaign_mission, campaign_id)

        # then->
        assert isinstance(campaign_service, ExternalDiscountCampaign)
        assert isinstance(campaign_service.mission, KycOrReferMission)
        assert campaign_service.type == CampaignType.EXTERNAL_DISCOUNT
        assert campaign_service.id == campaign_id

    def test_choose_campaign_by_type_invalid_arguments_error(self):
        # given ->
        campaign_type = None
        campaign_mission = CampaignMission.KYC_OR_REFER
        campaign_id = '10M_nobitex_snapp'

        # when->
        with self.assertRaises(InvalidCampaignException) as context:
            choose_campaign_by_type(campaign_type, campaign_mission, campaign_id)

        # then->
        self.assertEqual(str(context.exception), 'not found any campaign for type=None')

    def test_choose_campaign_by_type_cached_success(self):
        # given ->
        call_count = 5
        campaign_type = CampaignType.REFERRAL
        objects_hashset = set()

        # when->
        for i in range(call_count):
            service = choose_campaign_by_type(campaign_type)
            objects_hashset.add(service.__hash__())

        # then->
        assert len(objects_hashset) == 1

    @patch('exchange.marketing.services.campaign.selector.Settings.get_list')
    def test_choose_campaign_by_name_valid_name_success(self, mock_settings_get):
        # given ->
        campaign_name = 'external_discount:kyc_or_refer:10M_nobitex_snapp'
        mock_settings_get.return_value = [campaign_name]

        # when->
        campaign_service = choose_campaign_by_name(campaign_name)

        # then->
        assert isinstance(campaign_service, ExternalDiscountCampaign)
        assert isinstance(campaign_service.mission, KycOrReferMission)
        assert campaign_service.type == CampaignType.EXTERNAL_DISCOUNT
        assert campaign_service.id == '10M_nobitex_snapp'

    @patch('exchange.marketing.services.campaign.selector.Settings.get_list')
    def test_choose_campaign_by_name_without_mission_success(self, mock_settings_get):
        # given ->
        campaign_name = 'discount:-:internal_campaign_id'
        mock_settings_get.return_value = [campaign_name]

        # when->
        campaign_service = choose_campaign_by_name(campaign_name)

        # then->
        assert isinstance(campaign_service, UserDiscountCampaign)
        assert campaign_service.mission is None
        assert campaign_service.type == CampaignType.DISCOUNT
        assert campaign_service.id == 'internal_campaign_id'

    @patch('exchange.marketing.services.campaign.selector.Settings.get_list')
    def test_choose_campaign_by_name_campaign_is_not_active_error(self, mock_settings_get):
        # given ->
        campaign_name = 'external_discount:kyc_or_refer:10M_nobitex_snapp'
        mock_settings_get.return_value = ['another_campaign']

        # when->
        with self.assertRaises(InvalidCampaignException) as context:
            choose_campaign_by_name(campaign_name)

        # then->
        self.assertEqual(
            str(context.exception),
            'not found any active campaign for ' 'name=external_discount:kyc_or_refer:10M_nobitex_snapp',
        )

    @patch('exchange.marketing.services.campaign.selector.Settings.get_list')
    def test_choose_campaign_by_name_unknown_type_error(self, mock_settings_get):
        # given ->
        campaign_name = 'custom_campaign:-:10M_nobitex_snapp'
        mock_settings_get.return_value = ['10M_nobitex_snapp']

        # when->
        with self.assertRaises(InvalidCampaignException) as context:
            choose_campaign_by_name(campaign_name)

        # then->
        self.assertEqual(
            str(context.exception), 'not found any active campaign for name=custom_campaign:-:10M_nobitex_snapp'
        )
