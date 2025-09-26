import json
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, Client
from rest_framework.status import HTTP_401_UNAUTHORIZED, HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN

from exchange.accounts.models import User
from exchange.base.models import Settings
from exchange.web_engage.models import WebEngageSMSLog
from exchange.web_engage.types import SSPDeliveryStatusCode
from exchange.web_engage.utils import generate_key


class TestSSPAPI(TestCase):

    def setUp(self):
        self.user = User.objects.get(id=201)
        self.user.mobile = '09980000000'
        self.user.save()
        self.webengage_token = generate_key()
        Settings.set("webengage_ssp_api_key", self.webengage_token)
        self.bad_webengage_token = "bad_token"

    def tearDown(self):
        WebEngageSMSLog.objects.all().delete()
        cache.delete("settings_webengage_ssp_api_key")

    @mock.patch("exchange.integrations.finnotext.requests.post")
    def test_successful_receive(self, mock_post):
        my_mock_response = mock.Mock(status_code=200)
        my_mock_response.json.return_value = {
            "trackId": "43d70b50-c767-4ef6-b220-202610782b05",
            "result": {
                "numberOfRecords": "2",
                "numberOfParts": "3"
            },
            "status": "DONE"
        }

        mock_post.return_value = my_mock_response

        client = Client(HTTP_AUTHORIZATION=f'Token {self.webengage_token}')
        response = client.post(
            '/integrations/webengage/private_ssp',
            REMOTE_ADDR="34.192.48.6",
            data=json.dumps({
                "version": "2.0",
                "smsData": {
                    "toNumber": self.user.get_webengage_id(),
                    "fromNumber": "PAXXXN",
                    "body": "Text message body"
                },
                "metadata": {
                    "campaignType": "PROMOTIONAL",
                    "timestamp": "2018-01-25T10:24:16+0000",
                    "messageId": "webengage-message-id",
                    "custom": {
                        "key1": "val1",
                        "key2": "val2"
                    },
                    "indiaDLT": {
                        "contentTemplateId": "xyz",
                        "principalEntityId": "abc"
                    }
                }
            }), content_type="application/json").json()
        assert WebEngageSMSLog.objects.filter(phone_number=self.user.mobile, status=WebEngageSMSLog.STATUS.new,
                                              message_id="webengage-message-id", text="Text message body").exists()
        assert response == {"status": "sms_accepted"}

    def test_bad_token(self):
        client = Client(HTTP_AUTHORIZATION=f'Bearer malformed_token')
        response = client.post(
            '/integrations/webengage/private_ssp',
            REMOTE_ADDR="34.192.48.6",
            data=json.dumps({
                "version": "2.0",
            }), content_type="application/json")
        response_data = response.json()
        assert response.status_code == HTTP_401_UNAUTHORIZED
        assert not WebEngageSMSLog.objects.filter().exists()
        assert response_data == {
            "status": "AuthenticationError",
            "statusCode": SSPDeliveryStatusCode.AUTHENTICATION_FAILURE.value,
            "message": "Malformed authentication header.",
        }

    def test_unsupported_version(self):
        client = Client(HTTP_AUTHORIZATION=f'Token {self.webengage_token}')
        response = client.post(
            '/integrations/webengage/private_ssp',
            REMOTE_ADDR="34.192.48.6",
            data=json.dumps({"version": "3.0"}), content_type="application/json")
        assert not WebEngageSMSLog.objects.filter().exists()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json() == {"status": "sms_rejected",
                                   "statusCode": SSPDeliveryStatusCode.UNSUPPORTED_PAYLOAD_VERSION.value,
                                   "message": "Version not supported",
                                   "supportedVersion": "2.0"}

    def test_invalid_number(self):
        client = Client(HTTP_AUTHORIZATION=f'Token {self.webengage_token}')
        response = client.post(
            '/integrations/webengage/private_ssp',
            REMOTE_ADDR="34.192.48.6",
            data=json.dumps({
                "version": "2.0",
                "smsData": {
                    "toNumber": "09980000000",
                    "fromNumber": "PAXXXN",
                    "body": "Text message body"
                },
                "metadata": {
                    "campaignType": "PROMOTIONAL",
                    "timestamp": "2018-01-25T10:24:16+0000",
                    "messageId": "webengage-message-id",
                    "custom": {
                        "key1": "val1",
                        "key2": "val2"
                    },
                }
            }), content_type="application/json")
        assert not WebEngageSMSLog.objects.all().exists()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json() == {"status": "sms_rejected",
                                   "statusCode": SSPDeliveryStatusCode.INVALID_MOBILE_NUMBER.value,
                                   "message": "Invalid mobile number"}

    def test_blocked_user(self):
        user = User.objects.get(id=202)
        user.user_type = User.USER_TYPES.blocked
        user.save(update_fields=['user_type'])
        client = Client(HTTP_AUTHORIZATION=f'Token {self.webengage_token}')
        response = client.post(
            '/integrations/webengage/private_ssp',
            REMOTE_ADDR="34.192.48.6",
            data=json.dumps({
                "version": "2.0",
                "smsData": {
                    "toNumber": user.get_webengage_id(),
                    "fromNumber": "PAXXXN",
                    "body": "Text message body"
                },
                "metadata": {
                    "campaignType": "PROMOTIONAL",
                    "timestamp": "2018-01-25T10:24:16+0000",
                    "messageId": "webengage-message-id",
                    "custom": {
                        "key1": "val1",
                        "key2": "val2"
                    },
                }
            }), content_type="application/json")
        assert not WebEngageSMSLog.objects.all().exists()
        assert response.status_code == HTTP_403_FORBIDDEN
        assert response.json() == {"status": "sms_rejected",
                                   "statusCode": SSPDeliveryStatusCode.RECIPIENT_BLACKLISTED.value,
                                   "message": "Recipient black listed"}
