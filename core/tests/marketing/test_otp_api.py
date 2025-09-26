from django.test.testcases import TestCase
from rest_framework import status

from exchange.accounts.models import User, UserOTP, UserSms
from exchange.base.models import Settings
from exchange.marketing.services.otp import send_sms_otp


class TestCampaignOTP(TestCase):

    def setUp(self):
        Settings.set_dict('active_campaigns', ['external_discount:kyc_or_refer:10M_snapp'])
        self.user = User.objects.get(pk=201)

    def tearDown(self):
        UserOTP.objects.all().delete()
        UserSms.objects.all().delete()
        Settings.set_dict('active_campaigns', [])

    def test_send_otp_with_invalid_campaign_error(self):
        expected_result = {
            'code': 'InvalidCampaign',
            'message': 'not found any active campaign for name=invalid-campaign',
            'status': 'failed',
        }

        # given ->
        mobile_number = '۹۱۲۳۴۵۶۷۸۹'
        utm_campaign = 'invalid-campaign'
        utm_source = 'snapp'
        utm_medium = 'web'

        # when->
        response = self.client.post(
            f'/marketing/campaign/otp?utmCampaign={utm_campaign}&utmSource={utm_source}&utmMedium={utm_medium}',
            data={'mobileNumber': mobile_number},
            content_type='application/json',
        )

        # then->
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == expected_result

    def test_send_otp_with_invalid_mobile_number_error(self):
        expected_result = {
            'code': 'ParseError',
            'message': 'Invalid mobile number',
            'status': 'failed',
        }

        # given ->
        mobile_number = ''
        utm_campaign = 'external_discount:kyc_or_refer:10M_snapp'
        utm_source = 'snapp'
        utm_medium = 'web'

        # when->
        response = self.client.post(
            f'/marketing/campaign/otp?utmCampaign={utm_campaign}&utmSource={utm_source}&utmMedium={utm_medium}',
            data={'mobileNumber': mobile_number},
            content_type='application/json',
        )

        # then->
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == expected_result

    def test_send_verify_otp_with_invalid_code_error(self):
        expected_result = {
            'code': 'ParseError',
            'message': '1 validation error for CampaignOTPVerifyRequest\n'
            'code\n'
            '  String should have at least 6 characters [type=string_too_short, '
            "input_value='', input_type=str]\n"
            '    For further information visit '
            'https://errors.pydantic.dev/2.10/v/string_too_short',
            'status': 'failed',
        }

        # given ->
        utm_campaign = 'external_discount:kyc_or_refer:10M_snapp'
        utm_source = 'snapp'
        utm_medium = 'web'

        # when->
        response = self.client.post(
            f'/marketing/campaign/otp/verify?utmCampaign={utm_campaign}&utmSource={utm_source}&utmMedium={utm_medium}',
            data={'mobileNumber': '09123659874', 'code': ''},
            content_type='application/json',
        )

        # then->
        response_body = response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response_body['code'] == 'ParseError'
        assert response_body['status'] == 'failed'

    def test_send_otp_success(self):
        # given ->
        mobile_number = '+۹۸۹۱۲۳۴۵۶۷۸۹'
        utm_campaign = 'external_discount:kyc_or_refer:10M_snapp'
        utm_source = 'snapp'
        utm_medium = 'web'

        # when->
        response = self.client.post(
            f'/marketing/campaign/otp?utmCampaign={utm_campaign}&utmSource={utm_source}&utmMedium={utm_medium}',
            data={'mobileNumber': mobile_number},
            content_type='application/json',
        )

        # then->
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'

        expected_mobile_number = "09123456789"
        otp = UserOTP.objects.filter(phone_number=expected_mobile_number).first()
        assert otp
        assert otp.phone_number == expected_mobile_number

    def test_verify_otp_success(self):
        mobile_number = '09123456789'
        expected_result = {
            'status': 'ok',
            'webengageId': None,
            'campaignDetails': {'status': 'NEEDS_KYC'},
        }

        # given ->
        usage = UserOTP.OTP_Usage.campaign
        send_sms_otp(mobile_number, usage)
        otp = UserOTP.objects.filter(phone_number=mobile_number).first()

        mobile_number = '۹۱۲۳۴۵۶۷۸۹'
        utm_campaign = 'external_discount:kyc_or_refer:10M_snapp'
        utm_source = 'snapp'
        utm_medium = 'web'
        request = {'mobileNumber': mobile_number, 'code': otp.code}

        # when->
        response = self.client.post(
            f'/marketing/campaign/otp/verify?utmCampaign={utm_campaign}&utmSource={utm_source}&utmMedium={utm_medium}',
            data=request,
            content_type='application/json',
        )

        # then->
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected_result
