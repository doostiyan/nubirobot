import json
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.marketing.exceptions import (
    InvalidCampaignException,
    MissionHasNotBeenCompleted,
    NoDiscountCodeIsAvailable,
)
from exchange.marketing.services.campaign.base import (
    BaseCampaign,
    RewardBasedCampaign,
    UserCampaignInfo,
    UserIdentifier,
    to_user_info,
)
from exchange.marketing.types import UserInfo


class CampaignAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user_info = UserInfo(
            webengage_id=self.user.get_webengage_id(),
            user_id=self.user.pk,
            level=self.user.user_type,
            mobile_number=self.user.mobile,
        )
        self.campaign_name = 'external_discount:trade:pizza'
        self.campaign_service = MagicMock()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')


class TestCampaignJoinRequestView(CampaignAPITestCase):
    def setUp(self):
        super().setUp()
        self.campaign_service.join.return_value = UserCampaignInfo(
            user_details=self.user_info,
            campaign_details={'status': 'DONE'},
        )

    @patch('exchange.marketing.api.views.campaign.choose_campaign_by_name')
    def test_successful_campaign_join(self, campaign_selector):
        expected_result = {
            'status': 'ok',
            'webengageId': self.user_info.webengage_id,
            'campaignDetails': {'status': 'DONE'},
        }

        # given ->
        campaign_selector.return_value = self.campaign_service
        data = {
            'utmSource': 'nobitex',
            'utmMedium': 'web',
            'utmCampaign': self.campaign_name,
        }

        # when->
        response = self.client.post('/marketing/campaign/join', data=json.dumps(data), content_type='application/json')

        # then->
        assert response.status_code == 200
        assert response.json() == expected_result

        campaign_selector.assert_called_once_with(self.campaign_name)
        self.campaign_service.join.assert_called_once_with(self.user_info)

    def test_invalid_utm_params(self):
        # given->
        data = {'utmCampaign': 'test_campaign'}
        # when->
        response = self.client.post('/marketing/campaign/join', data=json.dumps(data), content_type='application/json')
        # then->
        assert response.status_code == 400
        assert response.json()['code'] == 'ParseError'

    def test_invalid_campaign(self):
        # given->
        self.campaign_service.side_effect = InvalidCampaignException('Invalid campaign')
        data = {'utm_campaign': 'invalid_campaign', 'utm_source': 'test_source', 'utm_medium': 'test_medium'}
        # when->
        response = self.client.post('/marketing/campaign/join', data=json.dumps(data), content_type='application/json')

        # then->
        assert response.status_code == 400
        assert response.json()['code'] == 'InvalidCampaign'


class TestCampaignInfoRequestView(CampaignAPITestCase):
    def setUp(self):
        super().setUp()
        self.campaign_service.get_campaign_details.return_value = {'status': 'DONE'}

    @patch('exchange.marketing.api.views.campaign.choose_campaign_by_name')
    def test_successful_campaign_info(self, campaign_selector):
        expected_result = {
            'status': 'ok',
            'webengageId': self.user_info.webengage_id,
            'campaignDetails': {'status': 'DONE'},
        }

        # given->
        campaign_selector.return_value = self.campaign_service
        utm_campaign = self.campaign_name
        utm_source = 'nobitex'
        utm_medium = 'web'

        # when->
        response = self.client.get(
            f'/marketing/campaign?utmCampaign={utm_campaign}&utmSource={utm_source}&utmMedium={utm_medium}',
        )

        # then->
        assert response.status_code == 200
        assert response.json() == expected_result
        campaign_selector.assert_called_once_with(self.campaign_name)
        self.campaign_service.get_campaign_details.assert_called_once_with(to_user_info(self.user))

    def test_invalid_utm_params(self):
        # when->
        response = self.client.get('/marketing/campaign?utmCampaign=test_campaign')
        # then->
        assert response.status_code == 400
        assert response.json()['code'] == 'ParseError'


class MockedSimpleCampaign(BaseCampaign):
    pass


class MockedRewardBasedCampaign(RewardBasedCampaign):
    def get_capacity_details(self) -> Dict[str, Any]:
        return {'total': 10, 'available': 6, 'assigned': 4}

    def __init__(self, reward_ex=None):
        self.reward_ex = reward_ex

    def send_reward(self, user_identifier: UserIdentifier, **kwargs):
        if self.reward_ex:
            raise self.reward_ex

    def get_campaign_details(self, user_identifier: UserIdentifier) -> Dict[str, Any]:
        return {'status': 'REWARDED'}


