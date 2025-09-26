import hashlib
import random
import string
import time

from django.test import Client
from django.test.testcases import TestCase
from rest_framework import status

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.marketing.models import ExternalDiscount
from exchange.web_engage.utils import generate_key


class TestSendExternalDiscount(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.webengage_token = generate_key()
        self.client = Client(HTTP_AUTHORIZATION=f'Token {self.webengage_token}')
        Settings.set("webengage_journey_api_key", self.webengage_token)
        Settings.set_dict('active_campaigns', ['external_discount:-:10M_snapp'])

    def tearDown(self):
        ExternalDiscount.objects.all().delete()
        Settings.set_dict('active_campaigns', [])
        Settings.set("webengage_journey_api_key", '')

    def test_send_external_when_no_code_is_available_error(self):
        expected_result = {
            'code': 'NoDiscountCodeIsAvailable',
            'message': 'not found any available discount to assign the user',
            'status': 'failed',
        }

        # given ->
        webengage_user_id = self.user.get_webengage_id()
        campaign_name = 'external_discount:-:10M_snapp'

        # when->
        response = self.client.post(
            '/marketing/campaign/webengage/discount/external',
            data={'userId': webengage_user_id, 'campaignName': campaign_name},
            content_type='application/json',
            REMOTE_ADDR="34.192.48.6",
        )

        # then->
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json() == expected_result

    def test_send_external_discount_success(self):
        # given ->
        webengage_user_id = self.user.get_webengage_id()
        campaign_name = 'external_discount:-:10M_snapp'
        self._create_external_discount('10M_snapp')

        # when->
        response = self.client.post(
            '/marketing/campaign/webengage/discount/external',
            data={'userId': webengage_user_id, 'campaignName': campaign_name},
            content_type='application/json',
            REMOTE_ADDR="34.192.48.6",
        )

        # then->
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'

        discount = ExternalDiscount.objects.filter(user=self.user).first()
        assert discount

    def _create_external_discount(self, campaign_id):
        return ExternalDiscount.objects.create(
            campaign_id=campaign_id,
            business_name='snapp',
            code=self._generate_discount_code(),
            description='sample description',
            enabled_at=ir_now(),
        )

    @staticmethod
    def _generate_discount_code():
        random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=3))
        raw_code = str(time.time()) + random_part
        hashed_code = hashlib.sha256(raw_code.encode()).hexdigest()
        referral_code = ''.join([char for char in hashed_code if char.isalnum()])[:7]
        return referral_code.upper()