class TestCampaignRewardRequestView(CampaignAPITestCase):
    def setUp(self):
        super().setUp()
        self.campaign_service = MockedRewardBasedCampaign()

    @patch('exchange.marketing.api.views.campaign.choose_campaign_by_name')
    def test_successful_reward_request(self, campaign_selector):
        expected_result = {
            'status': 'ok',
            'webengageId': self.user_info.webengage_id,
            'campaignDetails': {'status': 'REWARDED'},
        }

        # given->
        campaign_selector.return_value = self.campaign_service
        data = {
            'utmSource': 'nobitex',
            'utmMedium': 'web',
            'utmCampaign': self.campaign_name,
        }
        # when->
        response = self.client.post(
            '/marketing/campaign/reward',
            data=json.dumps(data),
            content_type='application/json',
        )

        # Assert
        assert response.status_code == 200
        assert response.json() == expected_result

        campaign_selector.assert_called_once_with(self.campaign_name)

    @patch('exchange.marketing.api.views.campaign.choose_campaign_by_name')
    def test_non_reward_based_campaign(self, campaign_selector):
        # given->
        campaign_selector.return_value = MagicMock()
        data = {
            'utmSource': 'nobitex',
            'utmMedium': 'web',
            'utmCampaign': self.campaign_name,
        }
        # when->
        response = self.client.post(
            '/marketing/campaign/reward',
            data=json.dumps(data),
            content_type='application/json',
        )

        # then->
        assert response.status_code == 400
        assert response.json()['code'] == 'InvalidCampaign'

    @patch('exchange.marketing.api.views.campaign.choose_campaign_by_name')
    def test_no_discount_code_available(self, campaign_selector):
        # given->
        campaign_selector.return_value = MockedRewardBasedCampaign(NoDiscountCodeIsAvailable())
        data = {
            'utmSource': 'nobitex',
            'utmMedium': 'web',
            'utmCampaign': self.campaign_name,
        }
        # when->
        response = self.client.post(
            '/marketing/campaign/reward',
            data=json.dumps(data),
            content_type='application/json',
        )

        # then->
        assert response.status_code == 503
        assert response.json()['code'] == 'NoDiscountCodeIsAvailable'

    @patch('exchange.marketing.api.views.campaign.choose_campaign_by_name')
    def test_mission_not_completed(self, campaign_selector):
        # given->
        campaign_selector.return_value = MockedRewardBasedCampaign(MissionHasNotBeenCompleted())
        data = {
            'utmSource': 'nobitex',
            'utmMedium': 'web',
            'utmCampaign': self.campaign_name,
        }
        # when->
        response = self.client.post(
            '/marketing/campaign/reward',
            data=json.dumps(data),
            content_type='application/json',
        )

        # then->
        assert response.status_code == 400
        assert response.json()['code'] == 'MissionHasNotBeenCompleted'


class TestCampaignRewardCapacityView(CampaignAPITestCase):
    def setUp(self):
        super().setUp()
        self.campaign_service = MockedRewardBasedCampaign()

    @patch('exchange.marketing.api.views.campaign.choose_campaign_by_name')
    def test_capacity_success(self, campaign_selector):
        expected_result = {
            'status': 'ok',
            'details': self.campaign_service.get_capacity_details(),
        }

        # given->
        campaign_selector.return_value = self.campaign_service
        utm_campaign = self.campaign_name
        utm_source = 'nobitex'
        utm_medium = 'web'

        # when->
        response = self.client.get(
            f'/marketing/campaign/reward/capacity?utmCampaign={utm_campaign}&utmSource={utm_source}&utmMedium={utm_medium}',
        )

        # then->
        assert response.status_code == 200
        assert response.json() == expected_result

    @patch('exchange.marketing.api.views.campaign.choose_campaign_by_name')
    def test_capacity_non_reward_campaign_failed(self, campaign_selector):
        # given->
        campaign_selector.return_value = MockedSimpleCampaign()
        utm_campaign = self.campaign_name
        utm_source = 'nobitex'
        utm_medium = 'web'

        # when->
        response = self.client.get(
            f'/marketing/campaign/reward/capacity?utmCampaign={utm_campaign}&utmSource={utm_source}&utmMedium={utm_medium}',
        )

        # then->
        assert response.status_code == 400
        assert response.json()['code'] == 'InvalidCampaign'
